# Use it from a chat app (MCP)

Resume Generator includes an **MCP server**. MCP (Model Context Protocol) is the standard way AI apps
plug in tools. Once it's connected, you can do everything by chatting in **Claude Desktop**, **Cursor**,
**ChatGPT desktop**, **Codex**, **Gemini CLI** and other MCP apps, without typing commands.

You still need the installs from [SETUP.md](SETUP.md) steps 2–4: Git, Python with the project
environment, and LaTeX for PDF resumes. The server runs the same engine on your computer; your
files never leave it except through the AI app you chat with.

## What the AI app can do through it

| Tool | What it does |
|---|---|
| `guide` | Reads the operating manual and task guides, so any app follows the same rules |
| `doctor` | Checks what is installed and explains how to fix anything missing |
| `list_profiles`, `create_profile` | Lists profiles, or starts a new one from the example |
| `read_file`, `write_file` | Reads and writes files **inside a profile folder only**. JSON is checked before saving. |
| `check` | Validates the profile and enforces the fact rules |
| `workrecord_digest` | Summarises your git work as evidence for resume bullets |
| `scan`, `save_jobs` | Fetches company job boards, and imports jobs the app found while browsing |
| `pick` | Picks the next job to apply to at each company |
| `tailor`, `preview_formats` | Builds a resume and returns a picture of the page; compares formats |
| `ats_check` | Checks how the resume reads in applicant tracking systems, and which job terms it covers |
| `application_sheet` | Gives the job link, which resume to upload, and your answers for the form |
| `tracker_list`, `tracker_show`, `tracker_set` | Reads the tracker, and records Applied, Interview, Rejected and other statuses |

Even through MCP, the app can't submit an application, type a password or invent a fact.
Filling a form in your browser still needs an app with browser control (see SETUP.md step 6). If
your app doesn't have it, ask for the answer sheet (`application_sheet`) and fill the form yourself.

## Connect it

You need two full paths. Replace `/Users/you/Resume-Generator` below with where you downloaded
the project.
- **Python:** `/Users/you/Resume-Generator/.venv/bin/python`. On Windows:
  `C:\Users\you\Resume-Generator\.venv\Scripts\python.exe`.
- **Server:** `/Users/you/Resume-Generator/engine/mcp_server.py`

### Claude Desktop
1. Open Claude Desktop, then **Settings → Developer → Edit Config**. This opens
   `claude_desktop_config.json`.
2. Put this in it (or add the `resume-generator` entry if `mcpServers` is already there), then save:
   ```json
   {
     "mcpServers": {
       "resume-generator": {
         "command": "/Users/you/Resume-Generator/.venv/bin/python",
         "args": ["/Users/you/Resume-Generator/engine/mcp_server.py"]
       }
     }
   }
   ```
   On Windows, write paths with double backslashes: `"C:\\Users\\you\\Resume-Generator\\.venv\\Scripts\\python.exe"`.
3. Quit and reopen Claude Desktop. **resume-generator** now appears in the tools (🔨/➕) menu.

### Claude Code
```sh
claude mcp add resume-generator -- /Users/you/Resume-Generator/.venv/bin/python /Users/you/Resume-Generator/engine/mcp_server.py
```
Inside this project folder, Claude Code can already run the commands directly. The server is
for using the project from other folders, or for a tidier, permission-free set of tools.

### Cursor
Add the same `mcpServers` block as Claude Desktop to `~/.cursor/mcp.json`, or to **Settings → MCP**.

### Codex CLI
Add this to `~/.codex/config.toml`:
```toml
[mcp_servers.resume-generator]
command = "/Users/you/Resume-Generator/.venv/bin/python"
args = ["/Users/you/Resume-Generator/engine/mcp_server.py"]
```

### Gemini CLI and others
Most apps take the same `command` and `args` pair. For Gemini CLI, add the `mcpServers` block to
`~/.gemini/settings.json`. For any other app, look for "MCP servers" in its settings.

## First message

> "Use the resume-generator tools. Read the guide first, run the doctor, then set me up."

The app reads the manual through `guide`, checks your installs and creates your profile. It
asks you for your notes, then follows the same steps as the terminal workflow.

## Check that it works

```sh
.venv/bin/python engine/test_mcp_server.py
```
This starts the server the way an app does and calls each tool. It uses only the example
profile and a temporary profile that it deletes afterwards.

**Problems?**
- **The tools don't appear.** Check both paths: copy each one into a terminal and press Enter to
  see that it exists. Then restart the app completely.
- **"No module named …" in the tool output.** Install the project's packages:
  `.venv/bin/pip install -r requirements.txt`.
- **"Which profile?"** You have more than one profile. Say which one, for example "use profile priya".
