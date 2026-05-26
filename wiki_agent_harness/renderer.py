"""Jinja2 page renderer.

A template is a single ``<name>.html.j2`` file that produces a complete HTML
document. Templates declare which slots they support by emitting them as
empty comment blocks in the rendered output; the harness later fills those
slots in place.

The built-in template directory lives next to this module. Callers can pass
``extra_template_dirs=[...]`` to :class:`Renderer` to add their own
templates with higher priority (a same-named file overrides the built-in).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from jinja2 import ChoiceLoader, Environment, FileSystemLoader, select_autoescape

from . import store
from . import slots as _slots


@dataclass
class TemplateInfo:
    """Discovered template + its declared slots and description."""
    name: str
    path: Path
    description: str = ""
    slots: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


class Renderer:
    """Renders new pages from templates and lists available templates."""

    def __init__(
        self,
        extra_template_dirs: list[Path] | None = None,
    ) -> None:
        builtin_dir = Path(__file__).parent / "templates"
        dirs: list[Path] = []
        if extra_template_dirs:
            dirs.extend(Path(p) for p in extra_template_dirs)
        dirs.append(builtin_dir)
        self._dirs = dirs
        self._env = Environment(
            loader=ChoiceLoader([FileSystemLoader(str(d)) for d in dirs]),
            autoescape=select_autoescape(enabled_extensions=("html",)),
            keep_trailing_newline=True,
            trim_blocks=False,
            lstrip_blocks=False,
        )

    # ── template discovery ─────────────────────────────────────────────
    def list_templates(self) -> list[TemplateInfo]:
        """Discover all page templates. Excludes ``base`` and ``_`` partials."""
        seen: dict[str, TemplateInfo] = {}
        for d in self._dirs:
            if not d.exists():
                continue
            for p in sorted(d.glob("*.html.j2")):
                name = p.name.removesuffix(".html.j2")
                if name == "base" or name.startswith("_"):
                    continue
                if name in seen:
                    continue
                info = _introspect_template(name, p)
                seen[name] = info
        return list(seen.values())

    def template_names(self) -> list[str]:
        return [t.name for t in self.list_templates()]

    def find_template(self, name: str) -> TemplateInfo | None:
        for t in self.list_templates():
            if t.name == name:
                return t
        return None

    # ── render ─────────────────────────────────────────────────────────
    def render_new_page(
        self,
        template: str,
        meta: dict[str, Any],
        *,
        depth: int = 0,
    ) -> str:
        """Render a brand-new page. Slots emitted by the template start empty.

        ``meta`` is YAML-dumped into the page's meta block. ``template`` and
        ``updated`` are added/overridden by the renderer.
        ``depth`` is how many folders deep the page sits relative to the vault
        root (used by the template to compute relative asset paths).
        """
        info = self.find_template(template)
        if info is None:
            raise ValueError(f"unknown template: {template!r}")

        meta = dict(meta)
        meta.setdefault("title", "Untitled")
        meta["template"] = template
        meta["updated"] = datetime.now().strftime("%Y-%m-%d")

        tmpl = self._env.get_template(f"{template}.html.j2")
        ctx = {
            "meta": meta,
            "meta_yaml": yaml.safe_dump(
                meta, sort_keys=False, allow_unicode=True,
                default_flow_style=False,
            ).rstrip(),
            "asset_root": "../" * depth if depth else "./",
            "title": meta.get("title", "Untitled"),
        }
        return tmpl.render(**ctx)

    def render_folder_index(
        self,
        folder_meta: dict[str, Any],
        children: list[dict[str, Any]],
        *,
        depth: int = 0,
        crowded_warning: bool = False,
        direct_page_count: int = 0,
    ) -> str:
        """Render a folder's README.html from the ``folder`` template."""
        info = self.find_template("folder")
        if info is None:
            raise ValueError("built-in template 'folder' is missing")

        meta = dict(folder_meta)
        meta["template"] = "folder"
        meta["updated"] = datetime.now().strftime("%Y-%m-%d")
        meta.setdefault("title", "Index")

        tmpl = self._env.get_template("folder.html.j2")
        ctx = {
            "meta": meta,
            "meta_yaml": yaml.safe_dump(
                meta, sort_keys=False, allow_unicode=True,
                default_flow_style=False,
            ).rstrip(),
            "asset_root": "../" * depth if depth else "./",
            "title": meta.get("title", "Index"),
            "children": children,
            "crowded_warning": crowded_warning,
            "direct_page_count": direct_page_count,
        }
        return tmpl.render(**ctx)


# ---------------------------------------------------------------------------
# Introspection
# ---------------------------------------------------------------------------


_DESC_RE = __import__("re").compile(
    r"\{#-?\s*description:\s*(?P<d>.*?)\s*-?#\}",
    __import__("re").DOTALL,
)


def _introspect_template(name: str, path: Path) -> TemplateInfo:
    """Read a template file to extract its description and declared slot ids."""
    text = path.read_text(encoding="utf-8")
    desc_match = _DESC_RE.search(text)
    description = desc_match.group("d").strip() if desc_match else ""
    # Slot ids are emitted into the rendered output, but we can also detect
    # them statically in the template source by scanning for the same
    # comment pattern (templates author them literally).
    slot_ids: list[str] = []
    import re
    for m in re.finditer(r'wah:slot\s+id="([^"]+)"', text):
        sid = m.group(1)
        if sid not in slot_ids:
            slot_ids.append(sid)
    return TemplateInfo(name=name, path=path, description=description,
                        slots=slot_ids)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def render_template_help(renderer: Renderer) -> str:
    """Human + agent-readable summary of available templates and slots."""
    out: list[str] = []
    for t in renderer.list_templates():
        out.append(f"- **{t.name}** — {t.description or '(no description)'}")
        if t.slots:
            out.append(f"  slots: {', '.join(t.slots)}")
    return "\n".join(out) if out else "(no templates)"


def depth_of(page_path: Path, vault_root: Path) -> int:
    """Folders between page_path and vault_root."""
    try:
        rel = page_path.resolve().relative_to(vault_root.resolve())
    except ValueError:
        return 0
    return len(rel.parts) - 1


def materialize_new_page(
    page_path: Path,
    *,
    template: str,
    meta: dict[str, Any],
    renderer: Renderer,
    vault_root: Path,
) -> Path:
    """Render a new page and write it to disk. Returns the path."""
    page_path.parent.mkdir(parents=True, exist_ok=True)
    html = renderer.render_new_page(
        template, meta, depth=depth_of(page_path, vault_root),
    )
    page_path.write_text(html, encoding="utf-8")
    return page_path
