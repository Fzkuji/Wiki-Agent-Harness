"""Post-ingest wikilink enrichment.

Approach:
  1. Read the wiki index.md.
  2. Read ONE wiki page.
  3. Ask the LLM to return ONLY a JSON list of {term, target} substitutions.
  4. Python applies substitutions deterministically.

For inbound enrichment: scan the vault for unlinked plain-text mentions
of a new page's name and convert validated ones to [[name]].
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Callable

from . import store

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """\
You identify which terms in a wiki page should become [[wikilinks]] pointing
to existing wiki pages.

You will receive:
  - a wiki index listing existing pages (each line roughly like `- pagename`)
  - the content of ONE wiki page

Return a JSON object listing which terms in the page content should be linked
to which index entries.

Response format (EXACTLY this JSON shape, nothing else):
{
  "links": [
    { "term": "exact text appearing in the content", "target": "index page name" }
  ]
}

Rules:
- Each "term" MUST be a literal substring present in the page content (case-sensitive).
- Each "target" MUST be a page listed in the wiki index.
- Include at most one entry per target (first mention).
- Only include clearly-matching terms.
- Do NOT link a term to the same page it appears in (no self-links).
- If no terms should be linked, return `{"links": []}`.
- Do NOT output preamble, explanations, or markdown fences — ONLY the JSON object.
"""


def enrich_page(
    page_path: Path,
    *,
    llm: Callable[[str, str], str],
    vault_root: Path | None = None,
) -> dict[str, Any]:
    """Run one enrichment pass over a single wiki page."""
    root = vault_root or store.root()
    if not page_path.exists():
        return {"ok": False, "error": "page does not exist"}

    try:
        content = page_path.read_text(encoding="utf-8")
    except OSError as e:
        return {"ok": False, "error": f"read: {e}"}

    index_path = root / "index.md"
    if not index_path.exists():
        return {"ok": False, "error": "no wiki index — nothing to link against"}
    index_text = index_path.read_text(encoding="utf-8")
    if not index_text.strip():
        return {"ok": False, "error": "wiki index is empty"}

    user_text = (
        f"## Wiki Index\n{index_text}\n\n"
        f"Page content:\n\n{content}"
    )

    try:
        raw = llm(SYSTEM_PROMPT, user_text)
    except Exception as e:
        logger.warning("enrich-wikilinks llm call failed for %s: %s", page_path, e)
        return {"ok": False, "error": f"llm: {e}"}

    links = _parse_link_response(raw)
    if not links:
        return {"ok": True, "changed": False, "n_links": 0}

    self_slug = page_path.stem.lower()
    links = [l for l in links if l["target"].lower().rstrip("s") != self_slug.rstrip("s")
             and l["target"].lower() != self_slug]

    enriched = _apply_links(content, links)
    if enriched == content:
        return {"ok": True, "changed": False, "n_links": 0}

    try:
        page_path.write_text(enriched, encoding="utf-8")
    except OSError as e:
        return {"ok": False, "error": f"write: {e}"}

    try:
        from . import index as _idx
        db = _idx_db_path(root)
        _idx.update_wiki_page(page_path, root, db)
    except Exception:
        pass

    return {"ok": True, "changed": True, "n_links": _count_new_links(content, enriched)}


def enrich_pages(
    paths: list[Path],
    *,
    llm: Callable[[str, str], str],
    vault_root: Path | None = None,
) -> dict[str, Any]:
    """Run enrichment on a batch of pages. Returns aggregate stats."""
    total_changed = 0
    total_links = 0
    errors: list[str] = []
    for p in paths:
        result = enrich_page(p, llm=llm, vault_root=vault_root)
        if not result.get("ok"):
            errors.append(f"{p.name}: {result.get('error')}")
            continue
        if result.get("changed"):
            total_changed += 1
            total_links += int(result.get("n_links") or 0)
    return {
        "ok": True,
        "pages_changed": total_changed,
        "links_added": total_links,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Inbound enrichment
# ---------------------------------------------------------------------------


INBOUND_SYSTEM_PROMPT = """\
You decide which plain-text mentions of a page name should become
[[wikilinks]] pointing at it.

You will receive:
  - the name of a wiki page (the link target)
  - a list of candidate mentions: each one is a context snippet from
    some OTHER page where the name appears as plain text

