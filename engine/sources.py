"""Job-board fetchers. Each platform yields normalised job dicts.

A fetcher has two steps so we only pull full descriptions for jobs that
survive the cheap title/location filter:
    list_jobs(company, criteria) -> iterable of stubs
    details(company, stub)       -> full job (adds 'description', 'url', ...)

Normalised job fields:
    job_id, title, locations (list[str]), url, posted (YYYY-MM-DD or ''),
    description (plain text), exp_text (text to read experience from)
"""
import html
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36'
PAUSE = 0.25  # seconds between requests; be polite to the boards


def http_json(url, body=None, retries=3):
    data = json.dumps(body).encode() if body is not None else None
    headers = {'User-Agent': UA, 'Accept': 'application/json'}
    if data is not None:
        headers['Content-Type'] = 'application/json'
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                time.sleep(PAUSE)
                return json.load(r)
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))


def html_to_text(s):
    if not s:
        return ''
    s = re.sub(r'(?i)<br\s*/?>|</(p|li|div|h\d|tr)>', '\n', s)
    s = re.sub(r'(?i)<li[^>]*>', '- ', s)
    s = re.sub(r'<[^>]+>', '', s)
    s = html.unescape(s).replace('\xa0', ' ')
    s = re.sub(r'[ \t]+', ' ', s)
    return re.sub(r'\n\s*\n+', '\n', s).strip()


# ---------------------------------------------------------------- Amazon
class Amazon:
    BASE = 'https://www.amazon.jobs'

    def list_jobs(self, company, criteria):
        b = company['board']
        offset, total = 0, None
        while total is None or offset < total:
            params = {'loc_query': b['loc_query'], 'country': b['country'],
                      'result_limit': 100, 'offset': offset, 'sort': 'recent'}
            if b.get('category'):  # amazon.jobs job category, e.g. software-development
                params['category[]'] = b['category']
            q = urllib.parse.urlencode(params)
            d = http_json(f'{self.BASE}/en/search.json?{q}')
            total = min(d['hits'], 2000)
            if not d['jobs']:
                break
            for j in d['jobs']:
                locs = [j.get('normalized_location') or j.get('location') or '']
                # multi-location postings list the others in 'locations'
                for extra in j.get('locations') or []:
                    try:
                        e = json.loads(extra) if isinstance(extra, str) else extra
                        locs.append(e.get('normalizedLocation') or e.get('location') or '')
                    except Exception:
                        pass
                try:
                    posted = datetime.strptime(j['posted_date'], '%B %d, %Y').strftime('%Y-%m-%d')
                except Exception:
                    posted = ''
                basic = html_to_text(j.get('basic_qualifications'))
                yield {
                    'job_id': str(j['id_icims']),
                    'title': j['title'].strip(),
                    'locations': [l for l in dict.fromkeys(locs) if l],
                    'url': self.BASE + j['job_path'],
                    'posted': posted,
                    'description': '\n\n'.join(filter(None, [
                        html_to_text(j.get('description')),
                        'BASIC QUALIFICATIONS\n' + basic,
                        'PREFERRED QUALIFICATIONS\n' + html_to_text(j.get('preferred_qualifications')),
                    ])),
                    # Amazon separates must-haves from nice-to-haves; read experience only from must-haves
                    'exp_text': basic,
                    '_complete': True,
                }
            offset += len(d['jobs'])

    def details(self, company, stub):
        return stub


