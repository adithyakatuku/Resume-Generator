# Task: choose which jobs to apply to

**Goal:** one strong, tailored application per company at a time, to jobs the candidate actually
qualifies for.

## Steps
1. `.venv/bin/python engine/scan.py --profile <name>` (fetches new postings, scores them, updates
   the tracker; companies whose board fails are reported and skipped).
2. `.venv/bin/python engine/pick.py --profile <name>` lists, per company with a free slot, the
   proposed job and backups. Ranking: qualified first (experience asked ≤ theirs), then Match +
   work-life-balance/pay reputation, then newest. `!` marks jobs asking more experience than they have.
3. For each proposal, read the cached description (`data/jobs/<company>/<id>.json`) and judge
   what the keyword score can't:
   - Hard requirements they don't meet (degree, licence, clearance, years at an employer known to
     screen strictly, a specific tool listed as mandatory): skip or flag.
   - The real work behind the title (a "developer" title that is support/sales/devrel; a design
     role that is really drafting).
   - Contract/temporary, location or relocation conditions.
   - Duplicate postings (same text, different ids): apply once, mark the others Skipped.
4. Present a short list: job, why it fits, risks, what to emphasise. Let the candidate choose.
5. Mark chosen ones: `pick.py --mark` for the proposals, or edit Status to `Shortlisted`; set
   rejected proposals to `Skipped` with a note so they aren't proposed again.
6. Continue with `tasks/write-plan.md` for each shortlisted job.
