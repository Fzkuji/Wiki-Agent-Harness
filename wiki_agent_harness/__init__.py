"""wiki_agent_harness — HTML-first, template-driven wiki for AI agents.

Three layers:
  1. Templates (Jinja2 + Tailwind/DaisyUI CDN) define page shells and slots.
  2. Agent fills slots; never writes raw HTML by hand.
  3. Folder ``README.html`` indexes are auto-generated.

Example::

    from wiki_agent_harness import Wiki, PromptSet

    w = Wiki(root="~/my-vault")
    print(w.tree())

    # Create a fresh page from the 'concept' template.
    path = w.new_page("topic-a/transformers", template="concept",
                      meta={"title": "Transformers", "tags": ["nlp"]})
    w.write_slot(path, "summary", "An attention-based architecture.")

    # Search.
    for hit in w.search("attention"):
        print(hit.path, hit.score)

    # Specialise prompts for a downstream project.
    w2 = Wiki(
        root="~/paper-vault",
        extra_template_dirs=["./my-paper-templates"],
        prompts=PromptSet().with_overrides(analysis=PAPER_ANALYSIS_PROMPT),
    )
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import index as _idx
from . import ingest as _ingest
from . import ops as _ops
from . import pages as _pages
from . import slots as _slots
from . import store
from .prompts import PromptSet
from .renderer import Renderer, TemplateInfo, materialize_new_page


class Wiki:
    """Bound view of one vault.

    Args:
        root: Vault root directory. Falls back to ``WAH_VAULT`` env or
            ``~/.agentic/memory/wiki``.
        extra_template_dirs: Additional Jinja2 template directories. Templates
            here take precedence over built-ins of the same name. Downstream
            projects use this to add domain-specific templates.
        prompts: Optional :class:`PromptSet` overriding the default ingest
            prompts. Downstream projects use this to specialise the
            analysis/generation pipeline for a specific domain.
        runtime: Optional agentic runtime used by ``ingest_session``. Anything
            with ``exec(content=[...], tools=..., max_iterations=...)`` works.
        purpose: One-paragraph statement of what the vault is for; passed
            into the ingest analysis prompt to govern scope.
    """

    def __init__(
        self,
        root: str | Path | None = None,
        *,
        extra_template_dirs: list[str | Path] | None = None,
        prompts: PromptSet | None = None,
        runtime: Any | None = None,
        purpose: str = "",
        audience: str = "",
    ) -> None:
        self.root: Path = (
            Path(root).expanduser() if root else store.root()
        )
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_dir = store.state_dir(self.root)
        self._db_path = store.index_db_path(self.state_dir)
        self.renderer = Renderer(
            extra_template_dirs=[Path(p) for p in (extra_template_dirs or [])]
        )
        self.prompts = prompts or PromptSet()
        self.runtime = runtime
        self.purpose = purpose
        from .prompts import DEFAULT_AUDIENCE
        self.audience = audience or DEFAULT_AUDIENCE

    # ── Read ────────────────────────────────────────────────────────────
    def find(self, name: str) -> Path | None:
        return _pages.find(name, self.root)

    def read(self, target: str | Path) -> str | None:
        return _pages.read(target, self.root)

    def tree(self, *, max_depth: int = 8) -> str:
        return _pages.folder_tree(self.root, max_depth=max_depth)

    def index(self) -> str:
        """Flat list of all content page paths, vault-relative."""
        return _pages.folder_index(self.root)

    def iter_pages(self):
        yield from _pages.iter_pages(self.root)

    def meta(self, target: str | Path) -> dict[str, Any]:
        html = self.read(target)
        if html is None:
            return {}
        return _slots.read_meta(html)

    def slot(self, target: str | Path, slot_id: str) -> str | None:
        html = self.read(target)
        if html is None:
            return None
        return _slots.read_slot(html, slot_id)

    def list_slots(self, target: str | Path) -> list[str]:
        html = self.read(target)
        if html is None:
            return []
        return _slots.list_slots(html)

    # ── Templates ──────────────────────────────────────────────────────
    def list_templates(self) -> list[TemplateInfo]:
        return self.renderer.list_templates()

    def template_help(self) -> str:
        from .renderer import render_template_help
        return render_template_help(self.renderer)

    # ── Write ──────────────────────────────────────────────────────────
    def new_page(
        self,
        path_or_name: str,
        *,
        template: str,
        meta: dict[str, Any] | None = None,
    ) -> Path:
        """Create a fresh page.

        ``path_or_name`` may be a bare name (page goes in vault root) or a
        relative path like ``"area/topic/page-name"`` (folders created).
        """
        s = str(path_or_name).strip()
        if "/" in s:
            folder, name = s.rsplit("/", 1)
            folder_path: str | None = folder
        else:
            folder_path, name = None, s
        return _ops.new_page(
            name, template=template, meta=meta, folder=folder_path,
            renderer=self.renderer, vault_root=self.root,
        )

    def write_slot(self, target: str | Path, slot_id: str, content: str) -> Path:
        path = self._resolve(target)
        _slots.write_slot_file(path, slot_id, content)
        _idx.update_page(path, self.root, self._db_path)
        return path

    def append_slot(self, target: str | Path, slot_id: str, content: str) -> Path:
        path = self._resolve(target)
        _slots.append_slot_file(path, slot_id, content)
        _idx.update_page(path, self.root, self._db_path)
        return path

    def set_meta(self, target: str | Path, updates: dict[str, Any]) -> Path:
        path = self._resolve(target)
        html = path.read_text(encoding="utf-8")
        current = _slots.read_meta(html)
        current.update(updates)
        path.write_text(_slots.write_meta(html, current), encoding="utf-8")
        _idx.update_page(path, self.root, self._db_path)
        return path

    def rerender_page(self, target: str | Path) -> bool:
        """Re-render a page from its current template, preserving slots."""
        path = self._resolve(target)
        return _ops.rerender_page(
            path, renderer=self.renderer, vault_root=self.root,
        )

    def rerender_all(self) -> int:
        """Re-render every harness-managed page (after template changes)."""
        return _ops.rerender_all_pages(self.root, renderer=self.renderer)

    def rebuild_folder_index(self, folder: str | Path | None = None) -> Path:
        if folder is None:
            folder_path = self.root
        elif isinstance(folder, Path):
            folder_path = folder if folder.is_absolute() else self.root / folder
        else:
            folder_path = self.root / folder
        return _ops.rebuild_folder_index(
            folder_path, renderer=self.renderer, vault_root=self.root,
        )

    def rebuild_all_folder_indexes(self) -> int:
        return _ops.rebuild_all_folder_indexes(
            self.root, renderer=self.renderer,
        )

    # ── Search ─────────────────────────────────────────────────────────
    def search(self, query: str, limit: int = 5):
        return _idx.search(query, self._db_path, limit=limit)

    def reindex(self) -> int:
        return _idx.reindex_all(self.root, self._db_path)

    # ── Health / git ───────────────────────────────────────────────────
    def lint(self) -> str:
        return _ops.lint(self.root, renderer=self.renderer)

    def stats(self) -> dict[str, Any]:
        return _ops.stats(self.root)

    def git_commit(self, message: str) -> dict[str, Any]:
        return _ops.git_commit(message, vault_root=self.root)

    # ── Agentic ingest ─────────────────────────────────────────────────
    def ingest_session(
        self,
        session_id: str,
        messages: list[dict[str, Any]],
        *,
        runtime: Any | None = None,
    ) -> dict[str, Any]:
        return _ingest.ingest_session(
            session_id, messages,
            vault_root=self.root,
            renderer=self.renderer,
            prompts=self.prompts,
            runtime=runtime or self.runtime,
            purpose=self.purpose,
            audience=self.audience,
        )

    def enrich_page(
        self, target: str | Path, *, runtime: Any | None = None,
    ) -> dict[str, Any]:
        """Have the agent rewrite a page's slots using rich components."""
        path = self._resolve(target)
        return _ingest.enrich_page(
            path,
            vault_root=self.root,
            renderer=self.renderer,
            prompts=self.prompts,
            runtime=runtime or self.runtime,
            audience=self.audience,
        )

    def enrich_all(
        self,
        *,
        runtime: Any | None = None,
        only_templates: list[str] | None = None,
        max_pages: int | None = None,
    ) -> dict[str, Any]:
        """Enrich every harness-managed page (or only a template subset)."""
        rt = runtime or self.runtime
        results: list[dict[str, Any]] = []
        for p in self.iter_pages():
            if max_pages is not None and len(results) >= max_pages:
                break
            meta = _slots.read_meta_file(p)
            tmpl = str(meta.get("template") or "")
            if only_templates and tmpl not in only_templates:
                continue
            results.append(self.enrich_page(p, runtime=rt))
        # Folder READMEs (template="folder") use rebuild_folder_index, not
        # enrich_page; iterate them separately.
        if not only_templates or "folder" in only_templates:
            from . import store as _store
            for readme in _store.iter_folder_indexes(self.root):
                if max_pages is not None and len(results) >= max_pages:
                    break
                results.append(self.enrich_page(readme, runtime=rt))
        return {
            "ok": True,
            "n_pages": len(results),
            "n_ok": sum(1 for r in results if r.get("ok") and not r.get("skipped")),
            "results": results,
        }

    # ── Internal ───────────────────────────────────────────────────────
    def _resolve(self, target: str | Path) -> Path:
        if isinstance(target, Path):
            return target if target.is_absolute() else self.root / target
        s = str(target).strip()
        if "/" in s or s.endswith(store.PAGE_SUFFIX):
            p = self.root / s
            if not p.suffix:
                p = p.with_suffix(store.PAGE_SUFFIX)
            return p
        found = _pages.find(s, self.root)
        if found is None:
            raise FileNotFoundError(f"page not found: {target!r}")
        return found


def default() -> Wiki:
    """Wiki bound to the default vault (WAH_VAULT or ~/.agentic/memory/wiki)."""
    return Wiki()


__all__ = [
    "Wiki",
    "PromptSet",
    "Renderer",
    "TemplateInfo",
    "default",
]