# ---------------------------------------------------------------- Workday
class Workday:
    def _base(self, b):
        return f"https://{b['tenant']}.{b['host']}.myworkdayjobs.com/wday/cxs/{b['tenant']}/{b['site']}"

    def list_jobs(self, company, criteria):
        b = company['board']
        # city searches plus role searches: multi-city postings ("3 Locations") can miss the city term
        terms = list(criteria['locations']['include']) + list(criteria.get('search_terms', []))
        if criteria['locations'].get('accept_remote_india'):
            terms.append('Remote India')
        terms += b.get('extra_search_terms', [])
        seen = set()
        for term in terms:
            offset, total = 0, None
            while total is None or offset < total:
                d = http_json(self._base(b) + '/jobs', {'appliedFacets': {}, 'limit': 20, 'offset': offset, 'searchText': term})
                if total is None:  # Workday only reports the total on the first page
                    total = min(d.get('total') or 0, 1000)
                posts = d.get('jobPostings') or []
                if not posts:
                    break
                for p in posts:
                    path = p.get('externalPath')
                    if not path or path in seen:
                        continue
                    seen.add(path)
                    yield {
                        'job_id': (p.get('bulletFields') or [path.rsplit('_', 1)[-1]])[0],
                        'title': p['title'].strip(),
                        # "2 Locations" is unknown until details are fetched
                        'locations': [p.get('locationsText') or ''],
                        '_path': path,
                    }
                offset += len(posts)

    def details(self, company, stub):
        d = http_json(self._base(company['board']) + stub['_path'])['jobPostingInfo']
        desc = html_to_text(d.get('jobDescription'))
        locs = [d.get('location') or ''] + list(d.get('additionalLocations') or [])
        if (d.get('remoteType') or '').lower().startswith('remote'):
            locs.append(f"Remote, {d.get('country', {}).get('descriptor', '')}")
        return dict(stub, job_id=d.get('jobReqId') or stub['job_id'], title=d['title'].strip(),
                    locations=[l for l in locs if l], url=d.get('externalUrl', ''),
                    posted=d.get('startDate', '') or '', description=desc, exp_text=desc)


# ---------------------------------------------------------------- SmartRecruiters
class SmartRecruiters:
    BASE = 'https://api.smartrecruiters.com/v1/companies'

    def list_jobs(self, company, criteria):
        c = company['board']['company']
        offset, total = 0, None
        while total is None or offset < total:
            d = http_json(f'{self.BASE}/{c}/postings?country=in&limit=100&offset={offset}')
            total = d['totalFound']
            if not d['content']:
                break
            for p in d['content']:
                loc = p.get('location') or {}
                parts = [loc.get('fullLocation') or loc.get('city') or '']
                if loc.get('remote'):
                    parts.append('Remote, India')
                yield {
                    'job_id': str(p['id']), 'title': p['name'].strip(), 'locations': parts,
                    'posted': (p.get('releasedDate') or '')[:10],
                }
            offset += len(d['content'])

    def details(self, company, stub):
        d = http_json(f"{self.BASE}/{company['board']['company']}/postings/{stub['job_id']}")
        sec = d.get('jobAd', {}).get('sections', {})
        parts = [sec.get(k, {}).get('text', '') for k in ('jobDescription', 'qualifications', 'additionalInformation')]
        desc = '\n\n'.join(html_to_text(p) for p in parts if p)
        return dict(stub, url=d.get('postingUrl', ''), description=desc,
                    exp_text=html_to_text(sec.get('qualifications', {}).get('text', '')) or desc)


# ---------------------------------------------------------------- Greenhouse
class Greenhouse:
    BASE = 'https://boards-api.greenhouse.io/v1/boards'

    def list_jobs(self, company, criteria):
        t = company['board']['token']
        for j in http_json(f'{self.BASE}/{t}/jobs').get('jobs', []):
            locs = [j.get('location', {}).get('name') or '']
            locs += [o.get('name', '') for o in j.get('offices') or []]
            yield {
                'job_id': str(j['id']), 'title': j['title'].strip(),
                'locations': [l for l in dict.fromkeys(locs) if l],
                'url': j.get('absolute_url', ''),
                'posted': (j.get('first_published') or j.get('updated_at') or '')[:10],
            }

    def details(self, company, stub):
        d = http_json(f"{self.BASE}/{company['board']['token']}/jobs/{stub['job_id']}")
        desc = html_to_text(html.unescape(d.get('content') or ''))
        return dict(stub, description=desc, exp_text=desc)


