#!/usr/bin/env python3
"""
Wiki Agent — main entry point.

Usage:
    python3 -m wiki_agent_harness "Organise my notes into a wiki"
    python3 wiki_agent_harness/main.py "Ingest today's session into the wiki"
"""

from __future__ import annotations

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openprogram import agentic_function
from openprogram.agentic_programming.runtime import Runtime
# render_options / extract_action moved into the decision module when
# buildin/ was slimmed down (build_catalog was the pre-rename options
# renderer; parse_action the pre-rename action extractor).
from openprogram.agentic_programming.decision import (
    render_options as build_catalog,
    extract_action as parse_action,
)


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

ACTIONS = {
    "ingest": {
        "function": None,  # handled inline
        "description": "Convert raw materials (text, notes, URLs, conversations) into structured wiki pages. Identifies entities/concepts, writes or updates pages, maintains [[wikilinks]], updates index.md + log.md.",
        "input": {
            "task": {"source": "llm", "description": "What to ingest and how"},
        },
    },
    "browse": {
        "function": None,
        "description": "Show the current vault structure — folder tree and page list by type. Use this to understand what already exists before ingest or refactor.",
        "input": {},
    },
    "lint": {
        "function": None,
        "description": "Run a health check on the vault: missing type fields, broken [[wikilinks]], orphaned pages, frontmatter issues.",
        "input": {},
    },
    "query": {
        "function": None,
        "description": "Answer a question by reading relevant wiki pages. Optionally save the answer as a new query or synthesis page for future reuse.",
        "input": {
            "task": {"source": "llm", "description": "The question to answer"},
        },
    },
    "refactor": {
        "function": None,
        "description": "Reorganise the vault: rename pages, fix broken links, merge duplicates, split overgrown pages, prune stubs.",
        "input": {
            "task": {"source": "llm", "description": "What to reorganise"},
        },
    },
}


@agentic_function(render_range={"depth": 0, "siblings": 0})
def _pick_action(task: str, vault_state: str, runtime: Runtime) -> dict:
    """Route a wiki request to one of: ingest, browse, lint, query, refactor."""
    catalog = build_catalog(ACTIONS)
    reply = runtime.exec(content=[{"type": "text", "text": (
        f"User request:\n{task}\n\n"
        f"Current vault state:\n{vault_state}\n\n"
        f"== Actions ==\n{catalog}\n\n"
        "Pick the one action whose description best matches what the user "
        "needs:\n"
        "- a question about existing content → query\n"
        "- adding or importing new material → ingest\n"
        "- an overview or list of what exists → browse\n"
        "- checking the vault for problems → lint\n"
        "- reorganising, renaming, or merging pages → refactor\n\n"
        "Reply with this exact JSON and nothing else:\n"
        '{"call": "<action>", "args": {"task": "..."}}'
    )}])
    action = parse_action(reply)
    if action is None:
        return {"action": "ingest", "task": task}
    call = action.get("call", "ingest")
    if call not in ACTIONS:
        call = "ingest"
    args = action.get("args") or {}
    return {"action": call, "task": args.get("task", task)}


@agentic_function(
    as_tool=True,
    toolset=("harness",),
    render_range={"siblings": -1},
    system=WIKI_SYSTEM_PROMPT,
    input={
        "task": {
            "source": "llm",
            "description": "What to do with the wiki",
            "placeholder": "e.g. Ingest my notes about LLMs into a structured wiki",
            "multiline": True,
        },
        "runtime": {"hidden": True},
    },
)
def wiki_agent(
    task: str,
    runtime: Runtime | None = None,
) -> dict:
    """Autonomous wiki-building agent. Organise knowledge into an Obsidian-compatible wiki.

    Accepts any natural-language request about a wiki vault: ingest new material,
    browse existing content, run a health check, answer a question, or reorganise pages.
    The agent routes the request to one operation, then returns a dict with keys
    action, vault, result. The vault directory is taken from the "Working in a
    folder" setting (runtime workdir), or defaults to WAH_VAULT env /
    ~/.agentic/memory/wiki.
    """
    if runtime is None:
        return {"error": "wiki_agent requires a runtime."}

    from wiki_agent_harness import Wiki

    # Use runtime workdir if set (from Web UI "Working in a folder"), else default vault
    root = None
    wd = getattr(runtime, "workdir", None)
    if wd:
        root = str(wd)
    w = Wiki(root=root, runtime=runtime)

    # Let LLM pick the action
    vault_state = f"{w.tree()}\n\nLint:\n{w.lint()}"
    decision = _pick_action(task=task, vault_state=vault_state, runtime=runtime)
    action = decision.get("action", "ingest")
    sub_task = decision.get("task", task)

    # Execute
    if action == "browse":
        return {"action": "browse", "vault": str(w.root), "result": w.tree()}

    if action == "lint":
        return {"action": "lint", "vault": str(w.root), "result": w.lint()}

    # ingest / query / refactor — agentic file operations via runtime
    action_desc = ACTIONS.get(action, {}).get("description", "")
    prompt = (
        f"Action: {action}\n{action_desc}\n\n"
        f"Task: {sub_task}\n\n"
        f"Vault: {w.root}\n\n"
        f"Current state:\n{vault_state}\n\n"
        "Use the file tools to read existing pages and write/edit pages as needed. "
        "Update index.md (table of contents) and append one entry to log.md when done."
    )
    result = runtime.exec(
        content=[{"type": "text", "text": prompt}],
        max_iterations=30,
        toolset="default",  # ingest/query/refactor read & write vault files
    )
    return {
        "action": action,
        "vault": str(w.root),
        "result": result if isinstance(result, str) else str(result),
    }


# ── CLI entry point ──────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Wiki Agent — build and maintain a knowledge wiki")
    parser.add_argument("task", nargs="?", default="Browse the wiki", help="Task description")
    args = parser.parse_args()

    try:
        from openprogram import create_runtime
        rt = create_runtime()
    except Exception as e:
        print(f"warning: could not create runtime ({e}); agentic actions will fail",
              file=sys.stderr)
        rt = None

    result = wiki_agent(task=args.task, runtime=rt)
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
