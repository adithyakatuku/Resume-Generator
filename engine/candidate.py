"""Which candidate profile the engine is working on.

Every engine command takes `--profile NAME` (a folder under profiles/, or a path).
Without it, RESUME_PROFILE is used, and failing that the only profile folder
other than profiles/example. All candidate data lives in that folder; the
engine itself holds none.
"""
import json
import os
import sys

ENGINE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(ENGINE)
PROFILES = os.path.join(REPO, 'profiles')
TEMPLATES = os.path.join(REPO, 'templates')
SCHEMAS = os.path.join(REPO, 'schemas')


def _take_flag():
    """Strip `--profile X` / `--profile=X` from argv so each CLI's own parser never sees it."""
    argv = sys.argv
    for i, a in enumerate(argv):
        if a == '--profile' and i + 1 < len(argv):
            os.environ['RESUME_PROFILE'] = argv[i + 1]
            del argv[i:i + 2]
            return
        if a.startswith('--profile='):
            os.environ['RESUME_PROFILE'] = a.split('=', 1)[1]
            del argv[i]
            return


_take_flag()

# requirement name for import names that differ (for the hint below)
_PIP_NAMES = {'pdfminer': 'pdfminer.six', 'docx': 'python-docx', 'PIL': 'pillow', 'fitz': 'pymupdf'}


def _friendly_missing_module(exc_type, exc, tb):
    """A missing Python package prints a fix instead of a traceback."""
    if issubclass(exc_type, ModuleNotFoundError) and exc.name and exc.name.split('.')[0] in (
            'openpyxl', 'pdfminer', 'jinja2', 'docx', 'jsonschema', 'PIL', 'fitz'):
        top = exc.name.split('.')[0]
        pip = r'.venv\Scripts\pip' if os.name == 'nt' else '.venv/bin/pip'
        py = r'.venv\Scripts\python' if os.name == 'nt' else '.venv/bin/python'
        sys.stderr.write(f'Missing Python package "{_PIP_NAMES.get(top, top)}".\n'
                         f'Install the project packages:  {pip} install -r requirements.txt\n'
                         f'and run commands with {py} (not plain python). To check everything: {py} engine/doctor.py\n')
        return
    sys.__excepthook__(exc_type, exc, tb)


sys.excepthook = _friendly_missing_module

_cached = None


def profile_dir():
    global _cached
    if _cached:
        return _cached
    name = os.environ.get('RESUME_PROFILE')
    if name:
        d = name if os.path.isdir(name) else os.path.join(PROFILES, name)
        if not os.path.isdir(d):
            raise SystemExit(f'Profile "{name}" not found (looked for {d}).')
    else:
        found = sorted(n for n in os.listdir(PROFILES)
                       if os.path.isdir(os.path.join(PROFILES, n)) and n != 'example' and not n.startswith('.'))
        if not found:
            raise SystemExit('No profile yet: copy profiles/example to profiles/<your-name>/ (see README.md).')
        if len(found) > 1:
            raise SystemExit(f'Several profiles ({", ".join(found)}): choose one with --profile NAME '
                             'or set RESUME_PROFILE.')
        d = os.path.join(PROFILES, found[0])
    _cached = os.path.abspath(d)
    return _cached


def path(*parts):
    return os.path.join(profile_dir(), *parts)


def load_json(name, default=None):
    p = path(name)
    if not os.path.exists(p):
        if default is not None:
            return default
        raise SystemExit(f'Missing {os.path.relpath(p, REPO)}. See README.md for what goes in a profile.')
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def is_example_data(obj):
    """True for files copied from profiles/example that still hold its fictional content."""
    return isinstance(obj, dict) and str(obj.get('_about', '')).startswith('FICTIONAL EXAMPLE')


def in_example_profile():
    return os.path.basename(profile_dir()) == 'example'


def refuse_example_data(obj, name):
    """Stop a real profile from using the example's fictional facts or form answers."""
    if is_example_data(obj) and not in_example_profile():
        raise SystemExit(f'{name} in profile "{os.path.basename(profile_dir())}" is still the fictional '
                         'example (Meera Rao). Replace it with your own: ask your agent to run '
                         'tasks/setup-profile.md and tasks/build-bank.md.')


def settings():
    """profile.json: small per-candidate settings (name, field, default template...)."""
    return load_json('profile.json', default={})
