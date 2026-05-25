"""Page-level read / find / iterate API.

Pages are ``.html`` files; each folder has at most one ``README.html``
auto-generated index.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from . import store


def find(name: str, vault_root: Path) -> Path | None:
    """Find a content page by filename stem (case-insensitive)."""
    target = name.lower().removesuffix(store.PAGE_SUFFIX)
    candidates: list[tuple[int, Path]] = []
    for p in vault_root.rglob(f"*{store.PAGE_SUFFIX}"):
        if p.name == store.FOLDER_INDEX:
            continue
        if p.stem.lower() == target:
            # rank 0 if the page's folder is named after it (topic folder
            # convention), else rank 1.
            rank = 0 if p.parent.name.lower() == target else 1
            candidates.append((rank, p))
    if not candidates:
        return None
    candidates.sort(key=lambda r: (r[0], len(str(r[1]))))
    return candidates[0][1]


def iter_pages(vault_root: Path) -> Iterable[Path]:
    yield from store.iter_content_pages(vault_root)


def read(target: str | Path, vault_root: Path) -> str | None:
    """Read a page by path or by filename stem. Returns HTML or None."""
    if isinstance(target, Path):
        path = target
    else:
        s = str(target).strip()
        if "/" in s or s.endswith(store.PAGE_SUFFIX):
            path = vault_root / s
            if not path.suffix:
                path = path.with_suffix(store.PAGE_SUFFIX)
        else:
            found = find(s, vault_root)
            if found is None:
                return None
            path = found
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def folder_tree(vault_root: Path, *, max_depth: int = 8) -> str:
    """Render the vault folder tree as an indented outline."""
    lines: list[str] = []

    def _walk(dir_path: Path, depth: int) -> None:
        if depth > max_depth:
            return
        entries = sorted(
            (e for e in dir_path.iterdir()
             if not e.name.startswith(".")
             and e.name != "Attachments"),
            key=lambda p: (not p.is_dir(), p.name.lower()),
        )
        for entry in entries:
            prefix = "  " * depth + ("- " if depth else "")
            if entry.is_dir():
                lines.append(f"{prefix}{entry.name}/")
                _walk(entry, depth + 1)
            elif entry.suffix == store.PAGE_SUFFIX and entry.name != store.FOLDER_INDEX:
                lines.append(f"{prefix}{entry.name}")

    if not vault_root.exists():
        return ""
    _walk(vault_root, 0)
    return "\n".join(lines)


def folder_index(vault_root: Path) -> str:
    """Flat list of all content pages, one per line, vault-relative."""
    lines = []
    for p in iter_pages(vault_root):
        rel = p.relative_to(vault_root)
        lines.append(str(rel))
    return "\n".join(lines)
