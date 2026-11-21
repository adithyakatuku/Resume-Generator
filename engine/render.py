"""Render a resume document (built by tailor.py) through a template.

A template is a folder with manifest.json and one entry file:

  {"engine": "latex",  "entry": "resume.tex.j2", "max_pages": 1,
   "latex_engine": "pdflatex",                   or "xelatex" / "lualatex" for system fonts (fontspec)
   "latex_packages": ["titlesec", ...]}           Jinja2 with LaTeX-safe syntax
  {"engine": "script", "entry": "render.py", "ext": "docx"}
                                                  Python module: render(doc, out_path, template_dir)
                                                  -> page count or None

Templates are looked up in <profile>/templates/<name>/ first, then templates/<name>/.
In LaTeX templates: \\VAR{x} prints, lines starting with %% are statements
(%% for ..., %% if ..., %% endfor), and the `tex` filter escapes plain text.
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile

import candidate  # noqa: E402  (engine/candidate.py: the active profile folder)

DEFAULT_TEMPLATE = 'classic-latex'
LATEX_ENGINES = ('pdflatex', 'xelatex', 'lualatex')


def tex(s):
    """Escape plain text for LaTeX."""
    rep = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#', '_': r'\_',
           '{': r'\{', '}': r'\}', '~': r'$\sim$', '^': r'\textasciicircum{}',
           '–': '--', '—': '---', '’': "'", '‘': '`', '“': '``', '”': "''", '→': r'$\rightarrow$'}
    out = ''.join(rep.get(ch, ch) for ch in str(s))
    # "B.Tech. in": a full stop before a lowercase word is an abbreviation, not a sentence end
    return re.sub(r'\.(\s+)(?=[a-z])', r'.\\ ', out)


def template_dir(name=None):
    name = name or candidate.settings().get('default_template') or DEFAULT_TEMPLATE
    for base in (candidate.path('templates'), candidate.TEMPLATES):
        d = os.path.join(base, name)
        if os.path.exists(os.path.join(d, 'manifest.json')):
            return d
    raise SystemExit(f'Template "{name}" not found in {candidate.path("templates")} or {candidate.TEMPLATES}.')


def manifest(d):
    with open(os.path.join(d, 'manifest.json'), encoding='utf-8') as f:
        return json.load(f)


def output_ext(name=None):
    m = manifest(template_dir(name))
    return 'pdf' if m['engine'] == 'latex' else m.get('ext', 'docx')


def render(doc, name, out_dir, stem):
    """Render doc with template `name` into out_dir/<stem>.<ext>. Returns (path, pages, max_pages)."""
    d = template_dir(name)
    m = manifest(d)
    if m['engine'] == 'latex':
        src = render_latex_source(doc, d, m)
        with open(os.path.join(out_dir, 'resume.tex'), 'w', encoding='utf-8') as f:
            f.write(src)
        out = os.path.join(out_dir, f'{stem}.pdf')
        pages = compile_pdf(src, out, m)
        return out, pages, m.get('max_pages')
    if m['engine'] == 'script':
        spec = importlib.util.spec_from_file_location('template_render', os.path.join(d, m['entry']))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out = os.path.join(out_dir, f'{stem}.{m.get("ext", "docx")}')
        pages = mod.render(doc, out, d)
        return out, pages, m.get('max_pages')
    raise SystemExit(f'{d}: unknown template engine {m["engine"]!r}')


def render_latex_source(doc, d, m):
    import jinja2
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(d),
        variable_start_string=r'\VAR{', variable_end_string='}',
        block_start_string=r'\BLOCK{', block_end_string='}',
        comment_start_string=r'\#{', comment_end_string='}',
        line_statement_prefix='%%', line_comment_prefix='%#',
        trim_blocks=True, lstrip_blocks=True, autoescape=False, keep_trailing_newline=True,
        undefined=jinja2.StrictUndefined)
    env.filters['tex'] = tex
    return env.get_template(m['entry']).render(doc=doc, contact=doc['contact'], sections=doc['sections'])


def compile_pdf(src, out_pdf, m=None):
    """Compile LaTeX in a temp dir (pdflatex unless the manifest says xelatex/lualatex),
    copy the PDF to out_pdf; return the page count."""
    work = tempfile.mkdtemp()
    try:
        with open(os.path.join(work, 'resume.tex'), 'w', encoding='utf-8') as f:
            f.write(src)
        tool = (m or {}).get('latex_engine', 'pdflatex')
        if tool not in LATEX_ENGINES:
            raise SystemExit(f'latex_engine must be one of {LATEX_ENGINES}, got {tool!r}')
        if not shutil.which(tool):
            raise SystemExit(f'{tool} not found. It comes with MacTeX/BasicTeX (Mac) and MiKTeX (Windows); '
                             'see docs/SETUP.md step 3, then reopen the terminal.')
        r = subprocess.run([tool, '-interaction=nonstopmode', '-halt-on-error', 'resume.tex'],
                           cwd=work, capture_output=True, text=True)
        log_path = os.path.join(work, 'resume.log')
        log = open(log_path, encoding='latin-1').read() if os.path.exists(log_path) else r.stdout
        if r.returncode != 0:
            err = [l for l in log.splitlines() if l.startswith('!')]
            hint = ''
            if any('.sty' in l and 'not found' in l for l in err) and m and m.get('latex_packages'):
                hint = ('\nMissing LaTeX package. With BasicTeX: tlmgr --usermode install '
                        + ' '.join(m['latex_packages']))
            if any('font' in l.lower() and 'not' in l.lower() for l in err):
                hint += ('\nA font named in the template is not installed on this computer: install it, '
                         'or change \\setmainfont in the template to a font you have.')
            if tool == 'pdflatex' and any('fontspec' in l.lower() for l in log.splitlines()[-40:]):
                hint += '\nThis template uses fontspec: set "latex_engine": "xelatex" in its manifest.json.'
            if tool != 'pdflatex' and any('pdfgentounicode' in l for l in log.splitlines()):
                hint += ('\n\\pdfgentounicode and \\input{glyphtounicode} are pdfLaTeX-only: '
                         'remove them for XeLaTeX/LuaLaTeX.')
            raise SystemExit('pdflatex failed:\n' + '\n'.join(err[:5] or log.splitlines()[-20:]) + hint)
        shutil.copy(os.path.join(work, 'resume.pdf'), out_pdf)
        found = re.search(r'Output written on resume\.pdf \((\d+) pages?', log)
        return int(found.group(1)) if found else None
    finally:
        shutil.rmtree(work, ignore_errors=True)
