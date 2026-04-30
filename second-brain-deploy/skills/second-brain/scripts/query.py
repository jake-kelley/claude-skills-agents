#!/usr/bin/env python
"""Query the second-brain. Usage: query.py "<query>" [--limit N]"""
import argparse
import re
import sys
from pathlib import Path

KB_ROOT = Path.home() / ".claude" / "second-brain"

STOPWORDS = {
    "the","a","an","and","or","but","is","are","was","were","be","been","being",
    "have","has","had","do","does","did","of","in","on","at","to","from","by",
    "with","for","about","this","that","these","those","what","which","how",
    "when","where","why","i","you","my","your","our","their","its","as","if",
}
TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_\-]{1,}")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def tokenize(text):
    return {t.lower() for t in TOKEN_RE.findall(text or "") if len(t) > 2 and t.lower() not in STOPWORDS}


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


def score(note, qtok):
    if not qtok:
        return 0.0
    title_t = tokenize(note["title"])
    tag_t = {t.lower() for t in note["tags"]}
    body_t = tokenize(note["body"][:3000])
    return len(qtok & title_t) * 4 + len(qtok & tag_t) * 3 + len(qtok & body_t) * 1


def excerpt(body, qtok, n=180):
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    if not paras:
        return body[:n]
    best = max(paras, key=lambda p: len(tokenize(p) & qtok))
    snippet = re.sub(r"\s+", " ", best)
    return snippet[:n] + ("..." if len(snippet) > n else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="+")
    ap.add_argument("--limit", type=int, default=8)
    args = ap.parse_args()

    q = " ".join(args.query)
    qtok = tokenize(q)
    if not qtok:
        print("No searchable terms in query.", file=sys.stderr)
        sys.exit(1)

    notes = []
    for md in KB_ROOT.rglob("*.md"):
        if md.name in ("README.md", "INDEX.md"):
            continue
        if any(p.startswith(".") for p in md.relative_to(KB_ROOT).parts):
            continue
        n = parse(md)
        if not n:
            continue
        n["score"] = score(n, qtok)
        if n["score"] > 0:
            notes.append(n)

    notes.sort(key=lambda x: x["score"], reverse=True)
    notes = notes[:args.limit]

    if not notes:
        print(f"No notes match: {q}")
        sys.exit(0)

    for n in notes:
        rel = n["path"].relative_to(KB_ROOT).as_posix()
        print(f"- **{n['title']}** — `{rel}` — {excerpt(n['body'], qtok)}")


if __name__ == "__main__":
    main()