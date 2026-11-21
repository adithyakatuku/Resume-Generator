"""Pick the next job to apply to at each company: one tailored application at a time.

    .venv/bin/python engine/pick.py           # proposals, best first
    .venv/bin/python engine/pick.py --mark    # also mark each proposal Shortlisted in the tracker
    .venv/bin/python engine/pick.py -b 3      # show 3 backups per company

A company gets a proposal only while it has fewer open applications
(Applied / Responded / Interview) than its max_active (criteria.json
max_active_per_company, or the company's own max_active). Within a company:

  1. qualified first: the experience asked is at most yours (from bank.json
     career_start), or not stated. Hard experience screens are what sank the
     Amazon SDE II applications, so fit alone is not enough;
  2. then Match, plus small bonuses for the company's wlb / pay reputation;
  3. then the newest posting.

Companies are listed best proposal first. When a company rejects you, re-run:
its next-best job becomes the proposal, with its own tailored resume.
"""
import argparse
import json
import os
import re
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import candidate  # noqa: E402
import tracker  # noqa: E402

ACTIVE = ('Applied', 'Responded', 'Interview')
CANDIDATE = ('New', 'Shortlisted', 'Tailored')
WLB_BONUS = {'good': 6, 'mixed': 0, 'unknown': 0}
PAY_BONUS = {'high': 6, 'good': 3, 'average': 0}


def my_years():
    y, m = map(int, candidate.load_json('bank.json')['career_start'].split('-'))
    t = date.today()
    return ((t.year - y) * 12 + t.month - m) / 12


def asks(row):
    m = re.match(r'(\d+)', str(row.get('Exp Asked') or ''))
    return int(m.group(1)) if m else None


def score(row, co, years):
    need = asks(row)
    qualified = need is None or need <= years
    match = int(row['Match']) if str(row.get('Match', '')).isdigit() else 50
    bonus = WLB_BONUS.get(co.get('wlb'), 0) + PAY_BONUS.get(co.get('pay'), 0)
    posted = row.get('Posted')
    fresh = posted.toordinal() if isinstance(posted, date) else 0
    return (qualified, match + bonus, fresh), qualified, match + bonus


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--mark', action='store_true', help='mark each proposal Shortlisted in the tracker')
    ap.add_argument('-b', '--backups', type=int, default=2, help='backups to list per company')
    a = ap.parse_args()

    default_max = candidate.load_json('criteria.json').get('max_active_per_company', 1)
    companies = {c['name']: c for c in candidate.load_json('companies.json')['companies']}
    rows = tracker.load()
    years = my_years()

    by_co = {}
    for r in rows.values():
        by_co.setdefault(r['Company'], []).append(r)

    proposals, full = [], []
    for name, rs in by_co.items():
        co = companies.get(name, {})
        cap = co.get('max_active', default_max)
        active = [r for r in rs if r.get('Status') in ACTIVE]
        cands = sorted((r for r in rs if r.get('Status') in CANDIDATE),
                       key=lambda r: score(r, co, years)[0], reverse=True)
        if len(active) >= cap:
            if cands:
                full.append((name, len(active), cap, len(cands)))
            continue
        if cands:
            proposals.append((name, co, cands))

    proposals.sort(key=lambda p: score(p[2][0], p[1], years)[0], reverse=True)
    print(f'Your experience: {years:.1f} years. "!" = asks more than that (likely screened out).\n')
    for name, co, cands in proposals:
        top = cands[0]
        _, ok, s = score(top, co, years)
        print(f'{name}  [wlb {co.get("wlb", "?")}, pay {co.get("pay", "?")}, {co.get("work_mode", "?")}]')
        for i, r in enumerate(cands[:1 + a.backups]):
            _, ok, s = score(r, co, years)
            tag = 'PICK  ' if i == 0 else 'backup'
            print(f'  {tag} {"" if ok else "!"}{r["Key"]:<22} score {s:>3}  asks {str(r.get("Exp Asked") or "?"):<5}'
                  f' posted {r.get("Posted") or "?"}  {r["Role"][:55]}')
        if len(cands) > 1 + a.backups:
            print(f'         (+{len(cands) - 1 - a.backups} more)')
    if full:
        print('\nAt their limit (waiting on an open application):')
        for name, n, cap, waiting in full:
            print(f'  {name}: {n} open / max {cap}; {waiting} job(s) waiting')
    if a.mark:
        n = 0
        for _, _, cands in proposals:
            if cands[0].get('Status') == 'New':
                cands[0]['Status'] = 'Shortlisted'
                n += 1
        tracker.save(rows)
        print(f'\nMarked {n} new pick(s) Shortlisted.')


if __name__ == '__main__':
    main()
