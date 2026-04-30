#!/usr/bin/env python
"""Query the second-brain via hybrid vector+FTS search.

Usage: python query.py "<query>" [--limit N]
"""
import argparse
import sys

import db
import embed
from _rrf import reciprocal_rank_fusion
from _text import KB_ROOT, tokenize, best_excerpt


def main():
    parser = argparse.ArgumentParser(description="Search the second-brain KB")
    parser.add_argument("query", nargs="+", help="Search query")
    parser.add_argument("--limit", type=int, default=8, help="Max results")
    args = parser.parse_args()

    q = " ".join(args.query)
    qtok = tokenize(q)
    if not qtok:
        print("No searchable terms in query.", file=sys.stderr)
        sys.exit(1)

    # Open DB
    try:
        conn = db.connect()
    except Exception as e:
        print(f"DB not initialized. Run: python {KB_ROOT}/../skills/second-brain/scripts/reindex.py", file=sys.stderr)
        sys.exit(2)

    # Hybrid search: BM25 + vector
    try:
        q_vec = embed.embed_query(q)
    except Exception as e:
        print(f"Embedding failed: {e}", file=sys.stderr)
        sys.exit(2)

    fts_hits = db.fts_search(conn, q, limit=50)
    vec_hits = db.vec_search(conn, q_vec, limit=50)

    # Convert to ranked lists for RRF
    fts_ranked = [nid for nid, _ in fts_hits]
    vec_ranked = [nid for nid, _ in vec_hits]
    fused = reciprocal_rank_fusion([fts_ranked, vec_ranked], k=60)
    top_ids = [nid for nid, _ in fused[:args.limit]]

    if not top_ids:
        print(f"No notes match: {q}")
        sys.exit(0)

    # Fetch and display
    notes = db.fetch_notes_by_id(conn, top_ids)
    notes_by_id = {n["id"]: n for n in notes}

    for nid in top_ids:
        n = notes_by_id[nid]
        excerpt = best_excerpt(n["body"], qtok, n_chars=180)
        print(f"- **{n['title']}** — `{n['path']}` — {excerpt}")

    conn.close()


if __name__ == "__main__":
    main()