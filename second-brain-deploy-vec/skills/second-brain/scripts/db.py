"""SQLite vector database for second-brain KB.

Manages the sqlite-vec index at ~/.claude/second-brain/.db/index.sqlite.
Markdown files in ~/.claude/second-brain/ remain the source of truth.
"""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

KB_ROOT = Path.home() / ".claude" / "second-brain"
DB_DIR = KB_ROOT / ".db"
DB_PATH = DB_DIR / "index.sqlite"

# Try to import sqlite_vec; fail loudly if missing (needed for KNN)
try:
    import sqlite_vec
except ImportError:
    print("Error: sqlite-vec not installed. Run: pip install sqlite-vec", file=sys.stderr)
    raise


def _ensure_db_dir():
    """Create .db directory if missing."""
    DB_DIR.mkdir(parents=True, exist_ok=True)


def connect() -> sqlite3.Connection:
    """Open DB connection, load sqlite-vec extension, ensure schema. Idempotent."""
    _ensure_db_dir()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # Load sqlite-vec extension
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)

    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection):
    """Create tables if they don't exist."""
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS notes (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        path            TEXT NOT NULL UNIQUE,
        title           TEXT NOT NULL,
        category        TEXT NOT NULL,
        tags_json       TEXT NOT NULL DEFAULT '[]',
        body            TEXT NOT NULL,
        mtime           REAL NOT NULL,
        content_hash    TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_notes_hash ON notes(content_hash);
    CREATE INDEX IF NOT EXISTS idx_notes_category ON notes(category);

    CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
        title, body,
        content='notes',
        content_rowid='id',
        tokenize='porter unicode61'
    );

    CREATE TABLE IF NOT EXISTS chunks (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        note_id     INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
        chunk_idx   INTEGER NOT NULL,
        text        TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_chunks_note ON chunks(note_id);

    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec USING vec0(
        chunk_id    INTEGER PRIMARY KEY,
        embedding   FLOAT[384]
    );

    CREATE TABLE IF NOT EXISTS schema_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
        INSERT INTO notes_fts(rowid, title, body) VALUES (new.id, new.title, new.body);
    END;
    CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
        INSERT INTO notes_fts(notes_fts, rowid, title, body) VALUES ('delete', old.id, old.title, old.body);
    END;
    CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
        INSERT INTO notes_fts(notes_fts, rowid, title, body) VALUES ('delete', old.id, old.title, old.body);
        INSERT INTO notes_fts(rowid, title, body) VALUES (new.id, new.title, new.body);
    END;
    """)

    # Initialize schema metadata
    conn.execute(
        "INSERT OR IGNORE INTO schema_meta (key, value) VALUES (?, ?)",
        ("version", "1")
    )
    conn.execute(
        "INSERT OR IGNORE INTO schema_meta (key, value) VALUES (?, ?)",
        ("embedding_model", "BAAI/bge-small-en-v1.5")
    )
    conn.execute(
        "INSERT OR IGNORE INTO schema_meta (key, value) VALUES (?, ?)",
        ("embedding_dim", "384")
    )
    conn.commit()


def upsert_note(conn: sqlite3.Connection, *, path: str, title: str,
                category: str, tags: list, body: str, mtime: float,
                content_hash: str) -> int:
    """Insert or update a note. Returns note ID. If content_hash is new,
    the caller should re-chunk and re-embed."""
    tags_json = json.dumps(tags)
    cursor = conn.execute(
        """INSERT OR REPLACE INTO notes
        (path, title, category, tags_json, body, mtime, content_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (path, title, category, tags_json, body, mtime, content_hash)
    )
    conn.commit()
    return cursor.lastrowid


def get_note_hash(conn: sqlite3.Connection, path: str) -> str | None:
    """Return the current content_hash for a note, or None if not indexed."""
    row = conn.execute(
        "SELECT content_hash FROM notes WHERE path = ?",
        (path,)
    ).fetchone()
    return row["content_hash"] if row else None


def delete_note(conn: sqlite3.Connection, path: str) -> None:
    """Delete a note and its chunks/vectors by path."""
    conn.execute("DELETE FROM notes WHERE path = ?", (path,))
    conn.commit()


def replace_chunks(conn: sqlite3.Connection, note_id: int,
                   chunks: list[str], embeddings: list[list[float]]) -> None:
    """Atomically replace all chunks + vectors for a note."""
    # Delete old chunks (cascades to vectors)
    conn.execute("DELETE FROM chunks WHERE note_id = ?", (note_id,))

    # Insert new chunks and vectors
    for chunk_idx, (text, embedding) in enumerate(zip(chunks, embeddings)):
        cursor = conn.execute(
            "INSERT INTO chunks (note_id, chunk_idx, text) VALUES (?, ?, ?)",
            (note_id, chunk_idx, text)
        )
        chunk_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO chunks_vec (chunk_id, embedding) VALUES (?, ?)",
            (chunk_id, embedding)
        )

    conn.commit()


