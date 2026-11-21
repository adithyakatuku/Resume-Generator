# Task: choose, change or add a resume format

Formats (templates) control only the look. Content always comes from `bank.json` through a plan,
so changing format never changes what the resume says. Templates live in `templates/<name>/`
(built-in, shared) or `profiles/<you>/templates/<name>/` (yours only; a folder there with the same
name as a built-in replaces it for you).

## Route 1: pick a built-in format
Look at the gallery in `README.md`, or see **your own resume** in every format:
```sh
.venv/bin/python engine/preview_templates.py --mine          # -> profiles/<you>/previews/<format>.pdf/.png
```
Then set `"default_template": "<name>"` in `profiles/<you>/profile.json` (all resumes), or
`"template": "<name>"` in one plan.

## Route 2: tweak a format (no LaTeX knowledge needed)
1. Copy the format into your profile under a new name:
   `cp -r templates/classic-latex profiles/<you>/templates/my-style`
2. Open `profiles/<you>/templates/my-style/resume.tex.j2`. Make **one change at a time** from the
   recipes below, then look at the result:
   ```sh
   .venv/bin/python engine/tailor.py resumes/<any folder>/plan.json --template my-style --open
   ```
   (writes to `resumes/<folder>/try-my-style/`; your real resumes are untouched)
3. Happy? Set `"default_template": "my-style"` in `profile.json`.

### Recipes (all in the top part of the file, before `\begin{document}`)

| To change | Find | Change to |
|---|---|---|
| Overall text size | `\documentclass[letterpaper,11pt]{article}` | `10pt` (smaller) or `12pt` (bigger). A4 paper: `a4paper` instead of `letterpaper` |
| Side margins | `\addtolength{\oddsidemargin}{-0.6in}` and `\addtolength{\textwidth}{1.19in}` | make the first more negative and the second bigger by the same amount *twice* (e.g. `-0.7in` and `1.39in`) for narrower margins |
| Top/bottom margins | `\addtolength{\topmargin}{-.7in}` and `\addtolength{\textheight}{1.4in}` | same idea: `-.8in` and `1.6in` |
| Font (built-in fonts) | add a line after `\usepackage{latexsym}` | `\usepackage{charter}` (Charter), `\usepackage{lmodern}` (Latin Modern), `\usepackage[default]{sourcesanspro}` (sans-serif; may need installing) |
| Font (any font on your computer) | remove `\input{glyphtounicode}` and `\pdfgentounicode=1`; add `\usepackage{fontspec}` and `\setmainfont{Georgia}` (any installed font name) | and in `manifest.json` add `"latex_engine": "xelatex"` |
| Name size | `{\Huge \scshape \VAR{contact.name|tex}}` | `\LARGE` (smaller) or `\huge`; drop `\scshape` for normal capitals |
| Section heading style | `\titleformat{\section}{ \vspace{-6pt}\scshape\raggedright\large\bfseries }` | remove `\scshape` for normal capitals; `\Large` for bigger headings |
| Heading colour | `\usepackage[usenames,dvipsnames]{color}` | `\usepackage[dvipsnames]{xcolor}` and, on the next line, `\definecolor{accent}{HTML}{1F4E79}`; then in `\titleformat{\section}` add `\color{accent}` right after the first `{`. Any hex colour; keep it dark for reading and printing |
| Line under headings | `[\color{black}\titlerule \vspace{-5pt}]` | delete it for no line; `\color{accent}` to colour it |
| Bullet symbol | in the bottom part, `[label=\textbullet]` | `[label=--]` (dash), `[label=$\circ$]` (circle) |

### Don't touch (or the content stops appearing)
- Anything containing `\VAR{` — that is where your content is inserted.
- Lines starting with `%%` — they repeat blocks for each job, bullet and section.
- The names of the commands defined with `\newcommand` (`\resumeItem`, `\resumeSubheading`,
  ...): the bottom part uses them. You *can* change what they do inside their `{...}`.

If it breaks, the error says which line; undo your last change, or ask your agent
*"my template fails with this error, fix it"*.

## Route 3: bring a design you like (e.g. an Overleaf/LaTeX template)
Give your agent the `.tex` file and say *"make my resume look like this"*. The agent:
1. Creates `profiles/<you>/templates/<name>/` with `manifest.json`
   (`latex_engine: xelatex` if the design uses `fontspec`/custom fonts; list its packages in
   `latex_packages`).
2. Keeps the design's preamble; replaces its sample content with the template syntax below,
   mapping each of its blocks (header, sections, job entries, bullet lists) to the resume document.
3. Renders with `tailor.py --template <name>` until it compiles to one page, runs
   `ats_check.py` on the `try-<name>` folder, and fixes parsing problems: icon fonts in the contact
   line (replace with plain text), two-column layouts and text in tables or boxes (ATS read these
   badly; prefer single column), fancy ligature fonts.

## Reference: template syntax
`manifest.json`: `{"engine": "latex", "entry": "resume.tex.j2", "max_pages": 1,
"latex_engine": "pdflatex" | "xelatex" | "lualatex", "latex_packages": [...]}`.
The entry file is Jinja2 with LaTeX-safe markers: `\VAR{expr}` prints a value, lines starting with
`%%` are statements (`%% for s in sections`, `%% if s.type == 'skills'`, `%% endfor`), and
`|tex` escapes text for LaTeX. The resume document it receives:
```
contact:  {name, phone, email, location, links: [{url, label}]}
sections: ordered list, each one of
  {type: summary,    title, text}
  {type: skills,     title, groups: [{name, items: [..]}]}
  {type: experience, title, entries: [{title, company, location, dates, bullets: [..],
                                       projects: [{heading, label, name, client, description, tech, bullets}]}]}
  {type: education,  title, entries: [{degree, school, when, grade, year}]}
  {type: projects,   title, entries: [{name, tech: [..], bullets: [..]}]}
  {type: list,       title, items: [..]}        certifications, awards, publications, ...
```

## Word or other formats: script templates
`manifest.json`: `{"engine": "script", "entry": "render.py", "ext": "docx"}`; `render.py` defines
`render(doc, out_path, template_dir)` and returns a page count or `None`. See
`templates/docx-basic/render.py` (python-docx). To reproduce a company's mandated Word format, keep
their .docx next to `render.py` and fill it (`profiles/<you>/templates/<company>-docx`).

## Checks before relying on a format
- `ats_check.py resumes/<folder>/try-<name>`: no `FIX` lines (a company-mandated format may
  legitimately lack a contact line or standard headings).
- One page when `max_pages` is 1.
- For a new **built-in** format: `.venv/bin/python engine/preview_templates.py <name>` writes its
  gallery preview; add it to the README table.
