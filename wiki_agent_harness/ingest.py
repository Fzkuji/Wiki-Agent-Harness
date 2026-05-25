"""Two-step agentic ingest pipeline.

  1. Python collects: conversation transcript, vault folder tree, flat page
     index, template catalog, purpose statement.
  2. Step 1 — Analysis: LLM emits a structured plain-text analysis (what
     pages to create/update, which template, which folder).
  3. Step 2 — Generation: agentic ``runtime.exec`` call performs the actual
     writes via slot-level edits. Prompts are overridable via PromptSet.
  4. Folder indexes are rebuilt for every touched folder.
  5. Search index is updated.
  6. Optional git commit snapshots the vault.

Prompts are parameterised so downstream projects can specialise the pipeline
(paper survey, memory store, CRM, ...) without forking the code: pass a
``PromptSet`` with overridden analysis/generation strings.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from . import index as _idx
from . import ops
from . import pages as _pages
from . import store
from .prompts import PromptSet
from .renderer import Renderer, render_template_help

logger = logging.getLogger(__name__)

REVIEW_BLOCK_RE = re.compile(
    r"<<<REVIEW_QUEUE>>>\s*(?P<json>\[.*?\])\s*<<<END>>>",
    re.DOTALL,
)


# ---------------------------------------------------------------------------
# Source rendering
# ---------------------------------------------------------------------------


def render_conversation(
    messages: Iterable[dict[str, Any]], *, max_chars: int = 16_000,
) -> str:
    lines: list[str] = []
    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                str(p.get("text", p)) if isinstance(p, dict) else str(p)
                for p in content
            )
        content = str(content).strip()
        if not content:
            continue
        lines.append(f"[{role}] {content}")
    text = "\n\n".join(lines)
    if len(text) > max_chars:
        text = "... [truncated head] ...\n\n" + text[-max_chars:]
    return text


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------


def ingest_session(
    session_id: str,
    messages: list[dict[str, Any]],
    *,
    vault_root: Path,
    renderer: Renderer,
    prompts: PromptSet,
    runtime: Any,
    purpose: str = "",
    audience: str = "",
) -> dict[str, Any]:
    """Run the two-step ingest over a finished conversation.

    ``runtime`` is the agentic runtime — any object exposing
    ``exec(content=[...], tools=..., max_iterations=...)`` works. Downstream
    callers compose their own.
    """
    if runtime is None:
        return {"ok": False, "error": "no runtime supplied"}

    today = datetime.now().strftime("%Y-%m-%d")
    slug = _session_slug(session_id, today)

    source = render_conversation(messages)
    tree_str = _pages.folder_tree(vault_root) or "(empty vault)"
    index_str = _pages.folder_index(vault_root) or "(no pages yet)"
    template_details = render_template_help(renderer)
    template_names = ", ".join(renderer.template_names())
    source_title = f"Session {session_id} ({today})"

    # ── Step 1: analysis ───────────────────────────────────────────────
    analysis_prompt = prompts.analysis.format(
        purpose=purpose or "(no explicit purpose set)",
        audience=audience or "(no explicit audience set)",
        index=index_str,
        tree=tree_str,
        templates=template_names,
        template_details=template_details,
        source=source,
        source_title=source_title,
    )
    try:
        analysis = runtime.exec(
            content=[{"type": "text", "text": analysis_prompt}],
            tools=[],
            max_iterations=1,
        )
    except Exception as e:
        return {"ok": False, "error": f"analysis: {e}"}
    if not analysis or not str(analysis).strip():
        return {"ok": False, "error": "analysis returned empty"}

    # ── Step 2: generation ─────────────────────────────────────────────
    from .components import render_component_palette
    gen_prompt = prompts.generation.format(
        vault_root=str(vault_root),
        source_slug=slug,
        today=today,
        audience=audience or "(no explicit audience set)",
        analysis=analysis,
        source=source,
        template_details=template_details,
        component_palette=render_component_palette(),
    )
    try:
        report = runtime.exec(
            content=[{"type": "text", "text": gen_prompt}],
            max_iterations=40,
        )
    except Exception as e:
        return {"ok": False, "error": f"generation: {e}"}

    # ── Post-ingest bookkeeping ────────────────────────────────────────
    touched, created = ops.git_touched_pages(vault_root)
    affected_folders = {p.parent for p in touched}
    for folder in affected_folders:
        try:
            ops.rebuild_folder_index(folder, renderer=renderer, vault_root=vault_root)
        except Exception as e:
            logger.warning("rebuild_folder_index failed for %s: %s", folder, e)

    db = store.index_db_path(store.state_dir(vault_root))
    for p in touched:
        try:
            _idx.update_page(p, vault_root, db)
        except Exception as e:
            logger.warning("index update failed for %s: %s", p, e)

    review_items = _parse_review_block(str(report))
    if review_items:
        _persist_reviews(review_items, source_slug=slug, ts=today,
                         state_dir=store.state_dir(vault_root))

    commit_info: dict[str, Any] = {}
    try:
        commit_info = ops.git_commit(f"ingest: {slug}", vault_root=vault_root)
    except Exception as e:
        commit_info = {"ok": False, "error": str(e)}

    return {
        "ok": True,
        "report": report,
        "pages_touched": len(touched),
        "pages_created": len(created),
        "folders_reindexed": len(affected_folders),
        "n_review_items": len(review_items),
        "commit": commit_info,
    }


# ---------------------------------------------------------------------------
# Page-level enrichment (rewrite slots to use rich components)
# ---------------------------------------------------------------------------


def enrich_page(
    page_path: Path,
    *,
    vault_root: Path,
    renderer: Renderer,
    prompts: PromptSet,
    runtime: Any,
    audience: str = "",
) -> dict[str, Any]:
    """Ask the runtime to rewrite a page's slots using the rich component
    palette. The agent edits the file in place via its standard file tools.
    """
    if runtime is None:
        return {"ok": False, "error": "no runtime supplied"}
    if not page_path.exists():
        return {"ok": False, "error": f"page not found: {page_path}"}

    from . import slots as _slots
    from .components import render_component_palette

    html = page_path.read_text(encoding="utf-8")
    meta = _slots.read_meta(html)
    template = str(meta.get("title") or "") and str(meta.get("template") or "")
    slot_ids = _slots.list_slots(html)
    if not slot_ids:
        return {"ok": True, "skipped": True, "reason": "no slots"}

    slots_dump_parts: list[str] = []
    for sid in slot_ids:
        content = _slots.read_slot(html, sid) or ""
        slots_dump_parts.append(
            f"### slot: `{sid}`\n```html\n{content.strip()}\n```\n"
        )
    slots_dump = "\n".join(slots_dump_parts)

    prompt = prompts.enrichment.format(
        page_path=str(page_path),
        template=template,
        audience=audience or "(no explicit audience set)",
        slots_dump=slots_dump,
        component_palette=render_component_palette(),
    )
    try:
        report = runtime.exec(
            content=[{"type": "text", "text": prompt}],
            max_iterations=20,
        )
    except Exception as e:
        return {"ok": False, "error": f"runtime: {e}"}

    db = store.index_db_path(store.state_dir(vault_root))
    try:
        _idx.update_page(page_path, vault_root, db)
    except Exception as e:
        logger.warning("index update after enrich failed: %s", e)

    return {"ok": True, "page": str(page_path.relative_to(vault_root)),
            "report": report}


# ---------------------------------------------------------------------------
# Review queue
# ---------------------------------------------------------------------------


def _parse_review_block(report: str) -> list[dict[str, str]]:
    m = REVIEW_BLOCK_RE.search(report or "")
    if not m:
        return []
    try:
        items = json.loads(m.group("json"))
    except json.JSONDecodeError:
        return []
    if not isinstance(items, list):
        return []
    out: list[dict[str, str]] = []
    for it in items:
        if isinstance(it, dict) and "kind" in it and "title" in it:
            out.append({
                "kind": str(it.get("kind", "")),
                "title": str(it.get("title", "")),
                "detail": str(it.get("detail", "")),
            })
    return out


def _persist_reviews(reviews: list[dict], *, source_slug: str, ts: str,
                     state_dir: Path) -> None:
    qpath = store.review_queue_path(state_dir)
    items: list[dict] = []
    if qpath.exists():
        try:
            items = json.loads(qpath.read_text(encoding="utf-8"))
        except Exception:
            items = []
    next_id = max((it.get("id", 0) for it in items), default=0) + 1
    for r in reviews:
        items.append({
            "id": next_id,
            "kind": r.get("kind"),
            "title": r.get("title", ""),
            "detail": r.get("detail", ""),
            "source_slug": source_slug,
            "created_at": ts,
            "resolved": False,
        })
        next_id += 1
    qpath.write_text(
        json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8",
    )


def _session_slug(session_id: str, today: str) -> str:
    short = session_id.replace("local_", "")[:10]
    return f"session-{short}-{today}"
