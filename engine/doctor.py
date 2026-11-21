"""Health check: is everything this project needs installed? Plain-language fixes for anything missing.

    .venv/bin/python engine/doctor.py                 # (Windows: .venv\\Scripts\\python engine\\doctor.py)
    .venv/bin/python engine/doctor.py --profile NAME  # also check what that profile's choices need

Checks Python and its packages, Git, LaTeX (and every LaTeX package each resume format uses),
XeLaTeX for formats that need it, optional preview tools, and, for a profile, whether its
chosen format works and whether it has browser job sites enabled (which need an AI agent with
browser control: that lives inside the agent, so the agent has to confirm it itself).
Exit status 1 when something required is missing.
"""
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TEMPLATES = os.path.join(REPO, 'templates')
OS = {'Darwin': 'mac', 'Windows': 'windows'}.get(platform.system(), 'linux')
PIP = r'.venv\Scripts\pip' if OS == 'windows' else '.venv/bin/pip'

# requirement name -> import name
IMPORTS = {'openpyxl': 'openpyxl', 'pdfminer.six': 'pdfminer', 'jinja2': 'jinja2', 'python-docx': 'docx',
           'jsonschema': 'jsonschema', 'pillow': 'PIL'}

FIX = {
    'python': {'mac': 'Install Python 3 from https://www.python.org/downloads/ (docs/SETUP.md step 2).',
               'windows': 'Install Python 3 from https://www.python.org/downloads/ and tick "Add python.exe to PATH" (docs/SETUP.md step 2).',
               'linux': 'Install Python 3.9+ with your package manager (e.g. sudo apt install python3 python3-venv).'},
    'venv': {'any': 'Create the project environment once: python3 -m venv .venv  (then install packages, below).'},
    'packages': {'any': f'Install the Python packages: {PIP} install -r requirements.txt'},
    'git': {'mac': 'Run: xcode-select --install  (docs/SETUP.md step 2).',
            'windows': 'Install Git from https://git-scm.com/download/win (docs/SETUP.md step 2).',
            'linux': 'Install git with your package manager (e.g. sudo apt install git).'},
    'latex': {'mac': 'Install BasicTeX from https://www.tug.org/mactex/morepackages.html, then reopen the terminal (docs/SETUP.md step 3).',
              'windows': 'Install MiKTeX from https://miktex.org/download and allow "install missing packages on-the-fly" (docs/SETUP.md step 3).',
              'linux': 'Install TeX Live (e.g. sudo apt install texlive-latex-extra texlive-xetex).'},
    'latex_pkg': {'mac': 'Run: tlmgr init-usertree; tlmgr --usermode install {pkgs}',
                  'windows': 'MiKTeX installs them automatically the first time; or open MiKTeX Console > Packages and install: {pkgs}',
                  'linux': 'Install them with tlmgr (tlmgr install {pkgs}) or your distro\'s texlive-* packages.'},
}

results = []  # (status, area, message, fix)


def say(status, area, msg, fix=''):
    results.append((status, area, msg, fix))


def fix(key, **kw):
    d = FIX[key]
    return (d.get(OS) or d.get('any', '')).format(**kw)


def check_python():
    v = sys.version_info
    if v < (3, 9):
        say('MISSING', 'Python', f'Python {v.major}.{v.minor} is too old (need 3.9+)', fix('python'))
    else:
        say('ok', 'Python', f'Python {v.major}.{v.minor}.{v.micro}')
    in_venv = sys.prefix != getattr(sys, 'base_prefix', sys.prefix)
    if not in_venv:
        venv = os.path.join(REPO, '.venv')
        if os.path.isdir(venv):
            say('warn', 'Python', 'not running inside the project environment (.venv)',
                'Run commands as .venv/bin/python ... (Windows: .venv\\Scripts\\python ...).')
        else:
            say('MISSING', 'Python', 'project environment .venv not created', fix('venv'))
    req = os.path.join(REPO, 'requirements.txt')
    names = [re.split(r'[<>=!~ ]', l.strip())[0] for l in open(req, encoding='utf-8') if l.strip() and not l.startswith('#')]
    missing = [n for n in names if not importlib.util.find_spec(IMPORTS.get(n.lower(), n.lower().replace('-', '_')))]
    if missing:
        say('MISSING', 'Python', 'packages not installed: ' + ', '.join(missing), fix('packages'))
    else:
        say('ok', 'Python', f'all {len(names)} packages installed')


def check_git():
    if shutil.which('git'):
        say('ok', 'Git', subprocess.run(['git', '--version'], capture_output=True, text=True).stdout.strip())
    else:
        say('MISSING', 'Git', 'git not found', fix('git'))


def template_dirs(profile_dir):
    out = {}
    for base in [TEMPLATES] + ([os.path.join(profile_dir, 'templates')] if profile_dir else []):
        if os.path.isdir(base):
            for name in sorted(os.listdir(base)):
                if os.path.exists(os.path.join(base, name, 'manifest.json')):
                    out[name] = os.path.join(base, name)  # profile templates override built-ins
    return out


def tex_needs(d, m):
    """LaTeX files a template loads: \\usepackage{a,b} -> a.sty, b.sty; \\input{x} -> x.tex."""
    src = open(os.path.join(d, m['entry']), encoding='utf-8').read()
    src = '\n'.join(l.split('%')[0] for l in src.splitlines())  # ignore comments
    files = []
    for group in re.findall(r'\\usepackage(?:\[[^\]]*\])?\{([^}]*)\}', src):
        files += [p.strip() + '.sty' for p in group.split(',') if p.strip()]
    files += [x if '.' in x else x + '.tex' for x in re.findall(r'\\input\{([^}]*)\}', src)]
    files.append(re.search(r'\\documentclass(?:\[[^\]]*\])?\{([^}]*)\}', src).group(1) + '.cls')
    return list(dict.fromkeys(files))