For each candidate, answer "yes" (this should be a wikilink) or
"no" (don't link it — same word, unrelated meaning, or generic usage).

Response format — EXACTLY this JSON shape, nothing else:
{
  "decisions": [
    { "i": 0, "link": true },
    { "i": 1, "link": false }
  ]
}

Be conservative. If a mention is ambiguous, say no.
"""


def enrich_inbound_for_new_page(
    new_page: Path,
    *,
    llm: Callable[[str, str], str],
    max_candidates: int = 30,
    vault_root: Path | None = None,
) -> dict[str, Any]:
    """Scan the vault for unlinked plain-text mentions of new_page.stem."""
    from . import ops as wiki_ops

    root = vault_root or store.root()
    name = new_page.stem
    raw_mentions = wiki_ops.unlinked_mentions(name, max_per_page=2, root=root)
    if not raw_mentions:
        return {"ok": True, "candidates": 0, "linked": 0, "pages_changed": 0}

    candidates: list[tuple[Path, str]] = []
    for entry in raw_mentions:
        page_path = root / entry["page"]
        for snippet in entry["occurrences"]:
            candidates.append((page_path, snippet))
            if len(candidates) >= max_candidates:
                break
        if len(candidates) >= max_candidates:
            break

    user_text = (
        f"Page name (link target): {name}\n\n"
        "Candidates:\n"
        + "\n".join(
            f"[{i}] page=`{p.relative_to(root)}` snippet: {s!r}"
            for i, (p, s) in enumerate(candidates)
        )
    )

    try:
        raw = llm(INBOUND_SYSTEM_PROMPT, user_text)
    except Exception as e:
        logger.warning("inbound enrich llm call failed for %s: %s", new_page, e)
        return {"ok": False, "error": f"llm: {e}"}

    decisions = _parse_inbound_response(raw)
    if not decisions:
        return {"ok": True, "candidates": len(candidates), "linked": 0, "pages_changed": 0}

    pages_changed: set[Path] = set()
    linked = 0
    for d in decisions:
        i = d.get("i")
        if not isinstance(i, int) or i < 0 or i >= len(candidates):
            continue
        if not d.get("link"):
            continue
        page_path, _snippet = candidates[i]
        if page_path in pages_changed:
            continue
        try:
            content = page_path.read_text(encoding="utf-8")
        except OSError:
            continue
        new_content = _apply_links(content, [{"term": name, "target": name}])
        if new_content != content:
            page_path.write_text(new_content, encoding="utf-8")
            pages_changed.add(page_path)
            linked += 1

    try:
        from . import index as _idx
        db = _idx_db_path(root)
        for p in pages_changed:
            _idx.update_wiki_page(p, root, db)
    except Exception:
        pass

    return {
        "ok": True,
        "candidates": len(candidates),
        "linked": linked,
        "pages_changed": len(pages_changed),
    }


def _idx_db_path(vault_root: Path) -> Path:
    state_dir = vault_root.parent / ".state"
    return store.index_db_path(state_dir)


def _parse_inbound_response(raw: str) -> list[dict[str, Any]]:
    if not raw or not raw.strip():
        return []
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    start = text.find("{")
    if start == -1:
        return []
    depth = 0
    in_str = False
    escape = False
    end = -1
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\" and in_str:
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        return []
    try:
        parsed = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []
    decisions = parsed.get("decisions")
    if not isinstance(decisions, list):
        return []
    out: list[dict[str, Any]] = []
    for d in decisions:
        if isinstance(d, dict) and isinstance(d.get("i"), int):
            out.append({"i": d["i"], "link": bool(d.get("link", False))})
    return out


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------


def _parse_link_response(raw: str) -> list[dict[str, str]]:
    if not raw or not raw.strip():
        return []
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)

    start = text.find("{")
    if start == -1:
        return []

    depth = 0
    in_str = False
    escape = False
    end = -1
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\" and in_str:
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        return []

    try:
        parsed = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []

    items = parsed.get("links")
    if not isinstance(items, list):
        return []

    out: list[dict[str, str]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        term = it.get("term")
        target = it.get("target")
        if isinstance(term, str) and isinstance(target, str) and term and target:
            out.append({"term": term, "target": target})
    return out


# ---------------------------------------------------------------------------
# Substitution
# ---------------------------------------------------------------------------


def _apply_links(content: str, links: list[dict[str, str]]) -> str:
    """Replace the first literal occurrence of each term with a wikilink."""
    body = content
    frontmatter = ""
    if content.startswith("---\n"):
        end = content.find("\n---\n", 4)
        if end != -1:
            frontmatter = content[:end + 5]
            body = content[end + 5:]

    linked: set[str] = set()
    for entry in links:
        term = entry["term"]
        target = entry["target"]
        tkey = target.lower()
        if tkey in linked:
            continue
        if not term or not target:
            continue

        idx = _find_unlinked_occurrence(body, term)
        if idx == -1:
            continue

        if term.lower() == target.lower():
            replacement = f"[[{term}]]"
        else:
            replacement = f"[[{target}|{term}]]"

        body = body[:idx] + replacement + body[idx + len(term):]
        linked.add(tkey)

    return frontmatter + body


def _find_unlinked_occurrence(text: str, term: str) -> int:
    if not term:
        return -1
    search_from = 0
    while search_from < len(text):
        idx = text.find(term, search_from)
        if idx == -1:
            return -1
        window_start = max(0, idx - 2)
        window = text[window_start:idx]
        if window.endswith("[["):
            search_from = idx + len(term)
            continue
        return idx
    return -1


def _count_new_links(before: str, after: str) -> int:
    return max(0, after.count("[[") - before.count("[["))
