# Wiki Agent Harness

A generic, template-driven HTML wiki for AI agents. Pages are real HTML
files (open in any browser); agents fill named slots inside a fixed
template shell, so they never have to write HTML or CSS by hand.

The harness is **deliberately loose**. It gives the agent five things —
the rendering layer, the slot primitive, full-text search, folder
auto-indexing, and a tidy-aware ingest pipeline — and lets the agent use
ordinary shell + file-edit tools for everything else (mv, rm, grep, edit).

---

## Table of contents

1. [Why](#why)
2. [Install](#install)
3. [Quick start (Python)](#quick-start-python)
4. [Quick start (CLI)](#quick-start-cli)
5. [Architecture](#architecture)
6. [Page format](#page-format)
7. [Built-in templates](#built-in-templates)
8. [Workflow: write + tidy, interleaved](#workflow-write--tidy-interleaved)
9. [Extension points](#extension-points)
10. [Python API reference](#python-api-reference)
11. [CLI reference](#cli-reference)
12. [Ingest pipeline](#ingest-pipeline)
13. [Acknowledgements](#acknowledgements)

---

## Why

Existing agent-memory systems either drop everything into one giant
markdown file (no structure) or build a custom React app (no portability).
This harness sits in between:

- **HTML pages** are the persistent artifact — open with any browser,
  host on any static server, version-control with git, hand to any other
  tool to read.
- **Templates** (Jinja2 + Bootstrap 5 via CDN) provide the shell, layout,
  and component styles. Zero build step. No Node. No JS framework.
- **Slots** are HTML-comment-delimited regions inside each page. Agents
  edit one slot at a time across many sessions without rewriting the
  rest of the page — successive ingests accumulate cleanly.
- **Folder `README.html`** indexes are auto-generated from each folder's
  current contents. No hand-curated table of contents.
- **Generic ingest pipeline** with overridable prompts: a downstream
  project (paper survey, memory store, CRM, bug tracker, …) specialises
  by passing its own templates and prompts, not by forking.

## Install

```bash
pip install -e .
# or, from another project:
pip install git+https://github.com/Fzkuji/Wiki-Agent-Harness.git
```

Installs:
- Python package `wiki_agent_harness` with the `Wiki` class
- CLI command `wah` (also reachable via `python -m wiki_agent_harness`)

## Quick start (Python)

```python
from wiki_agent_harness import Wiki

w = Wiki(root="~/my-vault")

page = w.new_page(
    "concepts/transformers",
    template="concept",
    meta={"title": "Transformers", "tags": ["nlp", "architecture"]},
)
w.write_slot(page, "summary",
             "An attention-based architecture that replaced RNNs.")
w.write_slot(page, "body",
             "<p>Multi-head self-attention as an alternative to recurrence.</p>")

print(w.tree())
print(w.lint())

for hit in w.search("attention"):
    print(hit.score, hit.path)
```

Open `~/my-vault/README.html` in a browser — that's the auto-generated
landing page.

## Quick start (CLI)

Set a default vault once, then drop the `--root` flag from later
commands:

```bash
export WAH_VAULT=~/my-vault

wah list-templates
wah new concepts/transformers -t concept --title Transformers --tag nlp
wah write-slot transformers summary --content "An attention-based architecture."
echo '<p>...body html...</p>' | wah write-slot transformers body
wah tree
wah search attention
wah lint
```

See [CLI reference](#cli-reference) for the full command list.

## Architecture

Three layers, bottom up:

```
┌──────────────────────────────────────────────────────────────┐
│  Ingest pipeline                                             │
│   (1) Analysis  ── LLM produces a plan from the source       │
│   (2) Generation ── agentic runtime writes/tidies pages       │
│   (3) Bookkeeping ── folder indexes + FTS + git commit        │
├──────────────────────────────────────────────────────────────┤
│  Wiki API + CLI                                              │
│   new_page · write_slot · append_slot · set_meta             │
│   read · meta · slot · find · tree · search · lint           │
│   rebuild_folder_index                                       │
├──────────────────────────────────────────────────────────────┤
│  Templates + slots                                           │
│   Jinja2 shell (Bootstrap CDN) + named slots + meta block    │
│   Source of truth: a folder of plain .html files             │
└──────────────────────────────────────────────────────────────┘
```

Anything not in this list — moving a page, deleting one, fixing hrefs,
merging two pages — uses ordinary shell + file-edit tools (`mv`, `rm`,
`grep`, your editor). The harness deliberately does not wrap them.

## Page format

Each page is one HTML file. Two kinds of agent-editable regions are
marked by HTML comments so they remain valid HTML:

```html
<!DOCTYPE html>
<html>
<head>...Bootstrap CDN...</head>
<body>
  <nav>...</nav>
  <main>
    <!-- wah:meta
template: concept
title: Transformers
tags: [nlp, architecture]
related:
  - href: ../papers/vaswani-2017.html
    title: Attention Is All You Need
updated: 2026-05-25
-->

    <h1>Transformers</h1>

    <!-- wah:slot id="summary" -->
    An attention-based architecture.
    <!-- /wah:slot -->

    <!-- wah:slot id="body" -->
    <p>Multi-head self-attention …</p>
    <!-- /wah:slot -->
  </main>
  <footer>...</footer>
</body>
</html>
```

- **Meta block** — one per page, YAML body, near the top of `<body>`.
  Carries title, template name, tags, related links, updated date.
- **Slots** — named regions for body content. Which slots exist is
  declared by the template.

Everything outside meta + slots is shell, regenerated on demand from
the template. Re-rendering preserves the current slot contents.

## Built-in templates

| Template | Purpose | Slots |
|---|---|---|
| `landing` | top-level overview / hero | tagline, body, highlights |
| `concept` | abstract idea / definition / technique | summary, body, examples, related_notes |
| `entity` | named thing (person, project, dataset) | summary, attributes, description, related_notes |
| `procedure` | step-by-step how-to | summary, prerequisites, steps, pitfalls |
| `source` | external reference (paper, article) | citation, abstract, key_points, excerpts |
| `comparison` | side-by-side comparison | summary, table, verdict |
| `note` | free-form catch-all | body |
| `folder` | auto-generated folder index (READMEs) | description |

`wah list-templates` (or `w.template_help()`) prints the catalog with
declared slots.

## Workflow: write + tidy, interleaved

Maintaining a vault means two equally important things:

1. **Writing pages** — turn new material into structured pages.
2. **Tending the folder structure** — keep folder READMEs informative,
   split folders before they overflow, rename / move / delete stale
   pages.

The default ingest prompt expects these to be **interleaved**, not
sequenced. After every 2–3 page writes, the agent pauses and tidies the
folders it just touched. Waiting until a folder has 10+ files before
reorganising leaves the index incoherent and makes navigation worse.

The harness provides the primitives that auto-rebuild and search; the
agent uses ordinary tools for the rest:

| Need | Tool |
|---|---|
| Create a new page | `Wiki.new_page` (template → HTML shell) |
| Fill / edit content | `Wiki.write_slot`, `Wiki.append_slot` |
| Update metadata | `Wiki.set_meta` |
| Write a folder's human-written description | `Wiki.write_slot(folder/README.html, "description", ...)` |
| Rename / move a page | `mv old.html new.html`, then `grep -rn 'href=".*old' .` and fix each match, then `rebuild_folder_index` on old + new parents |
| Delete a page | `rm page.html`, then fix dangling hrefs, then `rebuild_folder_index` |
| Spot housekeeping problems | `Wiki.lint()` — flags crowded folders (>7 direct pages), empty descriptions, broken hrefs, empty folders |

The folder `description` slot survives across rebuilds, so once an agent
writes a description it won't be wiped when new sibling pages appear.

## Extension points

Three knobs let a downstream project specialise the harness without
forking.

### Custom templates

```python
w = Wiki(
    root="~/paper-vault",
    extra_template_dirs=["./my-templates"],
)
```

Any `*.html.j2` file in `./my-templates/` becomes a valid template name.
Same-named file overrides the built-in. Each template extends
`base.html.j2` and emits `<!-- wah:slot id="..." -->` blocks. Add a
header comment so introspection picks up the description:

```jinja
{#- description: arxiv paper notes. Slots: tldr, claims, method, results, critique. -#}
{% extends "base.html.j2" %}
{% block main %}
<h1>{{ meta.get("title") }}</h1>
<section>
  <h2>TL;DR</h2>
  <!-- wah:slot id="tldr" --><!-- /wah:slot -->
</section>
...
{% endblock %}
```

### Custom prompts

```python
from wiki_agent_harness import Wiki, PromptSet

prompts = PromptSet().with_overrides(analysis=MY_ANALYSIS_PROMPT)
w = Wiki(root="~/paper-vault", prompts=prompts)
```

Default prompts are domain-neutral. Override either `analysis` or
`generation` (or both) to bias toward your domain — paper triage, bug
triage, CRM notes, whatever.

### Purpose

```python
w = Wiki(
    root="~/research-memory",
    purpose="Track open questions and reading notes for my PhD on "
            "uncertainty quantification in LLMs. Skip generic ML facts.",
)
```

The `purpose` string is injected into the analysis prompt to govern
scope.

## Python API reference

### Class `Wiki`

```python
Wiki(
    root: str | Path | None = None,
    *,
    extra_template_dirs: list[str | Path] | None = None,
    prompts: PromptSet | None = None,
    runtime: Any | None = None,
    purpose: str = "",
)
```

#### Read

| Method | Returns | Purpose |
|---|---|---|
| `tree(max_depth=8)` | str | folder outline |
| `index()` | str | flat list of all content page paths, vault-relative |
| `iter_pages()` | Iterator[Path] | every content page |
| `find(name)` | Path \| None | resolve a name (case-insensitive) to a path |
| `read(target)` | str \| None | full HTML of a page |
| `meta(target)` | dict | parsed meta block |
| `slot(target, slot_id)` | str \| None | one slot's content |
| `list_slots(target)` | list[str] | slot ids declared on a page |
| `list_templates()` | list[TemplateInfo] | discovered templates |
| `template_help()` | str | one-line summary of every template |

#### Write

| Method | Purpose |
|---|---|
| `new_page(path, *, template, meta=None)` | render a fresh page; auto-rebuilds the chain of folder indexes |
| `write_slot(target, slot_id, content)` | overwrite a slot |
| `append_slot(target, slot_id, content)` | append to a slot |
| `set_meta(target, updates)` | merge into the meta block |
| `rebuild_folder_index(folder=None)` | regenerate one folder's `README.html` (preserves its `description` slot) |
| `rebuild_all_folder_indexes()` | regenerate every folder's `README.html` |

#### Search

| Method | Purpose |
|---|---|
| `search(query, limit=5)` | BM25 FTS5 over the concatenated slot text of every page |
| `reindex()` | full FTS rebuild |

#### Health / git

| Method | Purpose |
|---|---|
| `lint()` | health report (missing meta, unknown template, broken hrefs, folder housekeeping) |
| `stats()` | counts (pages total, by template, FTS row count) |
| `git_commit(message)` | `git add -A && git commit -m …` |

#### Agentic ingest

```python
w.ingest_session(session_id: str, messages: list[dict], *, runtime=None)
```

Runs the two-step pipeline (analysis → generation) over a conversation.
See [Ingest pipeline](#ingest-pipeline).

### Module-level helpers

```python
from wiki_agent_harness import PromptSet, Renderer, TemplateInfo, default

default()      # Wiki bound to ~/.agentic/memory/wiki (or $WAH_VAULT)
PromptSet()    # default prompts; .with_overrides(...) to tweak
```

## CLI reference

The CLI mirrors the Python API. Every command takes `--root PATH` (or
falls back to `$WAH_VAULT`).

### Read

```
wah tree [--max-depth N]      # folder outline
wah index                     # flat path list
wah find NAME                 # resolve a name to a path
wah read TARGET               # print a page's full HTML
wah meta TARGET               # print a page's meta block as YAML
wah slot TARGET SLOT_ID       # print one slot's content (raw HTML)
wah list-slots TARGET         # slot ids declared on a page
wah list-templates            # template catalog with descriptions + slots
```

### Write

```
wah new PATH --template T [--title TITLE] [--tag X ...] [--meta K=V ...]
    # PATH may be a bare name or 'area/topic/name'
    # --meta values are JSON-decoded when possible:
    #   --meta 'priority=3' --meta 'draft=true' --meta 'aliases=[a,b]'

wah write-slot TARGET SLOT_ID  [--content "..." | --file PATH | -]
wah append-slot TARGET SLOT_ID [--content "..." | --file PATH | -]
    # If neither --content nor --file given, reads from stdin.

wah set-meta TARGET KEY=VAL [KEY=VAL ...]
```

### Folder index

```
wah rebuild [FOLDER]          # regenerate one folder's README.html
wah rebuild-all               # regenerate every folder's README.html
```

### Search

```
wah search "query terms" [--limit N]      # BM25 over slot text
wah reindex                                # full FTS rebuild
```

### Health / git

```
wah lint
wah stats
wah commit "message"
```

### Examples

Create a topic, fill it, search, lint:

```bash
export WAH_VAULT=~/research-vault

wah new ml/transformer -t concept \
        --title Transformer --tag nlp --tag architecture

cat <<'HTML' | wah write-slot transformer body
<p>Multi-head self-attention as the dominant sequence model.</p>
<h3>Key components</h3>
<ul>
  <li>Multi-head attention</li>
  <li>Feed-forward layers</li>
  <li>Layer normalisation</li>
  <li>Residual connections</li>
</ul>
HTML

wah set-meta transformer 'related=[{href: "../papers/vaswani-2017.html", title: "Attention Is All You Need"}]'

wah search attention
wah lint
wah commit "add transformer concept page"
```

Move a page (ordinary shell, then patch hrefs, then rebuild):

```bash
cd $WAH_VAULT
mkdir -p architectures
mv ml/transformer.html architectures/transformer.html

# fix any hrefs pointing at the old location
grep -rln 'href="../ml/transformer\.html"' .       # locate
# edit each match by hand, OR e.g.:
grep -rln 'href="../ml/transformer\.html"' . \
  | xargs sed -i '' 's|href="../ml/transformer\.html"|href="../architectures/transformer.html"|g'

wah rebuild ml
wah rebuild architectures
wah lint        # verify zero broken links
```

## Ingest pipeline

`ingest_session(session_id, messages, runtime=)` runs in two steps:

1. **Analysis.** The harness assembles purpose statement + folder tree +
   flat page index + template catalog + the source (rendered
   conversation), runs the `analysis` prompt against the runtime, and
   gets back a structured plan (which pages to create / update, which
   template, which folder, plus a folder-housekeeping section).
2. **Generation.** The harness runs the `generation` prompt against the
   runtime with file tools enabled; the agent calls `new_page`,
   `write_slot`, etc., interleaved with shell-level tidying (`mv`,
   `rm`, grep + edit).

After step 2, the harness automatically:

- rebuilds folder indexes for every touched folder (up to the vault
  root),
- refreshes FTS index entries,
- parses an optional review queue block out of the agent's report
  (`<<<REVIEW_QUEUE>>>…<<<END>>>` JSON list) and appends to
  `.state/review-queue.json`,
- runs `git commit` if the vault is a git repo.

### Runtime contract

The `runtime` is any object exposing:

```python
runtime.exec(
    content=[{"type": "text", "text": "..."}],
    tools=[...] | None,
    max_iterations=int,
) -> str
```

This matches OpenProgram's runtime, but anything that satisfies the
shape (Anthropic SDK wrapper, custom REPL, mock) works.

### Specialising for a domain

```python
from wiki_agent_harness import Wiki, PromptSet

PAPER_ANALYSIS = """\
You are an arXiv paper analyst. For each paper in the source, list:
  - title
  - one-line claim
  - method category (architectural | training | evaluation | theory)
  - existing related page in the wiki (check the index)
  - target folder (under papers/<year>/)

Folder housekeeping section: same as default.
... {purpose} ... {index} ... {tree} ... {templates} ...
... {template_details} ... {source_title} ... {source}
"""

w = Wiki(
    root="~/paper-vault",
    extra_template_dirs=["./paper-templates"],
    prompts=PromptSet().with_overrides(analysis=PAPER_ANALYSIS),
    purpose="Reading notes for my reading group; keep critique sharp.",
)

w.ingest_session(session_id, messages, runtime=my_runtime)
```

## Acknowledgements

- **Andrej Karpathy** — [llm-wiki.md](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f):
  the persistent-accumulation model and the index + log navigation
  pattern.
- **nashsu** — [llm_wiki](https://github.com/nashsu/llm_wiki):
  the two-phase ingest pipeline (analyse first, generate second) and
  the human-review queue.
- **OpenProgram canvas tool** — the named-block-in-comments format used
  here for slots is the same idea applied to HTML.

## Part of [OpenProgram](https://github.com/Fzkuji/OpenProgram)
