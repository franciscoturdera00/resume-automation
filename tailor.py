#!/usr/bin/env -S .venv/bin/python3
"""Resume tailoring pipeline — from job posting to ATS-friendly DOCX."""

import argparse
import json
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
import anthropic
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")

MASTER_RESUME = SCRIPT_DIR / "master_resume.json"
PROMPT_FILE = SCRIPT_DIR / "prompts" / "tailor_prompt.txt"


# ---------------------------------------------------------------------------
# Step 0 — Job input resolution
# ---------------------------------------------------------------------------

def resolve_job(job_input: str) -> str:
    """Normalize job input (URL, .txt path, or raw text) to plain text."""
    if job_input.startswith("http"):
        return fetch_job_from_url(job_input)
    elif job_input.endswith(".txt") and Path(job_input).is_file():
        return Path(job_input).read_text()
    else:
        return job_input


def fetch_job_from_url(url: str) -> str:
    """Use Playwright to fetch JS-rendered job postings."""
    if "linkedin.com" in url:
        print(
            "Error: LinkedIn blocks headless browsers. "
            "Copy the job description and pass it via --job \"$(pbpaste)\" or a .txt file.",
            file=sys.stderr,
        )
        sys.exit(1)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        text = page.inner_text("body")
        browser.close()
    return text


# ---------------------------------------------------------------------------
# Step 1 — Claude tailoring
# ---------------------------------------------------------------------------

def call_claude(job_description: str, master: dict) -> dict:
    """Send master resume + job description to Claude and return tailored JSON."""
    system_prompt = PROMPT_FILE.read_text()
    user_message = (
        f"Job Posting:\n{job_description}\n\n"
        f"Master Resume:\n{json.dumps(master)}"
    )

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        temperature=0,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text # type: ignore
    # Strip accidental markdown fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"```\s*$", "", raw, flags=re.MULTILINE)
    return json.loads(raw.strip())


# ---------------------------------------------------------------------------
# Step 2 — DOCX renderer (modern design)
# ---------------------------------------------------------------------------

ACCENT = "2B4C7E"  # dark steel blue
DARK = "1A1A1A"    # near-black for body text
GRAY = "555555"    # secondary text


def set_spacing(paragraph, before=0, after=0, line=240):
    """Set paragraph spacing in twips."""
    pPr = paragraph._p.get_or_add_pPr()
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:before"), str(before))
    spacing.set(qn("w:after"), str(after))
    spacing.set(qn("w:line"), str(line))
    spacing.set(qn("w:lineRule"), "auto")
    pPr.append(spacing)


def set_font(run, size, bold=False, color=DARK, name="Calibri"):
    """Apply font styling."""
    run.font.name = name
    run.font.size = Pt(size)
    run.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)


def setup_page(doc):
    """Configure US Letter, balanced margins."""
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.5)
    section.bottom_margin = Inches(0.5)
    section.left_margin = Inches(0.7)
    section.right_margin = Inches(0.7)


def setup_bullet_numbering(doc):
    """Create a bullet list numbering definition and return the numId."""
    numbering_part = doc.part.numbering_part
    numbering_elm = numbering_part._element

    abstract_num_id = "1"
    abstract_num = OxmlElement("w:abstractNum")
    abstract_num.set(qn("w:abstractNumId"), abstract_num_id)

    lvl = OxmlElement("w:lvl")
    lvl.set(qn("w:ilvl"), "0")

    start = OxmlElement("w:start")
    start.set(qn("w:val"), "1")
    lvl.append(start)

    num_fmt = OxmlElement("w:numFmt")
    num_fmt.set(qn("w:val"), "bullet")
    lvl.append(num_fmt)

    lvl_text = OxmlElement("w:lvlText")
    lvl_text.set(qn("w:val"), "\u2022")
    lvl.append(lvl_text)

    lvl_jc = OxmlElement("w:lvlJc")
    lvl_jc.set(qn("w:val"), "left")
    lvl.append(lvl_jc)

    pPr = OxmlElement("w:pPr")
    ind = OxmlElement("w:ind")
    ind.set(qn("w:left"), "360")
    ind.set(qn("w:hanging"), "180")
    pPr.append(ind)
    lvl.append(pPr)

    rPr = OxmlElement("w:rPr")
    rFonts = OxmlElement("w:rFonts")
    rFonts.set(qn("w:ascii"), "Symbol")
    rFonts.set(qn("w:hAnsi"), "Symbol")
    rFonts.set(qn("w:hint"), "default")
    rPr.append(rFonts)
    lvl.append(rPr)

    abstract_num.append(lvl)
    numbering_elm.append(abstract_num)

    num_id = "1"
    num = OxmlElement("w:num")
    num.set(qn("w:numId"), num_id)
    abstract_ref = OxmlElement("w:abstractNumId")
    abstract_ref.set(qn("w:val"), abstract_num_id)
    num.append(abstract_ref)
    numbering_elm.append(num)

    return num_id


def add_bullet(doc, text, num_id):
    """Add a bullet paragraph."""
    p = doc.add_paragraph()
    run = p.add_run(text)
    set_font(run, 10.5, color=DARK)

    pPr = p._p.get_or_add_pPr()
    numPr = OxmlElement("w:numPr")
    ilvl = OxmlElement("w:ilvl")
    ilvl.set(qn("w:val"), "0")
    numPr.append(ilvl)
    numId = OxmlElement("w:numId")
    numId.set(qn("w:val"), num_id)
    numPr.append(numId)
    pPr.append(numPr)

    set_spacing(p, before=0, after=5)
    return p


