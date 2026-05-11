"""Wiki operations — pure-Python + agentic ops on the vault."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from . import store
from . import helpers as h

logger = logging.getLogger(__name__)


def _db_path(vault_root: Path) -> Path:
    state_dir = vault_root.parent / ".state"
    return store.index_db_path(state_dir)


# ---------------------------------------------------------------------------
# Lint
# ---------------------------------------------------------------------------


def lint(root: Path | None = None) -> str:
    """Walk the vault and report structural issues. Returns markdown."""
    vault_root = root or store.root()
    pages: list[Path] = list(h.iter_md_files(vault_root))
    if not pages:
        return "# Wiki lint report\n\n(empty vault — nothing to lint)"

    stems = {p.stem.lower(): p for p in pages}

    missing_type: list[str] = []
    bad_type: list[tuple[str, str]] = []
    missing_status: list[str] = []
    stem_mismatch: list[tuple[str, str]] = []
    broken_links: list[tuple[str, str]] = []
    inbound: dict[str, int] = {}
    outbound: dict[str, int] = {}
    folder_children: dict[Path, list[Path]] = {}

    for p in pages:
        rel = p.relative_to(vault_root)
        text = p.read_text(encoding="utf-8")
        fm, body = h.parse_frontmatter(text)
        t = fm.get("type")
        if not t:
            missing_type.append(str(rel))
        elif t not in store.WIKI_PAGE_TYPES:
            bad_type.append((str(rel), str(t)))
        if t == "query" and not fm.get("status"):
            missing_status.append(str(rel))

        if p.parent != vault_root and p.parent.name != p.stem:
            stem_mismatch.append((p.parent.name, p.stem))

        if p.parent != vault_root and p.parent.name == p.stem:
            folder_children[p.parent] = [
                c for c in p.parent.iterdir() if c.is_dir()
            ]

        stem_l = p.stem.lower()
        outbound.setdefault(stem_l, 0)
        for target in h.extract_wikilinks(body):
            outbound[stem_l] += 1
            inbound[target] = inbound.get(target, 0) + 1
            if target not in stems:
                broken_links.append((str(rel), target))

    orphans = [
        p.stem for p in pages
        if inbound.get(p.stem.lower(), 0) == 0
        and outbound.get(p.stem.lower(), 0) == 0
    ]

    refactor_candidates = [
        f.name for f, children in folder_children.items() if len(children) >= 6
    ]

    out: list[str] = [
        "# Wiki lint report",
        "",
        f"Pages: {len(pages)}",
        f"Missing `type:` frontmatter:           {len(missing_type)}",
        f"Unknown `type:` value:                 {len(bad_type)}",
        f"Query pages missing `status:`:         {len(missing_status)}",
        f"Folder/stem mismatches:                {len(stem_mismatch)}",
        f"Broken `[[wikilinks]]`:                {len(broken_links)}",
        f"Orphan pages:                          {len(orphans)}",
        f"Topics with ≥6 children (refactor?):   {len(refactor_candidates)}",
        "",
    ]

    def _section(title: str, rows: list[str]) -> None:
        if not rows:
            return
        out.append(f"## {title}")
        out.extend(f"- {r}" for r in rows[:30])
        if len(rows) > 30:
            out.append(f"- ... and {len(rows) - 30} more")
        out.append("")

    _section("Missing type", missing_type)
    _section("Unknown type", [f"`{p}` → `{t}`" for p, t in bad_type])
    _section("Query missing status", missing_status)
    _section("Folder/stem mismatch",
             [f"folder=`{f}`, stem=`{s}`" for f, s in stem_mismatch])
    _section("Broken wikilinks",
             [f"`{p}` → `[[{t}]]`" for p, t in broken_links])
    _section("Orphans", orphans)
    _section("Refactor candidates", refactor_candidates)

    return "\n".join(out).rstrip()


# ---------------------------------------------------------------------------
# Rename
# ---------------------------------------------------------------------------


def rename(old: str, new: str, root: Path | None = None) -> dict[str, Any]:
    """Rename a node by stem, rewriting all [[old]] → [[new]] wikilinks."""
    vault_root = root or store.root()
    db = _db_path(vault_root)
    target = h.find_node(vault_root, old)
    if target is None:
        return {"ok": False, "error": f"no page named {old!r}"}
    old_path_for_index = target

    if target.parent != vault_root and target.parent.name == target.stem:
        new_folder = target.parent.parent / new
        if new_folder.exists():
            return {"ok": False, "error": f"destination {new_folder} exists"}
        target.parent.rename(new_folder)
        (new_folder / f"{target.stem}.md").rename(new_folder / f"{new}.md")
        new_path_for_index = new_folder / f"{new}.md"
    else:
        new_path = target.with_name(f"{new}.md")
        if new_path.exists():
            return {"ok": False, "error": f"destination {new_path} exists"}
        target.rename(new_path)
        new_path_for_index = new_path

    rewrites = 0
    changed_paths: list[Path] = []
    for p in h.iter_md_files(vault_root):
        before = p.read_text(encoding="utf-8")
        after = h.rewrite_wikilinks(before, old, new)
        if after != before:
            p.write_text(after, encoding="utf-8")
            rewrites += 1
            changed_paths.append(p)

    try:
        from . import index as _idx
        _idx.remove_wiki_page(old_path_for_index, vault_root, db)
        _idx.update_wiki_page(new_path_for_index, vault_root, db)
        for p in changed_paths:
            _idx.update_wiki_page(p, vault_root, db)
    except Exception:
        pass

    return {"ok": True, "rewrites": rewrites}


def tree(root: Path | None = None, *, max_depth: int = 8) -> str:
    vault_root = root or store.root()
    return h.folder_tree(vault_root, max_depth=max_depth)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def delete_page(name: str, *, prune_refs: bool = True, root: Path | None = None) -> dict[str, Any]:
    """Delete a page and optionally strip [[name]] references across the vault."""
    vault_root = root or store.root()
    db = _db_path(vault_root)
    target = h.find_node(vault_root, name)
    if target is None:
        return {"ok": False, "error": f"no page named {name!r}"}

    deleted: list[str] = []
    if target.parent != vault_root and target.parent.name == target.stem:
        import shutil
        children = [c for c in target.parent.iterdir() if c.is_dir()]
        if children:
            return {
                "ok": False,
                "error": f"topic {name!r} still has {len(children)} subtopic children",
            }
        shutil.rmtree(target.parent)
        deleted.append(str(target.parent.relative_to(vault_root)))
    else:
        target.unlink()
        deleted.append(str(target.relative_to(vault_root)))

    try:
        from . import index as _idx
        _idx.remove_wiki_page(target, vault_root, db)
    except Exception:
        pass

    refs_stripped = 0
    if prune_refs:
        import re
        name_l = name.lower().removesuffix(".md")
        link_re = re.compile(r"\[\[([^\]|#]+?)(\|[^\]]+?)?(#[^\]]+?)?\]\]")
        for p in h.iter_md_files(vault_root):
            before = p.read_text(encoding="utf-8")
            masked, repls = h.mask_code(before)

            def _sub(m: "re.Match[str]") -> str:
                if m.group(1).strip().lower() != name_l:
                    return m.group(0)
                alias = (m.group(2) or "")[1:] if m.group(2) else ""
                anchor = m.group(3) or ""
                return (alias or m.group(1).strip()) + anchor

            after = h.unmask_code(link_re.sub(_sub, masked), repls)
            if after != before:
                p.write_text(after, encoding="utf-8")
                refs_stripped += 1
                try:
                    from . import index as _idx
                    _idx.update_wiki_page(p, vault_root, db)
                except Exception:
                    pass

    return {"ok": True, "deleted": deleted, "refs_stripped": refs_stripped}


# ---------------------------------------------------------------------------
# Backlinks
# ---------------------------------------------------------------------------


def backlinks(name: str, root: Path | None = None) -> list[dict[str, str]]:
    """Find every page with a [[name]] wikilink. Fast path via index."""
    import re
    vault_root = root or store.root()
    db = _db_path(vault_root)
    name_l = name.lower().removesuffix(".md")
    link_re = re.compile(r"\[\[([^\]|#]+?)(?:\|[^\]]+?)?(?:#[^\]]+?)?\]\]")
    out: list[dict[str, str]] = []
    try:
        from . import index as _idx
        rel_paths = _idx.inbound(name, db)
    except Exception:
        rel_paths = []

    if not rel_paths:
        for p in h.iter_md_files(vault_root):
            if p.stem.lower() == name_l:
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue
            masked, _ = h.mask_code(text)
            for m in link_re.finditer(masked):
                if m.group(1).strip().lower() == name_l:
                    start = max(0, m.start() - 60)
                    end = min(len(text), m.end() + 60)
                    snippet = text[start:end].replace("\n", " ").strip()
                    out.append({"page": str(p.relative_to(vault_root)), "snippet": snippet})
                    break
        return out

    for rel in rel_paths:
        p = vault_root / rel
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        masked, _ = h.mask_code(text)
        for m in link_re.finditer(masked):
            if m.group(1).strip().lower() == name_l:
                start = max(0, m.start() - 60)
                end = min(len(text), m.end() + 60)
                snippet = text[start:end].replace("\n", " ").strip()
                out.append({"page": rel, "snippet": snippet})
                break
    return out


# ---------------------------------------------------------------------------
# Unlinked mentions
# ---------------------------------------------------------------------------


def unlinked_mentions(name: str, *, max_per_page: int = 3, root: Path | None = None) -> list[dict[str, Any]]:
    """Find pages that mention ``name`` in plain text without a [[wikilink]]."""
    import re
    vault_root = root or store.root()
    name_l = name.lower().removesuffix(".md")
    pattern = re.compile(rf"(?<![\w]){re.escape(name)}(?![\w])", re.IGNORECASE)
    link_re = re.compile(r"\[\[[^\]]+\]\]")

    out: list[dict[str, Any]] = []
    for p in h.iter_md_files(vault_root):
        if p.stem.lower() == name_l:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        _fm, body = h.parse_frontmatter(text)
        masked, _ = h.mask_code(body)
        masked = link_re.sub(lambda m: " " * len(m.group(0)), masked)

        snippets: list[str] = []
        for m in pattern.finditer(masked):
            start = max(0, m.start() - 50)
            end = min(len(masked), m.end() + 50)
            ctx = body[start:end].replace("\n", " ").strip()
            snippets.append(ctx)
            if len(snippets) >= max_per_page:
                break
        if snippets:
            out.append({"page": str(p.relative_to(vault_root)), "occurrences": snippets})
    return out


# ---------------------------------------------------------------------------
# Relink
# ---------------------------------------------------------------------------


def relink(old: str, new: str, root: Path | None = None) -> dict[str, Any]:
    """Rewrite [[old]] → [[new]] across the vault without moving files."""
    vault_root = root or store.root()
    db = _db_path(vault_root)
    rewrites = 0
    changed: list[str] = []
    changed_paths: list[Path] = []
    for p in h.iter_md_files(vault_root):
        before = p.read_text(encoding="utf-8")
        after = h.rewrite_wikilinks(before, old, new)
        if after != before:
            p.write_text(after, encoding="utf-8")
            rewrites += after.lower().count(f"[[{new.lower()}") - before.lower().count(f"[[{new.lower()}")
            changed.append(str(p.relative_to(vault_root)))
            changed_paths.append(p)
    try:
        from . import index as _idx
        for p in changed_paths:
            _idx.update_wiki_page(p, vault_root, db)
    except Exception:
        pass
    return {"ok": True, "rewrites": rewrites, "pages": changed}


# ---------------------------------------------------------------------------
# Prune broken wikilinks
# ---------------------------------------------------------------------------


def prune_broken_links(*, dry_run: bool = True, root: Path | None = None) -> dict[str, Any]:
    """Find broken [[wikilinks]] and optionally strip the brackets."""
    import re
    vault_root = root or store.root()
    db = _db_path(vault_root)
    pages = list(h.iter_md_files(vault_root))
    stems = {p.stem.lower() for p in pages}

    wikilink_re = re.compile(r"\[\[([^\]|#]+?)(\|[^\]]+?)?(#[^\]]+?)?\]\]")
    broken: list[tuple[str, str]] = []
    applied = 0
    for p in pages:
        before = p.read_text(encoding="utf-8")
        masked, repls = h.mask_code(before)

        def _sub(m: "re.Match[str]") -> str:
            target = m.group(1).strip()
            if target.lower() in stems:
                return m.group(0)
            broken.append((str(p.relative_to(vault_root)), target))
            if dry_run:
                return m.group(0)
            alias = (m.group(2) or "")[1:] if m.group(2) else ""
            anchor = m.group(3) or ""
            return (alias or target) + anchor

        after = h.unmask_code(wikilink_re.sub(_sub, masked), repls)
        if not dry_run and after != before:
            p.write_text(after, encoding="utf-8")
            applied += 1
            try:
                from . import index as _idx
                _idx.update_wiki_page(p, vault_root, db)
            except Exception:
                pass

    return {"ok": True, "broken": broken, "applied": applied, "dry_run": dry_run}


# ---------------------------------------------------------------------------
# Survey (agentic)
# ---------------------------------------------------------------------------


SURVEY_PROMPT = """\
You are rewriting a topic page in our wiki as a coherent
Wikipedia-style article from its child pages.

