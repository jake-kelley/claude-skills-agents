#!/usr/bin/env python
"""Consolidate the second-brain: regen INDEX.md, rebuild metadata, report near-dupes."""
import hashlib
import json
import re
import sys
from pathlib import Path

KB_ROOT = Path.home() / ".claude" / "second-brain"
META_DIR = KB_ROOT / ".metadata"
HASHES_PATH = META_DIR / "hashes.json"
TAGS_PATH = META_DIR / "tags.json"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse(path):
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    m = FRONTMATTER_RE.match(text)
    title = path.stem
    tags = []
    body = text
    if m:
        body = text[m.end():]
        for line in m.group(1).splitlines():
            if line.startswith("title:"):
                title = line.split(":", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("tags:"):
                rest = line.split(":", 1)[1].strip().strip("[]")
                tags = [t.strip().strip('"').strip("'") for t in rest.split(",") if t.strip()]
    return {"path": path, "title": title, "tags": tags, "body": body}


def main():
    sections = {"concepts": [], "recipes": [], "references": [], "decisions": [], "tools": [], "domains": []}
    notes = []
    hashes = {}
    tags_idx = {}

    for md in KB_ROOT.rglob("*.md"):
        if md.name in ("README.md", "INDEX.md"):
            continue
        if any(p.startswith(".") for p in md.relative_to(KB_ROOT).parts):
            continue
        n = parse(md)
        if not n:
            continue
        rel = md.relative_to(KB_ROOT).as_posix()
        top = rel.split("/", 1)[0]
        if top in sections:
            sections[top].append((n["title"], rel))
        notes.append(n)
        body_hash = hashlib.sha256(n["body"].strip().encode("utf-8", errors="ignore")).hexdigest()[:16]
        if body_hash in hashes:
            print(f"NEAR-DUPE (same hash): {hashes[body_hash]} <-> {rel}")
        hashes[body_hash] = rel
        for t in n["tags"]:
            tags_idx.setdefault(t.lower(), [])
            if rel not in tags_idx[t.lower()]:
                tags_idx[t.lower()].append(rel)

    # near-dupe by title token similarity
    by_dir = {}
    for n in notes:
        d = n["path"].parent
        by_dir.setdefault(d, []).append(n)
    for d, ns in by_dir.items():
        for i, a in enumerate(ns):
            ta = set(a["path"].stem.split("-"))
            for b in ns[i + 1:]:
                tb = set(b["path"].stem.split("-"))
                if not ta or not tb:
                    continue
                ratio = len(ta & tb) / len(ta | tb)
                if ratio >= 0.7:
                    print(f"NEAR-DUPE (title): {a['path'].relative_to(KB_ROOT)} <-> {b['path'].relative_to(KB_ROOT)} (ratio={ratio:.2f})")

    # write metadata
    META_DIR.mkdir(parents=True, exist_ok=True)
    HASHES_PATH.write_text(json.dumps(hashes, indent=2, sort_keys=True), encoding="utf-8")
    TAGS_PATH.write_text(json.dumps(tags_idx, indent=2, sort_keys=True), encoding="utf-8")

    # rebuild INDEX
    lines = ["# Index", "", "_Auto-regenerated. Do not edit manually._", ""]
    for sec in ["concepts", "recipes", "references", "decisions", "tools", "domains"]:
        lines.append(f"## {sec}")
        lines.append("")
        if not sections[sec]:
            lines.append("_(none yet)_")
        else:
            for title, rel in sorted(sections[sec], key=lambda x: x[0].lower()):
                lines.append(f"- [{title}]({rel})")
        lines.append("")
    (KB_ROOT / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"\nConsolidated: {len(notes)} notes, {len(tags_idx)} tags. INDEX regenerated.")


if __name__ == "__main__":
    main()
