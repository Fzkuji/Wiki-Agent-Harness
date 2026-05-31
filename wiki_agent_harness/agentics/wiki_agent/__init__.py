"""``wiki_agent`` — top-level dispatcher for any wiki-related task."""
from __future__ import annotations

from typing import Any

from openprogram.agentic_programming import decision
from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(
    input={
        "task": {
            "description": (
                "Natural-language description of what to do with the wiki. "
                "Examples: 'ingest these notes about transformers', "
                "'enrich the Methodology landing page', 'browse the vault', "
                "'check for broken links', 'find pages about distillation'."
            ),
            "placeholder": "e.g. Ingest the conversation above into the wiki.",
            "multiline": True,
        },
        "vault": {
            "description": (
                "Vault root path. Falls back to runtime workdir, then "
                "$WAH_VAULT, then ~/.agentic/memory/wiki."
            ),
            "placeholder": "default: ~/.agentic/memory/wiki",
        },
        "purpose": {
            "description": (
                "One-paragraph statement of what the vault is for; "
                "passed to ingest's analysis prompt to govern scope."
            ),
            "multiline": True,
            "placeholder": "default: (none)",
        },
        "audience": {
            "description": (
                "What the reader is assumed to already know. Sub-topic "
                "concepts outside this baseline must be defined in baseline "
                "terms or linked to their own page — never jargon "
                "explaining jargon. Used by both ingest and enrich."
            ),
            "multiline": True,
            "placeholder": "default: a generally technical reader",
        },
    },
)
def wiki_agent(
    task: str,
    vault: str = "",
    purpose: str = "",
    audience: str = "",
    runtime: Runtime = None,
) -> dict:
    """Maintain a wiki vault — route to ingest, enrich, browse, lint, or search depending on the task."""
    from wiki_agent_harness import Wiki

    root = vault.strip() or None
    if root is None and runtime is not None:
        wd = getattr(runtime, "workdir", None)
        if wd:
            root = str(wd)

    w = Wiki(
        root=root, runtime=runtime,
        purpose=purpose or "",
        audience=audience or "",
    )

    state = (
        f"vault root: {w.root}\n\n"
        f"folder tree:\n{w.tree()}\n\n"
        f"stats: {w.stats()}\n\n"
        f"lint (head):\n{w.lint()[:600]}"
    )

    def _do_ingest() -> dict:
        import hashlib
        session_id = f"wiki-ingest-{hashlib.sha256(task.encode()).hexdigest()[:6]}"
        return w.ingest_session(
            session_id,
            [{"role": "user", "content": task}],
            runtime=runtime,
        )

    def _do_enrich() -> dict:
        return w.enrich_all(runtime=runtime)

    def _do_browse() -> dict:
        return {"action": "browse", "vault": str(w.root),
                "tree": w.tree(), "stats": w.stats()}

    def _do_lint() -> dict:
        return {"action": "lint", "vault": str(w.root), "report": w.lint()}

    def _do_search() -> dict:
        return {
            "action": "search", "task": task,
            "results": [
                {"path": h.path, "title": h.title, "snippet": h.snippet,
                 "template": h.template, "score": h.score}
                for h in w.search(task, limit=10)
            ],
        }

    return decision.make(
        (
            f"Pick the wiki operation that best matches the user task.\n\n"
            f"User task:\n{task}\n\n"
            f"Current vault state:\n{state}\n\n"
            f"Routing hints:\n"
            f"  - 'ingest' / 'add' / 'save these notes' / 'remember this' → ingest\n"
            f"  - 'enrich' / 'rewrite' / 'visualize' / 'make X richer' → enrich\n"
            f"  - 'show' / 'list' / 'what's in' / 'tree' → browse\n"
            f"  - 'check' / 'broken links' / 'health' → lint\n"
            f"  - anything else (looks like a query against existing content) → search"
        ),
        {
            "ingest":  _do_ingest,
            "enrich":  _do_enrich,
            "browse":  _do_browse,
            "lint":    _do_lint,
            "search":  _do_search,
        },
    )