Topic file:  {topic_path}
Vault root:  {vault_root}

YOUR JOB

1. Read `{topic_path}` — that's the topic page to rewrite.
2. Read every child page in `{topic_folder}/` (the same folder).
3. Cluster the children into 2-5 natural sub-areas if there are
   enough; if fewer than 4 children, just write one cohesive article.
4. Use `edit` (preferred) or `write` to update `{topic_path}` so its
   BODY (after the YAML frontmatter) is a coherent prose article
   discussing the children with `[[wikilinks]]` to them.
5. Preserve the frontmatter verbatim. Keep the `# <Title>` heading.
6. Don't touch any of the child pages.

Return: one-line confirmation of what you did.
"""


def survey(topic: str, root: Path | None = None) -> dict[str, Any]:
    """Rewrite a topic page from its children (agentic)."""
    vault_root = root or store.root()
    target = h.find_node(vault_root, topic)
    if target is None:
        return {"ok": False, "error": f"no page named {topic!r}"}
    if target.parent == vault_root or target.parent.name != target.stem:
        return {"ok": False, "error": f"page {topic!r} is a leaf, not a topic folder"}

    runtime = _build_runtime()
    if runtime is None:
        return {"ok": False, "error": "no runtime configured"}

    prompt = SURVEY_PROMPT.format(
        topic_path=str(target),
        topic_folder=str(target.parent),
        vault_root=str(vault_root),
    )
    try:
        report = runtime.exec(
            content=[{"type": "text", "text": prompt}],
            max_iterations=20,
        )
    except Exception as e:
        return {"ok": False, "error": f"exec: {e}"}
    return {"ok": True, "report": report}


# ---------------------------------------------------------------------------
# Refactor (agentic)
# ---------------------------------------------------------------------------


REFACTOR_PROMPT = """\
You are refactoring an overgrown topic in our wiki. The topic has
≥6 direct children — propose 2-4 sub-clusters and reorganise.

