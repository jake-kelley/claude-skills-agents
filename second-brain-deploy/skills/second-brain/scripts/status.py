#!/usr/bin/env python
"""Print second-brain status: counts, publish target, toggles."""
import json
from pathlib import Path

KB_ROOT = Path.home() / ".claude" / "second-brain"
CFG = KB_ROOT / ".config.json"


def main():
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    sections = ["concepts", "recipes", "references", "decisions", "tools", "domains"]
    print(f"Second brain: {KB_ROOT}\n")
    total = 0
    for sec in sections:
        d = KB_ROOT / sec
        n = sum(1 for _ in d.rglob("*.md")) if d.exists() else 0
        total += n
        print(f"  {sec:12} {n}")
    print(f"  {'TOTAL':12} {total}\n")
    print(f"auto_capture: {cfg.get('auto_capture')}")
    print(f"auto_inject:  {cfg.get('auto_inject')}")
    print(f"extractor:    {cfg.get('extractor_model')}")
    pub = cfg.get("publish", {})
    print(f"publish:      {pub.get('remote_url') or '(not configured)'}")


if __name__ == "__main__":
    main()