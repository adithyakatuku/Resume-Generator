"""Assisted applying: open the job, hand over the right resume and answers,
then record the application in the tracker. You submit the form yourself.

    .venv/bin/python engine/apply.py                 # jobs ready to apply, newest postings first
    .venv/bin/python engine/apply.py amazon:10604005 # apply to one
    .venv/bin/python engine/apply.py --done amazon:10604005   # mark applied without the walkthrough

Applying to one job:
  1. opens the job posting in your browser (sign in and click Apply),
  2. copies the tailored resume's path to the clipboard: in the upload dialog
     press Cmd+Shift+G, paste, Enter,
  3. prints your standard answers from <profile>/private/applicant.json,
  4. asks whether you submitted; "y" marks the job Applied (dated today).

Close applications.xlsx in Excel first, or the tracker update cannot be saved.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import candidate  # noqa: E402
import tracker  # noqa: E402
from tailor import resume_for  # noqa: E402

READY = ('Tailored', 'Shortlisted')
MAX_AGE = 60


def load_applicant():
    APPLICANT = candidate.path('private', 'applicant.json')
    if not os.path.exists(APPLICANT):
        raise SystemExit(f'Missing {os.path.relpath(APPLICANT)}. Copy profiles/example/private/applicant.json '
                         'there and fill it in.')
    with open(APPLICANT, encoding='utf-8') as f:
        a = json.load(f)
    empty = [k for k, v in a.items() if not k.startswith('_') and v in ('', None)]
    if empty:
        print(f'note: still blank in applicant.json: {", ".join(empty)}\n')
    return a


def experience_text(bank):
    y, m = map(int, bank['career_start'].split('-'))
    t = date.today()
    months = (t.year - y) * 12 + t.month - m
    return f'{months // 12} years {months % 12} months'


def worked_at(company, previous):
    """Answer "have you worked at <company> before?" from applicant.json."""
    first = company.split()[0].lower()
    hit = [p for p in previous if first in p.lower() or p.lower().split()[0] in company.lower()]
    return f'Yes ({", ".join(hit)})' if hit else 'No'


def answers(bank, a, company=''):
    """The answer sheet: facts from bank.json, then every field in applicant.json in its
    own order (labels from the keys), then its `extra` questions."""
    c = bank['contact']
    sheet = [('Name', c['name']), ('Email', c.get('email')), ('Phone', c.get('phone'))]
    import tailor
    def link_name(url):
        u = url.lower()
        return 'LinkedIn' if 'linkedin.' in u else 'GitHub' if 'github.' in u else 'Portfolio / website'
    sheet += [(link_name(l['url']), l['url']) for l in tailor.contact_links(c)]
    if bank.get('career_start'):
        sheet.append(('Total experience', experience_text(bank)))
    if bank.get('experience'):
        e = bank['experience'][0]
        sheet.append(('Current employer / title', f"{e['company']} / {e['title']}"))
    for edu in bank.get('education', [])[:1]:
        sheet.append(('Education', ', '.join(str(x) for x in (edu.get('degree'), edu.get('school'), edu.get('year')) if x)
                      + (f" ({edu['grade']})" if edu.get('grade') else '')))
    for k, v in a.items():
        if k.startswith('_') or k == 'extra':
            continue
        if k == 'previously_employed_by':
            sheet.append((f'Worked at {company or "this company"} before', worked_at(company, v or [])))
            continue
        label = k.replace('_', ' ').strip().capitalize()
        sheet.append((label, ', '.join(v) if isinstance(v, list) else v))
    sheet += [(k, v) for k, v in (a.get('extra') or {}).items()]
    return sheet


def jd_hash(key):
    cid, jid = key.split(':', 1)
    p = candidate.path('data', 'jobs', cid, re.sub(r'[^\w.-]', '_', jid) + '.json')
    if not os.path.exists(p):
        return None
    d = json.load(open(p, encoding='utf-8'))['description']
    return hashlib.md5(re.sub(r'\s+', ' ', d).encode()).hexdigest()


def age(r):
    p = r.get('Posted')
    return (date.today() - p).days if isinstance(p, date) else None


def list_ready(rows):
    ready = [r for r in rows.values() if r.get('Status') in READY]
    if not ready:
        print('Nothing ready: no Tailored or Shortlisted jobs.')
        return
    groups = {}
    for r in ready:
        groups.setdefault(jd_hash(r['Key']), []).append(r['Key'])
    # newest first: fresh postings get the most recruiter attention (owner's preference)
    ready.sort(key=lambda r: age(r) if age(r) is not None else 10 ** 6)
    print(f'{"key":<18}{"age":>4} {"left":>5}  {"status":<11} role')
    for r in ready:
        a = age(r)
        left = f'{MAX_AGE - a}d' if a is not None else '?'
        twins = [k for k in groups.get(jd_hash(r['Key']), []) if k != r['Key']]
        same = f'  (same posting text as {", ".join(twins)})' if twins and jd_hash(r['Key']) else ''
        rel, policy = resume_for(r['Key'])
        flag = '' if os.path.exists(candidate.path(rel)) else f'  [needs {rel.split("/")[1]} resume]'
        print(f'{r["Key"]:<18}{a if a is not None else "?":>4} {left:>5}  {r["Status"]:<11} {r["Role"][:55]}{flag}{same}')


def mark_applied(rows, key, note=''):
    r = rows[key]
    r['Status'] = 'Applied'
    r['Applied On'] = date.today()
    if note:
        r['Notes'] = (str(r.get('Notes') or '') + ('; ' if r.get('Notes') else '') + note).strip()
    tracker.save(rows)
    print(f'{key} marked Applied ({date.today():%d %b %Y}).')


def walkthrough(rows, key):
    r = rows.get(key)
    if not r:
        raise SystemExit(f'{key} is not in the tracker.')
    if r.get('Status') not in READY:
        print(f'warning: {key} is "{r.get("Status")}", not Tailored/Shortlisted.')
    bank = candidate.load_json('bank.json')
    a = load_applicant()
    rel, policy = resume_for(key)
    pdf = candidate.path(rel)
    if not os.path.exists(pdf):
        kind = 'per-job' if policy == 'per_application' else 'company-wide'
        raise SystemExit(f'No {kind} resume at {rel} ({r["Company"]} resume_policy={policy}); build it with tailor.py first.')
    if r.get('Resume') != rel:
        r['Resume'] = rel  # record what is actually being sent

    print(f'{r["Role"]}  [{r["Company"]}]  posted {r.get("Posted")}, {age(r)} days ago\n{r["URL"]}\n')
    subprocess.run(['open', r['URL']], check=False)
    subprocess.run(['pbcopy'], input=pdf.encode(), check=False)
    print(f'Resume path copied to clipboard (upload dialog: Cmd+Shift+G, paste, Enter):\n  {pdf}')
    if policy == 'profile':
        print(f'  {r["Company"]} keeps one resume per profile: this upload is what all your {r["Company"]} applications show.')
    elif policy == 'unknown':
        print(f'  {r["Company"]} resume handling is unverified: note whether the form prefilled an earlier resume,'
              ' then set resume_policy in companies.json.')
    print()
    print('Answers')
    for k, v in answers(bank, a, r['Company']):
        print(f'  {k + ":":<26} {v if v not in ("", None) else "(not set)"}')
    print()
    try:
        done = input('Did you submit the application? [y/N] ').strip().lower() == 'y'
    except EOFError:
        done = False
    if done:
        note = input('Optional note (e.g. referral, questions asked): ').strip()
        mark_applied(rows, key, note)
    else:
        print('Not marked. Re-run when you have applied, or use --done.')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('key', nargs='?', help='tracker key, e.g. amazon:10604005')
    ap.add_argument('--done', action='store_true', help='just mark KEY as applied today')
    a = ap.parse_args()
    rows = tracker.load()
    if not a.key:
        list_ready(rows)
    elif a.done:
        if a.key not in rows:
            raise SystemExit(f'{a.key} is not in the tracker.')
        mark_applied(rows, a.key)
    else:
        walkthrough(rows, a.key)


if __name__ == '__main__':
    main()