def check_latex(profile_dir, default_template):
    tpls = template_dirs(profile_dir)
    latex_tpls = {n: d for n, d in tpls.items() if json.load(open(os.path.join(d, 'manifest.json')))['engine'] == 'latex'}
    kpse = shutil.which('kpsewhich')
    for name, d in latex_tpls.items():
        m = json.load(open(os.path.join(d, 'manifest.json'), encoding='utf-8'))
        tool = m.get('latex_engine', 'pdflatex')
        role = 'your default format' if name == default_template else 'only needed if you use it'
        severity = 'MISSING' if name == default_template or (not default_template and name == 'classic-latex') else 'warn'
        label = f'LaTeX: {name}'
        if not shutil.which(tool):
            say(severity, label, f'{tool} not found ({role})', fix('latex'))
            continue
        if not kpse:
            say('warn', label, 'cannot check LaTeX packages (kpsewhich not found)')
            continue
        missing = [f for f in tex_needs(d, m)
                   if not subprocess.run([kpse, f], capture_output=True, text=True).stdout.strip()]
        if missing:
            # the package usually has the file's name (titlesec.sty -> titlesec); a few differ, and
            # `tlmgr info --list <file>` or the format's manifest latex_packages can tell
            pkgs = ' '.join(dict.fromkeys(os.path.splitext(f)[0] for f in missing))
            say(severity, label, f'missing LaTeX files: {", ".join(missing)} ({role})', fix('latex_pkg', pkgs=pkgs))
        else:
            say('ok', label, f'{tool} and all {len(tex_needs(d, m))} LaTeX packages present')
    if not latex_tpls:
        say('ok', 'LaTeX', 'no LaTeX formats in use')


def check_previews():
    have = [t for t in ('sips', 'qlmanage') if shutil.which(t)]
    if importlib.util.find_spec('fitz'):
        have.append('pymupdf')
    if have:
        say('ok', 'Previews', 'thumbnail tools: ' + ', '.join(have))
    else:
        say('warn', 'Previews', 'no tool to make preview thumbnails (PDF/Word files are still written)',
            f'Optional: {PIP} install pymupdf')


def check_profile(profile_dir):
    name = os.path.basename(profile_dir)
    say('ok', 'Profile', f'profiles/{name}')
    settings = {}
    p = os.path.join(profile_dir, 'profile.json')
    if os.path.exists(p):
        settings = json.load(open(p, encoding='utf-8'))
    tpl = settings.get('default_template', 'classic-latex')
    tdirs = template_dirs(profile_dir)
    if tpl not in tdirs:
        say('MISSING', 'Profile', f'default_template "{tpl}" does not exist', 'Set profile.json default_template to a folder in templates/ or your profile\'s templates/.')
    srcs_p = os.path.join(profile_dir, 'sources.json')
    if os.path.exists(srcs_p):
        browser = [s['name'] for s in json.load(open(srcs_p, encoding='utf-8')).get('sources', [])
                   if s.get('type') == 'browser' and s.get('enabled')]
        if browser:
            say('agent', 'Browser', f'browser job sites enabled: {", ".join(browser)}. Searching them needs an AI agent '
                'that can control your browser; only the agent can confirm it has that.',
                'Claude Code: install the "Claude in Chrome" extension, then run /chrome (or start with claude --chrome). '
                'Other agents: connect Playwright MCP or the agent\'s browser feature (docs/SETUP.md step 6). '
                'Or set enabled=false for those sites in sources.json.')
        else:
            say('ok', 'Browser', 'no browser job sites enabled (company feeds need no browser)')
    if not os.path.exists(os.path.join(profile_dir, 'private', 'applicant.json')):
        say('warn', 'Profile', 'private/applicant.json missing (needed to fill application forms)',
            'Ask your agent to set it up (tasks/setup-profile.md step 7).')
    say('ok', 'Profile', 'for the contents of your files, run: engine/check.py all')
    return tpl


def find_profile():
    """The profile to check, without exiting when there is none (doctor runs before setup)."""
    name = os.environ.get('RESUME_PROFILE')
    if '--profile' in sys.argv:
        name = sys.argv[sys.argv.index('--profile') + 1]
    profiles = os.path.join(REPO, 'profiles')
    if name:
        d = name if os.path.isdir(name) else os.path.join(profiles, name)
        return d if os.path.isdir(d) else None
    found = [n for n in os.listdir(profiles) if os.path.isdir(os.path.join(profiles, n)) and n != 'example' and not n.startswith('.')]
    return os.path.join(profiles, found[0]) if len(found) == 1 else None


def main():
    print(f'Checking your setup ({ {"mac": "macOS", "windows": "Windows", "linux": "Linux"}[OS] })...\n')
    check_python()
    check_git()
    profile_dir = find_profile()
    tpl = check_profile(profile_dir) if profile_dir else None
    if not profile_dir:
        say('warn', 'Profile', 'no profile yet (or several: pass --profile NAME)',
            'Ask your agent: "Set me up" (it copies profiles/example and replaces it with your details).')
    check_latex(profile_dir, tpl)
    check_previews()

    marks = {'ok': '  ok  ', 'warn': ' note ', 'MISSING': 'NEEDED', 'agent': ' AGENT'}
    for status, area, msg, how in results:
        print(f'[{marks[status]}] {area}: {msg}')
        if how and status != 'ok':
            print(f'          -> {how}')
    needed = sum(1 for r in results if r[0] == 'MISSING')
    print('\n' + ('Everything required is installed.' if not needed else
                  f'{needed} required item(s) missing: follow the "->" steps above, then run this again.'))
    sys.exit(1 if needed else 0)


if __name__ == '__main__':
    main()
