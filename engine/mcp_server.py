"""MCP server: use Resume Generator by chatting in any MCP-capable AI app
(Claude Desktop, Claude Code, Cursor, ChatGPT desktop, Codex, Gemini CLI, ...).

Speaks the Model Context Protocol over stdio (JSON-RPC 2.0, one message per line) using only the
standard library, so it runs on the project's Python 3.9+ with nothing extra to install. Each
tool runs the matching engine command for one profile, exactly as in a terminal. See
docs/MCP.md for connecting it to an app.

    .venv/bin/python engine/mcp_server.py      # the app starts this itself; you don't run it
"""
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PROFILES = os.path.join(REPO, 'profiles')
PY = sys.executable  # the interpreter running this server (the project's .venv)
VERSION = '0.1.0'
PROTOCOL = '2025-06-18'
MAX_TEXT = 60000

INSTRUCTIONS = """Resume Generator: builds a verified fact bank from a person's notes, tailors one-page resumes per job, scans job boards, and tracks applications in Excel. Works for any profession.

Ground rules (always):
1. Never invent facts. Every bullet, number, skill, date and title must come from the person. Anything you draft from evidence is "verified": false with a "check" question until they confirm it.
2. Rewording keeps the facts: never add a number, tool or claim a bank bullet doesn't contain (the tailor tool rejects plans that do).
3. Ask, don't guess, on judgement calls: self-assessment questions on forms, salary, notice period, relocation.
4. The person submits applications. Never click Submit/Apply/Send, never type passwords or codes, never create accounts.
5. Personal data stays in their profile; don't copy it elsewhere. private/applicant.json holds pay and address.
6. A new profile is a copy of a fictional example (Meera Rao): replace everything; the tools refuse example data.
7. After changing profile files, run the check tool and fix every ERROR.

Start with guide("agents") for the full manual, and guide("<task>") for each step: setup-profile, build-bank, mine-workrecord, verify-bank, browse-search, pick-review, write-plan, fill-application, track-replies, add-template. New person: run doctor, then create_profile and guide("setup-profile")."""


# ---------------------------------------------------------------- helpers
def profile_names():
    return sorted(n for n in os.listdir(PROFILES) if os.path.isdir(os.path.join(PROFILES, n)) and not n.startswith('.'))


def profile_dir(name):
    if not name:
        real = [n for n in profile_names() if n != 'example']
        if len(real) != 1:
            raise ToolError('Which profile? Pass "profile" (one of: ' + ', '.join(profile_names()) + ').')
        name = real[0]
    if not re.fullmatch(r'[A-Za-z0-9._-]+', name) or not os.path.isdir(os.path.join(PROFILES, name)):
        raise ToolError(f'No profile "{name}". Existing: ' + ', '.join(profile_names()))
    return name, os.path.join(PROFILES, name)


def inside(base, rel):
    """Resolve rel under base, refusing anything that escapes it (../, absolute paths, symlinks out)."""
    p = os.path.realpath(os.path.join(base, rel or '.'))
    if p != os.path.realpath(base) and not p.startswith(os.path.realpath(base) + os.sep):
        raise ToolError(f'"{rel}" is outside the profile folder.')
    if f'{os.sep}.git{os.sep}' in p + os.sep:
        raise ToolError('The .git folder is off limits.')
    return p


class ToolError(Exception):
    pass


def run(script, args, profile=None, progress=None, timeout=900):
    """Run an engine command; return (exit code, combined output)."""
    cmd = [PY, os.path.join(HERE, script)] + list(args)
    if profile:
        cmd += ['--profile', profile]
    proc = subprocess.Popen(cmd, cwd=REPO, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            env={**os.environ, 'PYTHONUNBUFFERED': '1'})
    out, lines, start = [], [0], time.time()

    def reader():
        for line in proc.stdout:
            out.append(line)
            lines[0] += 1

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    beat = 0
    while t.is_alive():
        t.join(5)
        if progress and t.is_alive():
            beat += 1
            progress(beat, f'{script}: {lines[0]} lines of output so far')
        if time.time() - start > timeout:
            proc.kill()
            out.append(f'\n(stopped after {timeout}s)')
            break
    proc.wait()
    text = ''.join(out)
    if len(text) > MAX_TEXT:
        text = text[:MAX_TEXT] + f'\n... ({len(text) - MAX_TEXT} more characters cut)'
    return proc.returncode, text


