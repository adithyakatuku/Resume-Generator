# Setting up, step by step

No programming knowledge needed. You'll install four things once, then talk to an AI
assistant in plain language; it runs everything else for you. Allow about 30–45 minutes.

**What you are installing and why**

| Thing | Why | Required? |
|---|---|---|
| **Git** | Downloads this project and keeps your copy up to date | Yes |
| **Python** | Runs the job scanner, resume builder and tracker | Yes |
| **LaTeX** | Turns your resume into a clean PDF | Yes, for PDF resumes (not for Word ones) |
| **An AI agent** | Reads your notes, builds your resume bank, picks jobs, fills forms | Yes |
| **Browser control** | Lets the agent search Naukri/LinkedIn and fill applications in your browser | Optional |
| **Microsoft Excel** (or Numbers/LibreOffice) | Opens your application tracker | You probably have one |

---

## 1. Open a terminal

The terminal is a window where you type commands. You'll paste a few commands from this page.

- **Mac:** press `Cmd + Space`, type `Terminal`, press Enter.
- **Windows:** press the Windows key, type `PowerShell`, press Enter.

To paste a command: copy it from this page, click in the terminal, paste (`Cmd+V` on Mac,
right-click on Windows), and press Enter. Wait until it finishes before the next one.

## 2. Install Git and Python

**Mac:**
1. Paste `xcode-select --install` and click *Install* in the window that appears. This gives you Git.
2. Download Python from <https://www.python.org/downloads/> (the big yellow button) and run the
   installer with all the default options.

**Windows:**
1. Download Git from <https://git-scm.com/download/win> and install with the default options.
2. Download Python from <https://www.python.org/downloads/>. **On the first installer screen, tick
   "Add python.exe to PATH"**, then click *Install Now*.
3. Close PowerShell and open it again so it notices the new programs.

Check it worked: paste `git --version` and then `python3 --version` (on Windows: `python --version`).
Each should print a version number.

## 3. Install LaTeX (for PDF resumes)

- **Mac:** download **BasicTeX** from <https://www.tug.org/mactex/morepackages.html>
  (`BasicTeX.pkg`), install it, then close and reopen the terminal and paste:
  ```
  tlmgr init-usertree; tlmgr --usermode install preprint titlesec enumitem fontawesome5 marvosym
  ```
  (The full **MacTeX** download also works and needs no extra packages, but it is about 5 GB.)
- **Windows:** download **MiKTeX** from <https://miktex.org/download>, install with default
  options, and choose *"Install missing packages on-the-fly: Yes"*.

If you only want Word (.docx) resumes, you can skip this step and set your format to
`docx-basic` later.

## 4. Download this project

Paste these one at a time (this puts the project in a folder called `Resume-Generator` in your
home folder):
```
cd ~
git clone <this project's GitHub address> Resume-Generator
cd Resume-Generator
python3 -m venv .venv
```
Then, **Mac:** `.venv/bin/pip install -r requirements.txt`
**Windows:** `.venv\Scripts\pip install -r requirements.txt`

## 5. Install an AI agent

Any of these works; pick one you have access to:

- **Claude Code** (Anthropic): install from <https://claude.com/claude-code>, then in the terminal
  run `cd ~/Resume-Generator` and `claude`. It reads `CLAUDE.md`/`AGENTS.md` automatically.
- **Codex CLI** (OpenAI), **Gemini CLI** (Google), **Cursor** or **VS Code with Copilot**: open the
  `Resume-Generator` folder in it. These tools read `AGENTS.md` on their own; if one doesn't, start
  by saying *"Read AGENTS.md first."*

**Rather not use a terminal app?** Use a desktop chat app instead: **Claude Desktop**, Cursor,
ChatGPT desktop or another app that supports MCP. Connect it to this project once by following
[MCP.md](MCP.md); after that you chat as usual and the app runs everything. A chat *website*
can't reach your computer, so it can only help with writing.

## 6. (Optional) Let the agent use your browser

Needed only for searching sites like Naukri or LinkedIn and for filling application forms.

- **Claude Code:** install the **Claude in Chrome** extension from the Chrome Web Store, sign in
  with the same account, then run `/chrome` in Claude Code (or start it with `claude --chrome`).
- **Other agents:** most support a browser through **Playwright MCP** or a "browser use" feature;
  ask your agent: *"Help me connect a browser to you"*, and it will walk you through it.

Then, in that browser, **log in to the job sites yourself** (Naukri, LinkedIn...). The agent uses
your logged-in session; it will never type your passwords, and it stops before any Submit button.

## 7. Check everything

Ask your agent: *"Run the doctor."* (or paste `.venv/bin/python engine/doctor.py`; on Windows
`.venv\Scripts\python engine\doctor.py`). It lists what's installed, and for anything missing it
says exactly what to install or run. Fix those, then run it again until it says
**"Everything required is installed."** Lines marked `note` are optional.

## 8. Start

Tell your agent, in your own words:

> "I'm new here. Set me up: copy the example profile for me, then help me write my notes."

It will create `profiles/<your-name>/`, ask about your experience, target roles and locations,
plus the standard questions job applications ask (notice period, expected salary, relocation...),
and follow the steps in `tasks/`. You then review and confirm every fact it drafts.

---

## Everyday use (just ask the agent)

- *"Scan for new jobs."* · *"Search Naukri for me."*
- *"What should I apply to next?"*
- *"Tailor my resume for the Bosch job."* · *"Fill in the application for it."*
- *"I got rejected by Wabtec."* / *"Bosch called me for an interview."*
- Open `profiles/<your-name>/applications.xlsx` in Excel any time to see your progress.

## Your data stays yours

Everything about you lives in `profiles/<your-name>/`. The project is told to ignore that folder,
so it is never uploaded with the project, even if you share it.

Your profile starts as a copy of a **fictional example** (Meera Rao). Your agent replaces all of
it with your own details; until it has, the tools refuse to build resumes or fill forms with it.

The most sensitive part is `profiles/<your-name>/private/applicant.json`: your salary, notice
period, address and other answers for application forms. Your agent asks you for these once.

**Backing up and using another computer:** ask your agent to *"back up my profile to a private
GitHub repository"*. It will ask whether to include `private/` too:
- **Include it** if nobody else can access that repository: everything syncs.
- **Leave it out** if you might ever share the repository (a mentor reviewing your resume, an app
  with access): then copy `private/` to your other computer yourself.

On another computer: download the project (step 4), then ask your agent to download your profile
into `profiles/<your-name>/`.

## If something goes wrong

First, run the doctor (step 7): it catches most missing installs. Otherwise paste the error into
your agent and ask *"What does this mean and how do I fix it?"* Common ones:

| Message | Fix |
|---|---|
| `command not found: python3` / `git` | Step 2 didn't finish; reinstall, then reopen the terminal |
| `pdflatex: command not found` | Step 3; reopen the terminal after installing |
| `File 'titlesec.sty' not found` (or another `.sty`) | Mac: `tlmgr --usermode install <name>`; Windows: let MiKTeX install it |
| `No profile yet` | Ask the agent to set up your profile (step 8) |
| `Missing Python package ...` | `.venv/bin/pip install -r requirements.txt` (Windows: `.venv\Scripts\pip ...`), and run commands with `.venv/bin/python` |
| `Could not write applications.xlsx` | Close the file in Excel, then retry |
