#!/usr/bin/env python
"""Stop hook: extract new settled facts from the just-finished turn.

Reads the recent transcript turns in Python, asks Haiku 4.5 (no tools) to emit
JSONL of new facts, then writes/merges Markdown notes deterministically.

Configured async in settings.json so the user is never blocked.
Recursion-guarded via KB_CAPTURE_RUNNING env var.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

KB_ROOT = Path.home() / ".claude" / "second-brain"
CONFIG_PATH = KB_ROOT / ".config.json"
META_DIR = KB_ROOT / ".metadata"
HASHES_PATH = META_DIR / "hashes.json"
TAGS_PATH = META_DIR / "tags.json"
LOG_PATH = Path.home() / ".claude" / "hooks" / "kb-capture.log"

VALID_CATEGORIES = {"concepts", "recipes", "references", "decisions", "tools", "domains"}
MAX_TRANSCRIPT_CHARS = 24000  # roughly 6k tokens of context for the extractor


def log(msg: str):
    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(msg.rstrip() + "\n")
    except Exception:
        pass


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, obj):
    try:
        path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")
    except Exception as e:
        log(f"save_json failed for {path}: {e!r}")


def load_config():
    return load_json(CONFIG_PATH, {})


def kebab(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", s.strip().lower()).strip("-")
    return s or "untitled"


def sha256_16(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()[:16]


def ulid_like(seed: str) -> str:
    h = hashlib.sha256(seed.encode("utf-8", errors="ignore")).hexdigest().upper()
    crockford = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    out = []
    for i in range(0, 26 * 2, 2):
        out.append(crockford[int(h[i:i + 2], 16) % 32])
    return "".join(out)


def read_transcript_excerpt(transcript_path: Path) -> str:
    """Return the most recent user+assistant exchange as readable text, capped."""
    try:
        lines = transcript_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception as e:
        log(f"transcript read failed: {e!r}")
        return ""

    msgs = []
    for line in lines:
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        t = obj.get("type")
        if t not in ("user", "assistant"):
            continue
        msg = obj.get("message") or {}
        role = msg.get("role") or t
        content = msg.get("content")
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text" and item.get("text"):
                        parts.append(item["text"])
            content = "\n".join(parts)
        if not isinstance(content, str) or not content.strip():
            continue
        msgs.append((role, content))

    # Take last few exchanges (up to MAX_TRANSCRIPT_CHARS, walking from the end)
    out = []
    total = 0
    for role, content in reversed(msgs):
        chunk = f"\n[{role}]\n{content}\n"
        if total + len(chunk) > MAX_TRANSCRIPT_CHARS and out:
            break
        out.append(chunk)
        total += len(chunk)
    out.reverse()
    return "".join(out).strip()


def existing_titles(limit: int = 200) -> str:
    titles = []
    if not KB_ROOT.exists():
        return "(none)"
    for md in KB_ROOT.rglob("*.md"):
        if md.name in ("README.md", "INDEX.md"):
            continue
        if any(part.startswith(".") for part in md.relative_to(KB_ROOT).parts):
            continue
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        title = md.stem
        for line in text.splitlines()[:20]:
            if line.startswith("title:"):
                title = line.split(":", 1)[1].strip().strip('"').strip("'")
                break
        rel = md.relative_to(KB_ROOT).as_posix()
        titles.append(f"- {title} ({rel})")
        if len(titles) >= limit:
            break
    return "\n".join(titles) if titles else "(none — KB is empty)"


def matches_blocklist(text: str, patterns) -> bool:
    for p in patterns or []:
        try:
            if re.search(p, text):
                return True
        except re.error:
            continue
    return False


def find_near_duplicate(target_dir: Path, title: str):
    """Return path of existing note with similar title, else None."""
    if not target_dir.exists():
        return None
    target_kebab = kebab(title)
    target_tokens = set(target_kebab.split("-"))
    if not target_tokens:
        return None
    best = None
    best_ratio = 0.0
    for md in target_dir.glob("*.md"):
        existing_tokens = set(md.stem.split("-"))
        if not existing_tokens:
            continue
        inter = len(target_tokens & existing_tokens)
        union = len(target_tokens | existing_tokens)
        ratio = inter / union if union else 0
        if ratio > best_ratio:
            best, best_ratio = md, ratio
    return best if best_ratio >= 0.7 else None


def write_or_merge_note(rec: dict, today: str, hashes: dict, tags_idx: dict, blocklist) -> str:
    category = rec.get("category", "")
    if category not in VALID_CATEGORIES:
        return f"skip: invalid category {category!r}"
    title = (rec.get("title") or "").strip()
    body = (rec.get("body") or "").strip()
    if not title or not body:
        return "skip: missing title or body"

    full_text = f"{title}\n{body}"
    if matches_blocklist(full_text, blocklist):
        return f"skip: blocklist match for {title!r}"

    body_hash = sha256_16(body)
    if body_hash in hashes:
        return f"skip: duplicate hash for {title!r}"

    if category == "domains":
        sub = kebab(rec.get("subtopic") or "general")
        target_dir = KB_ROOT / "domains" / sub
    else:
        target_dir = KB_ROOT / category
    target_dir.mkdir(parents=True, exist_ok=True)

    fname = kebab(title) + ".md"
    fpath = target_dir / fname

    near = find_near_duplicate(target_dir, title)
    if near and near != fpath:
        try:
            existing = near.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            existing = ""
        update_block = f"\n\n## Update {today}\n\n{body}\n"
        new_text = existing.rstrip() + update_block
        new_text = re.sub(r"^updated:.*$", f"updated: {today}", new_text, count=1, flags=re.MULTILINE)
        near.write_text(new_text, encoding="utf-8")
        hashes[body_hash] = near.relative_to(KB_ROOT).as_posix()
        return f"merged into {near.relative_to(KB_ROOT).as_posix()}"

    if fpath.exists():
        return f"skip: file exists {fpath.name}"

    tags = rec.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    tags = [str(t).strip().lower() for t in tags if str(t).strip()][:8]

    source = rec.get("source") or "transcript:unknown"

    nid = ulid_like(title + body_hash)
    fm_tags = "[" + ", ".join(tags) + "]"
    frontmatter = (
        "---\n"
        f"id: {nid}\n"
        f"title: {title}\n"
        f"tags: {fm_tags}\n"
        f"source: {source}\n"
        f"created: {today}\n"
        f"updated: {today}\n"
        f"hash: {body_hash}\n"
        "---\n\n"
    )
    fpath.write_text(frontmatter + body.rstrip() + "\n", encoding="utf-8")

    hashes[body_hash] = fpath.relative_to(KB_ROOT).as_posix()
    rel = fpath.relative_to(KB_ROOT).as_posix()
    for t in tags:
        tags_idx.setdefault(t, [])
        if rel not in tags_idx[t]:
            tags_idx[t].append(rel)
    return f"wrote {rel}"


def regenerate_index():
    sections = {
        "concepts": [], "recipes": [], "references": [],
        "decisions": [], "tools": [], "domains": [],
    }
    for md in KB_ROOT.rglob("*.md"):
        if md.name in ("README.md", "INDEX.md"):
            continue
        if any(part.startswith(".") for part in md.relative_to(KB_ROOT).parts):
            continue
        rel = md.relative_to(KB_ROOT).as_posix()
        top = rel.split("/", 1)[0]
        if top not in sections:
            continue
        title = md.stem
        try:
            for line in md.read_text(encoding="utf-8", errors="ignore").splitlines()[:20]:
                if line.startswith("title:"):
                    title = line.split(":", 1)[1].strip().strip('"').strip("'")
                    break
        except Exception:
            pass
        sections[top].append((title, rel))

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


EXTRACTOR_PROMPT = """Extract new settled knowledge from this transcript excerpt.

