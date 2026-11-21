# Task: tailor a resume for one job

**Goal:** a one-page resume that fits this job as closely as the bank's true facts allow.

## Inputs
- the job: `data/jobs/<company>/<job id>.json` (title, description)
- `bank.json`, `profile.json`, `vocab.json`
- where it goes: `.venv/bin/python -c "import sys; sys.path.insert(0,'engine'); import tailor; print(tailor.resume_for('<company>:<job id>'))"`
  prints the resume path (per job, or one company-wide resume when the company's
  `resume_policy` is `profile` and several applications are open there)

## Steps
1. Read the description. List what it centres on: must-have skills, responsibilities, domain,
   level, and the words it uses for them.
2. Create `resumes/<company>-<job id>/plan.json` (schema `schemas/plan.schema.json`; examples in
   `profiles/example/resumes/` and any earlier plans):
   - `summary`: 2–3 lines in the job's language, only facts the bank supports. Years of experience
     go in `summary_years` (e.g. "2+") so the number check allows them.
   - `skills`: `[[category, [skills...]], ...]`, most relevant first, only skills in the bank.
   - `experience`: roles (bank ids), each with `bullets` and/or `projects` (bank bullet ids), most
     relevant first. A bullet can be `{"id": ..., "text": "shorter wording"}`: same facts,
     no new numbers.
   - `education`, `personal_projects`, other sections only if they help this job.
   - `sections`: order of sections if not the default (summary, skills, experience, education, projects).
   - `template`: only to override the profile's default.
   - `rationale`: two or three sentences: what the job wants and how this selection answers it.
3. `.venv/bin/python engine/tailor.py resumes/<folder>/plan.json --profile <name>`
   - "plan rejected" → fix the plan (never by editing the bank to fit).
   - more than one page → drop the least relevant bullet or tighten wording, re-run.
4. `.venv/bin/python engine/ats_check.py resumes/<folder> --profile <name>`
   - fix every parsing `FIX`;
   - for `missing` keywords: if the bank backs it, use the job's word for it; if not, ask the
     candidate whether it's true before adding anything to the bank. Never stuff keywords.
5. Show the candidate the PDF/DOCX and the rationale; apply their edits; set the job's tracker
   Status to `Tailored` and Resume to the path from `resume_for`.
