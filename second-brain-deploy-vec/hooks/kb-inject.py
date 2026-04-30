#!/usr/bin/env python
"""UserPromptSubmit hook: search second-brain via hybrid vector+FTS and inject relevant notes.

Reads hook input JSON from stdin. Must be fast and silent (10s timeout).
"""
import json
import logging
import sys
from pathlib import Path

KB_ROOT = Path.home() / ".claude" / "second-brain"
CONFIG_PATH = KB_ROOT / ".config.json"
LOG_PATH = Path.home() / ".claude" / "hooks" / "kb-inject.log"

# Setup logging (silent, file only)
logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.WARNING,
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


def load_config():
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def log_error(msg: str):
    logging.error(msg)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    if data.get("hook_event_name") not in (None, "UserPromptSubmit"):
        return

    cfg = load_config()
    if not cfg.get("auto_inject", True):
        return

    if not KB_ROOT.exists():
        return

    prompt = data.get("prompt", "") or ""
    if len(prompt.strip()) < 3:
        return

    # Hybrid retrieval via vector DB
    try:
        # Import here to defer loading until needed
        sys.path.insert(0, str(KB_ROOT / ".." / ".." / "skills" / "second-brain" / "scripts"))
        import db
        import embed
        from _rrf import reciprocal_rank_fusion
        from _text import best_excerpt, tokenize

        conn = db.connect()
        q_vec = embed.embed_query(prompt)
        qtok = tokenize(prompt)

        # Hybrid search
        fts = [nid for nid, _ in db.fts_search(conn, prompt, limit=30)]
        vec = [nid for nid, _ in db.vec_search(conn, q_vec, limit=30)]
        fused = reciprocal_rank_fusion([fts, vec], k=60)

        rcfg = cfg.get("retrieval", {})
        max_notes = int(rcfg.get("max_notes", 5))
        min_rrf = float(rcfg.get("min_rrf_score", 1.0 / (60 + 5 + 1)))

        candidates = [(nid, s) for nid, s in fused if s >= min_rrf][:max_notes]
        if not candidates:
            conn.close()
            return

        notes = db.fetch_notes_by_id(conn, [nid for nid, _ in candidates])
        conn.close()
    except Exception as e:
        log_error(f"Retrieval failed: {e}")
        return

    # Build additionalContext
    excerpt_chars = int(cfg.get("retrieval", {}).get("excerpt_chars", 200))
    max_total = int(cfg.get("retrieval", {}).get("max_total_chars", 8000))

    lines = ["The following notes from your second-brain knowledge base may be relevant:"]
    total = len(lines[0])

    for n in notes:
        snippet = best_excerpt(n["body"], qtok, n_chars=excerpt_chars)
        block = f"\n- **{n['title']}** (`{n['path']}`): {snippet}"
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


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
