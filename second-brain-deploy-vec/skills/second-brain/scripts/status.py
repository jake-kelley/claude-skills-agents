#!/usr/bin/env python
"""Print second-brain status: counts, publish target, toggles, DB stats."""
import json
from pathlib import Path

import db

KB_ROOT = Path.home() / ".claude" / "second-brain"
CFG = KB_ROOT / ".config.json"


def main():
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    sections = ["concepts", "recipes", "references", "decisions", "tools", "domains"]
    print(f"KB at {KB_ROOT}\n")
    total = 0
    for sec in sections:
        d = KB_ROOT / sec
        n = sum(1 for _ in d.rglob("*.md")) if d.exists() else 0
        total += n
        print(f"  {sec:12} {n}")
    print(f"  {'TOTAL':12} {total}\n")

    # DB stats
    try:
        conn = db.connect()
        s = db.stats(conn)
        conn.close()
        if s["notes"] == total:
            sync_status = "(in sync)"
        elif s["notes"] == 0:
            sync_status = "(not initialized — run /second-brain reindex)"
        else:
            sync_status = f"(out of sync: {s['notes']} indexed vs {total} on disk — run /second-brain consolidate)"
        print(f"Vector DB at {db.DB_PATH}")
        print(f"  Indexed notes: {s['notes']} {sync_status}")
        print(f"  Chunks: {s['chunks']}")
        print(f"  Embeddings: {s['vectors']}")
        print(f"  Embedding model: BAAI/bge-small-en-v1.5 (384-dim, local)")
        print(f"  DB size: {s['db_size_mb']:.1f} MB\n")
    except Exception as e:
        print(f"Vector DB: not available ({e})\n")

    print(f"auto_capture: {cfg.get('auto_capture')}")
    print(f"auto_inject:  {cfg.get('auto_inject')}")
    models = cfg.get("models", {})
    print(f"extractor:    {models.get('extractor', 'claude-haiku-4-5-20251001')}")
    pub = cfg.get("publish", {})
    print(f"publish:      {pub.get('remote_url') or '(not configured)'}")


if __name__ == "__main__":
    main()