# ---------------------------------------------------------------- Lever
class Lever:
    def list_jobs(self, company, criteria):
        t = company['board']['token']
        for j in http_json(f'https://api.lever.co/v0/postings/{t}?mode=json') or []:
            cat = j.get('categories') or {}
            locs = list(cat.get('allLocations') or []) or [cat.get('location') or '']
            if (j.get('workplaceType') or '').lower() == 'remote':
                locs = [f'Remote, {l}' for l in locs]
            parts = [j.get('descriptionPlain') or '']
            for lst in j.get('lists') or []:
                parts.append(lst.get('text', '') + '\n' + html_to_text(lst.get('content', '')))
            parts.append(j.get('additionalPlain') or '')
            desc = '\n\n'.join(p for p in parts if p)
            created = j.get('createdAt')
            yield {
                'job_id': j['id'], 'title': j['text'].strip(), 'locations': [l for l in locs if l],
                'url': j.get('hostedUrl', ''),
                'posted': datetime.utcfromtimestamp(created / 1000).strftime('%Y-%m-%d') if created else '',
                'description': desc, 'exp_text': desc, '_complete': True,
            }

    def details(self, company, stub):
        return stub


# ---------------------------------------------------------------- Ashby
class Ashby:
    def list_jobs(self, company, criteria):
        t = company['board']['token']
        for j in http_json(f'https://api.ashbyhq.com/posting-api/job-board/{t}').get('jobs', []):
            locs = [j.get('location') or ''] + [x.get('location', '') for x in j.get('secondaryLocations') or []]
            if j.get('isRemote') or (j.get('workplaceType') or '').lower() == 'remote':
                locs = [f'Remote, {l}' for l in locs if l] or ['Remote']
            desc = j.get('descriptionPlain') or html_to_text(j.get('descriptionHtml') or '')
            yield {
                'job_id': j['id'], 'title': j['title'].strip(), 'locations': [l for l in dict.fromkeys(locs) if l],
                'url': j.get('jobUrl', ''), 'posted': (j.get('publishedAt') or '')[:10],
                'description': desc, 'exp_text': desc, '_complete': True,
            }

    def details(self, company, stub):
        return stub


# ---------------------------------------------------------------- Oracle Recruiting Cloud
class OracleCloud:
    """Oracle Recruiting Cloud (Oracle itself, many hospitals and banks). board: host (e.g.
    eeho.fa.us2.oraclecloud.com), site (siteNumber, e.g. CX_45001), optional location_id (a
    country or city id from the site's location facet), optional job_url ({id} placeholder)."""
    PAGE = 25

    def _api(self, b, resource, finder, expand):
        return (f"https://{b['host']}/hcmRestApi/resources/latest/{resource}?onlyData=true"
                f"&expand={expand}&finder={finder}")

    def list_jobs(self, company, criteria):
        b = company['board']
        terms = list(criteria.get('search_terms') or []) + b.get('extra_search_terms', []) or ['']
        seen = set()
        for term in terms:
            offset, total = 0, None
            while total is None or offset < total:
                parts = [f"siteNumber={b['site']}", f'limit={self.PAGE}', f'offset={offset}', 'sortBy=POSTING_DATES_DESC']
                if term:
                    parts.append('keyword=' + urllib.parse.quote(f'"{term}"'))
                if b.get('location_id'):
                    parts.append(f"locationId={b['location_id']}")
                d = http_json(self._api(b, 'recruitingCEJobRequisitions', 'findReqs;' + ','.join(parts),
                                        'requisitionList.secondaryLocations'))
                item = (d.get('items') or [{}])[0]
                if total is None:
                    total = min(item.get('TotalJobsCount') or 0, 500)
                reqs = item.get('requisitionList') or []
                if not reqs:
                    break
                for r in reqs:
                    if r['Id'] in seen:
                        continue
                    seen.add(r['Id'])
                    locs = [r.get('PrimaryLocation') or ''] + [s.get('Name', '') for s in r.get('secondaryLocations') or []]
                    yield {'job_id': str(r['Id']), 'title': r['Title'].strip(), 'locations': [l for l in locs if l],
                           'posted': (r.get('PostedDate') or '')[:10]}
                offset += len(reqs)

    def details(self, company, stub):
        b = company['board']
        d = http_json(self._api(b, 'recruitingCEJobRequisitionDetails',
                                f'ById;Id="{stub["job_id"]}",siteNumber={b["site"]}', 'all'))
        r = (d.get('items') or [{}])[0]
        desc = '\n'.join(html_to_text(r.get(k)) for k in
                         ('ExternalDescriptionStr', 'ExternalResponsibilitiesStr', 'ExternalQualificationsStr') if r.get(k))
        locs = [r.get('PrimaryLocation') or ''] + [s.get('Name', '') for s in r.get('secondaryLocations') or []]
        url = (b.get('job_url') or f"https://{b['host']}/hcmUI/CandidateExperience/en/sites/{b['site']}/job/{{id}}").format(id=stub['job_id'])
        return dict(stub, locations=[l for l in locs if l] or stub['locations'], url=url,
                    posted=(r.get('ExternalPostedStartDate') or stub.get('posted') or '')[:10],
                    description=desc, exp_text=desc)


