"""First-pass match score: how well a job description fits bank.json.

    .venv/bin/python engine/match.py            # score unscored jobs, print the ranking
    .venv/bin/python engine/match.py --force    # rescore every job

The score is a quick keyword measure for sorting, not a verdict. It finds the
terms a description asks for, weights must-haves over nice-to-haves,
and checks them against the skills in bank.json, using the profile's vocab.json.
"Java, Python or C++" style lists count as met when you know any one of them.
Read the top of the list yourself (or ask your agent to) before shortlisting.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import candidate  # noqa: E402

_VOCAB = None


def vocab():
    """The profile's vocab.json, compiled. See profiles/example/vocab.json for the format."""
    global _VOCAB
    if _VOCAB is None:
        v = candidate.load_json('vocab.json')
        v['patterns'] = {k: re.compile(r'(?<![\w+#.])(?:' + rx + r')(?![\w+#])', re.I)
                         for k, rx in v.get('terms', {}).items()}
        v['fundamentals'] = set(v.get('fundamentals', []))
        v['near'] = v.get('near', {})
        _VOCAB = v
    return _VOCAB


CHOICE = re.compile(r'\b(at least one|one or more|one of|such as|e\.g\.|like|or|and/or)\b', re.I)
PREFERRED = re.compile(r'preferred|nice to have|good to have|bonus|plus|desired', re.I)
REQUIRED = re.compile(r'basic|minimum|required|requirements|qualifications|what you|you have|must|responsibilit|you will|role', re.I)


def user_terms():
    """Canonical terms the candidate has: via vocab "have" if given, else any term whose
    pattern matches one of the bank's skills. Fundamentals always count."""
    v = vocab()
    bank = candidate.load_json('bank.json')
    skills = {s for group in bank.get('skills', {}).values() for s in group}
    if v.get('have'):
        have = {k for k, name in v['have'].items() if name in skills}
    else:
        have = {k for k, p in v['patterns'].items() if any(p.search(s) for s in skills)}
    return have | v['fundamentals']


def candidate_years():
    start = candidate.load_json('bank.json').get('career_start')
    if not start:
        return None
    from datetime import date
    y, m = map(int, start.split('-'))
    t = date.today()
    return ((t.year - y) * 12 + t.month - m) // 12


def score(text, exp_label, have):
    """Return (0-100, matched terms, gaps ordered by weight)."""
    v = vocab()
    weight, mode = {}, 'required'
    for line in text.split('\n'):
        s = line.strip()
        if not s:
            continue
        if len(s) < 70 and PREFERRED.search(s) and not s.startswith('-'):
            mode = 'preferred'
        elif len(s) < 70 and REQUIRED.search(s) and not s.startswith('-'):
            mode = 'required'
        found = [k for k, p in v['patterns'].items() if p.search(s)]
        if not found:
            continue
        # "Java, Python or C++": knowing any one satisfies the whole list
        if CHOICE.search(s) and any(k in have for k in found):
            found = [k for k in found if k in have]
        # bulleted asks are requirements; prose (team blurbs, mission statements) barely counts
        bullet = bool(re.match(r'[-•*·]|\d+[.)]\s', s))
        if mode == 'preferred' or 'preferred' in s.lower():
            w = 1.0 if bullet else 0.5
        else:
            w = 2.0 if bullet else 0.5
        for k in found:
            weight[k] = max(weight.get(k, 0), w)
    near = v['near']
    got = sum(w * (1.0 if k in have else near.get(k, 0)) for k, w in weight.items())
    total = sum(weight.values())
    # smoothed toward 70 so descriptions naming few technologies don't swing to 0 or 100
    pct = 100 * (got + 1.4) / (total + 2)
    need = re.match(r'(\d+)', exp_label or '')
    years = candidate_years()
    if need and years is not None:
        # relative to the candidate: asking well below their years is a plus, above is a minus
        gap = int(need.group(1)) - years
        pct += 6 if gap <= -1 else {0: 4, 1: 0, 2: -8}.get(gap, -15)
    gaps = sorted((k for k in weight if k not in have and k not in v['fundamentals']),
                  key=lambda k: (-weight[k], near.get(k, 0)))
    return max(0, min(100, round(pct))), sorted(k for k in weight if k in have), gaps


def job_text(company_id, job_id):
    p = candidate.path('data', 'jobs', company_id, re.sub(r'[^\w.-]', '_', job_id) + '.json')
    if not os.path.exists(p):
        return None
    with open(p, encoding='utf-8') as f:
        j = json.load(f)
    return j.get('title', '') + '\n' + j.get('description', '')


def score_rows(rows, force=False):
    """Fill Match and Gaps on tracker rows from cached descriptions. Returns count scored."""
    have, n = user_terms(), 0
    for key, r in rows.items():
        if r.get('Match') not in ('', None) and not force:
            continue
        cid, jid = key.split(':', 1)
        text = job_text(cid, jid)
        if text is None:
            continue
        s, _, gaps = score(text, str(r.get('Exp Asked') or ''), have)
        r['Match'], r['Gaps'] = s, ', '.join(gaps[:5])
        n += 1
    return n


def main():
    sys.path.insert(0, HERE)
    import tracker
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--force', action='store_true', help='rescore jobs that already have a Match')
    ap.add_argument('-n', type=int, default=15, help='how many to list')
    a = ap.parse_args()
    rows = tracker.load()
    n = score_rows(rows, a.force)
    tracker.save(rows)
    print(f'scored {n} job(s)\n')
    ranked = sorted((r for r in rows.values() if r.get('Status') in tracker.OPEN and r.get('Match') != ''),
                    key=lambda r: -int(r['Match']))
    for r in ranked[:a.n]:
        print(f"{r['Match']:>3}  {r['Exp Asked']:<5} {r['Company'][:14]:<14} {r['Role'][:60]:<60} gaps: {r.get('Gaps') or '-'}")


if __name__ == '__main__':
    main()
