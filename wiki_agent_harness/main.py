#!/usr/bin/env python3
"""
Wiki Agent — main entry point.

Usage:
    python3 -m wiki_agent_harness "Organise my notes into a wiki"
    python3 wiki_agent_harness/main.py "Ingest today's session into the wiki"
    python3 wiki_agent_harness/main.py --vault ~/my-vault "Build a wiki from scratch"
"""

from __future__ import annotations

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openprogram import agentic_function
from openprogram.agentic_programming.runtime import Runtime


WIKI_SYSTEM_PROMPT = """\
You are a wiki-building agent. Your job is to create and maintain a structured,
Obsidian-compatible knowledge wiki from the user's materials (conversations,
documents, notes, URLs).

Core principles:
- Pages are persistent. Ingest extends the wiki; it never regenerates from scratch.
- Every page has a `type:` field: entity / concept / procedure / user / source / query / synthesis.
- Folder hierarchy = taxonomy. Use [[wikilinks]] to connect related pages.
- Keep index.md as a table of contents. Append one entry per session to log.md.
- When in doubt, create a page. Stubs are better than missing knowledge.

Available tools: read, write, edit files inside the vault directory.
"""


@agentic_function(
    render_range={"siblings": -1},
    system=WIKI_SYSTEM_PROMPT,
    input={
        "task": {
            "source": "llm",
            "description": "What to do with the wiki",
            "placeholder": "e.g. Ingest my notes about LLMs into a structured wiki",
            "multiline": True,
        },
        "vault": {
            "description": "Path to the wiki vault directory",
            "placeholder": "e.g. ~/my-vault  (leave blank for default)",
        },
        "action": {
            "description": "Operation to perform",
            "options": ["ingest", "browse", "lint", "query", "refactor"],
        },
        "runtime": {"hidden": True},
    },
)
def wiki_agent(
    task: str,
    vault: str = "",
    action: str = "ingest",
    runtime: Runtime | None = None,
) -> dict:
    """Autonomous wiki-building agent. Organise knowledge into an Obsidian-compatible wiki.

    Supports five operations:

    **ingest** — Convert raw materials (text, notes, URLs) into structured wiki pages.
    Analyses content, identifies entities / concepts, writes or updates pages,
    maintains [[wikilinks]], and updates index.md + log.md.

    **browse** — Show the current vault structure (folder tree + page list by type).

    **lint** — Health check: missing type fields, broken wikilinks, orphaned pages.

    **query** — Answer a question from the wiki, and optionally save the answer as
    a new `query` or `synthesis` page for future reuse.

    **refactor** — Reorganise overgrown sections: rename pages, merge duplicates,
    split large pages, prune broken links.

    Args:
        task: Natural-language description of what to do.
        vault: Path to the vault root directory. Defaults to WAH_VAULT env or
               ~/.agentic/memory/wiki.
        action: One of ingest / browse / lint / query / refactor.
        runtime: LLM runtime instance (injected by the harness).

    Returns:
        dict with keys: action, vault, summary, pages_touched.
    """
    from wiki_agent_harness import Wiki

    root = vault.strip() or None
    w = Wiki(root=root, runtime=runtime)

    if action == "browse":
        tree = w.tree()
        lint = w.lint()
        return {
            "action": "browse",
            "vault": str(w.root),
            "tree": tree,
            "lint_summary": lint.splitlines()[0] if lint else "",
        }

    if action == "lint":
        report = w.lint()
        return {
            "action": "lint",
            "vault": str(w.root),
            "report": report,
        }

    if action == "refactor":
        result = []
        for name, info in _find_refactor_candidates(w):
            result.append(f"- {name}: {info}")
        return {
            "action": "refactor",
            "vault": str(w.root),
            "candidates": "\n".join(result) if result else "No obvious candidates found.",
            "note": "Use memory_rename / memory_relink / memory_delete tools to apply changes.",
        }

    # ingest / query — hand off to the agentic ingest pipeline via runtime
    if runtime is None:
        return {
            "action": action,
            "vault": str(w.root),
            "error": "A runtime is required for ingest and query operations.",
        }

    # Build a prompt that describes the vault state + the user's task
    tree = w.tree()
    lint_lines = w.lint().splitlines()[:5]
    context = f"Vault: {w.root}\n\n{tree}\n\nLint (first 5 lines):\n" + "\n".join(lint_lines)

    prompt = (
        f"Action: {action}\n\n"
        f"Task: {task}\n\n"
        f"Current vault state:\n{context}\n\n"
        "Use the file tools to read existing pages and write / edit pages as needed. "
        "All paths are relative to the vault root unless absolute. "
        "Update index.md (table of contents) and append one entry to log.md when done."
    )

    result = runtime.exec(prompt, max_iterations=30)
    pages = w.lint()  # re-lint to count after changes

    return {
        "action": action,
        "vault": str(w.root),
        "summary": result if isinstance(result, str) else str(result),
        "lint_after": pages.splitlines()[0] if pages else "",
    }


def _find_refactor_candidates(w) -> list[tuple[str, str]]:
    """Return pages that may need refactoring (stubs, no type, etc.)."""
    from wiki_agent_harness import store
    candidates = []
    for p in w.iter_pages():
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if len(text.strip()) < 100:
            candidates.append((p.stem, "stub — very short page"))
        elif "type:" not in text[:300]:
            candidates.append((p.stem, "missing type: frontmatter"))
    return candidates[:20]


# ── CLI entry point ──────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Wiki Agent — build and maintain a knowledge wiki")
    parser.add_argument("task", nargs="?", default="browse", help="Task description")
    parser.add_argument("--vault", default="", help="Vault directory path")
    parser.add_argument("--action", default="ingest",
                        choices=["ingest", "browse", "lint", "query", "refactor"])
    args = parser.parse_args()

    try:
        from openprogram.legacy_providers import create_runtime
        rt = create_runtime()
    except Exception:
        rt = None

    result = wiki_agent(task=args.task, vault=args.vault, action=args.action, runtime=rt)
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