def add_section_header(doc, text):
    """Add section header with accent-colored bottom border."""
    p = doc.add_paragraph()
    run = p.add_run(text.upper())
    set_font(run, 11.5, bold=True, color=ACCENT)

    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")
    bottom.set(qn("w:space"), "2")
    bottom.set(qn("w:color"), ACCENT)
    pBdr.append(bottom)
    pPr.append(pBdr)

    set_spacing(p, before=120, after=40)


def add_header(doc, meta):
    """Render name, title, and contact details."""
    # Name
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(meta["name"].upper())
    set_font(run, 20, bold=True, color=ACCENT)
    run.font.character_spacing = Pt(1.5)
    set_spacing(p, before=0, after=0)

    # Title
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(meta["title"])
    set_font(run, 11.5, color=GRAY)
    set_spacing(p, before=20, after=20)

    # Contact line
    contact_parts = []
    for key in ("location", "phone", "email", "linkedin", "github", "relocation"):
        if meta.get(key):
            contact_parts.append(meta[key])

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sep = "  \u00b7  "  # middle dot separator
    run = p.add_run(sep.join(contact_parts))
    set_font(run, 8.5, color=GRAY)
    set_spacing(p, before=0, after=60)


def add_summary(doc, summary_text):
    """Render the summary paragraph."""
    p = doc.add_paragraph()
    run = p.add_run(summary_text)
    set_font(run, 10.5, color=DARK)
    set_spacing(p, before=0, after=40)


def add_experience(doc, experience, num_id):
    """Render experience entries."""
    for job in experience:
        # Title + Company line
        p = doc.add_paragraph()
        run = p.add_run(job["title"])
        set_font(run, 11, bold=True, color=DARK)
        run = p.add_run(f"  |  {job['company']}  |  {job['location']}")
        set_font(run, 10.5, color=GRAY)
        set_spacing(p, before=60, after=0)

        # Dates
        p = doc.add_paragraph()
        run = p.add_run(f"{job['start']} \u2013 {job['end']}")
        set_font(run, 10, color=GRAY)
        set_spacing(p, before=0, after=20)

        for bullet in job["bullets"]:
            add_bullet(doc, bullet, num_id)


def add_skills(doc, skills):
    """Render skills as labeled inline lists."""
    for label, items in skills.items():
        p = doc.add_paragraph()
        run = p.add_run(f"{label.title()}: ")
        set_font(run, 10.5, bold=True, color=ACCENT)
        run = p.add_run(", ".join(items))
        set_font(run, 10.5, color=DARK)
        set_spacing(p, before=0, after=20)


def add_projects(doc, projects, num_id):
    """Render projects."""
    for proj in projects:
        p = doc.add_paragraph()
        run = p.add_run(proj["name"])
        set_font(run, 11, bold=True, color=DARK)
        run = p.add_run(f"  |  {', '.join(proj['tech'])}")
        set_font(run, 10.5, color=GRAY)
        set_spacing(p, before=60, after=20)

        add_bullet(doc, proj["description"], num_id)


def add_education(doc, education):
    """Render education entries."""
    for edu in education:
        p = doc.add_paragraph()
        run = p.add_run(edu["degree"])
        set_font(run, 11, bold=True, color=DARK)
        if edu.get("honors"):
            run = p.add_run(f"  |  {edu['honors']}")
            set_font(run, 10.5, color=ACCENT)
        set_spacing(p, before=60, after=0)

        p = doc.add_paragraph()
        run = p.add_run(f"{edu['institution']}  |  {edu['location']}  |  {edu['start']} \u2013 {edu['end']}")
        set_font(run, 10.5, color=GRAY)
        set_spacing(p, before=0, after=0)


def render_docx(data: dict, output_path: Path):
    """Build a one-page ATS-friendly DOCX from tailored JSON."""
    doc = Document()
    setup_page(doc)

    # Initialize bullet numbering
    doc.add_paragraph("", style="List Bullet")
    doc._body._body.remove(doc.paragraphs[-1]._p)
    num_id = setup_bullet_numbering(doc)

    add_header(doc, data["meta"])
    add_summary(doc, data["summary"])

    add_section_header(doc, "Experience")
    add_experience(doc, data["experience"], num_id)

    add_section_header(doc, "Skills")
    add_skills(doc, data["skills"])

    add_section_header(doc, "Projects")
    add_projects(doc, data["projects"], num_id)

    add_section_header(doc, "Education")
    add_education(doc, data["education"])

    doc.save(str(output_path))


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Lowercase, replace spaces/special chars with underscores."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Tailor a resume for a job posting")
    parser.add_argument("--job", required=True, help="Job posting URL, .txt file path, or raw text")
    parser.add_argument("--dry-run", action="store_true", help="Print tailored JSON without writing files")
    args = parser.parse_args()

    # 0. Resolve input
    print("Resolving job input...")
    job_description = resolve_job(args.job)
    print(f"Job description: {len(job_description)} chars")

    # 1. Load master resume
    master = json.loads(MASTER_RESUME.read_text())

    # 2. Call Claude
    print("Calling Claude API...")
    tailored = call_claude(job_description, master)
    print(f"Tailored for: {tailored['company']} — {tailored['job_title']}")

    # 3. Build output directory
    company = slugify(tailored["company"])
    job_title = slugify(tailored["job_title"])
    out_dir = Path(SCRIPT_DIR / "output" / company / job_title)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 4. Save artifacts
    (out_dir / "job_description.txt").write_text(job_description)
    (out_dir / "tailored_resume.json").write_text(json.dumps(tailored, indent=2))

    if args.dry_run:
        print(json.dumps(tailored, indent=2))
        print(f"\nJSON saved to: {out_dir}/tailored_resume.json")
        return

    render_docx(tailored, out_dir / "resume.docx")

    print(f"Done: {out_dir}/")


if __name__ == "__main__":
    main()
