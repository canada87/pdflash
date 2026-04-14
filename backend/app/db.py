from __future__ import annotations
import os
import sqlite3
from typing import Optional

_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS doc (
  id           INTEGER PRIMARY KEY,
  hash         TEXT UNIQUE NOT NULL,
  path         TEXT NOT NULL,
  title        TEXT,
  author       TEXT,
  page_count   INTEGER NOT NULL,
  size_bytes   INTEGER NOT NULL,
  mtime        INTEGER NOT NULL,
  added_at     INTEGER NOT NULL,
  status       TEXT NOT NULL,
  fail_reason  TEXT,
  blurhash     TEXT,
  outline_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_doc_status ON doc(status);
CREATE INDEX IF NOT EXISTS idx_doc_added  ON doc(added_at DESC);

CREATE TABLE IF NOT EXISTS progress (
  doc_id       INTEGER PRIMARY KEY REFERENCES doc(id) ON DELETE CASCADE,
  last_page    INTEGER NOT NULL DEFAULT 1,
  last_opened  INTEGER NOT NULL,
  pages_seen   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS bookmark (
  id           INTEGER PRIMARY KEY,
  doc_id       INTEGER NOT NULL REFERENCES doc(id) ON DELETE CASCADE,
  page         INTEGER NOT NULL,
  label        TEXT,
  created_at   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS tag (
  id   INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS doc_tag (
  doc_id INTEGER NOT NULL REFERENCES doc(id) ON DELETE CASCADE,
  tag_id INTEGER NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
  PRIMARY KEY (doc_id, tag_id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS page_fts USING fts5(
  doc_id UNINDEXED,
  page   UNINDEXED,
  text,
  tokenize = 'unicode61 remove_diacritics 2'
);
"""


def init_db(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def get_doc_by_hash(conn: sqlite3.Connection, doc_hash: str) -> Optional[dict]:
    row = conn.execute("SELECT * FROM doc WHERE hash = ?", (doc_hash,)).fetchone()
    return dict(row) if row else None


def upsert_doc(conn: sqlite3.Connection, data: dict) -> int:
    """Insert or update a doc record. Returns doc_id."""
    existing = conn.execute(
        "SELECT id FROM doc WHERE hash = ?", (data["hash"],)
    ).fetchone()

    if existing:
        doc_id = existing[0]
        conn.execute(
            """
            UPDATE doc
            SET path=?, title=?, author=?, page_count=?, size_bytes=?,
                mtime=?, status=?, fail_reason=NULL, blurhash=NULL, outline_json=?
            WHERE id=?
            """,
            (
                data["path"], data["title"], data["author"],
                data["page_count"], data["size_bytes"], data["mtime"],
                data["status"], data["outline_json"], doc_id,
            ),
        )
        # Clear stale FTS entries so they get repopulated
        conn.execute("DELETE FROM page_fts WHERE doc_id = ?", (doc_id,))
        conn.commit()
        return doc_id

    cur = conn.execute(
        """
        INSERT INTO doc (hash, path, title, author, page_count, size_bytes,
                         mtime, added_at, status, outline_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["hash"], data["path"], data["title"], data["author"],
            data["page_count"], data["size_bytes"], data["mtime"],
            data["added_at"], data["status"], data["outline_json"],
        ),
    )
    conn.commit()
    return cur.lastrowid


def update_doc_status(
    conn: sqlite3.Connection,
    doc_id: int,
    status: str,
    *,
    blurhash: str = None,
    fail_reason: str = None,
) -> None:
    conn.execute(
        "UPDATE doc SET status=?, blurhash=?, fail_reason=? WHERE id=?",
        (status, blurhash, fail_reason, doc_id),
    )
    conn.commit()


def insert_page_fts(
    conn: sqlite3.Connection, rows: list[tuple[int, int, str]]
) -> None:
    """rows: list of (doc_id, page_num, full_text)"""
    conn.executemany(
        "INSERT INTO page_fts (doc_id, page, text) VALUES (?, ?, ?)", rows
    )
    conn.commit()


def search_fts(
    conn: sqlite3.Connection,
    query: str,
    doc_id: int = None,
    limit: int = 50,
) -> list[dict]:
    snippet_expr = "snippet(page_fts, 2, '<b>', '</b>', '…', 20)"
    if doc_id is not None:
        rows = conn.execute(
            f"SELECT doc_id, page, {snippet_expr} AS snippet"
            " FROM page_fts WHERE doc_id=? AND text MATCH ? ORDER BY rank LIMIT ?",
            (doc_id, query, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT doc_id, page, {snippet_expr} AS snippet"
            " FROM page_fts WHERE text MATCH ? ORDER BY rank LIMIT ?",
            (query, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_docs(
    conn: sqlite3.Connection,
    status: str = "ready",
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM doc WHERE status=? ORDER BY added_at DESC LIMIT ? OFFSET ?",
        (status, limit, offset),
    ).fetchall()
    return [dict(r) for r in rows]


# ── Gallery / reader queries ──────────────────────────────────────────────────

_PROGRESS_COLS = """
    COALESCE(p.last_page, 1)  AS last_page,
    p.last_opened,
    COALESCE(p.pages_seen, 0) AS pages_seen,
    CAST(ROUND(100.0 * COALESCE(p.pages_seen, 0) / d.page_count) AS INTEGER)
        AS progress_pct
"""


def get_doc_by_id(conn: sqlite3.Connection, doc_id: int) -> Optional[dict]:
    row = conn.execute(
        f"""
        SELECT d.*, {_PROGRESS_COLS}
        FROM doc d
        LEFT JOIN progress p ON p.doc_id = d.id
        WHERE d.id = ?
        """,
        (doc_id,),
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["tags"] = _get_doc_tags(conn, doc_id)
    return d


def get_docs_gallery(
    conn: sqlite3.Connection,
    *,
    tag: str = None,
    q: str = None,
    sort: str = "recent",
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    where = ["d.status = 'ready'"]
    params: list = []

    if tag:
        where.append(
            "d.id IN (SELECT dt.doc_id FROM doc_tag dt"
            " JOIN tag t ON t.id = dt.tag_id WHERE t.name = ?)"
        )
        params.append(tag)

    if q:
        where.append("(d.title LIKE ? OR d.author LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]

    order = {
        "recent": "d.added_at DESC",
        "title": "d.title ASC COLLATE NOCASE",
        "progress": "progress_pct DESC",
    }.get(sort, "d.added_at DESC")

    sql = f"""
        SELECT d.*, {_PROGRESS_COLS},
               (SELECT GROUP_CONCAT(t.name, ',')
                FROM tag t JOIN doc_tag dt ON dt.tag_id = t.id
                WHERE dt.doc_id = d.id) AS tags_csv
        FROM doc d
        LEFT JOIN progress p ON p.doc_id = d.id
        WHERE {' AND '.join(where)}
        ORDER BY {order}
        LIMIT ? OFFSET ?
    """
    params += [limit, offset]
    rows = conn.execute(sql, params).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        csv = d.pop("tags_csv", None)
        d["tags"] = csv.split(",") if csv else []
        result.append(d)
    return result


def get_continue_reading(conn: sqlite3.Connection, limit: int = 6) -> list[dict]:
    rows = conn.execute(
        f"""
        SELECT d.id, d.hash, d.title, d.author, d.page_count, d.blurhash,
               {_PROGRESS_COLS}
        FROM progress p
        JOIN doc d ON d.id = p.doc_id
        WHERE d.status = 'ready' AND p.pages_seen < d.page_count
        ORDER BY p.last_opened DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_progress(conn: sqlite3.Connection, doc_id: int, page: int) -> None:
    import time as _t
    conn.execute(
        """
        INSERT INTO progress (doc_id, last_page, last_opened, pages_seen)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(doc_id) DO UPDATE SET
            last_page    = excluded.last_page,
            last_opened  = excluded.last_opened,
            pages_seen   = MAX(pages_seen, excluded.pages_seen)
        """,
        (doc_id, page, int(_t.time()), page),
    )
    conn.commit()


def delete_doc_from_db(conn: sqlite3.Connection, doc_id: int) -> None:
    conn.execute("DELETE FROM doc WHERE id = ?", (doc_id,))
    conn.commit()


def _get_doc_tags(conn: sqlite3.Connection, doc_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT t.name FROM tag t JOIN doc_tag dt ON dt.tag_id = t.id WHERE dt.doc_id = ?",
        (doc_id,),
    ).fetchall()
    return [r[0] for r in rows]


# ── Bookmarks ─────────────────────────────────────────────────────────────────

def get_bookmarks(conn: sqlite3.Connection, doc_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM bookmark WHERE doc_id = ? ORDER BY page", (doc_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def create_bookmark(
    conn: sqlite3.Connection, doc_id: int, page: int, label: Optional[str] = None
) -> dict:
    import time as _t
    cur = conn.execute(
        "INSERT INTO bookmark (doc_id, page, label, created_at) VALUES (?, ?, ?, ?)",
        (doc_id, page, label, int(_t.time())),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM bookmark WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def delete_bookmark(conn: sqlite3.Connection, bookmark_id: int) -> None:
    conn.execute("DELETE FROM bookmark WHERE id = ?", (bookmark_id,))
    conn.commit()


# ── Tags ──────────────────────────────────────────────────────────────────────

def get_all_tags(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM tag ORDER BY name COLLATE NOCASE").fetchall()
    return [dict(r) for r in rows]


def create_tag(conn: sqlite3.Connection, name: str) -> dict:
    try:
        cur = conn.execute("INSERT INTO tag (name) VALUES (?)", (name,))
        conn.commit()
        return {"id": cur.lastrowid, "name": name}
    except Exception:
        row = conn.execute("SELECT * FROM tag WHERE name = ?", (name,)).fetchone()
        return dict(row)


def delete_tag(conn: sqlite3.Connection, tag_id: int) -> None:
    conn.execute("DELETE FROM tag WHERE id = ?", (tag_id,))
    conn.commit()


def add_doc_tag(conn: sqlite3.Connection, doc_id: int, tag_id: int) -> None:
    try:
        conn.execute(
            "INSERT INTO doc_tag (doc_id, tag_id) VALUES (?, ?)", (doc_id, tag_id)
        )
        conn.commit()
    except Exception:
        pass  # already exists


def remove_doc_tag(conn: sqlite3.Connection, doc_id: int, tag_id: int) -> None:
    conn.execute(
        "DELETE FROM doc_tag WHERE doc_id = ? AND tag_id = ?", (doc_id, tag_id)
    )
    conn.commit()
