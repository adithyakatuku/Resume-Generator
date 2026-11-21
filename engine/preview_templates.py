"""See what resume formats look like, side by side.

Built-in gallery (for the README), always from the fictional example candidate:
    .venv/bin/python engine/preview_templates.py               # every template in templates/
    .venv/bin/python engine/preview_templates.py docx-basic    # just these
  -> templates/<name>/preview.pdf (or .docx) + preview.png

Your own resume in every format, including your own templates:
    .venv/bin/python engine/preview_templates.py --mine [--plan resumes/<folder>/plan.json] [names] [--profile NAME]
  -> <profile>/previews/<name>.pdf (or .docx) + <name>.png, never in the shared repo.
  Default plan: the most recently changed plan in your resumes/ folder.

PNG thumbnails use PyMuPDF if installed (pip install pymupdf), else macOS's built-in `sips`
(PDF) and Quick Look (Word); without them only the PDF/DOCX is written. Thumbnails are
flattened onto white (Pillow) so they read in dark-mode viewers such as GitHub.
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

MINE = '--mine' in sys.argv
if MINE:
    sys.argv.remove('--mine')
else:
    # gallery mode must never render a real candidate: drop any --profile and force the example
    for flag in [a for a in sys.argv if a.startswith('--profile')]:
        i = sys.argv.index(flag)
        del sys.argv[i:i + (1 if '=' in flag else 2)]
    os.environ['RESUME_PROFILE'] = 'example'

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import candidate  # noqa: E402
import render  # noqa: E402
import tailor  # noqa: E402


def flatten_white(png):
    """Paint the thumbnail onto an opaque white page. PDF pages are transparent, and a
    transparent preview shows black text on a black page in dark-mode viewers (e.g. GitHub)."""
    try:
        from PIL import Image
    except ImportError:
        return
    im = Image.open(png)
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        bg = Image.new('RGB', im.size, 'white')
        bg.paste(im, mask=im.split()[-1])
        bg.save(png, optimize=True)


def thumbnail(pdf, png, width=900):
    try:
        import fitz  # PyMuPDF
        page = fitz.open(pdf)[0]
        page.get_pixmap(dpi=int(width / page.rect.width * 72)).save(png)
        return True
    except ImportError:
        pass
    if shutil.which('sips'):
        r = subprocess.run(['sips', '-s', 'format', 'png', '-Z', str(width), pdf, '--out', png],
                           capture_output=True)
        return r.returncode == 0
    return False


def docx_thumbnail(docx, png, width=900):
    """macOS Quick Look can draw a .docx; elsewhere, open the .docx itself."""
    if not shutil.which('qlmanage'):
        return False
    work = tempfile.mkdtemp()
    try:
        subprocess.run(['qlmanage', '-t', '-s', str(width), '-o', work, docx], capture_output=True)
        made = os.path.join(work, os.path.basename(docx) + '.png')
        if os.path.exists(made):
            shutil.move(made, png)
            return True
        return False
    finally:
        shutil.rmtree(work, ignore_errors=True)


def template_names(dirs):
    names = []
    for base in dirs:
        if os.path.isdir(base):
            names += [d for d in sorted(os.listdir(base)) if os.path.exists(os.path.join(base, d, 'manifest.json'))]
    return list(dict.fromkeys(names))


def pick_plan(arg):
    if arg:
        return arg if os.path.exists(arg) else candidate.path(arg)
    plans = glob.glob(candidate.path('resumes', '*', 'plan.json'))
    if not plans:
        raise SystemExit('No plans yet: write one first (tasks/write-plan.md) or pass --plan PATH.')
    return max(plans, key=os.path.getmtime)


def main():
    args = sys.argv[1:]
    plan_arg = None
    if '--plan' in args:
        i = args.index('--plan')
        plan_arg = args[i + 1]
        del args[i:i + 2]
    if MINE:
        plan_path = pick_plan(plan_arg)
        names = args or template_names([candidate.path('templates'), candidate.TEMPLATES])
        out_dir = candidate.path('previews')
        os.makedirs(out_dir, exist_ok=True)
        print(f'your resume from {os.path.relpath(plan_path, candidate.profile_dir())}:')
    else:
        plan_path = os.path.join(candidate.PROFILES, 'example', 'resumes', 'bosch-general', 'plan.json')
        names = args or template_names([candidate.TEMPLATES])
    with open(plan_path, encoding='utf-8') as f:
        try:
            doc = tailor.build_document(json.load(f))
        except tailor.PlanError as e:
            raise SystemExit(str(e))

    for name in names:
        work = tempfile.mkdtemp()
        try:
            try:
                out, pages, _ = render.render(doc, name, work, 'preview')
            except SystemExit as e:  # one broken template should not stop the others
                print(f'{name:<18} FAILED: {str(e).splitlines()[0]}')
                continue
            ext = os.path.splitext(out)[1]
            if MINE:
                dest_dir, stem = out_dir, name
            else:
                dest_dir, stem = os.path.join(candidate.TEMPLATES, name), 'preview'
            for old in ('.pdf', '.docx', '.png'):
                if os.path.exists(os.path.join(dest_dir, stem + old)):
                    os.remove(os.path.join(dest_dir, stem + old))
            dest = os.path.join(dest_dir, stem + ext)
            shutil.copy(out, dest)
            png = os.path.join(dest_dir, stem + '.png')
            made = thumbnail(dest, png) if ext == '.pdf' else docx_thumbnail(dest, png)
            if made:
                flatten_white(png)
            print(f'{name:<18} -> {os.path.relpath(dest, candidate.REPO)}' + (' + .png' if made else '')
                  + (f' ({pages} page{"s" if pages != 1 else ""})' if pages else ''))
        finally:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    main()
