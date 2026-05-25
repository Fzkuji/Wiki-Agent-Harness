---
name: wiki_agent
description: "Maintain a wiki vault — ingest source material into structured pages, enrich existing pages with visual components, browse / search / lint the vault. Top-level dispatcher; routes via decision.make to wiki_ingest, wiki_enrich, browse, lint, or search. Triggers: 'add to wiki', 'save these notes', 'ingest into wiki', 'enrich the page', 'visualize the docs', 'browse the vault', 'search the wiki', 'check broken links', 'wiki health'."
---

# wiki_agent

Single entry that routes a natural-language wiki task to the right operation.
Backed by ``wiki_agent_harness.Wiki``.

## When to use

- User mentions "wiki", "vault", "notes folder", or one of the trigger phrases.
- User has source material (text, transcript, doc, URL) they want stored
  in a structured, browsable form.
- User wants to improve / rewrite an existing wiki page visually.

## Inputs

- ``task`` — free-form description of what to do.
- ``vault`` — optional vault root (falls back to runtime workdir, then
  ``$WAH_VAULT``, then ``~/.agentic/memory/wiki``).

## Routing

Uses ``decision.make`` to pick one of: ``ingest`` / ``enrich`` / ``browse``
/ ``lint`` / ``search``. The picked branch runs and its return becomes the
function's return.

## Related

- ``wiki_ingest`` — invoked when the user is adding new material.
- ``wiki_enrich`` — invoked to rewrite a page's slots with rich
  components (stat-grid, mermaid, callout, gloss tooltip, ...).
