# Task: record replies and keep the tracker honest

When the candidate reports news about an application, update `applications.xlsx` through the
engine (so dates and the Summary stay right), not by hand-editing other columns.

```sh
.venv/bin/python engine/track.py set <company>:<job id> Rejected --note "Rejected 2026-11-21, no reason given" --profile <name>
.venv/bin/python engine/track.py list --status Applied,Responded,Interview --profile <name>
.venv/bin/python engine/track.py show <company>:<job id> --profile <name>    # row + job description
```
`set` stamps Last Update (and Applied On), appends the note, and rebuilds the Summary and Applied
by Date sheets. Through MCP: the `tracker_set`, `tracker_list` and `tracker_show` tools.

Status meanings: `Responded` = any positive contact (recruiter call, test, email);
`Interview`; `Offer`; `Rejected` = any rejection; `Skipped` = decided not to apply (kept so the
scanner doesn't suggest it again). `Closed` rows are removed automatically.

After a rejection, `pick.py` frees that company's slot and proposes its next-best job. Look for
patterns across rejections (same level, same requirement, same speed) and tell the candidate:
fast rejections usually mean a hard screen (years, degree, location), not resume wording. Adjust
`criteria.json` (or a `company_overrides` entry) so the scanner stops proposing such roles.
