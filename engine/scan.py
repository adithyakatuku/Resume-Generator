"""Scan company job boards for eligible roles and update applications.xlsx.

Usage (from the repo root):
    .venv/bin/python engine/scan.py                  # all enabled API companies
    .venv/bin/python engine/scan.py amazon f5        # just these
    .venv/bin/python engine/scan.py --dry-run -v     # show decisions, write nothing
    .venv/bin/python engine/scan.py --refresh        # no scan: just rebuild Summary / Applied by Date

Pipeline per company: list jobs -> title filter -> location filter ->
fetch full description -> experience filter -> tracker row.
Then jobs an agent found on browser sources (sources.json, tasks/browse-search.md) and saved
to data/inbox/ go through the same filters (scan.py --import-only to do just that).
Full descriptions are cached in <profile>/data/jobs/<company>/<job_id>.json
for the resume-tailoring step.
"""
import argparse
import glob
import copy
import json
import os
import re
import sys
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import candidate  # noqa: E402
import sources  # noqa: E402
import tracker  # noqa: E402
import match  # noqa: E402



def load_json(name):
    return candidate.load_json(name)


def word_re(words):
    return re.compile(r'(?<![a-z0-9])(' + '|'.join(re.escape(w.lower()) for w in words) + r')(?![a-z0-9])')


class Rules:
    def __init__(self, crit):
        self.crit = crit
        self.inc = word_re(crit['title_include'])
        self.exc = word_re(crit['title_exclude'])
        self.cities = [c.lower() for c in crit['locations']['include']]
        self.remote_ok = crit['locations'].get('accept_remote_india', False)
        # remote roles also count when open to a wider region that includes India (APAC, worldwide...)
        regions = crit['locations'].get('remote_regions', ['india'])
        self.remote_re = re.compile(r'\b(' + '|'.join(re.escape(r.lower()) for r in regions) + r')\b|^in,|\bind\b')
        self.lo, self.hi = crit['experience_years']['min'], crit['experience_years']['max']
        self.max_age = crit.get('max_posting_age_days')
        self.desc_exc = word_re(crit['description_exclude']) if crit.get('description_exclude') else None

    def for_company(self, co):
        """Rules with this company's overrides from criteria.json applied."""
        o = self.crit.get('company_overrides', {}).get(co['id'])
        if not o:
            return self
        r = copy.copy(self)
        if 'max_years' in o:
            r.hi = o['max_years']
        if o.get('title_exclude'):
            r.exc = word_re(self.crit['title_exclude'] + o['title_exclude'])
        if o.get('description_exclude'):
            r.desc_exc = word_re(self.crit.get('description_exclude', []) + o['description_exclude'])
        return r

    def employment(self, text):
        m = self.desc_exc.search((text or '').lower()) if self.desc_exc else None
        return f'description excludes "{m.group(1)}"' if m else None

    def age(self, posted):
        """Return (days-or-None, reason-or-None)."""
        try:
            days = (date.today() - datetime.strptime(posted[:10], '%Y-%m-%d').date()).days
        except (TypeError, ValueError):
            return None, None
        if self.max_age is not None and days > self.max_age:
            return days, f'posted {days} days ago'
        return days, None

    def title(self, t):
        t = t.lower()
        m = self.exc.search(t)
        if m:
            return f'title excludes "{m.group(1)}"'
        if not self.inc.search(t):
            return 'title not a dev role'
        return None

    def location(self, locs, final):
        for l in locs:
            ll = l.lower()
            if any(c in ll for c in self.cities):
                return None
            if self.remote_ok and re.search(r'remote|virtual|home[- ]based|anywhere', ll) and self.remote_re.search(ll):
                return None
            # Workday summary text like "3 Locations" can't be judged until details are fetched
            if not final and re.fullmatch(r'\d+ locations', ll.strip()):
                return None
        return 'location: ' + '; '.join(locs)[:60]

    # "3+ years", "2-5 years", "2 to 4 yrs", "minimum of 3 years"
    EXP = re.compile(r'(\d{1,2})\s*(?:\+|plus)?\s*(?:(?:-|–|—|to)\s*(\d{1,2})\s*\+?)?\s*(?:years?|yrs?)\b', re.I)

    def experience(self, text):
        """Return (label, reason-or-None). Uses the largest stated minimum,
        so '5+ years overall, 2+ in React' reads as 5."""
        mins, maxs = [], []
        for line in re.split(r'[\n.;]', text):
            if not re.search(r'experience|exp\b|professional|industry|work|software|engineering|development|programming|building', line, re.I):
                continue
            for m in self.EXP.finditer(line):
                lo = int(m.group(1))
                if lo > 20:  # "over 25 years of serving customers"
                    continue
                mins.append(lo)
                if m.group(2):
                    maxs.append(int(m.group(2)))
        if not mins:
            return '?', None
        need = max(mins)
        label = f'{need}-{max(maxs)}' if maxs and max(maxs) > need else f'{need}+'
        if need > self.hi:
            return label, f'asks {label} yrs'
        if maxs and max(maxs) < self.lo:
            return label, f'asks only {label} yrs'
        return label, None


