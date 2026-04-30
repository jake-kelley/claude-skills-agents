#!/usr/bin/env python
"""UserPromptSubmit hook: search second-brain and inject relevant notes.

Reads hook input JSON from stdin, scores notes by keyword overlap with the
user's prompt, emits the top-N as additionalContext. Must be fast and silent.
"""
import json
import os
import re
import sys
from pathlib import Path

KB_ROOT = Path.home() / ".claude" / "second-brain"
CONFIG_PATH = KB_ROOT / ".config.json"

STOPWORDS = {
    "the","a","an","and","or","but","is","are","was","were","be","been","being",
    "have","has","had","do","does","did","will","would","could","should","may",
    "might","must","shall","can","of","in","on","at","to","from","by","with",
    "for","about","against","between","into","through","during","before","after",
    "above","below","up","down","out","off","over","under","again","further",
    "then","once","this","that","these","those","i","you","he","she","it","we",
    "they","what","which","who","whom","whose","why","how","when","where","not",
    "no","yes","just","only","very","so","too","also","like","than","my","your",
    "their","our","its","as","if","because","while","there","here","any","some",
    "all","each","every","both","few","more","most","other","such","own","same",
    "want","need","use","using","get","make","let","please","thanks"
}

TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_\-]{1,}")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def load_config():
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def tokenize(text: str) -> set:
    return {t.lower() for t in TOKEN_RE.findall(text or "") if len(t) > 2 and t.lower() not in STOPWORDS}


def parse_note(path: Path):
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    m = FRONTMATTER_RE.match(text)
    title = path.stem
    tags = []
    body = text
    if m:
        fm = m.group(1)
        body = text[m.end():]
        for line in fm.splitlines():
            if line.startswith("title:"):
                title = line.split(":", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("tags:"):
                rest = line.split(":", 1)[1].strip()
                tags = [t.strip().strip('"').strip("'") for t in rest.strip("[]").split(",") if t.strip()]
    return {"path": path, "title": title, "tags": tags, "body": body}


def score(note, query_tokens: set) -> float:
    if not query_tokens:
        return 0.0
    title_tokens = tokenize(note["title"])
    tag_tokens = {t.lower() for t in note["tags"]}
    body_tokens = tokenize(note["body"][:2000])
    title_hit = len(query_tokens & title_tokens) * 4.0
    tag_hit = len(query_tokens & tag_tokens) * 3.0
    body_hit = len(query_tokens & body_tokens) * 1.0
    return title_hit + tag_hit + body_hit


def excerpt(body: str, query_tokens: set, n: int) -> str:
    if not body:
        return ""
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    if not paras:
        return body[:n].strip()
    best, best_score = paras[0], -1
    for p in paras:
        s = len(tokenize(p) & query_tokens)
        if s > best_score:
            best, best_score = p, s
    snippet = re.sub(r"\s+", " ", best)
    if len(snippet) > n:
        snippet = snippet[:n].rsplit(" ", 1)[0] + "..."
    return snippet


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if data.get("hook_event_name") not in (None, "UserPromptSubmit"):
        sys.exit(0)

    cfg = load_config()
    if not cfg.get("auto_inject", True):
        sys.exit(0)
    if not KB_ROOT.exists():
        sys.exit(0)

    prompt = data.get("prompt", "") or ""
    qtok = tokenize(prompt)
    if len(qtok) < 1:
        sys.exit(0)

    rcfg = cfg.get("retrieval", {})
    max_notes = int(rcfg.get("max_notes", 5))
    excerpt_chars = int(rcfg.get("excerpt_chars", 200))
    max_total = int(rcfg.get("max_total_chars", 8000))

    notes = []
    for md in KB_ROOT.rglob("*.md"):
        if md.name in ("README.md", "INDEX.md"):
            continue
        if any(part.startswith(".") for part in md.relative_to(KB_ROOT).parts):
            continue
        n = parse_note(md)
        if not n:
            continue
        n["score"] = score(n, qtok)
        if n["score"] > 0:
            notes.append(n)

    notes.sort(key=lambda x: x["score"], reverse=True)
    notes = notes[:max_notes]
    if not notes:
        sys.exit(0)

    lines = ["The following notes from your second-brain knowledge base may be relevant:"]
    total = len(lines[0])
    for n in notes:
        rel = n["path"].relative_to(KB_ROOT).as_posix()
        snippet = excerpt(n["body"], qtok, excerpt_chars)
        block = f"\n- **{n['title']}** (`{rel}`): {snippet}"
        if total + len(block) > max_total:
            break
        lines.append(block)
        total += len(block)
    lines.append("\n_Cite a note path if you use its content. Verify before relying on age-sensitive facts._")

    out = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": "".join(lines),
        }
    }
    print(json.dumps(out))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
