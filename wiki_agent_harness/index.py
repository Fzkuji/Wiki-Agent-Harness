"""SQLite FTS5 search over page slot text.

Stripped of the legacy wikilink graph table — link structure now lives in
the rendered HTML (``<a href>``) and the per-page meta ``related`` list,
neither of which needs a database.

Schema:
  wiki_fts(path UNINDEXED, title, template UNINDEXED, body)
      one row per content page (folder indexes are excluded).
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from . import store
from . import slots as _slots

_lock = threading.RLock()


@contextmanager
def _conn(db_path: Path) -> Iterator[sqlite3.Connection]:
    with _lock:
        c = sqlite3.connect(str(db_path))
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()


def init(db_path: Path) -> None:
    with _conn(db_path) as c:
        c.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5("
            "path UNINDEXED, title, template UNINDEXED, body, "
            "tokenize='porter unicode61')"
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS index_meta ("
            "key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )


def reindex_all(vault_root: Path, db_path: Path) -> int:
    init(db_path)
    with _conn(db_path) as c:
        c.execute("DELETE FROM wiki_fts")
        n = 0
        for path in store.iter_content_pages(vault_root):
            try:
                html = path.read_text(encoding="utf-8")
            except OSError:
                continue
            meta = _slots.read_meta(html)
            title = str(meta.get("title") or path.stem)
            template = str(meta.get("template") or "")
            body = _slots.slot_text(html)
            rel = str(path.relative_to(vault_root))
            c.execute(
                "INSERT INTO wiki_fts (path, title, template, body) VALUES (?,?,?,?)",
                (rel, title, template, body),
            )
            n += 1
        c.execute(
            "INSERT OR REPLACE INTO index_meta (key, value) VALUES "
            "('last_reindex', datetime('now'))"
        )
    return n


def update_page(path: Path, vault_root: Path, db_path: Path) -> None:
    if path.name == store.FOLDER_INDEX:
        return
    try:
        rel = str(path.relative_to(vault_root))
    except ValueError:
        return
    init(db_path)
    if not path.exists():
        with _conn(db_path) as c:
            c.execute("DELETE FROM wiki_fts WHERE path = ?", (rel,))
        return
    try:
        html = path.read_text(encoding="utf-8")
    except OSError:
        return
    meta = _slots.read_meta(html)
    title = str(meta.get("title") or path.stem)
    template = str(meta.get("template") or "")
    body = _slots.slot_text(html)
    with _conn(db_path) as c:
        c.execute("DELETE FROM wiki_fts WHERE path = ?", (rel,))
        c.execute(
            "INSERT INTO wiki_fts (path, title, template, body) VALUES (?,?,?,?)",
            (rel, title, template, body),
        )


def remove_page(path: Path, vault_root: Path, db_path: Path) -> None:
    try:
        rel = str(path.relative_to(vault_root))
    except ValueError:
        return
    init(db_path)
    with _conn(db_path) as c:
        c.execute("DELETE FROM wiki_fts WHERE path = ?", (rel,))


@dataclass
class Hit:
    path: str
    title: str
    template: str
    snippet: str
    score: float


def _sanitize(query: str) -> str:
    import re
    terms = [t for t in re.split(r"[^\w一-鿿]+", query) if t]
    if not terms:
        return ""
    return " OR ".join(terms)


def search(query: str, db_path: Path, limit: int = 5) -> list[Hit]:
    init(db_path)
    q = _sanitize(query)
    if not q:
        return []
    with _conn(db_path) as c:
        rows = c.execute(
            "SELECT path, title, template, "
            "snippet(wiki_fts, 3, '«', '»', '…', 16) AS snip, "
            "bm25(wiki_fts) AS score FROM wiki_fts WHERE wiki_fts MATCH ? "
            "ORDER BY score LIMIT ?",
            (q, limit),
        ).fetchall()
    return [
        Hit(r["path"], r["title"], r["template"] or "", r["snip"], -r["score"])
        for r in rows
    ]


def stats(db_path: Path) -> dict:
    init(db_path)
    with _conn(db_path) as c:
        n = c.execute("SELECT COUNT(*) FROM wiki_fts").fetchone()[0]
        last = c.execute(
            "SELECT value FROM index_meta WHERE key = 'last_reindex'"
        ).fetchone()
    return {"pages": n, "last_reindex": last[0] if last else None}