def thumbnail_png(path):
    """First page of a PDF/DOCX as PNG bytes, or None (PyMuPDF / sips / Quick Look).
    Runs in a child process: importing preview_templates here would change this server's environment."""
    tmp = tempfile.mkdtemp()
    try:
        png = os.path.join(tmp, 'p.png')
        code = ('import sys; sys.path.insert(0, sys.argv[1]); import preview_templates as pt\n'
                'src, png = sys.argv[2], sys.argv[3]\n'
                'ok = pt.thumbnail(src, png) if src.endswith(".pdf") else pt.docx_thumbnail(src, png)\n'
                'ok and pt.flatten_white(png); sys.exit(0 if ok else 1)')
        r = subprocess.run([PY, '-c', code, HERE, path, png], cwd=REPO, stdin=subprocess.DEVNULL, capture_output=True, timeout=60,
                           env={**os.environ, 'RESUME_PROFILE': 'example'})
        if r.returncode != 0 or not os.path.exists(png):
            return None
        with open(png, 'rb') as f:
            return f.read()
    except Exception:
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def text(s, error=False):
    return {'content': [{'type': 'text', 'text': s}], 'isError': error}


def from_run(code, out, extra=None):
    res = text(out.strip() or '(no output)', error=code != 0)
    if extra:
        res['content'].extend(extra)
    return res


# ---------------------------------------------------------------- tools
def t_guide(a):
    name = (a.get('name') or 'agents').lower().replace('.md', '')
    files = {'agents': 'AGENTS.md', 'readme': 'README.md', 'setup': 'docs/SETUP.md', 'roadmap': 'ROADMAP.md',
             'mcp': 'docs/MCP.md'}
    rel = files.get(name, f'tasks/{name}.md')
    p = os.path.join(REPO, rel)
    if not os.path.exists(p):
        tasks = sorted(f[:-3] for f in os.listdir(os.path.join(REPO, 'tasks')))
        raise ToolError(f'No guide "{name}". Available: {", ".join(list(files) + tasks)}')
    with open(p, encoding='utf-8') as f:
        return text(f.read())


def t_doctor(a):
    name = a.get('profile')
    if name:
        name, _ = profile_dir(name)
    return from_run(*run('doctor.py', [], name))


def t_list_profiles(a):
    lines = []
    for n in profile_names():
        d = os.path.join(PROFILES, n)
        bank = os.path.join(d, 'bank.json')
        who = ''
        if os.path.exists(bank):
            try:
                with open(bank, encoding='utf-8') as f:
                    who = json.load(f).get('contact', {}).get('name', '')
            except ValueError:
                who = '(bank.json unreadable)'
        lines.append(f'{n}: {who}' + ('  (fictional example)' if n == 'example' else ''))
    return text('\n'.join(lines) or 'No profiles.')


def t_create_profile(a):
    name = a.get('name', '')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,40}', name) or name == 'example':
        raise ToolError('Use a short lowercase name with letters, digits or "-" (e.g. "priya-sharma").')
    dest = os.path.join(PROFILES, name)
    if os.path.exists(dest):
        raise ToolError(f'Profile "{name}" already exists.')
    shutil.copytree(os.path.join(PROFILES, 'example'), dest)
    shutil.rmtree(os.path.join(dest, 'resumes', 'bosch-general'), ignore_errors=True)
    return text(f'Created profiles/{name} as a copy of the fictional example. Everything in it must be replaced '
                '(the tools refuse example data). Next: guide("setup-profile") and guide("build-bank"); '
                'start by asking the person for their notes and writing notes.txt with write_file.')


def t_read_file(a):
    name, d = profile_dir(a.get('profile'))
    p = inside(d, a.get('path', ''))
    if os.path.isdir(p):
        items = []
        for root, dirs, files in os.walk(p):
            dirs[:] = [x for x in dirs if x != '.git']
            for f in sorted(files):
                items.append(os.path.relpath(os.path.join(root, f), d))
            if len(items) > 400:
                break
        return text('\n'.join(items[:400]) or '(empty)')
    if not os.path.exists(p):
        raise ToolError(f'No file {a.get("path")} in profile {name}.')
    if p.endswith(('.pdf', '.docx', '.png', '.xlsx')):
        res = text(f'{os.path.relpath(p, d)} is a {p.rsplit(".", 1)[1].upper()} file ({os.path.getsize(p)} bytes); '
                   'use the tracker tools for applications.xlsx.')
        png = thumbnail_png(p) if p.endswith(('.pdf', '.docx')) else None
        if png:
            res['content'].append({'type': 'image', 'data': base64.b64encode(png).decode(), 'mimeType': 'image/png'})
        return res
    with open(p, encoding='utf-8', errors='replace') as f:
        content = f.read()
    return text(content if len(content) <= MAX_TEXT else content[:MAX_TEXT] + '\n... (cut)')


