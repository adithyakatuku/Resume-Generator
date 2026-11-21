# Task: record replies and keep the tracker honest

When the candidate reports news about an application, update `applications.xlsx` through the
engine (so dates and the Summary stay right), not by hand-editing other columns.

```python
import sys; sys.path.insert(0, 'engine'); import tracker
rows = tracker.load()
rows['<company>:<job id>']['Status'] = 'Rejected'   # Responded | Interview | Offer | Rejected | Skipped
rows['<company>:<job id>']['Notes'] = 'Rejected 2026-11-21 (no reason given).'
tracker.save(rows)   # stamps Last Update, rebuilds Summary and Applied by Date
```
(run with `RESUME_PROFILE=<name>` set, or from a script that passes `--profile`)

Status meanings: `Responded` = any positive contact (recruiter call, test, email);
`Interview`; `Offer`; `Rejected` = any rejection; `Skipped` = decided not to apply (kept so the
scanner doesn't suggest it again). `Closed` rows are removed automatically.

After a rejection, `pick.py` frees that company's slot and proposes its next-best job. Look for
patterns across rejections (same level, same requirement, same speed) and tell the candidate:
fast rejections usually mean a hard screen (years, degree, location), not resume wording. Adjust
`criteria.json` (or a `company_overrides` entry) so the scanner stops proposing such roles.
