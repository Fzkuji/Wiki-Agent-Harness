# Wiki Agent Harness

A portable, self-contained wiki subsystem for AI agents. Obsidian-style vault with wikilink graph, SQLite FTS5 search, and agentic ingest/enrich pipelines. Zero external dependencies — pure Python standard library.

## Design

Three-layer architecture (after Karpathy):

```
Raw Sources  →  Wiki (markdown pages)  →  Schema (governance docs)
```

Pages are persistent artifacts that accumulate across sessions. Every ingest pass extends the wiki rather than regenerating it from scratch. The vault is plain markdown + YAML frontmatter + `[[wikilink]]` references — fully compatible with Obsidian out of the box.

Each page carries a `type:` field drawn from seven semantic roles: `entity`, `concept`, `procedure`, `user`, `source`, `query`, `synthesis`. Folder hierarchy acts as taxonomy; type acts as semantic metadata.

## Install

```bash
pip install -e .
# or, from another project:
pip install git+https://github.com/Fzkuji/Wiki-Agent-Harness.git
```

## Quick start

```python
from wiki_agent_harness import Wiki

w = Wiki(root="~/my-vault")   # defaults to WAH_VAULT env or ~/.agentic/memory/wiki

print(w.tree())                # folder outline
print(w.read("SomeTopic"))     # page by filename stem

# Link maintenance
w.rename("OldName", "NewName") # move + cascade-rewrite all [[wikilinks]]
w.prune_broken_links()
for hit in w.backlinks("SomeTopic"):
    print(hit["page"], hit["snippet"])

# Health check
print(w.lint())

# Agentic ingest (requires a runtime callable — see _runtime.py extension point)
w.ingest_session(session_id, messages, runtime=my_runtime)
```

## Operations

| Method | Purpose |
|--------|---------|
| `tree()` | Folder outline |
| `read(target)` | Read page by filename or path |
| `find(name)` | Resolve filename stem to absolute path |
| `iter_pages()` | Iterate all content pages |
| `lint()` | Structural health report |
| `rename(old, new)` | Move file + cascade-rewrite wikilinks |
| `relink(old, new)` | Cascade-rewrite wikilinks only |
| `prune_broken_links()` | Strip dangling `[[...]]` |
| `backlinks(name)` | Inbound references (Obsidian-style) |
| `unlinked_mentions(name)` | Plain-text mentions not yet linked |
| `delete_page(name)` | Remove page + optionally prune refs |
| `stats()` | Page counts, pending reviews, FTS rows |
| `ingest_session(...)` | Two-phase agentic conversation ingest |
| `git_commit(msg)` | Stage + commit vault changes |

## Runtime extension point

Agentic operations (`ingest_session`) require a runtime callable. Create `wiki_agent_harness/_runtime.py` in your project and expose `build_autodetect()` — the package will pick it up automatically. If absent, agentic ops raise a clear error asking you to supply a runtime.

## Acknowledgements

- **Andrej Karpathy** — [llm-wiki.md](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): originated the three-layer architecture (Raw Sources → Wiki → Schema), the persistent-accumulation model, and the Ingest / Query / Lint operation modes. The `index.md` + `log.md` dual-navigation pattern also comes from this design.

- **nashsu** — [llm_wiki](https://github.com/nashsu/llm_wiki): demonstrated the two-phase ingest pipeline (analyse first, generate second), the async human review queue, and the `type:`-based semantic page classification. The seven page types used here are derived from this project's schema.
