"""SQLite FTS5 index over the wiki vault — BM25 search + wikilink graph.

Two persistent structures:

* ``wiki_fts(path, title, type, body)`` — one row per content .md page.
  ``path`` is relative to the vault root.
* ``wiki_links(src_path, target_name)`` — one row per [[wikilink]] occurrence.
  Enables O(rows) backlink / outbound lookups without full vault scans.

All functions accept an explicit ``db_path: Path`` so the index is
portable across vaults.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .helpers import parse_frontmatter, extract_wikilinks
from . import store as _store

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
    """Create tables if they don't exist."""
    with _conn(db_path) as c:
        c.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5("
            "path UNINDEXED, title, type UNINDEXED, body, "
            "tokenize='porter unicode61')"
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS wiki_links ("
            "src_path TEXT NOT NULL, "
            "target_name TEXT NOT NULL, "
            "PRIMARY KEY (src_path, target_name))"
        )
        c.execute("CREATE INDEX IF NOT EXISTS wiki_links_target ON wiki_links(target_name)")
        c.execute("CREATE INDEX IF NOT EXISTS wiki_links_src ON wiki_links(src_path)")
        c.execute(
            "CREATE TABLE IF NOT EXISTS index_meta ("
            "key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )


def reindex_all(vault_root: Path, db_path: Path) -> int:
    """Full reindex of the vault. Returns the number of pages indexed."""
    init(db_path)
    with _conn(db_path) as c:
        c.execute("DELETE FROM wiki_fts")
        c.execute("DELETE FROM wiki_links")
        n = 0
        for path in _store.iter_pages(vault_root):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            fm, body = parse_frontmatter(text)
            t = fm.get("type") or ""
            rel = str(path.relative_to(vault_root))
            c.execute(
                "INSERT INTO wiki_fts (path, title, type, body) VALUES (?,?,?,?)",
                (rel, path.stem, str(t), body),
            )
            for target in extract_wikilinks(body):
                c.execute(
                    "INSERT OR IGNORE INTO wiki_links (src_path, target_name) "
                    "VALUES (?, ?)", (rel, target.lower()),
                )
            n += 1
        c.execute(
            "INSERT OR REPLACE INTO index_meta (key, value) VALUES "
            "('last_reindex', datetime('now'))"
        )
    return n


def update_wiki_page(path: Path, vault_root: Path, db_path: Path) -> None:
    """Re-index one page incrementally. No-op if governance page or missing."""
    if path.name in _store.GOVERNANCE_PAGES:
        return
    try:
        rel = str(path.relative_to(vault_root))
    except ValueError:
        return
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    fm, body = parse_frontmatter(text)
    t = fm.get("type") or ""
    init(db_path)
    with _conn(db_path) as c:
        c.execute("DELETE FROM wiki_fts WHERE path = ?", (rel,))
        c.execute("DELETE FROM wiki_links WHERE src_path = ?", (rel,))
        c.execute(
            "INSERT INTO wiki_fts (path, title, type, body) VALUES (?,?,?,?)",
            (rel, path.stem, str(t), body),
        )
        for target in extract_wikilinks(body):
            c.execute(
                "INSERT OR IGNORE INTO wiki_links (src_path, target_name) "
                "VALUES (?, ?)", (rel, target.lower()),
            )


def remove_wiki_page(path: Path, vault_root: Path, db_path: Path) -> None:
    """Drop FTS + link rows for a page (after delete or before rename)."""
    try:
        rel = str(path.relative_to(vault_root))
    except ValueError:
        return
    init(db_path)
    with _conn(db_path) as c:
        c.execute("DELETE FROM wiki_fts WHERE path = ?", (rel,))
        c.execute("DELETE FROM wiki_links WHERE src_path = ?", (rel,))


def inbound(name: str, db_path: Path) -> list[str]:
    """Pages that link TO ``name``. Returns relative paths."""
    init(db_path)
    name_l = name.lower().removesuffix(".md")
    with _conn(db_path) as c:
        rows = c.execute(
            "SELECT src_path FROM wiki_links WHERE target_name = ? ORDER BY src_path",
            (name_l,),
        ).fetchall()
    return [r["src_path"] for r in rows]


def outbound(src_path: str, db_path: Path) -> list[str]:
    """Targets this page links to. ``src_path`` is relative to vault root."""
    init(db_path)
    with _conn(db_path) as c:
        rows = c.execute(
            "SELECT target_name FROM wiki_links WHERE src_path = ? ORDER BY target_name",
            (src_path,),
        ).fetchall()
    return [r["target_name"] for r in rows]


@dataclass
class WikiHit:
    path: str
    title: str
    type: str
    snippet: str
    score: float

    @property
    def kind(self) -> str:
        return self.type

    @property
    def slug(self) -> str:
        return self.title


def _sanitize(query: str) -> str:
    import re
    terms = [t for t in re.split(r"[^\w一-鿿]+", query) if t]
    if not terms:
        return ""
    return " OR ".join(terms)


def search_wiki(query: str, db_path: Path, limit: int = 5) -> list[WikiHit]:
    """BM25 full-text search over wiki pages."""
    init(db_path)
    q = _sanitize(query)
    if not q:
        return []
    with _conn(db_path) as c:
        rows = c.execute(
            "SELECT path, title, type, snippet(wiki_fts, 3, '«', '»', '…', 16) AS snip, "
            "bm25(wiki_fts) AS score FROM wiki_fts WHERE wiki_fts MATCH ? "
            "ORDER BY score LIMIT ?",
            (q, limit),
        ).fetchall()
    return [WikiHit(r["path"], r["title"], r["type"] or "", r["snip"], -r["score"]) for r in rows]


def stats(db_path: Path) -> dict:
    """Return index row counts and last-reindex timestamp."""
    init(db_path)
    with _conn(db_path) as c:
        wn = c.execute("SELECT COUNT(*) FROM wiki_fts").fetchone()[0]
        last = c.execute(
            "SELECT value FROM index_meta WHERE key = 'last_reindex'"
        ).fetchone()
    return {
        "wiki_pages": wn,
        "last_reindex": last[0] if last else None,
    }
