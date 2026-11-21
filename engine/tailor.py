"""Build a tailored resume from a per-job plan and the profile's bank.json.

    .venv/bin/python engine/tailor.py resumes/<folder>/plan.json [--profile NAME]
    .venv/bin/python engine/tailor.py resumes/<folder>/plan.json --template my-style --open
        try a format without editing the plan (output: resumes/<folder>/try-my-style/)

The plan picks and orders facts from bank.json and supplies the summary and the
skills line for one job. This script refuses a plan that
  * uses a bullet or item that does not exist or is not verified,
  * lists a skill bank.json does not contain,
  * rewords a bullet with a number that its bank text does not contain,
  * puts a number in the summary that no bank fact contains.
It then builds a neutral resume document and hands it to a template
(templates/<name>/ or <profile>/templates/<name>/) chosen by the plan's
"template", else profile.json "default_template", else classic-latex.
Output (PDF or DOCX, plus the template's source file) goes next to the plan.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import candidate  # noqa: E402
import render  # noqa: E402

POLICIES = ('per_application', 'profile', 'unknown')
DEFAULT_SECTIONS = ['summary', 'skills', 'experience', 'education', 'projects']
# optional top-level bank lists a plan can include by id: {"id", "text", "verified"} items
LIST_SECTIONS = ['certifications', 'licenses', 'publications', 'awards', 'languages', 'portfolio', 'activities']


def output_stem():
    """File name (no extension) for every resume of this candidate: First_Last_Resume."""
    name = candidate.load_json('bank.json')['contact']['name']
    stem = candidate.settings().get('output_name', '{name}_Resume')
    return stem.format(name=re.sub(r'\s+', '_', name.strip()))


def resume_for(key):
    """Which resume a job should use, from its company's resume_policy in companies.json.

    Returns (path relative to the profile, policy). A per-job resume
    (resumes/<company>-<job id>/) when the company keeps a resume per application
    or when only one application is held there at a time (max_active 1);
    otherwise one shared company resume (resumes/<company>-general/).
    """
    cid, jid = key.split(':', 1)
    co = next((c for c in candidate.load_json('companies.json')['companies'] if c['id'] == cid), {})
    policy = co.get('resume_policy', 'unknown')
    if policy not in POLICIES:
        raise ValueError(f'{cid}: resume_policy must be one of {POLICIES}, got {policy!r}')
    max_active = co.get('max_active', candidate.load_json('criteria.json').get('max_active_per_company', 1))
    safe_jid = re.sub(r'[^\w.-]', '_', jid)
    # one open application at a company means its resume can fit that one job exactly,
    # whatever the policy; with several open at once, profile/unknown companies share one
    per_job = policy == 'per_application' or max_active == 1
    folder = f'{cid}-{safe_jid}' if per_job else f'{cid}-general'
    folder_path = candidate.path('resumes', folder)
    ext = render.output_ext(read_plan_template(folder_path))
    return f'resumes/{folder}/{output_stem()}.{ext}', policy


def read_plan_template(folder):
    p = os.path.join(folder, 'plan.json')
    if os.path.exists(p):
        with open(p, encoding='utf-8') as f:
            return json.load(f).get('template')
    return None


class PlanError(Exception):
    pass


def numbers(s):
    return set(re.findall(r'\d+(?:[.,]\d+)?', s or ''))


def load_bank():
    bank = candidate.load_json('bank.json')
    candidate.refuse_example_data(bank, 'bank.json')
    facts = {}
    for e in bank.get('experience', []):
        for b in e.get('bullets', []):  # role-level, spanning projects
            facts[b['id']] = b
        for p in e.get('projects', []):
            for b in p.get('bullets', []):
                facts[b['id']] = b
    for p in bank.get('personal_projects', []):
        for b in p.get('bullets', []):
            facts[b['id']] = b
    for sec in LIST_SECTIONS:
        for item in bank.get(sec, []):
            facts[item['id']] = item
    return bank, facts


def resolve_bullet(entry, facts, errors):
    bid, text = (entry, None) if isinstance(entry, str) else (entry['id'], entry.get('text'))
    b = facts.get(bid)
    if not b:
        errors.append(f'unknown bullet "{bid}"')
        return ''
    if not b.get('verified'):
        errors.append(f'bullet "{bid}" is not verified in bank.json')
    if text:
        extra = numbers(text) - numbers(b['text'])
        if extra:
            errors.append(f'bullet "{bid}" rewording adds numbers not in the bank: {sorted(extra)}')
        return text
    # plain-language wording for outside readers wins over internal names, once approved
    if b.get('public'):
        if not b.get('public_verified'):
            errors.append(f'bullet "{bid}" has public wording awaiting approval (public_verified=false)')
        return b['public']
    return b['text']


def month(ym):
    y, m = ym.split('-')
    return ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'June', 'July', 'Aug', 'Sept', 'Oct', 'Nov', 'Dec'][int(m) - 1] + ' ' + y


def contact_links(c):
    """Contact links as [{url, label}]: an explicit `links` list, else the classic keys."""
    if c.get('links'):
        raw = [(l['url'], l.get('label')) if isinstance(l, dict) else (l, None) for l in c['links']]
    else:
        raw = [(c[k], None) for k in ('linkedin', 'github', 'portfolio', 'website') if c.get(k)]
    out = []
    for url, label in raw:
        if not label:
            label = re.sub(r'^https?://(www\.)?', '', url).rstrip('/')
        out.append({'url': url, 'label': label})
    return out


def build_document(plan):
    """Validate the plan against the bank and return the neutral resume document."""
    bank, facts = load_bank()
    errors = []
    all_skills = {s for v in bank.get('skills', {}).values() for s in v}
    bank_numbers = set().union(*(numbers(b.get('text')) for b in facts.values())) if facts else set()

    years = plan.get('summary_years')  # e.g. "2+": derived from career_start, allowed in the summary
    allowed = bank_numbers | (numbers(years) if years else set())
    extra = numbers(plan.get('summary', '')) - allowed
    if extra:
        errors.append(f'summary has numbers not backed by a bank fact: {sorted(extra)}')
    for _, items in plan.get('skills', []):
        for s in items:
            if s not in all_skills:
                errors.append(f'skill "{s}" is not in bank.json')

    settings = candidate.settings()
    prefix = plan.get('project_label', settings.get('project_heading_prefix'))
    c = bank['contact']
    doc = {'contact': {'name': c['name'], 'phone': c.get('phone'), 'email': c.get('email'),
                       'location': c.get('location'), 'links': contact_links(c)},
           'sections': []}
    exps = {e['id']: e for e in bank.get('experience', [])}
    edus = {e['id']: e for e in bank.get('education', [])}
    pps = {p['id']: p for p in bank.get('personal_projects', [])}

    for sec in plan.get('sections', DEFAULT_SECTIONS):
        if sec == 'summary' and plan.get('summary'):
            doc['sections'].append({'type': 'summary', 'title': 'Summary', 'text': plan['summary']})
        elif sec == 'skills' and plan.get('skills'):
            doc['sections'].append({'type': 'skills', 'title': 'Skills',
                                    'groups': [{'name': n, 'items': i} for n, i in plan['skills']]})
        elif sec == 'experience' and plan.get('experience'):
            entries = []
            for ex in plan['experience']:
                e = exps.get(ex['id'])
                if not e:
                    errors.append(f'unknown experience "{ex["id"]}"')
                    continue
                projects = {p['id']: p for p in e.get('projects', [])}
                entry = {'title': e['title'], 'company': e['company'], 'location': e.get('location', ''),
                         'dates': f'{month(e["start"])} – {month(e["end"]) if e.get("end") else "Present"}',
                         'bullets': [resolve_bullet(b, facts, errors) for b in ex.get('bullets', [])],
                         'projects': []}
                for pr in ex.get('projects', []):
                    p = projects.get(pr['id'])
                    if not p:
                        errors.append(f'unknown project "{pr["id"]}"')
                        continue
                    label = pr.get('label') or ', '.join(x for x in (p.get('name'), p.get('client')) if x)
                    entry['projects'].append({
                        'label': label, 'heading': f'{prefix}: {label}' if prefix else label,
                        'name': p.get('name'), 'client': p.get('client'),
                        'description': p.get('description', ''), 'tech': p.get('tech', []),
                        'bullets': [resolve_bullet(b, facts, errors) for b in pr.get('bullets', [])]})
                entries.append(entry)
            doc['sections'].append({'type': 'experience', 'title': 'Experience', 'entries': entries})
        elif sec == 'education' and plan.get('education'):
            entries = []
            for eid in plan['education']:
                ed = edus.get(eid)
                if not ed:
                    errors.append(f'unknown education "{eid}"')
                    continue
                if not ed.get('verified'):
                    errors.append(f'education "{eid}" is not verified in bank.json')
                when = ed.get('when') or (f'Graduated: {ed["year"]}' if ed.get('year') else '')
                entries.append({'degree': ed['degree'], 'school': ed['school'], 'when': when,
                                'grade': ed.get('grade', ''), 'year': ed.get('year')})
            doc['sections'].append({'type': 'education', 'title': 'Education', 'entries': entries})
        elif sec == 'projects' and plan.get('personal_projects'):
            entries = []
            for pr in plan['personal_projects']:
                p = pps.get(pr['id'])
                if not p:
                    errors.append(f'unknown personal project "{pr["id"]}"')
                    continue
                entries.append({'name': p['name'], 'tech': pr.get('tech') or p.get('tech', [])[:5],
                                'bullets': [resolve_bullet(b, facts, errors) for b in pr.get('bullets', [])]})
            doc['sections'].append({'type': 'projects', 'title': 'Projects', 'entries': entries})
        elif sec in LIST_SECTIONS and plan.get(sec):
            items = [resolve_bullet(i, facts, errors) for i in plan[sec]]
            doc['sections'].append({'type': 'list', 'title': sec.title(), 'items': items})
        elif sec not in DEFAULT_SECTIONS + LIST_SECTIONS:
            errors.append(f'unknown section "{sec}"')

    if errors:
        raise PlanError('\n  '.join(['plan rejected:'] + errors))
    return doc


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('plan', help='path to plan.json (absolute, or relative to the profile folder)')
    ap.add_argument('--template', help="try another format without editing the plan; output goes to "
                                       "<plan folder>/try-<template>/ so the job's real resume is untouched")
    ap.add_argument('--open', action='store_true', help='open the result when done (macOS/Windows/Linux)')
    a = ap.parse_args()
    plan_path = a.plan if os.path.exists(a.plan) else candidate.path(a.plan)
    plan_path = os.path.abspath(plan_path)
    with open(plan_path, encoding='utf-8') as f:
        plan = json.load(f)
    try:
        doc = build_document(plan)
    except PlanError as e:
        raise SystemExit(str(e))
    out_dir = os.path.dirname(plan_path)
    if a.template:
        out_dir = os.path.join(out_dir, f'try-{a.template}')
        os.makedirs(out_dir, exist_ok=True)
    out, pages, limit = render.render(doc, a.template or plan.get('template'), out_dir, output_stem())
    shown = os.path.relpath(out, candidate.profile_dir())
    print(f'wrote {out if shown.startswith("..") else shown}'
          + (f' ({pages} page{"s" if pages != 1 else ""})' if pages else ''))
    if pages and limit and pages > limit:
        print(f'WARNING: more than {limit} page(s); drop or shorten bullets in the plan.')
    if a.open:
        open_file(out)


def open_file(path):
    import subprocess
    if sys.platform == 'darwin':
        subprocess.run(['open', path], check=False)
    elif os.name == 'nt':
        os.startfile(path)  # noqa: S606 (Windows only)
    else:
        subprocess.run(['xdg-open', path], check=False)


if __name__ == '__main__':
    main()
