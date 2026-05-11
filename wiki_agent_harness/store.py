"""Path resolution for the wiki vault.

Override the default vault root with the ``WAH_VAULT`` environment variable,
or pass ``root=`` to :class:`Wiki`.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

GOVERNANCE_PAGES = (
    "AGENTS.md", "SCHEMA.md", "purpose.md",
    "index.md", "log.md", "overview.md", "reflections.md",
)

WIKI_PAGE_TYPES = (
    "entity",
    "concept",
    "procedure",
    "user",
    "source",
    "query",
    "synthesis",
)


def root() -> Path:
    """Default vault root. Override with WAH_VAULT env var or pass root= to Wiki()."""
    custom = os.environ.get("WAH_VAULT")
    if custom:
        return Path(custom).expanduser()
    return Path.home() / ".agentic" / "memory" / "wiki"


def reflections_path(vault_root: Path) -> Path:
    return vault_root / "reflections.md"


def review_queue_path(state_dir: Path) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "review-queue.json"


def index_db_path(state_dir: Path) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "wiki-index.sqlite"


def iter_pages(vault_root: Path) -> Iterable[Path]:
    for p in sorted(vault_root.rglob("*.md")):
        if p.name not in GOVERNANCE_PAGES:
            yield p
