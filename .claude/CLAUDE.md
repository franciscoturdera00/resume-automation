# Resume Automation — Project Guide

## What this is

A CLI pipeline that tailors a master resume to any job posting using Claude, then renders a polished DOCX. Single-file architecture (`tailor.py`).

## Architecture

```
tailor.py              # Everything: scraper, Claude client, DOCX renderer, CLI
master_resume.json     # Tagged master resume (bullets, projects, skills, summaries)
prompts/tailor_prompt.txt  # System prompt controlling Claude's tailoring behavior
output/<company>/<job>/    # Generated artifacts per job application
```

## Key conventions

- **Single file** — Don't split `tailor.py` into modules unless it exceeds ~600 lines or gains a second output format.
- **Shebang** — Uses `#!/usr/bin/env -S .venv/bin/python3` so it runs directly without activating the venv.
- **Model** — Currently uses `claude-sonnet-4-6`. Change in `call_claude()` if needed.
- **Word limit** — Controlled in `prompts/tailor_prompt.txt`, not in code. Currently 450 words for summary + bullets.
- **DOCX design** — Modern style with Calibri font, dark steel blue accent (`#2B4C7E`), colored section headers. Constants are `ACCENT`, `DARK`, `GRAY` at the top of the renderer section.

## How to run

```bash
./tailor.py --job "<URL or .txt path>"       # Full run
./tailor.py --job "<URL>" --dry-run          # JSON only, no DOCX
```

## Master resume structure

Entries in `master_resume.json` are tagged so Claude can match them to job postings:
- `experience[].bullets[]` — each has `tags` and `priority`
- `projects[]` — each has `tags` and `priority`
- `summaries[]` — multiple pre-written summaries, Claude picks the best match
- `titles[]` — multiple headline options, Claude picks and rewrites

When adding new entries, always include relevant `tags` for matching.

## Output

Every run (including dry-run) saves to `output/<company>/<job_title>/`:
- `tailored_resume.json` — Claude's tailored output
- `job_description.txt` — scraped posting text
- `resume.docx` — rendered resume (full run only)

## Gotchas

- LinkedIn URLs are blocked by their anti-bot measures. Use clipboard paste instead.
- Playwright must be installed (`playwright install chromium`) for URL scraping.
- `.env` must contain `ANTHROPIC_API_KEY`.