def t_write_file(a):
    name, d = profile_dir(a.get('profile'))
    rel = a.get('path', '')
    if not rel or rel.endswith('/'):
        raise ToolError('Give a file path inside the profile, e.g. "bank.json" or "resumes/acme-123/plan.json".')
    p = inside(d, rel)
    content = a.get('content', '')
    if p.endswith('.json'):
        try:
            json.loads(content)
        except ValueError as e:
            raise ToolError(f'Not valid JSON: {e}. Nothing was written.')
    if p.endswith(('.xlsx', '.pdf', '.docx')):
        raise ToolError('Binary outputs are written by the engine, not by hand.')
    os.makedirs(os.path.dirname(p), exist_ok=True)
    existed = os.path.exists(p)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(content if content.endswith('\n') else content + '\n')
    return text(f'{"Updated" if existed else "Created"} {os.path.relpath(p, d)} in profile {name}. '
                'Run the check tool before relying on it.')


def t_check(a):
    name, _ = profile_dir(a.get('profile'))
    what = a.get('what', 'all')
    args = ['plan', a['plan']] if what == 'plan' else [what]
    if what == 'plan' and not a.get('plan'):
        raise ToolError('what="plan" needs "plan": the plan path, e.g. resumes/acme-123/plan.json')
    return from_run(*run('check.py', args, name))


def t_scan(a, progress):
    name, _ = profile_dir(a.get('profile'))
    args = list(a.get('companies') or [])
    for flag in ('dry_run', 'import_only', 'verbose', 'refresh'):
        if a.get(flag):
            args.append('--' + flag.replace('_', '-') if flag != 'verbose' else '-v')
    return from_run(*run('scan.py', args, name, progress=progress))


def t_pick(a):
    name, _ = profile_dir(a.get('profile'))
    return from_run(*run('pick.py', ['--mark'] if a.get('mark') else [], name))


def t_tailor(a, progress):
    name, d = profile_dir(a.get('profile'))
    plan = a.get('plan', '')
    inside(d, plan)
    args = [plan] + (['--template', a['template']] if a.get('template') else [])
    code, out = run('tailor.py', args, name, progress=progress)
    extra = []
    m = re.search(r'wrote (\S+\.(?:pdf|docx))', out)
    if code == 0 and m:
        path = m.group(1) if os.path.isabs(m.group(1)) else os.path.join(d, m.group(1))
        png = thumbnail_png(path)
        if png:
            extra.append({'type': 'image', 'data': base64.b64encode(png).decode(), 'mimeType': 'image/png'})
        out += f'\nFile: {path}'
    return from_run(code, out, extra)


def t_ats_check(a):
    name, d = profile_dir(a.get('profile'))
    folder = a.get('folder', '')
    inside(d, folder)
    return from_run(*run('ats_check.py', [folder] + list(a.get('job_keys') or []), name))


def t_preview_formats(a, progress):
    name, d = profile_dir(a.get('profile'))
    args = ['--mine'] + (['--plan', a['plan']] if a.get('plan') else []) + list(a.get('formats') or [])
    code, out = run('preview_templates.py', args, name, progress=progress)
    extra = []
    for png in sorted(f for f in os.listdir(os.path.join(d, 'previews')) if f.endswith('.png')) if os.path.isdir(os.path.join(d, 'previews')) else []:
        if a.get('formats') and png[:-4] not in a['formats']:
            continue
        with open(os.path.join(d, 'previews', png), 'rb') as f:
            extra.append({'type': 'text', 'text': png[:-4]})
            extra.append({'type': 'image', 'data': base64.b64encode(f.read()).decode(), 'mimeType': 'image/png'})
    return from_run(code, out, extra)


def t_tracker_list(a):
    name, _ = profile_dir(a.get('profile'))
    return from_run(*run('track.py', ['list', '--status', ','.join(a.get('statuses') or [])], name))


def t_tracker_show(a):
    name, _ = profile_dir(a.get('profile'))
    return from_run(*run('track.py', ['show', a['key']], name))


def t_tracker_set(a):
    name, _ = profile_dir(a.get('profile'))
    args = ['set', a['key'], a['status']] + (['--note', a['note']] if a.get('note') else [])
    return from_run(*run('track.py', args, name))


def t_application_sheet(a):
    name, _ = profile_dir(a.get('profile'))
    if not a.get('key'):
        return from_run(*run('apply.py', [], name))
    return from_run(*run('apply.py', [a['key'], '--sheet'], name))