Topic file:    {topic_path}
Topic folder:  {topic_folder}
Vault root:    {vault_root}

YOUR JOB

1. Read `{topic_path}` and every child page in `{topic_folder}/`.
2. Decide on 2-4 sub-cluster names that group the children naturally.
3. For each cluster, create a new subtopic folder + page:
   `{topic_folder}/<Cluster Name>/<Cluster Name>.md`
   with `type: topic` frontmatter and a short opening paragraph.
4. Move each child page's folder under the right sub-cluster.
5. Edit `{topic_path}` to mention each new sub-cluster with a [[wikilink]].
6. Wikilinks to the moved pages STAY VALID because they use filename stems.

Return: one-line confirmation of what you did, or an error.
"""


def refactor(topic: str, root: Path | None = None) -> dict[str, Any]:
    vault_root = root or store.root()
    target = h.find_node(vault_root, topic)
    if target is None:
        return {"ok": False, "error": f"no page named {topic!r}"}
    if target.parent == vault_root or target.parent.name != target.stem:
        return {"ok": False, "error": f"page {topic!r} is a leaf, not a topic folder"}

    children = [c for c in target.parent.iterdir() if c.is_dir()]
    if len(children) < 6:
        return {"ok": False, "error": f"only {len(children)} children — not enough for refactor"}

    runtime = _build_runtime()
    if runtime is None:
        return {"ok": False, "error": "no runtime configured"}

    prompt = REFACTOR_PROMPT.format(
        topic_path=str(target),
        topic_folder=str(target.parent),
        vault_root=str(vault_root),
    )
    try:
        report = runtime.exec(
            content=[{"type": "text", "text": prompt}],
            max_iterations=30,
        )
    except Exception as e:
        return {"ok": False, "error": f"exec: {e}"}
    return {"ok": True, "report": report}


# ---------------------------------------------------------------------------
# Runtime helper
# ---------------------------------------------------------------------------


def _build_runtime() -> Any | None:
    try:
        from wiki_agent_harness._runtime import build_autodetect
        return build_autodetect()
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Git commit
# ---------------------------------------------------------------------------


def git_commit(message: str, root: Path | None = None) -> dict[str, Any]:
    """Stage all changes in the vault and commit."""
    import subprocess
    vault_root = root or store.root()
    if not (vault_root / ".git").exists():
        return {"ok": False, "error": "vault is not a git repo"}

    try:
        subprocess.run(
            ["git", "-C", str(vault_root), "add", "-A"],
            check=True, capture_output=True, timeout=15,
        )
        status = subprocess.run(
            ["git", "-C", str(vault_root), "status", "--porcelain"],
            check=True, capture_output=True, timeout=15, text=True,
        ).stdout.strip()
        if not status:
            return {"ok": True, "committed": False}
        subprocess.run(
            ["git", "-C", str(vault_root), "commit", "-m", message,
             "--author", "WikiAgentHarness <memory@wiki-agent.local>"],
            check=True, capture_output=True, timeout=15,
        )
        h_val = subprocess.run(
            ["git", "-C", str(vault_root), "rev-parse", "--short", "HEAD"],
            check=True, capture_output=True, timeout=15, text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError as e:
        return {"ok": False, "error": f"git: {e.stderr.decode() if e.stderr else e}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "committed": True, "hash": h_val}


# ---------------------------------------------------------------------------
# Review queue
# ---------------------------------------------------------------------------


def review_list(*, only_pending: bool = True, root: Path | None = None) -> list[dict[str, Any]]:
    import json
    vault_root = root or store.root()
    state_dir = vault_root.parent / ".state"
    qpath = store.review_queue_path(state_dir)
    if not qpath.exists():
        return []
    try:
        items = json.loads(qpath.read_text(encoding="utf-8"))
    except Exception:
        return []
    if only_pending:
        items = [it for it in items if not it.get("resolved")]
    return items


def review_resolve(item_id: int, *, action: str = "ack", note: str = "",
                   root: Path | None = None) -> dict[str, Any]:
    import json
    from datetime import datetime
    vault_root = root or store.root()
    state_dir = vault_root.parent / ".state"
    qpath = store.review_queue_path(state_dir)
    if not qpath.exists():
        return {"ok": False, "error": "review queue is empty"}
    try:
        items = json.loads(qpath.read_text(encoding="utf-8"))
    except Exception as e:
        return {"ok": False, "error": f"parse: {e}"}
    for it in items:
        if it.get("id") == item_id:
            it["resolved"] = True
            it["resolved_at"] = datetime.now().isoformat(timespec="seconds")
            it["resolution"] = {"action": action, "note": note}
            qpath.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
            return {"ok": True, "item": it}
    return {"ok": False, "error": f"no item with id={item_id}"}


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def stats(root: Path | None = None) -> dict[str, Any]:
    vault_root = root or store.root()
    pages = list(h.iter_md_files(vault_root))
    by_type: dict[str, int] = {}
    for p in pages:
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        fm, _ = h.parse_frontmatter(text)
        t = fm.get("type") or "?"
        by_type[t] = by_type.get(t, 0) + 1

    db = _db_path(vault_root)
    try:
        from . import index as _idx
        idx_stats = _idx.stats(db)
    except Exception:
        idx_stats = {}

    pending_reviews = len(review_list(only_pending=True, root=vault_root))

    return {
        "pages_total": len(pages),
        "pages_by_type": by_type,
        "pending_reviews": pending_reviews,
        "fts_wiki_rows": idx_stats.get("wiki_pages", 0),
        "last_reindex": idx_stats.get("last_reindex"),
        "vault_root": str(vault_root),
    }
