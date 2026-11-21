# Task: set up a candidate profile

**Goal:** from the candidate's notes, create the field-specific configuration the engine needs:
`profile.json`, `criteria.json`, `vocab.json` and a starter `companies.json`.
The engine ships no profession presets; you build them for this person.

## Inputs
- `profiles/<name>/notes.txt` (copied from `profiles/example/notes.txt`), especially the
  "Target" section: field, target job titles, seniority, locations, remote preference,
  pay / work-life-balance priorities, companies they like or want to avoid.
- `profiles/example/*` as worked examples of every file.

## Steps
1. **profile.json** — name, one-line field description, `default_template`
   (`classic-latex` unless they want Word: `docx-basic`; `compact-latex` for long careers),
   `project_heading_prefix` (`null` unless they work through client projects, e.g. "Client Project").
2. **criteria.json** (schema `schemas/criteria.schema.json`):
   - `experience_years`: the range of *asked* experience worth applying to (usually their years −1 to +1.5).
   - `locations.include`: cities as they appear on job boards; `accept_remote_india` / `remote_regions`
     if they want remote (adapt the field name's country to theirs, e.g. remote_regions `["germany","emea","europe"]`).
   - `title_include`: words that appear in titles they want (lowercase, whole words).
     `title_exclude`: seniority above them, unrelated tracks, contract/intern words.
   - `search_terms`: 1–3 role phrases for boards that need a search (Workday).
   - `max_posting_age_days` (60 is a good default), `max_active_per_company` (1 recommended).
3. **vocab.json** (schema `schemas/vocab.schema.json`) — the words job descriptions in *their*
   field use: tools, methods, standards, certifications (e.g. mechanical: SolidWorks, GD&T, FEA,
   ANSYS, DFMEA; civil: AutoCAD, STAAD.Pro, IS codes, BIM, Primavera; design: Figma, design systems,
   usability testing). 40–80 `terms` as `name -> regex` (lowercase alternatives, `|`-separated,
   escape `+ . #`). `fundamentals`: what everyone in the field is assumed to know. `near`: partial
   credit for close substitutes (0–1). `phrases`: 15–30 requirement phrases recruiters search for
   (ownership, stakeholder communication, documentation, field-specific practices). Leave `have`
   out: the engine matches terms against the bank's skills automatically.
4. **companies.json** (schema `schemas/companies.schema.json`) — 10–20 employers that hire their
   role in their locations. For each, find its job board and **verify the feed before adding it**:
   - Greenhouse: `https://boards-api.greenhouse.io/v1/boards/<token>/jobs` returns jobs → `platform: greenhouse, board: {token}`
   - Lever: `https://api.lever.co/v0/postings/<token>?mode=json` → `lever`
   - Ashby: `https://api.ashbyhq.com/posting-api/job-board/<token>` → `ashby`
   - SmartRecruiters: `https://api.smartrecruiters.com/v1/companies/<Name>/postings` → `smartrecruiters, board: {company}`
   - Workday: find `<tenant>.wd<N>.myworkdayjobs.com/<site>` on the careers page; POST
     `{"appliedFacets":{},"limit":1,"offset":0,"searchText":"<city>"}` to
     `https://<tenant>.wd<N>.myworkdayjobs.com/wday/cxs/<tenant>/<site>/jobs` → `workday, board: {tenant, host, site}`
     (a 303 to a maintenance page means Workday is down; retry later, the address may still be right).
   - Anything else (custom sites, Taleo, iCIMS, Oracle): add it with `platform` set to that name and
     `status: "needs-browser"`; the scanner skips it.
   Set `wlb` and `pay` (good/mixed/unknown, high/good/average/unknown) only from reputation you can
   justify; use `unknown` otherwise. `resume_policy: "unknown"` until a real application shows it.
5. Run `.venv/bin/python engine/check.py setup --profile <name>` and fix every ERROR.
6. Run `.venv/bin/python engine/scan.py --dry-run -v --profile <name>` and look at what is kept
   and rejected. Adjust `title_include/exclude` and locations until the kept titles are right.

## Done when
`check.py setup` reports 0 errors and a dry-run scan keeps plausible titles for this person.
