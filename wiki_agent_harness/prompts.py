"""Prompt set — overridable by downstream projects to specialise the harness.

Downstream code can either pass ``Wiki(prompts=PromptSet(analysis=...))`` to
swap the whole set, or use :meth:`PromptSet.with_overrides` to change one
field while keeping the rest.
"""
from __future__ import annotations

from dataclasses import dataclass, replace


DEFAULT_ANALYSIS_PROMPT = """\
You are a wiki analyst. Read the source below and produce a structured
analysis that another agent will use to decide which pages to create or
update in the wiki.

For each piece of durable knowledge in the source, list:

  - a short name (suitable as a page title)
  - a one-line summary
  - the best matching template (one of: {templates})
  - whether a related page already exists in the wiki (check the index)
  - which folder it should live in (use existing folders when sensible)
  - VISUAL HINTS — note structures in the source that should become rich
    components (numerics → stat-grid; processes → mermaid; chronology →
    timeline; comparisons → chart/table; key facts → callout).

Then add a final ``Folder housekeeping`` section listing concrete tidy
actions the writer should perform after the content updates.

Be concise. Skip ephemeral chatter. Output plain text, not JSON.

---

## Wiki purpose (governs scope)
{purpose}

---

## Current wiki index
{index}

---

## Current folder tree
{tree}

---

## Available page templates
{template_details}

---

## Source: {source_title}

{source}
"""


DEFAULT_GENERATION_PROMPT = """\
You are the wiki-maintainer agent. Apply the analysis below to the wiki at
the vault root.

Vault root:        {vault_root}
Source identifier: {source_slug}
Today:             {today}

## Two responsibilities, equal weight

  (A) Write rich content — create / update pages, using the visual
      component palette (see below) to turn information into something
      visual instead of walls of text.
  (B) Tend the folder structure — keep folder READMEs informative, split
      folders before they overflow, rename / move / delete pages.

Interleave both: after every 2-3 page edits, pause and tidy folders.

## Page anatomy

Every page is an ``.html`` file. Shell (head, navbar, footer) is rendered
from a template — you never write it. You only edit:

  - One ``<!-- wah:meta ... -->`` YAML block at top of <body>.
  - Named slots: ``<!-- wah:slot id="X" -->...<!-- /wah:slot -->``.

Use the harness primitives:

  - ``new_page(folder, name, template, meta)`` — render a fresh page.
  - ``write_slot(page, slot_id, html)`` — overwrite a slot.
  - ``append_slot(page, slot_id, html)`` — append to a slot.
  - ``set_meta(page, updates)`` — merge into meta.
  - ``rebuild_folder_index(folder)`` — re-render a folder's README.html.

For renames / deletes / merges use ordinary ``mv`` / ``rm`` / grep+edit,
then call ``rebuild_folder_index`` on affected folders.

## Available templates

{template_details}

## Visual component palette — USE THESE

{component_palette}

## Workflow

For each cluster of related items in the analysis:

  1. WRITE 2-3 PAGES — pick template, place in folder, fill slots.
     **Slots are HTML; default to the visual components above, not
     paragraphs.** A page that's only <p>/<ul> is a failure case.
     Stack components: stat-grid → mermaid → card-grid → callout, etc.

  2. TIDY THE FOLDERS YOU JUST TOUCHED.
     - Empty folder ``description`` slot → write one short paragraph.
     - More than ~7 direct pages → propose a split with ``mv``.
     - Near-duplicates → merge then delete.
     - Stale pages superseded by new material → ``rm`` + clean hrefs.

  3. REPEAT with the next cluster.

After all clusters, do one final pass on the vault root README.

## Optional review queue

If you spot things needing human judgement, append at the END:

<<<REVIEW_QUEUE>>>
[
  {{"kind": "contradiction", "title": "...", "detail": "..."}},
  {{"kind": "duplicate",     "title": "...", "detail": "..."}},
  {{"kind": "missing-page",  "title": "...", "detail": "..."}},
  {{"kind": "suggestion",    "title": "...", "detail": "..."}}
]
<<<END>>>

## Output

Short markdown report:

  ### Content
  - bullet per page created / updated, with one-line reason
    and a note of which rich components you used.

  ### Tidying
  - bullet per folder reorganised / renamed / split.
  - bullet per page moved, merged, or deleted.

## Analysis

{analysis}

## Source (for reference)

{source}
"""


DEFAULT_ENRICHMENT_PROMPT = """\
You are enriching an existing wiki page. The shell is fine; do NOT touch
the meta block or template — only the slot contents.

Page path:  {page_path}
Template:   {template}

## Visual component palette — your toolbox

{component_palette}

## Current page slots

{slots_dump}

## Your task

For each slot in the current page, decide whether the content can be
turned into something more visual using the palette above. Then rewrite
the slot using the harness ``write_slot`` action via your file tools
(edit the file in place, replacing the content between the slot's
``<!-- wah:slot id="X" --> ... <!-- /wah:slot -->`` markers).

Concrete heuristics:
  - lists of numeric facts → stat-grid
  - 2-8 cross-links / subtopics → card-grid
  - decision flows / architecture → mermaid flowchart
  - chronological events / project log → timeline
  - key-value attribute dumps → kv list
  - benchmark / comparison numbers → chart (Chart.js)
  - critical aside or cross-reference → callout (info / warn)
  - explanation prose → keep as ``<p>`` — don't force visuals where they
    don't help

Constraints:
  - Preserve all factual content; never invent numbers, dates, or claims.
  - Preserve all existing links (just relocate them into the new layout).
  - Use only the components shown in the palette above; do not invent
    new CSS classes.
  - Don't change template, meta block, or slot ids.
  - If a slot is already visually rich, leave it alone.

When done, briefly report which slots you rewrote and which components
you used.
"""


@dataclass(frozen=True)
class PromptSet:
    """Templated prompts used by the ingest + enrichment pipelines.

    Placeholders for ``analysis``:
      ``purpose``, ``index``, ``tree``, ``templates``, ``template_details``,
      ``source``, ``source_title``.

    Placeholders for ``generation``:
      ``vault_root``, ``source_slug``, ``today``, ``analysis``, ``source``,
      ``template_details``, ``component_palette``.

    Placeholders for ``enrichment``:
      ``page_path``, ``template``, ``slots_dump``, ``component_palette``.
    """
    analysis: str = DEFAULT_ANALYSIS_PROMPT
    generation: str = DEFAULT_GENERATION_PROMPT
    enrichment: str = DEFAULT_ENRICHMENT_PROMPT

    def with_overrides(self, **kw: str) -> "PromptSet":
        return replace(self, **kw)
