"""ATS-style check of a tailored resume against its job description.

    .venv/bin/python engine/ats_check.py resumes/amazon-10604005
    .venv/bin/python engine/ats_check.py resumes/amazon-general amazon:10589588 amazon:10583673

1. Parsing: extracts the PDF (or DOCX) text, PDF with pdfminer (what many ATS parsers build
   on) and checks for junk glyphs, ligature damage, contact details and the
   standard section headings.
2. Keywords: finds the terms the job description uses (the profile's vocab.json
   terms and requirement phrases) and reports which the resume contains.
   Missing terms are prompts to check the bank, not words to stuff in: only
   add a term when it is true.
"""
import json
import os
import re
import sys
import unicodedata

from pdfminer.high_level import extract_text

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import candidate  # noqa: E402
from match import vocab  # noqa: E402
from tailor import output_stem  # noqa: E402

SECTIONS = ['summary', 'skills', 'experience', 'education']


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    folder = sys.argv[1] if os.path.isdir(sys.argv[1]) else candidate.path(sys.argv[1])
    job_keys = sys.argv[2:]  # e.g. amazon:10589588 ...; a general resume has no job of its own
    plan_file = os.path.join(folder, 'plan.json')
    if not os.path.exists(plan_file):  # a try-<template>/ folder from tailor.py --template
        plan_file = os.path.join(os.path.dirname(os.path.abspath(folder)), 'plan.json')
    plan = json.load(open(plan_file, encoding='utf-8'))
    text = resume_text(folder)
    low = text.lower()
    contact = candidate.load_json('bank.json')['contact']

    print('PARSING')
    junk = sorted({c for c in text if '(cid:' in text or unicodedata.category(c) in ('Co', 'Cn') or c == '�'})
    cid = len(re.findall(r'\(cid:\d+\)', text))
    lig = sum(text.count(c) for c in 'ﬀﬁﬂﬃﬄ')
    checks = [
        ('no unreadable glyphs', cid == 0 and not junk, f'{cid} "(cid:N)" codes, {len(junk)} private-use chars'),
        ('no ligature damage', lig == 0, f'{lig} ligature chars'),
        ('email', bool(re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', text)), ''),
        ('phone', bool(re.search(r'\+?\d[\d -]{9,}', text)), ''),
    ]
    import tailor
    for link in tailor.contact_links(contact):
        checks.append((f'link {link["label"]}', link['label'].lower() in low, 'not found as plain text'))
    checks += [
        ('standard sections', all(s in low for s in SECTIONS), ', '.join(s for s in SECTIONS if s not in low)),
    ]
    for name, ok, detail in checks:
        print(f'  {"ok " if ok else "FIX"}  {name}' + (f'  ({detail})' if not ok and detail else ''))

    keys = job_keys or ([plan['job']] if plan.get('job') else [])
    if not keys:
        print('\nKEYWORDS  skipped: general resume, pass job keys to compare (e.g. amazon:10589588)')
    for key in keys:
        keyword_report(key, low, len(keys) > 1)


def resume_text(folder):
    """Text of the rendered resume (PDF via pdfminer, DOCX via its XML)."""
    stem = output_stem()
    pdf, docx = os.path.join(folder, stem + '.pdf'), os.path.join(folder, stem + '.docx')
    if os.path.exists(pdf):
        return extract_text(pdf)
    if os.path.exists(docx):
        import zipfile
        with zipfile.ZipFile(docx) as z:
            xml = z.read('word/document.xml').decode('utf-8')
        xml = re.sub(r'</w:p>', '\n', xml)
        return re.sub(r'<[^>]+>', '', xml)
    raise SystemExit(f'No {stem}.pdf or .docx in {folder}; run tailor.py first.')


def keyword_report(key, low, label):
    cid_, jid = key.split(':', 1)
    job = json.load(open(candidate.path('data', 'jobs', cid_, re.sub(r'[^\w.-]', '_', jid) + '.json'), encoding='utf-8'))
    v = vocab()
    jd = job['description']
    for cut in v.get('jd_cut', []):  # boilerplate footers (EEO notes, benefits)
        jd = jd.split(cut)[0]
    jd = jd.lower()
    covered, ignore = set(v.get('covered_by_phrases', [])), set(v.get('phrases_ignore', []))
    wanted, present = [], []
    for name, pat in v['patterns'].items():
        if name in covered:
            continue
        if pat.search(jd):
            wanted.append(name)
            if pat.search(low):
                present.append(name)
    for name, pat in v.get('phrases', {}).items():
        if name in ignore:
            continue
        if re.search(pat, jd):
            wanted.append(name)
            if re.search(pat, low):
                present.append(name)
    missing = [w for w in wanted if w not in present]
    head = f'{key} ({job.get("title", "")[:45]})' if label else 'the job description'
    print(f'\nKEYWORDS  {len(present)}/{len(wanted)} of the terms in {head}')
    if not label:
        print('  present:', ', '.join(present) or '-')
    print('  missing:', ', '.join(missing) or '-')

if __name__ == '__main__':
    main()
