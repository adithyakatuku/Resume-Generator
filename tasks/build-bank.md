# Task: build bank.json from notes.txt

**Goal:** turn the candidate's rough notes into `profiles/<name>/bank.json`, the single source of
truth that every resume draws from. Structure and wording are your job; facts are theirs.

## Inputs
- `notes.txt` (free text; headings are suggestions, not rules)
- `data/workrecord_digest.txt` if `tasks/mine-workrecord.md` was run
- an existing resume they paste in, if any
- `schemas/bank.schema.json`, `profiles/example/bank.json` (worked example)

## Steps
1. **contact**: name exactly as they want it printed, phone, email, location, links
   (LinkedIn, GitHub, portfolio, Behance, personal site) as `links: [{"url": ...}]`.
2. **career_start**: month their professional (non-internship) work began, `YYYY-MM`.
3. **education**: one entry per degree/diploma: `degree`, `school`, `year` (or `when`, e.g.
   "Expected: 2027"), `grade` if they want it shown.
4. **experience**: one entry per role, newest first: `company`, `title`, `location`, `start`, `end`
   (`null` = present). Put achievements in `bullets`; when one role spans distinct projects or
   clients, use `projects: [{id, name, client, description, tech, bullets}]`.
5. **bullets**: one achievement each, past tense, specific: action + what + scale/result.
   Keep every number they gave; never estimate one. Give each a stable kebab-case `id`
   (`<employer-or-project>-<topic>`), `skills` it proves, and `"verified": false` with a
   `"check"` question whenever you inferred, merged, or reworded beyond trivially.
   Internal names (module codes, team jargon) go in `text`; also write a plain-language
   `public` version an outside recruiter understands, with `"public_verified": false`.
6. **personal_projects**, **certifications**, **licenses**, **publications**, **awards**,
   **languages**, **portfolio**, **activities**: include only what they gave; items are
   `{id, text, verified}`.
7. **skills**: `category -> [names]`, grouped the way their field writes resumes (e.g. "CAD/CAE",
   "Standards", "Software"). Include only skills they claim; note tools they listed but no bullet
   supports in a top-level `skills_check` string so they can decide.
8. Run `.venv/bin/python engine/check.py bank --profile <name>`; fix every ERROR.
9. Hand over to `tasks/verify-bank.md`.

## Rules
- Never upgrade claims ("helped with" stays "helped with", not "led").
- Contradictions between sources (dates, titles, numbers): keep both in a `check`, ask.
- Don't drop facts silently; if something doesn't fit, put it in a `check` note.
