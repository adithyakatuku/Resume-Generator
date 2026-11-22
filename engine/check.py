"""Validate a profile's files, so agent output is checked the same way whichever agent wrote it.

    .venv/bin/python engine/check.py bank            # bank.json: schema + fact rules
    .venv/bin/python engine/check.py setup           # profile, criteria, companies, vocab, sources, workrecord
    .venv/bin/python engine/check.py plan PATH       # a resume plan: schema + every tailor.py fact check
    .venv/bin/python engine/check.py all             # bank + setup + every plan under resumes/
    (add --profile NAME when there is more than one profile)

Exit status is non-zero when anything is an ERROR; WARN lines are things a human
should look at (unverified facts, unanswered checks) but do not block.
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import candidate  # noqa: E402

ERRORS, WARNS = [], []


def err(msg):
    ERRORS.append(msg)


def warn(msg):
    WARNS.append(msg)


def schema_check(name, data, label):
    import jsonschema
    with open(os.path.join(candidate.SCHEMAS, f'{name}.schema.json'), encoding='utf-8') as f:
        schema = json.load(f)
    for e in sorted(jsonschema.Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.path)):
        where = '/'.join(str(p) for p in e.path) or '(top)'
        err(f'{label}: {where}: {e.message[:160]}')


def facts(bank):
    """Yield (where, fact) for every bullet/item in the bank."""
    for e in bank.get('experience', []):
        for b in e.get('bullets', []):
            yield f'experience {e["id"]}', b
        for p in e.get('projects', []):
            for b in p.get('bullets', []):
                yield f'project {p["id"]}', b
    for p in bank.get('personal_projects', []):
        for b in p.get('bullets', []):
            yield f'personal project {p["id"]}', b
    for sec in ('certifications', 'licenses', 'publications', 'awards', 'languages', 'portfolio', 'activities'):
        for b in bank.get(sec, []):
            yield sec, b


def check_not_example():
    if candidate.in_example_profile():
        return
    names = ['bank.json', 'criteria.json', 'companies.json', 'vocab.json', 'profile.json', 'sources.json',
             'workrecord.json', os.path.join('private', 'applicant.json')]
    for n in names:
        if os.path.exists(candidate.path(n)):
            with open(candidate.path(n), encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except ValueError:
                    continue
            if candidate.is_example_data(data):
                err(f'{n}: still the fictional example; replace it with this candidate\'s own '
                    '(tasks/setup-profile.md, tasks/build-bank.md)')
    notes = candidate.path('notes.txt')
    if os.path.exists(notes) and open(notes, encoding='utf-8').read().startswith('FICTIONAL EXAMPLE'):
        err('notes.txt: still the fictional example; write your own notes')


def check_bank():
    bank = candidate.load_json('bank.json')
    schema_check('bank', bank, 'bank.json')
    skills = {s for group in bank.get('skills', {}).values() for s in group}
    seen = {}
    ids = [e.get('id') for e in bank.get('experience', [])] + [e.get('id') for e in bank.get('education', [])]
    unverified = 0
    for where, b in facts(bank):
        bid = b.get('id')
        if bid in seen:
            err(f'bank.json: duplicate id "{bid}" ({where} and {seen[bid]})')
        seen[bid] = where
        if not b.get('verified'):
            unverified += 1
            warn(f'bank.json: "{bid}" not verified yet' + (f' — {b["check"]}' if b.get('check') else ''))
        if b.get('public') and not b.get('public_verified'):
            warn(f'bank.json: "{bid}" plain-language wording awaits approval')
        if b.get('public'):
            extra = set(re.findall(r'\d+(?:[.,]\d+)?', b['public'])) - set(re.findall(r'\d+(?:[.,]\d+)?', b['text']))
            if extra:
                err(f'bank.json: "{bid}" public wording adds numbers not in its text: {sorted(extra)}')
        for s in b.get('skills', []):
            if s not in skills:
                warn(f'bank.json: "{bid}" tags skill "{s}" that is not in the skills lists (fine for concept tags)')
    for e in bank.get('education', []):
        if not e.get('verified'):
            warn(f'bank.json: education "{e.get("id")}" not verified yet')
    if len(ids) != len(set(ids)):
        err('bank.json: experience/education ids must be unique')
    if not bank.get('career_start'):
        warn('bank.json: no career_start (YYYY-MM); experience-based ranking will be skipped')
    print(f'bank.json: {len(seen)} facts, {unverified} unverified, {len(skills)} skills')


def check_setup():
    import sources
    s = candidate.load_json('profile.json', default={})
    schema_check('profile', s, 'profile.json')
    crit = candidate.load_json('criteria.json')
    schema_check('criteria', crit, 'criteria.json')
    for key in ('title_include', 'title_exclude', 'description_exclude'):
        for w in crit.get(key, []):
            try:
                re.compile(re.escape(w))
            except re.error as e:
                err(f'criteria.json: {key} "{w}": {e}')
    cos = candidate.load_json('companies.json')
    schema_check('companies', cos, 'companies.json')
    needs = {'amazon': ['loc_query', 'country'], 'workday': ['tenant', 'host', 'site'], 'smartrecruiters': ['company'],
             'greenhouse': ['token'], 'lever': ['token'], 'ashby': ['token'],
             'oracle': ['host', 'site'], 'phenom': ['base']}
    ids = set()
    for c in cos.get('companies', []):
        if c['id'] in ids:
            err(f'companies.json: duplicate id "{c["id"]}"')
        ids.add(c['id'])
        if c['platform'] in sources.FETCHERS:
            missing = [k for k in needs.get(c['platform'], []) if k not in (c.get('board') or {})]
            if missing:
                err(f'companies.json: {c["id"]} ({c["platform"]}) board is missing {missing}')
        elif c.get('enabled', True):
            warn(f'companies.json: {c["id"]} uses {c["platform"]}, which has no feed reader; it will be skipped (needs-browser)')
    vocab = candidate.load_json('vocab.json')
    schema_check('vocab', vocab, 'vocab.json')
    for k, rx in {**vocab.get('terms', {}), **vocab.get('phrases', {})}.items():
        try:
            re.compile(rx)
        except re.error as e:
            err(f'vocab.json: "{k}" pattern does not compile: {e}')
    for k in vocab.get('have', {}):
        if k not in vocab.get('terms', {}):
            err(f'vocab.json: have["{k}"] has no matching term')
    if os.path.exists(candidate.path('sources.json')):
        srcs = candidate.load_json('sources.json')
        schema_check('sources', srcs, 'sources.json')
        for x in srcs.get('sources', []):
            if x.get('type') == 'browser' and x.get('enabled') and not x.get('search_url'):
                warn(f'sources.json: browser source "{x["id"]}" has no search_url; the agent will navigate it by hand')
    if os.path.exists(candidate.path('workrecord.json')):
        schema_check('workrecord', candidate.load_json('workrecord.json'), 'workrecord.json')
    print(f'setup: {len(ids)} companies, {len(vocab.get("terms", {}))} vocab terms, '
          f'{len(crit.get("title_include", []))} title keywords')


def check_plan(path):
    import tailor
    with open(path, encoding='utf-8') as f:
        plan = json.load(f)
    label = os.path.relpath(path, candidate.profile_dir())
    schema_check('plan', plan, label)
    try:
        tailor.build_document(plan)
    except tailor.PlanError as e:
        for line in str(e).splitlines()[1:]:
            err(f'{label}: {line.strip()}')


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ('bank', 'setup', 'plan', 'all'):
        raise SystemExit(__doc__)
    what = args[0]
    check_not_example()
    if what in ('bank', 'all'):
        check_bank()
    if what in ('setup', 'all'):
        check_setup()
    if what == 'plan':
        if len(args) < 2:
            raise SystemExit('plan needs a path')
        p = args[1] if os.path.exists(args[1]) else candidate.path(args[1])
        check_plan(p)
    if what == 'all':
        plans = sorted(glob.glob(candidate.path('resumes', '*', 'plan.json')))
        for p in plans:
            check_plan(p)
        print(f'plans: {len(plans)} checked')
    for w in WARNS:
        print('WARN ', w)
    for e in ERRORS:
        print('ERROR', e)
    print(f'\n{len(ERRORS)} error(s), {len(WARNS)} warning(s)')
    sys.exit(1 if ERRORS else 0)


if __name__ == '__main__':
    main()
