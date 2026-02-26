# Resume Tailoring Pipeline

CLI tool that takes a job posting, sends it with your master resume to Claude, and generates a tailored ATS-friendly DOCX.

## How it works

1. **Scrape** — Fetches the job posting via Playwright (or reads from a `.txt` file / raw text)
2. **Tailor** — Sends the job description + master resume to Claude, which selects and rewrites the most relevant experience, projects, and skills
3. **Render** — Generates a polished one-page DOCX with modern formatting

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Create a `.env` file with your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

## Usage

```bash
# From a job posting URL
./tailor.py --job "https://job-boards.greenhouse.io/company/jobs/123"

# Dry run — prints tailored JSON + saves it, but skips DOCX generation
./tailor.py --job "https://..." --dry-run

# From a text file
./tailor.py --job path/to/job_description.txt

# From clipboard (macOS)
./tailor.py --job "$(pbpaste)"
```

## Output

Files are saved to `output/<company>/<job_title>/`:

```
output/
  anthropic/
    applied_ai_engineer_startups/
      resume.docx            # Final tailored resume
      tailored_resume.json   # Claude's tailored JSON output
      job_description.txt    # Scraped job posting text
```

## Project structure

```
tailor.py              # Main pipeline script (scraper, Claude client, DOCX renderer)
master_resume.json     # Source resume with tagged bullets, projects, and skills
prompts/
  tailor_prompt.txt    # System prompt for Claude
requirements.txt       # Python dependencies
```

## Customization

- **Master resume** — Edit `master_resume.json` to add/update experience, projects, skills, and summaries. Tag entries so Claude can match them to job postings.
- **Prompt** — Edit `prompts/tailor_prompt.txt` to adjust tailoring behavior, word count limits, or output schema.
- **DOCX styling** — Modify the renderer functions in `tailor.py` (colors, fonts, spacing are defined as constants at the top of the renderer section).

## Notes

- LinkedIn URLs are blocked (they reject headless browsers). Copy-paste the description instead.
- The pipeline uses Claude Sonnet 4.6 by default. Change the model in `tailor.py` if needed.