def scan_company(co, rules):
    fetch = sources.FETCHERS[co['platform']]
    rules = rules.for_company(co)
    stats = dict(listed=0, title=0, location=0, eligible=0)
    eligible, rejects = [], []
    for stub in fetch.list_jobs(co, rules.crit):
        stats['listed'] += 1
        why = (rules.title(stub['title']) or rules.location(stub['locations'], stub.get('_complete', False))
               or rules.age(stub.get('posted'))[1])
        if why:
            rejects.append((stub['title'], why))
            continue
        stats['title'] += 1
        job = fetch.details(co, stub)
        why = rules.location(job['locations'], True)
        if why:
            rejects.append((job['title'], why))
            continue
        stats['location'] += 1
        why = rules.age(job.get('posted'))[1] or rules.employment(job.get('description'))
        if why:
            rejects.append((job['title'], why))
            continue
        exp, why = rules.experience(job.get('exp_text') or job.get('description', ''))
        job['exp'] = exp
        if why:
            rejects.append((job['title'], why))
            continue
        stats['eligible'] += 1
        eligible.append(job)
    return eligible, rejects, stats


def location_label(locs, rules):
    """Matching locations first, then a count of the rest."""
    hit = [l for l in locs if rules.location([l], True) is None]
    rest = len(locs) - len(hit)
    return '; '.join(hit) + (f' (+{rest} more)' if rest else '')


def cache_job(co, job):
    d = candidate.path('data', 'jobs', co['id'])
    os.makedirs(d, exist_ok=True)
    keep = {k: v for k, v in job.items() if not k.startswith('_')}
    keep['company'] = co['name']
    with open(os.path.join(d, re.sub(r'[^\w.-]', '_', job['job_id']) + '.json'), 'w', encoding='utf-8') as f:
        json.dump(keep, f, indent=2, ensure_ascii=False)


def _norm(text):
    return re.sub(r'[^a-z0-9]+', ' ', (text or '').lower()).strip()


