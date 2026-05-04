"""Check UTF-8 encoding for text files.

Usage:
    python scripts/check-utf8.py <file>
    python scripts/check-utf8.py <file1> <file2> ...

Exit codes:
    0: All files are UTF-8
    1: Some files are not UTF-8

Example:
    python scripts/check-utf8.py skills/manual-bb-test-harness/SKILL.md
"""

from __future__ import annotations

import sys
from pathlib import Path


def check_utf8(path: Path) -> bool:
    """Check if file is valid UTF-8."""
    try:
        path.read_text(encoding="utf-8")
        return True
    except UnicodeDecodeError:
        return False


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/check-utf8.py <file> [<file> ...]", file=sys.stderr)
        return 1

    errors: list[str] = []

    for arg in sys.argv[1:]:
        path = Path(arg)
        if not path.exists():
            continue
        if not check_utf8(path):
            errors.append(str(path))

    if errors:
        print(f"UTF-8 encoding errors in:", file=sys.stderr)
        for p in errors:
            print(f"  - {p}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())