def fts_search(conn: sqlite3.Connection, query: str, limit: int = 50
               ) -> list[tuple[int, float]]:
    """BM25 search. Returns [(note_id, bm25_score)]."""
    rows = conn.execute(
        """SELECT rowid, rank FROM notes_fts
        WHERE notes_fts MATCH ?
        ORDER BY rank
        LIMIT ?""",
        (query, limit)
    ).fetchall()
    # FTS5 rank is negative; negate for descending score
    return [(row["rowid"], -row["rank"]) for row in rows]


def vec_search(conn: sqlite3.Connection, query_embedding: list[float],
               limit: int = 50) -> list[tuple[int, float]]:
    """Vector KNN search. Returns [(note_id, min_distance)] aggregated to note level."""
    import struct
    # Serialize query embedding to binary format
    query_bytes = struct.pack('f' * len(query_embedding), *query_embedding)

    # Query vec0 for closest embeddings
    rows = conn.execute(
        """SELECT chunk_id, distance FROM chunks_vec
        WHERE embedding MATCH ?
        ORDER BY distance
        LIMIT ?""",
        (query_bytes, limit * 3)  # Get extra results to ensure coverage
    ).fetchall()

    # Map chunks back to notes and aggregate by min distance
    note_scores = {}
    for row in rows:
        chunk_id = row["chunk_id"]
        distance = row["distance"]
        note_id = conn.execute(
            "SELECT note_id FROM chunks WHERE id = ?",
            (chunk_id,)
        ).fetchone()["note_id"]
        if note_id not in note_scores:
            note_scores[note_id] = distance
        else:
            note_scores[note_id] = min(note_scores[note_id], distance)

    # Sort by distance (ascending, so lower/closer is better) and limit
    sorted_results = sorted(note_scores.items(), key=lambda x: x[1])
    return sorted_results[:limit]


def fetch_notes_by_id(conn: sqlite3.Connection, note_ids: list[int]) -> list[dict]:
    """Fetch note rows as dicts given a list of IDs. Preserves order."""
    placeholders = ",".join("?" * len(note_ids))
    rows = conn.execute(
        f"SELECT id, path, title, category, tags_json, body FROM notes WHERE id IN ({placeholders})",
        note_ids
    ).fetchall()

    # Rebuild dict preserving input order
    result = []
    id_to_row = {row["id"]: row for row in rows}
    for nid in note_ids:
        if nid in id_to_row:
            row = id_to_row[nid]
            result.append({
                "id": row["id"],
                "path": row["path"],
                "title": row["title"],
                "category": row["category"],
                "tags": json.loads(row["tags_json"]),
                "body": row["body"]
            })

    return result


def stats(conn: sqlite3.Connection) -> dict:
    """Return DB statistics."""
    note_count = conn.execute("SELECT COUNT(*) as c FROM notes").fetchone()["c"]
    chunk_count = conn.execute("SELECT COUNT(*) as c FROM chunks").fetchone()["c"]
    vec_count = conn.execute("SELECT COUNT(*) as c FROM chunks_vec").fetchone()["c"]
    db_size_mb = DB_PATH.stat().st_size / (1024 * 1024)

    return {
        "notes": note_count,
        "chunks": chunk_count,
        "vectors": vec_count,
        "db_size_mb": round(db_size_mb, 2)
    }
