"""Check UTF-8 encoding for text files.

Usage:
    python scripts/check-utf8.py <file>
    python scripts/check-utf8.py <file1> <file2> ...
    python scripts/check-utf8.py --version

Exit codes:
    0: All files are UTF-8
    1: Some files are not UTF-8

Example:
    python scripts/check-utf8.py skills/manual-bb-test-harness/SKILL.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bb_harness import __version__


def check_utf8(path: Path) -> bool:
    """Check if file is valid UTF-8."""
    try:
        path.read_text(encoding="utf-8")
        return True
    except UnicodeDecodeError:
        return False


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check UTF-8 encoding for text files",
    )
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Files to check",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"check-utf8 {__version__}",
    )

    args = parser.parse_args()

    if not args.files:
        parser.print_help()
        return 1

    errors: list[str] = []

    for path in args.files:
        if not path.exists():
            print(f"File not found: {path}", file=sys.stderr)
            continue
        if not check_utf8(path):
            errors.append(str(path))

    if errors:
        print("UTF-8 encoding errors in:", file=sys.stderr)
        for p in errors:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print(f"All {len(args.files)} files are valid UTF-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
