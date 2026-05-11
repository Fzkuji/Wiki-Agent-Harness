"""wiki_agent_harness — portable Obsidian-style wiki subsystem for AI agents.

Zero external dependencies (pure stdlib).

Example::

    from wiki_agent_harness import Wiki

    w = Wiki(root="~/my-vault")
    print(w.tree())
    print(w.lint())
    links = w.backlinks("SomeTopic")
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from . import access, enrich, helpers, ingest, ops

# Free-function re-exports for callers that prefer module-level API.
from .access import (  # noqa: F401
    find, read, tree, iter_pages, page_type, pages_of_type, root,
)
from .ops import (  # noqa: F401
    lint, rename, relink, prune_broken_links, backlinks,
    unlinked_mentions, survey, refactor, git_commit,
)
from .ingest import (  # noqa: F401
    ingest_session, ingest_session_by_id,
)
from .enrich import (  # noqa: F401
    enrich_page, enrich_pages, enrich_inbound_for_new_page,
)


class Wiki:
    """Bound view of a single vault.

    Args:
        root: Vault root directory. If omitted, uses ``store.root()``
            (``WAH_VAULT`` env var or ``~/.agentic/memory/wiki``).
        runtime: Optional runtime for agentic ops (ingest, survey, refactor).
        llm: Optional ``(system, user) -> str`` callable for non-agentic
            LLM calls (enrich).
    """

    def __init__(
        self,
        root: str | Path | None = None,
        *,
        runtime: Any | None = None,
        llm: Callable[[str, str], str] | None = None,
    ) -> None:
        from . import store as _store
        self.root: Path = Path(root).expanduser() if root else _store.root()
        self.root.mkdir(parents=True, exist_ok=True)
        self._state_dir = self.root.parent / ".state"
        self._db_path = _store.index_db_path(self._state_dir)
        self._runtime = runtime
        self._llm = llm

    # ── Read ────────────────────────────────────────────────────────────
    def find(self, name: str) -> Path | None:
        return helpers.find_node(self.root, name)

    def read(self, target: str | Path) -> str | None:
        return access.read(target, vault_root=self.root)

    def tree(self, *, max_depth: int = 8) -> str:
        return helpers.folder_tree(self.root, max_depth=max_depth)

    def iter_pages(self):
        yield from helpers.iter_md_files(self.root)

    def page_type(self, path: Path) -> str | None:
        return access.page_type(path)

    def pages_of_type(self, t: str) -> list[Path]:
        return access.pages_of_type(t, vault_root=self.root)

    # ── Lint + link ops ─────────────────────────────────────────────────
    def lint(self) -> str:
        return ops.lint(root=self.root)

    def rename(self, old: str, new: str) -> dict[str, Any]:
        return ops.rename(old, new, root=self.root)

    def relink(self, old: str, new: str) -> dict[str, Any]:
        return ops.relink(old, new, root=self.root)

    def prune_broken_links(self, *, dry_run: bool = True) -> dict[str, Any]:
        return ops.prune_broken_links(dry_run=dry_run, root=self.root)

    def backlinks(self, name: str) -> list[dict[str, str]]:
        return ops.backlinks(name, root=self.root)

    def unlinked_mentions(self, name: str, *, max_per_page: int = 3) -> list[dict[str, Any]]:
        return ops.unlinked_mentions(name, max_per_page=max_per_page, root=self.root)

    # ── Agentic ops (need a runtime) ────────────────────────────────────
    def survey(self, topic: str) -> dict[str, Any]:
        return ops.survey(topic, root=self.root)

    def refactor(self, topic: str) -> dict[str, Any]:
        return ops.refactor(topic, root=self.root)

    def ingest_session(
        self, session_id: str, messages: list[dict[str, Any]],
        *, runtime: Any | None = None,
    ) -> dict[str, Any]:
        return ingest.ingest_session(
            session_id, messages,
            runtime=runtime or self._runtime,
            vault_root=self.root,
        )

    def ingest_session_by_id(self, session_id: str) -> dict[str, Any]:
        return ingest.ingest_session_by_id(session_id, vault_root=self.root)

    # ── Git ─────────────────────────────────────────────────────────────
    def git_commit(self, message: str) -> dict[str, Any]:
        return ops.git_commit(message, root=self.root)

    # ── Index ────────────────────────────────────────────────────────────
    def reindex(self) -> int:
        from . import index as _idx
        return _idx.reindex_all(self.root, self._db_path)

    def search(self, query: str, limit: int = 5):
        from . import index as _idx
        return _idx.search_wiki(query, self._db_path, limit=limit)

    # ── Stats ────────────────────────────────────────────────────────────
    def stats(self) -> dict[str, Any]:
        return ops.stats(root=self.root)


def default() -> Wiki:
    """Return a Wiki bound to the default vault (WAH_VAULT or ~/.agentic/memory/wiki)."""
    return Wiki()


__all__ = [
    # Class
    "Wiki", "default",
    # Submodules
    "access", "helpers", "ops", "ingest", "enrich",
    # Free-function re-exports
    "find", "read", "tree", "iter_pages", "page_type", "pages_of_type", "root",
    "lint", "rename", "relink", "prune_broken_links",
    "backlinks", "unlinked_mentions", "survey", "refactor", "git_commit",
    "ingest_session", "ingest_session_by_id",
    "enrich_page", "enrich_pages", "enrich_inbound_for_new_page",
]
