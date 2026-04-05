"""MCP adapter for resume-automation tool."""

import sys
import json
import shutil
import tempfile
from pathlib import Path

_RA_ROOT = Path(__file__).resolve().parent.parent  # resume-automation/
_TOOLS_LIB = _RA_ROOT.parent / "tools" / "lib"
sys.path.insert(0, str(_TOOLS_LIB))
sys.path.insert(0, str(_RA_ROOT))  # so `import tailor` works

from tool_base import ToolResult, setup_logging
from tailor import (
    call_claude,
    render_docx,
    tailor_with_loop,
    slugify,
    SCRIPT_DIR,
    MASTER_RESUME,
)

logger = setup_logging("resume_automation")


def tailor_resume(job_description: str, dry_run: bool = False) -> ToolResult:
    """
    Tailor a resume to a job description.

    The caller is responsible for fetching the job description — this tool only
    accepts the raw text. Lilo should use WebFetch, chrome MCP, or ask the user
    to paste the JD before calling.

    When not dry_run, runs a writer → render → measure → aesthetic-review loop
    that iterates until the rendered resume fills exactly one page and passes a
    vision-based aesthetic check.

    Args:
        job_description: Full job posting text.
        dry_run: Skip DOCX rendering and the fit loop; only produce tailored JSON.

    Returns:
        ToolResult with data containing company, job_title, output_dir,
        files_written, fit {pages, fill_ratio}, history, and dry_run.
    """
    if not job_description or not job_description.strip():
        return ToolResult(
            success=False,
            data={},
            message="job_description is empty — fetch the posting before calling this tool",
        )

    logger.info(f"Tailoring resume ({len(job_description)} chars, dry_run={dry_run})")

    master = json.loads(MASTER_RESUME.read_text())

    if dry_run:
        tailored = call_claude(job_description, master)
        company = slugify(tailored["company"])
        job_title = slugify(tailored["job_title"])
        out_dir = SCRIPT_DIR / "output" / company / job_title
        out_dir.mkdir(parents=True, exist_ok=True)

        files_written = []
        jd_path = out_dir / "job_description.txt"
        jd_path.write_text(job_description)
        files_written.append(str(jd_path.resolve()))

        json_path = out_dir / "tailored_resume.json"
        json_path.write_text(json.dumps(tailored, indent=2))
        files_written.append(str(json_path.resolve()))

        return ToolResult(
            success=True,
            data={
                "company": tailored["company"],
                "job_title": tailored["job_title"],
                "output_dir": str(out_dir.resolve()),
                "files_written": files_written,
                "dry_run": True,
            },
            message=f"Dry run tailored for {tailored['company']} — {tailored['job_title']}",
        )

    # Full flow: stage into temp, loop, move to final out_dir.
    with tempfile.TemporaryDirectory(prefix="resume_stage_") as staging:
        staging_dir = Path(staging)
        tailored, fit, history = tailor_with_loop(
            job_description, master, staging_dir, max_iterations=3
        )

        company = slugify(tailored["company"])
        job_title = slugify(tailored["job_title"])
        out_dir = SCRIPT_DIR / "output" / company / job_title
        out_dir.mkdir(parents=True, exist_ok=True)

        files_written = []
        jd_path = out_dir / "job_description.txt"
        jd_path.write_text(job_description)
        files_written.append(str(jd_path.resolve()))

        json_path = out_dir / "tailored_resume.json"
        json_path.write_text(json.dumps(tailored, indent=2))
        files_written.append(str(json_path.resolve()))

        history_path = out_dir / "fit_history.json"
        history_path.write_text(json.dumps(history, indent=2))
        files_written.append(str(history_path.resolve()))

        # Copy staged artifacts (resume.docx, resume.pdf, .page1.png) into out_dir
        for f in staging_dir.iterdir():
            dest = out_dir / f.name
            shutil.copy2(f, dest)
            if f.suffix in (".docx", ".pdf"):
                files_written.append(str(dest.resolve()))

    alerts = []
    if fit["pages"] > 1:
        alerts.append(f"Resume overflowed to {fit['pages']} pages after {len(history)} iterations")
    elif fit["fill_ratio"] < 0.88:
        alerts.append(f"Resume only fills {int(fit['fill_ratio']*100)}% of page 1")
    last_aesthetics = history[-1]["aesthetics"] if history else {}
    if isinstance(last_aesthetics, dict) and not last_aesthetics.get("acceptable", True):
        alerts.append(f"Aesthetic reviewer flagged issues: {'; '.join(last_aesthetics.get('issues', []))}")

    return ToolResult(
        success=True,
        data={
            "company": tailored["company"],
            "job_title": tailored["job_title"],
            "output_dir": str(out_dir.resolve()),
            "files_written": files_written,
            "fit": {"pages": fit["pages"], "fill_ratio": fit["fill_ratio"]},
            "iterations": len(history),
            "dry_run": False,
        },
        message=f"Tailored resume for {tailored['company']} — {tailored['job_title']} "
                f"({fit['pages']}pg, {int(fit['fill_ratio']*100)}% fill, {len(history)} iter)",
        alerts=alerts,
    )


def list_outputs() -> ToolResult:
    """
    List previously tailored resumes under output/.

    Returns:
        ToolResult with data containing outputs list of {company, job_title, files, mtime}.
    """
    output_dir = SCRIPT_DIR / "output"
    outputs = []

    if not output_dir.exists():
        logger.info("No output/ directory found")
        return ToolResult(
            success=True,
            data={"outputs": []},
            message="Found 0 tailored resumes",
        )

    for company_dir in output_dir.iterdir():
        if not company_dir.is_dir():
            continue
        company = company_dir.name

        for job_dir in company_dir.iterdir():
            if not job_dir.is_dir():
                continue
            job_title = job_dir.name

            files = []
            mtime = None
            for f in job_dir.iterdir():
                if f.is_file() and not f.name.startswith('.'):
                    files.append(f.name)
                    f_mtime = f.stat().st_mtime
                    if mtime is None or f_mtime > mtime:
                        mtime = f_mtime

            outputs.append({
                "company": company,
                "job_title": job_title,
                "files": files,
                "mtime": mtime,
            })

    logger.info(f"Found {len(outputs)} tailored resume(s)")
    return ToolResult(
        success=True,
        data={"outputs": outputs},
        message=f"Found {len(outputs)} tailored resume{'s' if len(outputs) != 1 else ''}",
    )