def import_inbox(rules, found, existing, dry_run, verbose):
    """Jobs an agent found on browser sources (tasks/browse-search.md), saved as JSON files in
    <profile>/data/inbox/ (one job, a list, or {"jobs": [...]}). They pass the same filters as
    feed jobs; a job already tracked under the same company + title (from any source) is skipped.
    Processed files move to data/inbox/done/. Returns {source: [kept, total]}."""
    inbox = candidate.path('data', 'inbox')
    files = sorted(f for f in glob.glob(os.path.join(inbox, '*.json')))
    stats = {}
    if not files:
        return stats
    seen = {(_norm(r.get('Company')), _norm(r.get('Role'))) for r in list(existing.values()) + list(found.values())}
    for path in files:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        jobs = data.get('jobs', []) if isinstance(data, dict) and 'jobs' in data else (data if isinstance(data, list) else [data])
        for j in jobs:
            src = j.get('source') or os.path.splitext(os.path.basename(path))[0]
            st = stats.setdefault(src, [0, 0])
            st[1] += 1
            co = {'id': re.sub(r'[^a-z0-9]+', '-', (j.get('company') or 'unknown').lower()).strip('-'),
                  'name': j.get('company') or 'Unknown'}
            r = rules.for_company(co)
            text = j.get('description', '')
            if j.get('experience'):
                text = f"Experience: {j['experience']} years\n" + text
            why = (r.title(j['title']) or r.location(j.get('locations', []), True) or r.age(j.get('posted'))[1]
                   or r.employment(text))
            exp, why2 = r.experience(text)
            why = why or why2
            dup = (_norm(co['name']), _norm(j['title'])) in seen
            if verbose:
                print(f'    {"+" if not (why or dup) else "-"} [{src}] {co["name"]}: {j["title"]}'
                      + (f'  ({why})' if why else '  (already tracked)' if dup else f'  [{exp}]'))
            if why or dup:
                continue
            seen.add((_norm(co['name']), _norm(j['title'])))
            st[0] += 1
            job = {'job_id': str(j['job_id']), 'title': j['title'], 'locations': j.get('locations', []),
                   'url': j.get('url', ''), 'posted': j.get('posted', ''), 'description': text, 'exp': exp,
                   'source': src, 'employer': co['name']}
            key = f'{src}:{job["job_id"]}'
            found[key] = {'Key': key, 'Company': co['name'], 'Role': job['title'],
                          'Location': location_label(job['locations'], rules) or '; '.join(job['locations'])[:80],
                          'Exp Asked': exp, 'Posted': job['posted'], 'URL': job['url']}
            if not dry_run:
                cache_job({'id': src, 'name': co['name']}, job)
        if not dry_run:
            os.makedirs(os.path.join(inbox, 'done'), exist_ok=True)
            os.replace(path, os.path.join(inbox, 'done', os.path.basename(path)))
    return stats


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('companies', nargs='*', help='company ids from companies.json (default: all enabled)')
    ap.add_argument('--dry-run', action='store_true', help='do not write the tracker or cache')
    ap.add_argument('--refresh', action='store_true', help='skip scanning; rebuild the summary views from your edits')
    ap.add_argument('-v', '--verbose', action='store_true', help='list kept and rejected jobs')
    ap.add_argument('--import-only', action='store_true',
                    help='skip company feeds; only import jobs an agent saved to data/inbox/')
    a = ap.parse_args()

    if a.refresh:
        rows = tracker.load()
        tracker.save(rows)
        print(f'rebuilt {os.path.relpath(tracker.xlsx_path())} ({len(rows)} jobs)')
        return

    rules = Rules(load_json('criteria.json'))
    srcs = candidate.load_json('sources.json', default={'sources': [{'id': 'company-boards', 'type': 'feeds', 'enabled': True}]})
    feeds_on = any(x['type'] == 'feeds' and x.get('enabled', True) for x in srcs['sources'])
    companies = load_json('companies.json')['companies'] if feeds_on and not a.import_only else []
    if a.companies and companies:
        unknown = set(a.companies) - {c['id'] for c in companies}
        if unknown:
            raise SystemExit(f'unknown company id(s): {", ".join(sorted(unknown))}')
        companies = [c for c in companies if c['id'] in a.companies]
    else:
        companies = [c for c in companies if c.get('enabled', True)]

    today = date.today().isoformat()
    found, scanned = {}, set()
    print(f'{"company":<26}{"listed":>7}{"title+loc":>10}{"location":>9}{"eligible":>9}')
    for co in companies:
        if co['platform'] not in sources.FETCHERS:
            print(f'{co["name"]:<26}  skipped: {co.get("status", "no fetcher")} ({co["careers_url"]})')
            continue
        try:
            jobs, rejects, s = scan_company(co, rules)
        except Exception as e:  # one broken board must not sink the whole scan
            print(f'{co["name"]:<26}  FAILED: {type(e).__name__}: {e}')
            continue
        scanned.add(co['name'])
        print(f'{co["name"]:<26}{s["listed"]:>7}{s["title"]:>10}{s["location"]:>9}{s["eligible"]:>9}')
        if a.verbose:
            for j in jobs:
                print(f'    + {j["title"]}  [{j["exp"]}]  {"; ".join(j["locations"])[:40]}')
            for t, why in rejects:
                if not why.startswith(('title not', 'title excludes')):
                    print(f'    - {t}  ({why})')
        for j in jobs:
            key = f'{co["id"]}:{j["job_id"]}'
            found[key] = {
                'Key': key, 'Company': co['name'], 'Role': j['title'],
                'Location': location_label(j['locations'], rules), 'Exp Asked': j['exp'],
                'Posted': j.get('posted', ''), 'URL': j.get('url', ''),
            }
            if not a.dry_run:
                cache_job(co, j)

    existing = tracker.load()
    if not a.companies:
        for src, (kept, total) in import_inbox(rules, found, existing, a.dry_run, a.verbose).items():
            print(f'{"inbox: " + src:<26}{total:>7}{"":>10}{"":>9}{kept:>9}')
    if a.dry_run:
        print(f'\n{len(found)} eligible jobs (dry run, nothing written)')
        return
    rows, new, closed = tracker.merge(existing, found, scanned, today)
    scored = match.score_rows(rows)
    tracker.save(rows)
    print(f'\n{len(found)} eligible, {len(new)} new, {len(closed)} closed, {scored} scored -> {os.path.relpath(tracker.xlsx_path())}')


if __name__ == '__main__':
    main()