def t_workrecord_digest(a, progress):
    name, d = profile_dir(a.get('profile'))
    code, out = run('workrecord_digest.py', [], name, progress=progress)
    p = os.path.join(d, 'data', 'workrecord_digest.txt')
    if code == 0 and os.path.exists(p):
        with open(p, encoding='utf-8') as f:
            out += '\n\n' + f.read()[:MAX_TEXT]
    return from_run(code, out)


def t_save_jobs(a):
    name, d = profile_dir(a.get('profile'))
    source = a.get('source', '')
    if not re.fullmatch(r'[a-z0-9-]+', source):
        raise ToolError('source must be a sources.json id such as "naukri".')
    jobs = a.get('jobs') or []
    need = ('company', 'job_id', 'title', 'url', 'description')
    bad = [i for i, j in enumerate(jobs) if not all(j.get(k) for k in need)]
    if bad:
        raise ToolError(f'Jobs {bad} are missing one of {need}. Nothing was saved.')
    for j in jobs:
        j['source'] = source
        j.setdefault('locations', [])
    inbox = os.path.join(d, 'data', 'inbox')
    os.makedirs(inbox, exist_ok=True)
    p = os.path.join(inbox, f'{source}-{time.strftime("%Y-%m-%d-%H%M%S")}.json')
    with open(p, 'w', encoding='utf-8') as f:
        json.dump({'jobs': jobs}, f, indent=2, ensure_ascii=False)
    return text(f'Saved {len(jobs)} job(s) to data/inbox/{os.path.basename(p)}. '
                'Now call scan with import_only=true to filter them into the tracker.')


P = {'type': 'string', 'description': 'Profile folder name (optional when there is only one besides "example").'}
TOOLS = [
    ('guide', t_guide, 'Read the operating manual (name="agents"), a task guide (setup-profile, build-bank, mine-workrecord, verify-bank, browse-search, pick-review, write-plan, fill-application, track-replies, add-template), or readme/setup/roadmap/mcp. Read "agents" first.',
     {'name': {'type': 'string'}}, []),
    ('doctor', t_doctor, 'Check what is installed (Python packages, Git, LaTeX and each format\'s packages) with plain fixes for anything missing.',
     {'profile': P}, []),
    ('list_profiles', t_list_profiles, 'List candidate profiles.', {}, []),
    ('create_profile', t_create_profile, 'Create a new profile as a copy of the fictional example, to be replaced with the person\'s own details.',
     {'name': {'type': 'string', 'description': 'lowercase, letters/digits/-'}}, ['name']),
    ('read_file', t_read_file, 'Read a file in a profile (notes.txt, bank.json, criteria.json, companies.json, sources.json, vocab.json, private/applicant.json, resumes/<folder>/plan.json, data/jobs/...). An empty path or a folder lists files. PDFs/Word files come back as a page image.',
     {'profile': P, 'path': {'type': 'string'}}, []),
    ('write_file', t_write_file, 'Create or replace a text file in a profile (JSON is validated). Only inside the profile folder. Run check afterwards.',
     {'profile': P, 'path': {'type': 'string'}, 'content': {'type': 'string'}}, ['path', 'content']),
    ('check', t_check, 'Validate profile files against the schemas and fact rules. what: bank | setup | plan | all.',
     {'profile': P, 'what': {'type': 'string', 'enum': ['bank', 'setup', 'plan', 'all']}, 'plan': {'type': 'string'}}, []),
    ('scan', t_scan, 'Fetch jobs from company job boards and import browser-found jobs, filter by criteria, score, and update the tracker. Can take several minutes.',
     {'profile': P, 'companies': {'type': 'array', 'items': {'type': 'string'}, 'description': 'company ids; default all enabled'},
      'dry_run': {'type': 'boolean'}, 'import_only': {'type': 'boolean'}, 'verbose': {'type': 'boolean'},
      'refresh': {'type': 'boolean', 'description': 'only rebuild the tracker views'}}, []),
    ('pick', t_pick, 'Propose the next job to apply to at each company (one open application per company). mark=true marks proposals Shortlisted.',
     {'profile': P, 'mark': {'type': 'boolean'}}, []),
    ('tailor', t_tailor, 'Render a resume from a plan (resumes/<folder>/plan.json). Rejects plans that use unverified facts or add numbers. Returns a page image. template= tries another format without editing the plan.',
     {'profile': P, 'plan': {'type': 'string'}, 'template': {'type': 'string'}}, ['plan']),
    ('ats_check', t_ats_check, 'Check how a rendered resume parses for applicant tracking systems and which job-description terms it covers.',
     {'profile': P, 'folder': {'type': 'string', 'description': 'resumes/<folder>'}, 'job_keys': {'type': 'array', 'items': {'type': 'string'}}}, ['folder']),
    ('preview_formats', t_preview_formats, 'Render the person\'s resume in every format (or the given ones) and return page images to compare.',
     {'profile': P, 'plan': {'type': 'string'}, 'formats': {'type': 'array', 'items': {'type': 'string'}}}, []),
    ('tracker_list', t_tracker_list, 'List tracked jobs, optionally by status (New, Shortlisted, Tailored, Applied, Responded, Interview, Offer, Rejected, Skipped).',
     {'profile': P, 'statuses': {'type': 'array', 'items': {'type': 'string'}}}, []),
    ('tracker_show', t_tracker_show, 'Show one tracked job with its full description.', {'profile': P, 'key': {'type': 'string'}}, ['key']),
    ('tracker_set', t_tracker_set, 'Set a job\'s status (e.g. Applied after the person submits, Rejected, Interview) with an optional note.',
     {'profile': P, 'key': {'type': 'string'}, 'status': {'type': 'string'}, 'note': {'type': 'string'}}, ['key', 'status']),
    ('application_sheet', t_application_sheet, 'Without key: jobs ready to apply to. With key: the posting URL, which resume to upload, and the answer sheet for the form.',
     {'profile': P, 'key': {'type': 'string'}}, []),
    ('workrecord_digest', t_workrecord_digest, 'Summarise the person\'s git work from workrecord.json (commit subjects, areas, file types; no code) for building bank bullets.',
     {'profile': P}, []),
    ('save_jobs', t_save_jobs, 'Save jobs found while browsing a job site (from sources.json) into the inbox; then scan with import_only=true. Each job: company, job_id, title, locations[], url, posted (YYYY-MM-DD), experience, description (full text).',
     {'profile': P, 'source': {'type': 'string'}, 'jobs': {'type': 'array', 'items': {'type': 'object'}}}, ['source', 'jobs']),
]
LONG = {'scan', 'tailor', 'preview_formats', 'workrecord_digest'}


