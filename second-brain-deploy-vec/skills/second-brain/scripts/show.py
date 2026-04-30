#!/usr/bin/env python
"""Show a note from the second-brain. Usage: show.py <path> [--full]"""
import argparse
import re
import sys
from pathlib import Path

KB_ROOT = Path.home() / ".claude" / "second-brain"
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def main():
    ap = argparse.ArgumentParser(description="Display a note from the second brain")
    ap.add_argument("path", help="Path to the note (relative to ~/.claude/second-brain/)")
    ap.add_argument("--full", action="store_true", help="Show full file including frontmatter")
    args = ap.parse_args()

    # Resolve the path
    note_path = KB_ROOT / args.path

    if not note_path.exists():
        print(f"Error: Note not found at {note_path}", file=sys.stderr)
        sys.exit(1)

    if not note_path.is_file():
        print(f"Error: {note_path} is not a file", file=sys.stderr)
        sys.exit(1)

    try:
        text = note_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    # If --full flag is set, show everything
    if args.full:
        print(text)
        return

    # Otherwise, strip frontmatter
    m = FRONTMATTER_RE.match(text)
    if m:
        body = text[m.end():]
        print(body)
    else:
        print(text)


if __name__ == "__main__":
    main()