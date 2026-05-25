"""HTML slot + meta block primitives.

Every rendered page contains two kinds of agent-editable regions, marked
by HTML comments so they remain valid HTML and survive any reformatting:

* **Meta block** — a single ``<!-- wah:meta ... -->`` near the top of
  ``<body>``. Body is YAML; carries page-level metadata (template name,
  title, tags, related, updated timestamp).

* **Slots** — ``<!-- wah:slot id="X" -->...<!-- /wah:slot -->`` regions.
  Each carries a named chunk of body HTML. The agent edits one slot at a
  time without touching the rest of the page, so successive ingests
  accumulate cleanly.

This module is the only place that knows the on-disk comment format.
Everything else (renderer, ingest, ops) goes through these primitives.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Regexes
# ---------------------------------------------------------------------------

_META_RE = re.compile(
    r"<!--\s*wah:meta\s*(?P<body>.*?)\s*-->",
    re.DOTALL,
)

_SLOT_RE = re.compile(
    r"<!--\s*wah:slot\s+id=\"(?P<id>[^\"]+)\"\s*-->"
    r"(?P<content>.*?)"
    r"<!--\s*/wah:slot\s*-->",
    re.DOTALL,
)


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------


def read_meta(html: str) -> dict[str, Any]:
    """Parse the first ``<!-- wah:meta ... -->`` block. Returns {} if absent."""
    m = _META_RE.search(html)
    if not m:
        return {}
    raw = m.group("body").strip()
    if not raw:
        return {}
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def write_meta(html: str, meta: dict[str, Any]) -> str:
    """Replace the meta block with ``meta`` (YAML-dumped). Block must exist."""
    new_body = yaml.safe_dump(
        meta, sort_keys=False, allow_unicode=True, default_flow_style=False
    ).rstrip()
    replacement = f"<!-- wah:meta\n{new_body}\n-->"
    if not _META_RE.search(html):
        raise ValueError("page has no <!-- wah:meta --> block to update")
    return _META_RE.sub(lambda _m: replacement, html, count=1)


# ---------------------------------------------------------------------------
# Slots
# ---------------------------------------------------------------------------


def list_slots(html: str) -> list[str]:
    """Return slot ids in document order."""
    return [m.group("id") for m in _SLOT_RE.finditer(html)]


def read_slot(html: str, slot_id: str) -> str | None:
    """Return the content of a slot, or None if missing.

    Returned content excludes the surrounding comment markers and any
    leading/trailing whitespace introduced by the template.
    """
    for m in _SLOT_RE.finditer(html):
        if m.group("id") == slot_id:
            return m.group("content").strip("\n")
    return None


def write_slot(html: str, slot_id: str, content: str) -> str:
    """Overwrite a slot in place. Raises if the slot is not declared.

    ``content`` is inserted verbatim (it may contain raw HTML); callers
    are responsible for any escaping appropriate to their use case.
    """
    if not _slot_exists(html, slot_id):
        raise KeyError(f"slot {slot_id!r} not found in page")

    def _sub(m: re.Match) -> str:
        if m.group("id") != slot_id:
            return m.group(0)
        return (
            f'<!-- wah:slot id="{slot_id}" -->\n'
            f"{content}\n"
            f"<!-- /wah:slot -->"
        )

    return _SLOT_RE.sub(_sub, html, count=0)


def append_slot(html: str, slot_id: str, content: str) -> str:
    """Append content to an existing slot's current value, separated by a newline."""
    current = read_slot(html, slot_id)
    if current is None:
        raise KeyError(f"slot {slot_id!r} not found in page")
    merged = f"{current}\n{content}" if current else content
    return write_slot(html, slot_id, merged)


def _slot_exists(html: str, slot_id: str) -> bool:
    return any(m.group("id") == slot_id for m in _SLOT_RE.finditer(html))


# ---------------------------------------------------------------------------
# File-level convenience
# ---------------------------------------------------------------------------


def read_meta_file(path: Path) -> dict[str, Any]:
    return read_meta(path.read_text(encoding="utf-8"))


def write_slot_file(path: Path, slot_id: str, content: str) -> None:
    html = path.read_text(encoding="utf-8")
    path.write_text(write_slot(html, slot_id, content), encoding="utf-8")


def append_slot_file(path: Path, slot_id: str, content: str) -> None:
    html = path.read_text(encoding="utf-8")
    path.write_text(append_slot(html, slot_id, content), encoding="utf-8")


def read_slot_file(path: Path, slot_id: str) -> str | None:
    return read_slot(path.read_text(encoding="utf-8"), slot_id)


def list_slots_file(path: Path) -> list[str]:
    return list_slots(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Plain-text projection (for full-text indexing)
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def slot_text(html: str) -> str:
    """Concatenate all slot contents stripped of HTML tags. Used by FTS."""
    parts: list[str] = []
    for m in _SLOT_RE.finditer(html):
        parts.append(_TAG_RE.sub(" ", m.group("content")))
    text = " ".join(parts)
    return _WS_RE.sub(" ", text).strip()