def tool_list():
    return [{'name': n, 'description': desc,
             'inputSchema': {'type': 'object', 'properties': props, 'required': req}}
            for n, _, desc, props, req in TOOLS]


# ---------------------------------------------------------------- protocol
_lock = threading.Lock()


def send(msg):
    with _lock:
        sys.stdout.write(json.dumps(msg, ensure_ascii=False) + '\n')
        sys.stdout.flush()


def handle(req):
    method, params, rid = req.get('method'), req.get('params') or {}, req.get('id')
    if method == 'initialize':
        asked = params.get('protocolVersion') or PROTOCOL
        return {'protocolVersion': asked if re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(asked)) else PROTOCOL,
                'capabilities': {'tools': {'listChanged': False}},
                'serverInfo': {'name': 'resume-generator', 'version': VERSION},
                'instructions': INSTRUCTIONS}
    if method == 'ping':
        return {}
    if method == 'tools/list':
        return {'tools': tool_list()}
    if method == 'tools/call':
        name, args = params.get('name'), params.get('arguments') or {}
        token = (params.get('_meta') or {}).get('progressToken')

        def progress(n, message):
            if token is not None:
                send({'jsonrpc': '2.0', 'method': 'notifications/progress',
                      'params': {'progressToken': token, 'progress': n, 'message': message}})

        for n, fn, *_ in TOOLS:
            if n == name:
                try:
                    return fn(args, progress) if n in LONG else fn(args)
                except ToolError as e:
                    return text(str(e), error=True)
                except KeyError as e:
                    return text(f'Missing argument {e}.', error=True)
                except Exception as e:  # never crash the server
                    return text(f'{type(e).__name__}: {e}', error=True)
        raise LookupError(f'Unknown tool {name}')
    raise NotImplementedError(method)


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError:
            send({'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'Parse error'}})
            continue
        if 'id' not in req:  # notification (initialized, cancelled, ...): nothing to answer
            continue
        try:
            send({'jsonrpc': '2.0', 'id': req['id'], 'result': handle(req)})
        except NotImplementedError as e:
            send({'jsonrpc': '2.0', 'id': req['id'], 'error': {'code': -32601, 'message': f'Method not found: {e}'}})
        except LookupError as e:
            send({'jsonrpc': '2.0', 'id': req['id'], 'error': {'code': -32602, 'message': str(e)}})
        except Exception as e:
            send({'jsonrpc': '2.0', 'id': req['id'], 'error': {'code': -32603, 'message': f'{type(e).__name__}: {e}'}})


if __name__ == '__main__':
    main()
