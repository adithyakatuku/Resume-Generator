"""docx-basic: a plain, ATS-friendly Word resume built with python-docx.

render(doc, out_path, template_dir) receives the resume document from
engine/tailor.py (contact + ordered sections) and writes a .docx.
Single column, standard headings, real bullet lists, no tables or text boxes,
so applicant tracking systems read it cleanly.
"""
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, Inches


def _heading(d, text):
    p = d.add_paragraph()
    r = p.add_run(text.upper())
    r.bold = True
    r.font.size = Pt(11)
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(2)
    return p


def _bullets(d, items):
    for t in items:
        p = d.add_paragraph(t, style='List Bullet')
        p.paragraph_format.space_after = Pt(0)


def _line(d, text, bold=False, italic=False):
    """One line of text. Details go inline ("Company · City · Dates") rather than on a right-aligned
    tab: tabs render inconsistently outside Word (Google Docs previews, Quick Look, some ATS text
    extractors), inline text reads the same everywhere."""
    p = d.add_paragraph()
    p.paragraph_format.space_after = Pt(0)
    r = p.add_run(text)
    r.bold, r.italic = bold, italic
    return p


def _join(*parts):
    return ' · '.join(x for x in parts if x)


def render(doc, out_path, template_dir):
    d = Document()
    for s in d.sections:
        s.left_margin = s.right_margin = Inches(0.6)
        s.top_margin = s.bottom_margin = Inches(0.5)
    style = d.styles['Normal']
    style.font.name = 'Calibri'
    style.font.size = Pt(10.5)

    c = doc['contact']
    p = d.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(c['name'])
    r.bold = True
    r.font.size = Pt(18)
    parts = [x for x in (c.get('phone'), c.get('email')) if x] + [l['label'] for l in c.get('links', [])]
    p = d.add_paragraph(' | '.join(parts))
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    for s in doc['sections']:
        _heading(d, s['title'])
        if s['type'] == 'summary':
            d.add_paragraph(s['text'])
        elif s['type'] == 'skills':
            for g in s['groups']:
                p = d.add_paragraph()
                p.paragraph_format.space_after = Pt(0)
                p.add_run(g['name'] + ': ').bold = True
                p.add_run(', '.join(g['items']))
        elif s['type'] == 'experience':
            for e in s['entries']:
                _line(d, e['title'], bold=True)
                _line(d, _join(e['company'], e.get('location'), e['dates']), italic=True)
                _bullets(d, e['bullets'])
                for pr in e['projects']:
                    p = d.add_paragraph()
                    p.paragraph_format.space_before = Pt(3)
                    p.paragraph_format.space_after = Pt(0)
                    p.add_run(pr['heading']).bold = True
                    _bullets(d, pr['bullets'])
        elif s['type'] == 'education':
            for ed in s['entries']:
                _line(d, ed['degree'], bold=True)
                _line(d, _join(ed['school'], ed.get('when'), ed.get('grade')), italic=True)
        elif s['type'] == 'projects':
            for pr in s['entries']:
                p = d.add_paragraph()
                p.paragraph_format.space_after = Pt(0)
                p.add_run(pr['name']).bold = True
                if pr.get('tech'):
                    p.add_run(' | ' + ', '.join(pr['tech'])).italic = True
                _bullets(d, pr['bullets'])
        elif s['type'] == 'list':
            _bullets(d, s['items'])
    d.save(out_path)
    return None  # Word decides pagination; check length by opening the file