# ---------------------------------------------------------------- Phenom
class Phenom:
    """Phenom People career sites (careers.<company>.com) through their /widgets endpoint.
    board: base (https://careers.cisco.com), lang (en_global), optional country (list, e.g.
    ["India"]) to narrow the search."""
    PAGE = 50

    def _post(self, b, body):
        return http_json(b['base'].rstrip('/') + '/widgets',
                         dict({'lang': b.get('lang', 'en_global'), 'deviceType': 'desktop', 'country': 'global',
                               'siteType': 'external'}, **body))

    def list_jobs(self, company, criteria):
        b = company['board']
        terms = list(criteria.get('search_terms') or []) + b.get('extra_search_terms', []) or ['']
        seen = set()
        for term in terms:
            offset, total = 0, None
            while total is None or offset < total:
                body = {'pageName': 'search-results', 'ddoKey': 'refineSearch', 'sortBy': 'Most recent',
                        'from': offset, 'size': self.PAGE, 'jobs': True, 'counts': False, 'keywords': term,
                        'global': True, 'all_fields': ['country', 'state', 'city'], 'clearAll': False,
                        'jdsource': 'facets', 'selected_fields': {'country': b['country']} if b.get('country') else {}}
                d = (self._post(b, body).get('refineSearch') or {})
                if total is None:
                    total = min(d.get('totalHits') or d.get('hits') or 0, 500)
                jobs = (d.get('data') or {}).get('jobs') or []
                if not jobs:
                    break
                for j in jobs:
                    jid = str(j.get('jobSeqNo') or j.get('jobId'))
                    if jid in seen:
                        continue
                    seen.add(jid)
                    locs = j.get('multi_location') or [j.get('location') or ', '.join(x for x in (j.get('city'), j.get('state'), j.get('country')) if x)]
                    yield {'job_id': str(j.get('reqId') or j.get('jobId') or jid), 'title': (j.get('title') or '').strip(),
                           'locations': [l for l in locs if l], 'posted': (j.get('postedDate') or '')[:10],
                           'url': j.get('applyUrl') or '', '_seq': jid}
                offset += len(jobs)

    def details(self, company, stub):
        b = company['board']
        d = self._post(b, {'pageName': 'job', 'ddoKey': 'jobDetail', 'jobId': stub['_seq']})
        j = ((d.get('jobDetail') or {}).get('data') or {}).get('job') or {}
        desc = html_to_text(j.get('description') or j.get('descriptionTeaser') or '')
        url = f"{b['base'].rstrip('/')}/global/en/job/{stub['_seq']}"
        # the detail's multi_location holds dicts ({locationName, cityState, country...}); the search's holds strings
        locs = [l if isinstance(l, str) else (l.get('locationName') or ', '.join(x for x in (l.get('cityState'), l.get('country')) if x))
                for l in j.get('multi_location') or []]
        return dict(stub, url=url, posted=(j.get('postedDate') or stub.get('posted') or '')[:10],
                    locations=[l for l in locs if l] or stub['locations'], description=desc, exp_text=desc)


FETCHERS = {'amazon': Amazon(), 'workday': Workday(), 'smartrecruiters': SmartRecruiters(),
            'greenhouse': Greenhouse(), 'lever': Lever(), 'ashby': Ashby(),
            'oracle': OracleCloud(), 'phenom': Phenom()}