Session id: {session_id}
Today: {today}

Existing note titles (do NOT duplicate — match by topic, not exact wording):
{existing_titles}

Transcript excerpt (most recent turns):
---
{transcript_excerpt}
---

Follow your agent rules. Output JSONL records or the single line NO_NEW_FACTS. Nothing else.
"""


def main():
    if os.environ.get("KB_CAPTURE_RUNNING"):
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except Exception:
        log("kb-capture: bad stdin JSON")
        sys.exit(0)

    cfg = load_config()
    if not cfg.get("auto_capture", True):
        sys.exit(0)

    transcript_path_s = data.get("transcript_path") or ""
    session_id = data.get("session_id") or "unknown"
    if not transcript_path_s:
        sys.exit(0)
    transcript_path = Path(transcript_path_s)
    if not transcript_path.exists():
        log(f"kb-capture: no transcript at {transcript_path_s}")
        sys.exit(0)

    excerpt = read_transcript_excerpt(transcript_path)
    if not excerpt or len(excerpt) < 200:
        log("kb-capture: transcript too short, skipping")
        sys.exit(0)

    today = date.today().isoformat()
    prompt = EXTRACTOR_PROMPT.format(
        session_id=session_id,
        today=today,
        existing_titles=existing_titles(),
        transcript_excerpt=excerpt,
    )

    model = cfg.get("models", {}).get("extractor", "claude-haiku-4-5-20251001")

    cmd = [
        "claude",
        "-p", prompt,
        "--agent", "kb-extractor",
        "--model", model,
        "--no-session-persistence",
        "--max-budget-usd", "0.10",
    ]

    env = dict(os.environ)
    env["KB_CAPTURE_RUNNING"] = "1"

    log(f"kb-capture: spawning extractor for session {session_id}, excerpt={len(excerpt)} chars")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300, check=False, env=env,
            encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        log("kb-capture: timeout after 300s")
        sys.exit(0)
    except FileNotFoundError:
        log("kb-capture: 'claude' CLI not on PATH")
        sys.exit(0)
    except Exception as e:
        log(f"kb-capture: subprocess exception {e!r}")
        sys.exit(0)

    log(f"kb-capture: extractor exit={result.returncode} stdout_len={len(result.stdout or '')} stderr_len={len(result.stderr or '')}")
    if result.stderr:
        log(f"kb-capture: stderr: {result.stderr[:500]}")

    output = (result.stdout or "").strip()
    if not output or output == "NO_NEW_FACTS":
        log("kb-capture: no new facts")
        sys.exit(0)

    hashes = load_json(HASHES_PATH, {})
    tags_idx = load_json(TAGS_PATH, {})
    blocklist = cfg.get("blocklist_patterns", [])

    wrote_any = False
    for line in output.splitlines():
        line = line.strip()
        if not line or line == "NO_NEW_FACTS":
            continue
        # Tolerate fenced code blocks the model might wrap output in
        if line.startswith("```"):
            continue
        try:
            rec = json.loads(line)
        except Exception:
            log(f"kb-capture: bad JSONL line: {line[:200]}")
            continue
        result_msg = write_or_merge_note(rec, today, hashes, tags_idx, blocklist)
        log(f"kb-capture: {result_msg}")
        if result_msg.startswith(("wrote", "merged")):
            wrote_any = True

    META_DIR.mkdir(parents=True, exist_ok=True)
    save_json(HASHES_PATH, hashes)
    save_json(TAGS_PATH, tags_idx)

    if wrote_any:
        try:
            regenerate_index()
            log("kb-capture: index regenerated")
        except Exception as e:
            log(f"kb-capture: index regen failed {e!r}")

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"kb-capture: fatal {e!r}")
        sys.exit(0)
