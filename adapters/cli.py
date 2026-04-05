"""CLI adapter for resume-automation tool."""

import argparse
import sys
from pathlib import Path

_RA_ROOT = Path(__file__).resolve().parent.parent  # resume-automation/
_TOOLS_LIB = _RA_ROOT.parent / "tools" / "lib"
sys.path.insert(0, str(_TOOLS_LIB))
sys.path.insert(0, str(_RA_ROOT))

from tool_base import run_tool, setup_logging
import adapters.mcp as mcp_adapters

logger = setup_logging("cli")


def main():
    """Parse CLI arguments and dispatch to tool functions."""
    parser = argparse.ArgumentParser(description="Resume automation tool CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # tailor subcommand
    tailor_parser = subparsers.add_parser("tailor", help="Tailor resume to a job posting")
    tailor_parser.add_argument(
        "--job-input",
        required=True,
        help="Job posting as URL, .txt file path, or raw text"
    )
    tailor_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip DOCX rendering; only save JSON and job description"
    )

    # list-outputs subcommand
    list_parser = subparsers.add_parser("list-outputs", help="List previously tailored resumes")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Dispatch to the appropriate function
    if args.command == "tailor":
        result = run_tool(mcp_adapters.tailor_resume, args.job_input, dry_run=args.dry_run)
        print(result.to_json())
        sys.exit(0 if result.success else 1)

    elif args.command == "list-outputs":
        result = run_tool(mcp_adapters.list_outputs)
        print(result.to_json())
        sys.exit(0 if result.success else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
