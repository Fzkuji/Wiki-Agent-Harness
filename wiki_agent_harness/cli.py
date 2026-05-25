"""Command-line interface for wiki_agent_harness.

Every Wiki method has a corresponding subcommand. The CLI is intentionally
thin — it only does argument parsing, value coercion, and printing.

Run ``wah --help`` for the full subcommand list, or ``wah <cmd> --help``
for any single command.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

from . import Wiki


# ---------------------------------------------------------------------------
# Value coercion
# ---------------------------------------------------------------------------


def _parse_kv(items: list[str]) -> dict[str, Any]:
    """``KEY=VAL`` pairs → dict. VAL is parsed as JSON when possible
    (so ``tags=[a,b]``, ``count=3``, ``draft=true`` all type-correctly);
    otherwise kept as a string.
    """
    out: dict[str, Any] = {}
    for raw in items:
        if "=" not in raw:
            raise SystemExit(f"--meta items must be KEY=VAL, got: {raw!r}")
        k, _, v = raw.partition("=")
        k = k.strip()
        v = v.strip()
        try:
            out[k] = yaml.safe_load(v)
        except yaml.YAMLError:
            out[k] = v
    return out


def _resolve_content(args: argparse.Namespace) -> str:
    """Pick slot content from --content STR, --file PATH, or stdin."""
    if args.content is not None:
        return args.content
    if args.file is not None:
        return Path(args.file).read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise SystemExit("provide --content, --file, or pipe content via stdin")


def _wiki(args: argparse.Namespace) -> Wiki:
    return Wiki(root=args.root) if args.root else Wiki()


def _print(obj: Any) -> None:
    if obj is None:
        return
    if isinstance(obj, (dict, list)):
        print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))
    else:
        print(obj)


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def cmd_tree(args):
    print(_wiki(args).tree(max_depth=args.max_depth))


def cmd_index(args):
    print(_wiki(args).index())


def cmd_find(args):
    p = _wiki(args).find(args.name)
    if p is None:
        raise SystemExit(f"not found: {args.name}")
    print(p)


def cmd_read(args):
    html = _wiki(args).read(args.target)
    if html is None:
        raise SystemExit(f"page not found: {args.target}")
    sys.stdout.write(html)


def cmd_meta(args):
    meta = _wiki(args).meta(args.target)
    if not meta:
        raise SystemExit(f"no meta block for: {args.target}")
    sys.stdout.write(yaml.safe_dump(
        meta, sort_keys=False, allow_unicode=True, default_flow_style=False,
    ))


def cmd_slot(args):
    val = _wiki(args).slot(args.target, args.slot_id)
    if val is None:
        raise SystemExit(f"slot not found: {args.slot_id}")
    sys.stdout.write(val)


def cmd_list_slots(args):
    for s in _wiki(args).list_slots(args.target):
        print(s)


def cmd_list_templates(args):
    w = _wiki(args)
    for t in w.list_templates():
        print(f"{t.name}")
        if t.description:
            print(f"  {t.description}")
        if t.slots:
            print(f"  slots: {', '.join(t.slots)}")


def cmd_new(args):
    meta: dict[str, Any] = {}
    if args.title:
        meta["title"] = args.title
    if args.tag:
        meta["tags"] = list(args.tag)
    if args.meta:
        meta.update(_parse_kv(args.meta))
    w = _wiki(args)
    path = w.new_page(args.path, template=args.template, meta=meta)
    print(path)


def cmd_write_slot(args):
    content = _resolve_content(args)
    path = _wiki(args).write_slot(args.target, args.slot_id, content)
    print(path)


def cmd_append_slot(args):
    content = _resolve_content(args)
    path = _wiki(args).append_slot(args.target, args.slot_id, content)
    print(path)


def cmd_set_meta(args):
    if not args.kv:
        raise SystemExit("set-meta requires at least one KEY=VAL")
    updates = _parse_kv(args.kv)
    path = _wiki(args).set_meta(args.target, updates)
    print(path)


def cmd_rebuild(args):
    w = _wiki(args)
    if args.folder:
        path = w.rebuild_folder_index(args.folder)
    else:
        path = w.rebuild_folder_index(None)
    print(path)


def cmd_rebuild_all(args):
    n = _wiki(args).rebuild_all_folder_indexes()
    print(f"rebuilt {n} folder indexes")


def cmd_rerender_all(args):
    n = _wiki(args).rerender_all()
    print(f"re-rendered {n} pages")


def _build_runtime(args):
    """Try to construct an OpenProgram runtime. Pass --no-runtime to skip."""
    if getattr(args, "no_runtime", False):
        return None
    try:
        from openprogram.agentic_programming.runtime import Runtime
        rt = Runtime()
        # Anchor the workdir on the vault root so file ops target the vault.
        if args.root and hasattr(rt, "set_workdir"):
            rt.set_workdir(args.root)
        return rt
    except Exception as e:
        print(f"warning: could not build runtime ({e}); enrich will fail",
              file=sys.stderr)
        return None


def cmd_enrich(args):
    rt = _build_runtime(args)
    w = _wiki(args)
    if args.target:
        out = w.enrich_page(args.target, runtime=rt)
    else:
        out = w.enrich_all(
            runtime=rt,
            only_templates=args.template if args.template else None,
            max_pages=args.limit,
        )
    _print(out)


def cmd_components(args):
    from .components import render_component_palette
    print(render_component_palette())


def cmd_search(args):
    hits = _wiki(args).search(args.query, limit=args.limit)
    if not hits:
        return
    for h in hits:
        print(f"{h.score:7.3f}  {h.template:12}  {h.path}")
        if h.snippet:
            print(f"          {h.snippet}")


def cmd_reindex(args):
    n = _wiki(args).reindex()
    print(f"indexed {n} pages")


def cmd_lint(args):
    print(_wiki(args).lint())


def cmd_stats(args):
    _print(_wiki(args).stats())


def cmd_commit(args):
    _print(_wiki(args).git_commit(args.message))


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wah",
        description="wiki_agent_harness CLI — HTML-first template-driven wiki for AI agents.",
    )
    p.add_argument(
        "--root", "-r",
        default=os.environ.get("WAH_VAULT"),
        help="Vault root directory (default: $WAH_VAULT or ~/.agentic/memory/wiki)",
    )

    sub = p.add_subparsers(dest="cmd", required=True, metavar="COMMAND")

    # Read --------------------------------------------------------------
    sp = sub.add_parser("tree", help="folder outline")
    sp.add_argument("--max-depth", type=int, default=8)
    sp.set_defaults(func=cmd_tree)

    sp = sub.add_parser("index", help="flat list of all page paths")
    sp.set_defaults(func=cmd_index)

    sp = sub.add_parser("find", help="resolve a name to a path")
    sp.add_argument("name")
    sp.set_defaults(func=cmd_find)

    sp = sub.add_parser("read", help="print a page's full HTML")
    sp.add_argument("target")
    sp.set_defaults(func=cmd_read)

    sp = sub.add_parser("meta", help="print a page's meta block as YAML")
    sp.add_argument("target")
    sp.set_defaults(func=cmd_meta)

    sp = sub.add_parser("slot", help="print one slot's content")
    sp.add_argument("target")
    sp.add_argument("slot_id")
    sp.set_defaults(func=cmd_slot)

    sp = sub.add_parser("list-slots", help="list a page's slot ids")
    sp.add_argument("target")
    sp.set_defaults(func=cmd_list_slots)

    sp = sub.add_parser("list-templates", help="show all templates with slots")
    sp.set_defaults(func=cmd_list_templates)

    # Write -------------------------------------------------------------
    sp = sub.add_parser("new", help="render a fresh page from a template")
    sp.add_argument("path", help="bare name or relative path like 'area/topic/name'")
    sp.add_argument("--template", "-t", required=True)
    sp.add_argument("--title")
    sp.add_argument("--tag", action="append", default=[],
                    help="repeatable; e.g. --tag nlp --tag arch")
    sp.add_argument("--meta", action="append", default=[],
                    help="repeatable KEY=VAL; values JSON-decoded when possible")
    sp.set_defaults(func=cmd_new)

    for name, handler in (("write-slot", cmd_write_slot),
                          ("append-slot", cmd_append_slot)):
        sp = sub.add_parser(name, help=f"{name} on a page")
        sp.add_argument("target")
        sp.add_argument("slot_id")
        sp.add_argument("--content", help="literal slot content")
        sp.add_argument("--file", help="read slot content from this file")
        sp.set_defaults(func=handler)

    sp = sub.add_parser("set-meta", help="merge KEY=VAL pairs into a page's meta block")
    sp.add_argument("target")
    sp.add_argument("kv", nargs="+", help="KEY=VAL ...")
    sp.set_defaults(func=cmd_set_meta)

    # Folder index ------------------------------------------------------
    sp = sub.add_parser("rebuild", help="regenerate one folder's README.html")
    sp.add_argument("folder", nargs="?", help="vault-relative; omit for root")
    sp.set_defaults(func=cmd_rebuild)

    sp = sub.add_parser("rebuild-all", help="regenerate every folder's README.html")
    sp.set_defaults(func=cmd_rebuild_all)

    sp = sub.add_parser("rerender-all",
                        help="re-render every managed page from its current template (preserves slots)")
    sp.set_defaults(func=cmd_rerender_all)

    sp = sub.add_parser("enrich",
                        help="agent rewrites slot(s) to use rich visual components")
    sp.add_argument("target", nargs="?",
                    help="page path or stem; omit to enrich all pages")
    sp.add_argument("--template", "-t", action="append",
                    help="restrict to pages of this template (repeatable)")
    sp.add_argument("--limit", "-n", type=int,
                    help="cap on number of pages when enriching all")
    sp.add_argument("--no-runtime", action="store_true",
                    help="don't try to build a runtime (mostly for testing)")
    sp.set_defaults(func=cmd_enrich)

    sp = sub.add_parser("components",
                        help="print the visual component palette reference")
    sp.set_defaults(func=cmd_components)

    # Search ------------------------------------------------------------
    sp = sub.add_parser("search", help="BM25 full-text search over page slots")
    sp.add_argument("query")
    sp.add_argument("--limit", "-n", type=int, default=10)
    sp.set_defaults(func=cmd_search)

    sp = sub.add_parser("reindex", help="full FTS index rebuild")
    sp.set_defaults(func=cmd_reindex)

    # Health ------------------------------------------------------------
    sp = sub.add_parser("lint", help="vault health report")
    sp.set_defaults(func=cmd_lint)

    sp = sub.add_parser("stats", help="page counts + by-template breakdown")
    sp.set_defaults(func=cmd_stats)

    # Git --------------------------------------------------------------
    sp = sub.add_parser("commit", help="git add -A && commit")
    sp.add_argument("message")
    sp.set_defaults(func=cmd_commit)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except SystemExit:
        raise
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
