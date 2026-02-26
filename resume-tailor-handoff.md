# Resume Tailor — Claude Code Handoff Doc (v4)
**Updated:** 2026-02-25  
**Owner:** Alas  
**Purpose:** Automate resume tailoring from a job posting URL (or pasted text) to a one-page, ATS-friendly DOCX

---

## Pipeline Overview

```
job URL / pasted text / .txt file
        ↓
  [0] resolve_job() — fetch + extract plain text if URL
        ↓
  job_description (plain text)
        ↓
  [1] Claude API (tailor + extract company + job title)
        ↓
  tailored_resume.json
        ↓
  [2] python-docx (render to .docx)
        ↓
  output/<company>/<job-title>/
    ├── resume.docx
    ├── tailored_resume.json
    └── job_description.txt
```

---

## Directory Structure

```
resume-tailor/
├── master_resume.json          # Source of truth — never edited by automation
├── tailor.py                   # Main entry point
├── prompts/
│   └── tailor_prompt.txt       # Claude system prompt
├── output/                     # Auto-created, gitignored
│   └── <company>/
│       └── <job-title>/
│           ├── resume.docx
│           ├── tailored_resume.json
│           └── job_description.txt
├── requirements.txt
└── README.md
```

---

## Step 0 — Job Input Resolution

The script accepts three input types and normalizes them all to plain text.

```python
def resolve_job(job_input: str) -> str:
    if job_input.startswith("http"):
        return fetch_job_from_url(job_input)
    elif job_input.endswith(".txt"):
        return open(job_input).read()
    else:
        return job_input                        # raw pasted string


def fetch_job_from_url(url: str) -> str:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        text = page.inner_text("body")
        browser.close()
    return text
```

**Why Playwright and not requests:** Most job boards (Greenhouse, Lever, Workday, Indeed) render content via JavaScript. A plain `requests.get()` returns an empty shell. Playwright runs a real headless Chromium and waits for the page to fully load.

**LinkedIn exception:** LinkedIn actively blocks headless browsers and serves a login wall. For LinkedIn postings, copy the job description text manually and pass it via clipboard (`--job "$(pbpaste)"`) or a `.txt` file. This is the one board where scraping reliably fails — don't try to work around it.

---

## Step 1 — Master Resume JSON

Already built. Located at `master_resume.json`.

The only addition needed before handoff: a `titles[]` array parallel to `summaries[]`. Claude rewrites the header title per job the same way it rewrites the summary.

---

## Step 2 — Claude Tailoring Prompt

**File:** `prompts/tailor_prompt.txt`

```
You are a professional resume writer specializing in technical roles.

You will receive:
1. A master resume in JSON format
2. A job posting (plain text)

Your task:
- Extract the company name and job title from the posting
- Pick the single best-matching title from the titles array and lightly rewrite it to fit the role
- Pick the single best-matching summary from the summaries array and lightly rewrite it to fit the role
- Select the most relevant experience bullets (max 3-4 per role) based on tags and relevance
- Select the most relevant projects (max 2-3) based on tags
- Flatten skills into three plain lists: Technical, Tools, and Other
- Rewrite selected bullets to mirror the language and keywords in the job posting
- Preserve factual accuracy — never invent metrics or experiences
- Stay within 420 words total across summary + all bullets combined — critical for one-page fit

Return ONLY valid JSON. No markdown fences, no explanation, no preamble.

Output schema:
{
  "company": "extracted company name",
  "job_title": "extracted job title",
  "meta": {
    "name": "...",
    "title": "rewritten headline for this role",
    "email": "...",
    "phone": "...",
    "location": "...",
    "relocation": "...",
    "linkedin": "...",
    "github": "..."
  },
  "summary": "single chosen and lightly rewritten summary string",
  "experience": [
    {
      "company": "...",
      "title": "...",
      "location": "...",
      "start": "...",
      "end": "...",
      "bullets": ["bullet text", "bullet text"]
    }
  ],
  "skills": {
    "technical": ["skill1", "skill2"],
    "tools": ["tool1", "tool2"],
    "other": ["other1", "other2"]
  },
  "projects": [
    {
      "name": "...",
      "tech": ["tech1", "tech2"],
      "description": "one sentence"
    }
  ],
  "education": [
    {
      "institution": "...",
      "degree": "...",
      "honors": "...",
      "location": "...",
      "start": "...",
      "end": "..."
    }
  ]
}
```

---

## Step 3 — python-docx Renderer

### ATS-safe formatting rules baked into the renderer:
- Single-column layout, no tables
- Arial font throughout
- Standard section headers: EXPERIENCE, SKILLS, PROJECTS, EDUCATION
- Plain bullets via docx numbering (no unicode symbols)
- No images, no icons, no color
- US Letter page size, 0.6in top/bottom margins, 0.65in left/right margins

### Font sizes:
| Element | Size |
|---|---|
| Name (H1) | 16pt bold |
| Headline / title | 11pt, centered |
| Section headers | 10pt bold, all caps, bottom border |
| Job title / company | 10pt bold |
| Dates, location | 9.5pt |
| Body / bullets | 9.5pt |
| Contact line | 9pt |

### Page setup:
```python
from docx.shared import Inches
from docx import Document

doc = Document()
section = doc.sections[0]
section.page_width    = Inches(8.5)
section.page_height   = Inches(11)
section.top_margin    = Inches(0.6)
section.bottom_margin = Inches(0.6)
section.left_margin   = Inches(0.65)
section.right_margin  = Inches(0.65)
```

