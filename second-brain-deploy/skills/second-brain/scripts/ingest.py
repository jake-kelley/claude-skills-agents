#!/usr/bin/env python
"""Explicit ingest: capture a URL or local file as a KB note via the extractor.

Usage: ingest.py <url-or-path>

Spawns the kb-extractor with the source content; written notes go to references/
or the appropriate category as the extractor decides.
"""
import importlib.util
import os
import subprocess
import sys
import urllib.request
from datetime import date
from pathlib import Path

KB_ROOT = Path.home() / ".claude" / "second-brain"
HOOK_DIR = Path.home() / ".claude" / "hooks"


def load_capture_module():
    spec = importlib.util.spec_from_file_location("kb_capture", str(HOOK_DIR / "kb-capture.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fetch(arg: str) -> tuple[str, str]:
    if arg.startswith(("http://", "https://")):
        try:
            req = urllib.request.Request(arg, headers={"User-Agent": "Mozilla/5.0 second-brain"})
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read().decode("utf-8", errors="replace")
            return arg, raw
        except Exception as e:
            print(f"Fetch failed: {e}", file=sys.stderr)
            sys.exit(1)
    p = Path(arg)
    if p.exists():
        return p.as_posix(), p.read_text(encoding="utf-8", errors="replace")
    print(f"Not a URL or existing file: {arg}", file=sys.stderr)
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: ingest.py <url-or-path>", file=sys.stderr)
        sys.exit(2)

    source, content = fetch(sys.argv[1])
    if len(content) > 40000:
        content = content[:40000] + "\n...[truncated]"

    mod = load_capture_module()
    today = date.today().isoformat()

    prompt = f"""Extract new settled knowledge from this source.

Source: {source}
Today: {today}

Existing note titles (do NOT duplicate):
{mod.existing_titles()}

Content:
---
{content}
---

Use {source} as the `source` value in any records you emit. Output JSONL or NO_NEW_FACTS."""

    model = mod.load_config().get("models", {}).get("ingest", "claude-haiku-4-5-20251001")
    cmd = [
        "claude", "-p", prompt,
        "--agent", "kb-extractor",
        "--model", model,
        "--no-session-persistence",
        "--max-budget-usd", "0.20",
    ]
    env = dict(os.environ)
    env["KB_CAPTURE_RUNNING"] = "1"

    print(f"Ingesting: {source}")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, env=env)
    if r.stderr:
        print(r.stderr[:500], file=sys.stderr)

    output = (r.stdout or "").strip()
    if not output or output == "NO_NEW_FACTS":
        print("No new facts to capture.")
        return

    cfg = mod.load_config()
    hashes = mod.load_json(mod.HASHES_PATH, {})
    tags_idx = mod.load_json(mod.TAGS_PATH, {})
    blocklist = cfg.get("blocklist_patterns", [])
    wrote_any = False
    for line in output.splitlines():
        line = line.strip()
        if not line or line == "NO_NEW_FACTS" or line.startswith("```"):
            continue
        try:
            import json as _j
            rec = _j.loads(line)
        except Exception:
            continue
        rec.setdefault("source", source)
        msg = mod.write_or_merge_note(rec, today, hashes, tags_idx, blocklist)
        print(msg)
        if msg.startswith(("wrote", "merged")):
            wrote_any = True

    mod.META_DIR.mkdir(parents=True, exist_ok=True)
    mod.save_json(mod.HASHES_PATH, hashes)
    mod.save_json(mod.TAGS_PATH, tags_idx)
    if wrote_any:
        mod.regenerate_index()
        print("INDEX regenerated.")


if __name__ == "__main__":
    main()