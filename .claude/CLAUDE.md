# Resume Automation — Project Guide

## What this is

A CLI pipeline that tailors a master resume to any job posting using Claude, then renders a polished one-page DOCX. Single-file architecture (`tailor.py`, ~400 lines).

## Architecture

```
tailor.py              # Everything: scraper, Claude client, DOCX renderer, CLI
master_resume.json     # Tagged master resume (bullets, projects, skills, summaries)
prompts/tailor_prompt.txt  # System prompt controlling Claude's tailoring behavior
output/<company>/<job>/    # Generated artifacts per job application
```

### Pipeline flow

1. **Resolve input** — URL (Playwright), `.txt` file, or raw text
2. **Call Claude** — sends master resume + job description, gets tailored JSON back
3. **Save artifacts** — `tailored_resume.json` + `job_description.txt` to output dir
4. **Render DOCX** — builds a styled one-page resume (skipped with `--dry-run`)

## Key conventions

- **Single file** — Don't split `tailor.py` into modules unless it exceeds ~600 lines or gains a second output format.
- **Shebang** — Uses `#!/usr/bin/env -S .venv/bin/python3` so it runs directly without activating the venv.
- **Model** — Uses Claude Code CLI (`claude -p`) with `--model sonnet`. Change in `call_claude()` if needed.
- **Word limit** — Controlled in `prompts/tailor_prompt.txt`, not in code. Currently **350 words** strict max across summary + headers + all bullets.
- **DOCX design** — Modern style with Calibri font, dark steel blue accent (`#2B4C7E`), colored section headers with bottom borders. Color constants at `tailor.py:92`: `ACCENT`, `DARK`, `GRAY`.
- **Output schema** — Claude must return bare JSON (no markdown fences). The code strips fences as a safety net (`tailor.py:83-84`).

## How to run

```bash
./tailor.py --job "<URL or .txt path>"       # Full run
./tailor.py --job "<URL>" --dry-run          # JSON only, no DOCX
./tailor.py --job "$(pbpaste)"               # Paste from clipboard (useful for LinkedIn)
```

## Dependencies

Managed via `requirements.txt` and a local `.venv`:
- `python-docx` — DOCX generation
- `playwright` — JS-rendered page scraping (requires `playwright install chromium`)

Also requires `claude` CLI (Claude Code) to be installed and authenticated.

## Master resume structure

Entries in `master_resume.json` are tagged so Claude can match them to job postings:
- `titles[]` — multiple headline options with `tags`, Claude picks and rewrites
- `summaries[]` — multiple pre-written summaries with `tags` and `priority`
- `experience[].bullets[]` — each has `tags` and `priority`
- `projects[]` — each has `tags` and `priority`
- `skills` — grouped by category (cloud, programming, automation, monitoring, collaboration)

When adding new entries, always include relevant `tags` for matching.

## Output

Every run (including dry-run) saves to `output/<company>/<job_title>/`:
- `tailored_resume.json` — Claude's tailored output
- `job_description.txt` — scraped posting text
- `resume.docx` — rendered resume (full run only)

Directory names are slugified (lowercase, underscores).

## Gotchas

- LinkedIn URLs are blocked by their anti-bot measures. Use clipboard paste instead.
- Playwright must be installed (`playwright install chromium`) for URL scraping.
- `claude` CLI must be installed and authenticated (no API key needed).
- The DOCX renderer uses low-level `python-docx` XML manipulation (OxmlElement) for bullet numbering and paragraph spacing — be careful when modifying these sections.
