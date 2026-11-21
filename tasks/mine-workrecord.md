# Task: mine the work record into bank bullets

**Goal:** find work the candidate did but didn't write down, from the evidence they point to in
`workrecord.json` (git repos, documents, links), and propose it as unverified bank bullets.

## Inputs
- `profiles/<name>/workrecord.json` (schema `schemas/workrecord.schema.json`):
  - `repos`: local paths + the git author names/emails that are them + dates + employer/project
  - `documents`: design docs, reports, theses, portfolio PDFs (paths)
  - `links`: portfolio sites, publications, public repos

## Steps
1. Run `.venv/bin/python engine/workrecord_digest.py --profile <name>`. Read
   `data/workrecord_digest.txt`: commit counts, areas touched, file types, commit subjects.
   (No source code is included, and you should not paste source code into the bank.)
2. If needed, inspect a repo further **read-only** (`git log -p` on one commit, a README, a design
   doc) to understand what a feature was. Don't run the project, don't change it.
3. Read each listed document/link the same way (for non-software fields this is the main source:
   project reports, drawings lists, site records, case studies).
4. Group the evidence into achievements: a feature, a module, a migration, a design, a test
   campaign, a site handled. One bullet per achievement, with what they did and its scope.
   Use counts the evidence directly supports ("built 6 modules": count them); never invent
   impact metrics ("improved performance by 30%") the evidence doesn't state.
5. Add bullets to the right experience/project in `bank.json` with `"verified": false`,
   `"sources": ["workrecord"]` and a `"check"` asking the candidate to confirm wording and any
   number, plus whether it is OK to mention (confidential client work).
6. Run `engine/check.py bank`, then continue with `tasks/verify-bank.md`.

## Notes
- Commits under another name (pairing, shared accounts) are only theirs if they listed that name.
- Work for a client may be confidential: describe the problem domain, not secrets.
