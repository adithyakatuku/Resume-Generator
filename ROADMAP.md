# Roadmap

Where this project goes next, and why. Lessons from real use shaped the order:

- **The resume was rarely the bottleneck.** Five rejections in a row came from a hard experience
  screen, not wording. Finding the right jobs and getting past screens matters more than polish.
- **Setup is the biggest barrier.** A terminal, Python, LaTeX and a coding agent stop most
  non-technical people at step one.
- **"Never invents facts" is the differentiator.** Every generated document must stay inside the
  verified bank, and that should be the headline.

## 1. Remove the setup barrier
- [x] **MCP server** (`engine/mcp_server.py`, `docs/MCP.md`): use everything by chatting in Claude
      Desktop, ChatGPT desktop, Cursor or any MCP-capable app: no terminal, no commands.
      Next: try it end-to-end in Claude Desktop with a new profile; expose resume pages as MCP resources.
- [ ] One-click installers: `setup.command` (macOS) and `setup.ps1` (Windows) that install the
      prerequisites and run the doctor.
- [ ] No-LaTeX default for non-technical users (Word/HTML-to-PDF), LaTeX formats optional.
- [ ] Local dashboard: tracker, resume previews and "what to apply to next" in one web page.

## 2. Cover the whole application
- [ ] Cover letters from the bank, under the same fact rules as resumes.
- [ ] Referral and recruiter messages (LinkedIn/email), which get past screens resumes can't.
- [ ] Interview prep: a STAR-story bank built from verified bullets, likely questions per job.
- [ ] Follow-up reminders (no reply after 21 days) and interview-round tracking.

## 3. Native to every field and country
- [ ] Field sections and formats: portfolio/case studies (design), projects table with scope and
      value (civil, mechanical), licences (PE, chartered), publications and academic CV (research),
      two-page CV and Europass (Europe).
- [ ] Example profiles for several fields (designer, civil engineer, data scientist, nurse) with
      rendered resumes in the gallery.
- [ ] Country conventions: pay terms (CTC vs base), notice periods, photos where expected,
      date formats, resumes in other languages.
- [ ] More job sources: Workable, Recruitee, Personio, SuccessFactors feeds; field-specific boards;
      government portals through the browser route.

## 4. Get smarter over time
- [ ] Outcome learning: reply rate by source, company, level and resume version; automatic pattern
      alerts (e.g. "all senior-level applications rejected within a week: likely a hard screen").
- [ ] Better matching: an optional AI pass that scores "will I pass the screen?" separately from
      "how well do I fit?", on top of the keyword score.
- [ ] Daily digest: scheduled scans sending "N new jobs worth applying to today".

## Done
- Candidate-, profession- and agent-agnostic engine; profiles kept out of the repository.
- Verified fact bank with plain-language wording and fact checks on every resume.
- Company feeds (Workday, Greenhouse, Lever, Ashby, SmartRecruiters, Amazon) and browser sources.
- One tailored application per company; Excel tracker with a live summary.
- Resume formats as templates with previews; XeLaTeX support; format walkthrough.
- `track.py` to record statuses from the command line; `apply.py --sheet` for non-interactive use.
- `doctor.py` prerequisite check; friendly errors; setup guide for non-technical users.
