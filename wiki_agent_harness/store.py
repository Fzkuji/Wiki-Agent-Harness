"""Path resolution for the wiki vault.

Override the default vault root with the ``WAH_VAULT`` environment variable,
or pass ``root=`` to :class:`Wiki`.

A vault is a folder tree of ``.html`` pages plus one ``README.html`` index
per folder. State (search index, review queue) lives in a sibling ``.state``
directory so the vault itself stays a clean publishable static site.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

#: Per-folder index page name. There is at most one per folder; never iterated
#: as content.
#: Per-folder index page name. ``README.html`` so browsers auto-serve it when
#: the user opens a folder URL.
FOLDER_INDEX = "README.html"

#: File suffix used for content pages.
PAGE_SUFFIX = ".html"


def root() -> Path:
    """Default vault root. Override with WAH_VAULT env var or pass root= to Wiki()."""
    custom = os.environ.get("WAH_VAULT")
    if custom:
        return Path(custom).expanduser()
    return Path.home() / ".agentic" / "memory" / "wiki"


def state_dir(vault_root: Path) -> Path:
    d = vault_root.parent / ".state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def index_db_path(state_dir_: Path) -> Path:
    return state_dir_ / "wiki-index.sqlite"


def review_queue_path(state_dir_: Path) -> Path:
    return state_dir_ / "review-queue.json"


#: Directories to skip when walking the vault — git/IDE/Obsidian/state dirs.
SKIP_DIRS = frozenset({".git", ".obsidian", ".runs", ".wah", "Attachments"})


def _in_skip_dir(rel: Path) -> bool:
    return any(part in SKIP_DIRS or part.startswith(".") for part in rel.parts)


def iter_content_pages(vault_root: Path) -> Iterable[Path]:
    """Every content ``.html`` page under ``vault_root`` except folder indexes
    and anything inside hidden / state directories.
    """
    for p in sorted(vault_root.rglob(f"*{PAGE_SUFFIX}")):
        if p.name == FOLDER_INDEX:
            continue
        if _in_skip_dir(p.relative_to(vault_root).parent):
            continue
        yield p


def iter_folder_indexes(vault_root: Path) -> Iterable[Path]:
    for p in sorted(vault_root.rglob(FOLDER_INDEX)):
        if _in_skip_dir(p.relative_to(vault_root).parent):
            continue
        yield p
