# Task: verify the bank with the candidate

**Goal:** get every fact the candidate will use confirmed, in one pass, without wearing them out.

## Steps
1. Run `.venv/bin/python engine/check.py bank --profile <name>`; the WARN lines list unverified
   facts, pending plain-language wording, and open `check` questions.
2. Group questions by theme and ask them together, numbered, short, answerable in a word:
   - conflicting facts (dates, titles, names)
   - numbers ("2000+ advertisers: correct?")
   - scope ("built" vs "contributed to"; designed only, or also shipped?)
   - plain-language rewrites: show internal vs public wording side by side
   - skills listed but not backed by any bullet: keep in the skills line, or drop?
3. Apply answers: set `verified: true` / `public_verified: true`, edit text, record the outcome
   in `check` (e.g. "Resolved: confirmed by candidate, 2026-11"), or remove the fact.
4. Run `check.py bank` again: 0 errors; remaining unverified facts are ones they chose to leave.
