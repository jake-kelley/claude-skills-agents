#!/usr/bin/env python
"""Reindex the KB: rebuild the vector database from Markdown source.

Usage: python reindex.py [--force]

  --force   Drop and recreate the DB before reindexing. Default: incremental
            by content_hash (only re-embeds changed notes).
"""
import argparse
import hashlib
import os
import sys
import time
from pathlib import Path

import db
import embed
from _text import KB_ROOT, parse_frontmatter


def content_hash(body: str) -> str:
    """SHA256 of body, first 16 chars (matches .metadata/hashes.json scheme)."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def walk_notes():
    """Walk KB and yield (rel_path, Path) for all notes."""
    for md in KB_ROOT.rglob("*.md"):
        if md.name in ("README.md", "INDEX.md"):
            continue
        if any(p.startswith(".") for p in md.relative_to(KB_ROOT).parts):
            continue
        rel_path = md.relative_to(KB_ROOT).as_posix()
        yield rel_path, md


def sync_one(conn, rel_path: str, md_path: Path, force: bool = False) -> tuple[bool, int, int]:
    """Index a single note. Returns (changed, chunks, embeddings)."""
    parsed = parse_frontmatter(md_path)
    if not parsed:
        return False, 0, 0

    title = parsed["title"]
    tags = parsed["tags"]
    body = parsed["body"]
    mtime = md_path.stat().st_mtime
    cat = rel_path.split("/")[0]  # category is first path component

    h = content_hash(body)
    old_h = db.get_note_hash(conn, rel_path)

    # If hash matches and not forced, skip
    if not force and old_h == h:
        return False, 0, 0

    # Upsert note
    note_id = db.upsert_note(
        conn,
        path=rel_path,
        title=title,
        category=cat,
        tags=tags,
        body=body,
        mtime=mtime,
        content_hash=h
    )

    # Chunk and embed
    chunks = embed.chunk_text(body)
    try:
        embeddings = embed.embed_texts(chunks)
    except Exception as e:
        print(f"  ERROR embedding {rel_path}: {e}", file=sys.stderr)
        return False, 0, 0

    # Replace chunks
    db.replace_chunks(conn, note_id, chunks, embeddings)

    return True, len(chunks), len(embeddings)


def main():
    parser = argparse.ArgumentParser(description="Reindex the KB")
    parser.add_argument("--force", action="store_true", help="Drop and recreate DB")
    args = parser.parse_args()

    conn = db.connect()

    # If forced, drop chunks/vectors (notes stay for now, will be reindexed)
    if args.force:
        print("Dropping existing chunks and vectors...")
        conn.execute("DELETE FROM chunks")
        conn.execute("DELETE FROM chunks_vec")
        conn.commit()

    # Walk notes and sync
    disk_notes = {}  # rel_path -> Path
    for rel_path, md_path in walk_notes():
        disk_notes[rel_path] = md_path

    print(f"Scanning {len(disk_notes)} notes...")
    start_time = time.time()

    stats = {"new": 0, "updated": 0, "deleted": 0, "skipped": 0, "chunks": 0, "errors": 0}

    # Index notes from disk
    for i, (rel_path, md_path) in enumerate(disk_notes.items(), 1):
        changed, chunks, vecs = sync_one(conn, rel_path, md_path, force=args.force)
        if changed:
            if db.get_note_hash(conn, rel_path) == content_hash(md_path.read_text()):
                # If old_hash was None, it's new
                old_h = db.get_note_hash(conn, rel_path)
                if old_h is None:
                    stats["new"] += 1
                else:
                    stats["updated"] += 1
            stats["chunks"] += chunks
            print(f"  [{i}/{len(disk_notes)}] indexed: {rel_path} ({chunks} chunks)")
        else:
            stats["skipped"] += 1

    # Detect deletions: notes in DB but not on disk
    db_notes = conn.execute("SELECT path FROM notes").fetchall()
    for row in db_notes:
        db_path = row["path"]
        if db_path not in disk_notes:
            db.delete_note(conn, db_path)
            stats["deleted"] += 1
            print(f"  deleted: {db_path}")

    elapsed = time.time() - start_time
    print(f"\nIndexed {stats['new']} new, {stats['updated']} updated, "
          f"{stats['deleted']} deleted, {stats['skipped']} skipped "
          f"({stats['chunks']} chunks) in {elapsed:.1f}s")

    conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Reindex failed: {e}", file=sys.stderr)
        sys.exit(1)