### Tight paragraph spacing:
```python
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def set_spacing(paragraph, before=0, after=2):
    pPr = paragraph._p.get_or_add_pPr()
    spacing = OxmlElement('w:spacing')
    spacing.set(qn('w:before'), str(before))
    spacing.set(qn('w:after'),  str(after))
    pPr.append(spacing)
```

### Section header with bottom border:
```python
def add_section_header(doc, text):
    p = doc.add_paragraph()
    run = p.add_run(text.upper())
    run.bold = True
    run.font.size = Pt(10)
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'),   'single')
    bottom.set(qn('w:sz'),    '6')
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), '000000')
    pBdr.append(bottom)
    pPr.append(pBdr)
    set_spacing(p, before=80, after=2)
```

### Bullets (use docx numbering, never unicode characters):
```python
# Define numbering once at document level using AbstractNum + Num
# Reference it per bullet paragraph via p._p.get_or_add_pPr().numPr
# See python-docx numbering documentation for full boilerplate
```

---

## Step 4 — Main Script (tailor.py)

```python
# pseudocode — Claude Code will implement

def main(job_input: str, dry_run: bool = False):

    # 0. Resolve job input to plain text
    job_description = resolve_job(job_input)

    # 1. Load master resume
    master = load_json("master_resume.json")

    # 2. Call Claude API to tailor
    response = call_claude(
        model="claude-haiku-4-5-20251001",
        temperature=0,
        system=load_file("prompts/tailor_prompt.txt"),
        user=f"Job Posting:\n{job_description}\n\nMaster Resume:\n{json.dumps(master)}"
    )

    # 3. Parse JSON — strip accidental markdown fences before json.loads()
    tailored = parse_json(response)

    # 4. Dry run — print and exit
    if dry_run:
        print(json.dumps(tailored, indent=2))
        return

    # 5. Build output directory: output/<company>/<job-title>/
    company   = slugify(tailored["company"])
    job_title = slugify(tailored["job_title"])
    out_dir   = Path(f"output/{company}/{job_title}")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 6. Save artifacts
    (out_dir / "job_description.txt").write_text(job_description)
    (out_dir / "tailored_resume.json").write_text(json.dumps(tailored, indent=2))
    render_docx(tailored, out_dir / "resume.docx")

    print(f"Done: {out_dir}/")


def render_docx(data: dict, output_path: Path):
    doc = Document()
    setup_page(doc)

    add_header(doc, data["meta"])
    add_summary(doc, data["summary"])
    add_section_header(doc, "Experience")
    add_experience(doc, data["experience"])
    add_section_header(doc, "Skills")
    add_skills(doc, data["skills"])
    add_section_header(doc, "Projects")
    add_projects(doc, data["projects"])
    add_section_header(doc, "Education")
    add_education(doc, data["education"])

    doc.save(output_path)
```

---

## Step 5 — Dependencies

```
# requirements.txt
anthropic>=0.25.0
python-docx>=1.1.0
playwright>=1.40.0
```

Install:
```bash
pip install anthropic python-docx playwright
playwright install chromium
```

---

## Step 6 — Usage (CLI)

```bash
# Job posting URL (Greenhouse, Lever, Workday, Indeed, etc.)
python tailor.py --job "https://jobs.lever.co/acme/12345"

# LinkedIn or any paywalled board — paste manually
python tailor.py --job "$(pbpaste)"

# From a text file
python tailor.py --job job.txt

# Dry run — preview Claude's output without writing files
python tailor.py --job "https://jobs.lever.co/acme/12345" --dry-run

# Output: output/acme_corp/senior_solutions_engineer/
#   ├── resume.docx
#   ├── tailored_resume.json
#   └── job_description.txt
```

---

## One-Page Strategy

Enforced entirely through the prompt:

- 420 word budget
- Max 3-4 bullets per role
- Max 2-3 projects
- Single summary (2-3 sentences)

At 9.5pt Arial with tight spacing this fits comfortably on one US Letter page. If a rare edge case overflows, open the DOCX and trim one bullet manually.

---

## Future Enhancements (Post-MVP)

- **Lilo integration:** `/tailor-resume <job_url>` via Telegram — runs full pipeline, returns DOCX
- **Cover letter:** Same Claude call, separate simple renderer, saved alongside resume in same output folder
- **Application tracker:** Append a row to a CSV (`output/applications.csv`) with company, job title, date, and output path every time the script runs

---

## Notes for Claude Code

- Use `temperature=0` — deterministic JSON output is critical
- Strip markdown fences before `json.loads()` — Claude occasionally wraps output in backtick blocks even when told not to
- Use python-docx numbering config for bullets, never insert bullet characters as text strings
- Set page size explicitly — python-docx defaults to A4
- Keep all spacing values in twips when using raw XML helpers (1 inch = 1440 twips)
- `slugify()` should lowercase and replace spaces/special chars with underscores
- Playwright's `wait_until="networkidle"` handles most JS-rendered boards; if a specific board still fails, try `wait_until="domcontentloaded"` with an explicit `page.wait_for_timeout(2000)` after
- LinkedIn blocks headless browsers — do not attempt to handle it programmatically, just surface a clear error message telling the user to paste manually

---

*Ready for Claude Code. Start with tailor.py, build out the renderer functions, then wire up the CLI args.*
