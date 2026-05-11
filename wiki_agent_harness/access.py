"""Wiki access — path-based read API over the Obsidian-style vault."""
from __future__ import annotations

from pathlib import Path

from . import store
from . import helpers as h


def root() -> Path:
    return store.root()


def find(name: str, vault_root: Path | None = None) -> Path | None:
    """Find a page by filename stem (case-insensitive)."""
    r = vault_root or store.root()
    return h.find_node(r, name)


def read(target: str | Path, vault_root: Path | None = None) -> str | None:
    """Read a page by path or by filename stem. Returns markdown text or None."""
    r = vault_root or store.root()
    if isinstance(target, Path):
        path = target
    else:
        s = str(target).strip()
        if "/" in s or s.endswith(".md"):
            path = r / s
            if not path.suffix:
                path = path.with_suffix(".md")
        else:
            found = find(s, r)
            if found is None:
                return None
            path = found
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def tree(vault_root: Path | None = None, *, max_depth: int = 8) -> str:
    r = vault_root or store.root()
    return h.folder_tree(r, max_depth=max_depth)


def iter_pages(vault_root: Path | None = None):
    r = vault_root or store.root()
    yield from h.iter_md_files(r)


def page_type(path: Path) -> str | None:
    """Read the ``type:`` frontmatter value of a page, or None."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    fm, _ = h.parse_frontmatter(text)
    t = fm.get("type")
    return t if isinstance(t, str) else None


def pages_of_type(t: str, vault_root: Path | None = None) -> list[Path]:
    """All pages where ``type: t`` (case-insensitive). Linear scan."""
    out: list[Path] = []
    for p in iter_pages(vault_root):
        if page_type(p) == t:
            out.append(p)
    return out
