# Operating manual for AI agents

This repo turns a candidate's rough notes and work history into a verified fact bank,
tailored resumes, a scanned list of matching jobs, and an Excel tracker of applications.
It works for any profession. Any capable coding agent (Claude Code, Codex, Cursor,
Gemini CLI, Copilot, ChatGPT with file access...) can run it; browser steps need the agent to
control a browser (see `docs/SETUP.md`): the deterministic work is
done by scripts in `engine/`; the judgement work is described step by step in `tasks/`,
and every agent output is checked by `engine/check.py`.

## Ground rules (always)

1. **Never invent facts.** Every bullet, number, skill, date and title on a resume must come
   from the candidate (`notes.txt`, `workrecord.json` evidence, or their answers). When you
   draft anything from evidence, mark it `"verified": false` and add a `"check"` question.
   Only the candidate sets `verified: true` (or tells you to).
2. **Rewording keeps the facts.** Plans may shorten or rephrase a bank bullet, never add a
   number, tool or claim it does not contain. `engine/check.py plan` enforces the numbers.
3. **Ask, don't guess, on judgement calls**: self-assessment answers on application forms
   (years of experience, degree questions), salary, notice period, relocation, anything that
   is the candidate's own statement.
4. **Outward actions are the candidate's.** You may open pages and fill forms; you never
   click Submit/Apply/Send, never type passwords or one-time codes, never create accounts,
   never pay. Stop at the review page and hand over.
5. **Privacy.** Personal data lives only in `profiles/<name>/` (git-ignored). Never copy it
   into engine files, issues, logs or third-party services. `private/` holds salary and
   addresses: read it to fill forms, never print it in shared outputs.
6. **Never use the example's data for a real person.** A new profile is a copy of the fictional
   `profiles/example` (Meera Rao); replace every file. `check.py` errors on leftovers, and
   `tailor.py` / `apply.py` refuse them.
7. **Check your work.** After editing a profile file run `engine/check.py` and fix every
   ERROR before telling the candidate you are done.

## Running commands

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # once
.venv/bin/python engine/doctor.py                                     # what's installed / missing, with fixes
.venv/bin/python engine/<script>.py ... --profile <name>              # --profile optional if only one profile
```
(Windows: `.venv\Scripts\python`.)

**Prerequisites are your job to check, not the person's to know.** Run `engine/doctor.py` when you
start setting someone up, after they install anything, and whenever a command fails with an
install-type error. Walk them through each `NEEDED` item in plain words (`docs/SETUP.md` has the
details per OS) and run the doctor again until it reports everything required. Lines marked
`AGENT` are about you: the doctor cannot see your tools.

**Browser control** (searching job sites, filling forms) lives inside you, not on the system.
Before any browser task, confirm you actually have browser tools in this session. If you don't,
say so and explain how to connect one (Claude Code: the "Claude in Chrome" extension + `/chrome`;
other agents: Playwright MCP or the agent's own browser feature; `docs/SETUP.md` step 6). Never
silently skip an enabled browser source.

| Script | What it does |
|---|---|
| `doctor.py` | Installed prerequisites (Python packages, Git, LaTeX + each format's packages, XeLaTeX) and what the profile's choices need |
| `check.py bank\|setup\|plan PATH\|all` | Validate profile files against `schemas/` and the fact rules |
| `workrecord_digest.py` | Summarise the candidate's git work into `data/workrecord_digest.txt` |
| `scan.py [ids] [--dry-run -v] [--refresh] [--import-only]` | Read company feeds + import browser-found jobs from `data/inbox/`, filter by `criteria.json`, update the tracker |
| `match.py [--force]` | Keyword fit score of each job against the bank (uses `vocab.json`) |
| `pick.py [--mark]` | Next job to apply to per company (one open application per company) |
| `tailor.py resumes/<folder>/plan.json [--template NAME] [--open]` | Render a resume from a plan through a template (`--template` tries a format into `try-<name>/` without editing the plan) |
| `preview_templates.py [names]` / `--mine [--plan P]` | Gallery: example resume through each built-in template into `templates/<name>/preview.*`; `--mine`: the candidate's resume through every format into `<profile>/previews/` |
| `ats_check.py resumes/<folder> [job keys]` | How the resume parses + which job terms it covers |
| `apply.py [key] [--done key]` | List ready jobs / walk through one application / mark applied |

## Tasks

| When | Task file |
|---|---|
| New candidate: set up field, locations, companies, vocabulary | `tasks/setup-profile.md` |
| Turn notes.txt into bank.json | `tasks/build-bank.md` |
| Mine git repos / documents listed in workrecord.json | `tasks/mine-workrecord.md` |
| Walk the candidate through unverified facts | `tasks/verify-bank.md` |
| Search job sites in the browser (Naukri, LinkedIn, any site in sources.json) | `tasks/browse-search.md` |
| Choose which jobs to apply to | `tasks/pick-review.md` |
| Tailor a resume for one job | `tasks/write-plan.md` |
| Fill an application form in a browser | `tasks/fill-application.md` |
| Record replies, rejections, interviews | `tasks/track-replies.md` |
| Choose, tweak or add a resume format | `tasks/add-template.md` |

## Where things are

```
engine/      scripts (no candidate data)        schemas/    JSON Schemas for profile files
templates/   built-in resume formats            tasks/      step-by-step agent instructions
profiles/example/   fictional sample candidate  profiles/<name>/   a real candidate (git-ignored)
```

A profile folder: `profile.json`, `notes.txt`, `workrecord.json`, `bank.json`, `criteria.json`,
`companies.json`, `sources.json`, `vocab.json`, `private/applicant.json`, and outputs `resumes/`, `data/`,
`applications.xlsx`. See `README.md` for what each holds.
