"""Shared text utilities for second-brain skill and hooks."""
import re
from pathlib import Path

KB_ROOT = Path.home() / ".claude" / "second-brain"

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


def tokenize(text: str) -> set:
    """Extract tokens from text: min 3 chars, no stopwords, lowercase."""
    return {t.lower() for t in TOKEN_RE.findall(text or "")
            if len(t) > 2 and t.lower() not in STOPWORDS}


def parse_frontmatter(path: Path) -> dict:
    """Parse a note from a .md file. Returns dict with title, tags, body.
    Returns None if file cannot be read."""
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


def best_excerpt(body: str, query_tokens: set, n_chars: int = 180) -> str:
    """Extract the best excerpt from body based on query token overlap.
    Returns first n_chars of the best matching paragraph."""
    if not body:
        return ""

    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    if not paras:
        return body[:n_chars].strip()

    best, best_score = paras[0], -1
    for p in paras:
        s = len(tokenize(p) & query_tokens)
        if s > best_score:
            best, best_score = p, s

    snippet = re.sub(r"\s+", " ", best)
    if len(snippet) > n_chars:
        snippet = snippet[:n_chars].rsplit(" ", 1)[0] + "..."
    return snippet
