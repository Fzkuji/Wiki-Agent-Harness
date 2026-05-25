"""Smoke tests for wiki_agent_harness v0.2 (HTML + templates + slots)."""
from __future__ import annotations

import pytest

from wiki_agent_harness import Wiki, PromptSet
from wiki_agent_harness import slots as _slots


@pytest.fixture()
def vault(tmp_path):
    return tmp_path / "vault"


# ── Wiki + templates ────────────────────────────────────────────────────


def test_instantiation(vault):
    w = Wiki(root=vault)
    assert w.root == vault
    assert vault.exists()


def test_builtin_templates_present(vault):
    w = Wiki(root=vault)
    names = w.renderer.template_names()
    for expected in ("concept", "entity", "procedure", "source",
                     "comparison", "landing", "note"):
        assert expected in names, f"missing built-in template: {expected}"


def test_template_introspection_finds_slots(vault):
    w = Wiki(root=vault)
    info = w.renderer.find_template("concept")
    assert info is not None
    assert "summary" in info.slots
    assert "body" in info.slots


# ── Page creation + slot ops ────────────────────────────────────────────


def test_new_page_writes_valid_html(vault):
    w = Wiki(root=vault)
    p = w.new_page("alpha", template="concept",
                   meta={"title": "Alpha", "tags": ["x"]})
    assert p.exists()
    html = p.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
    assert "Alpha" in html
    meta = _slots.read_meta(html)
    assert meta["title"] == "Alpha"
    assert meta["template"] == "concept"
    assert meta["tags"] == ["x"]
    assert "summary" in _slots.list_slots(html)


def test_write_slot_in_place(vault):
    w = Wiki(root=vault)
    p = w.new_page("beta", template="concept", meta={"title": "Beta"})
    w.write_slot(p, "summary", "One-line summary.")
    assert w.slot(p, "summary") == "One-line summary."
    # Other slots untouched.
    assert w.slot(p, "body") is not None


def test_append_slot(vault):
    w = Wiki(root=vault)
    p = w.new_page("gamma", template="concept", meta={"title": "Gamma"})
    w.write_slot(p, "body", "First.")
    w.append_slot(p, "body", "<p>Second.</p>")
    body = w.slot(p, "body")
    assert "First." in body
    assert "<p>Second.</p>" in body


def test_set_meta_round_trip(vault):
    w = Wiki(root=vault)
    p = w.new_page("delta", template="entity", meta={"title": "Delta"})
    w.set_meta(p, {"tags": ["a", "b"], "title": "Delta Renamed"})
    meta = w.meta(p)
    assert meta["title"] == "Delta Renamed"
    assert meta["tags"] == ["a", "b"]


def test_new_page_in_subfolder(vault):
    w = Wiki(root=vault)
    p = w.new_page("area/topic/thing", template="concept",
                   meta={"title": "Thing"})
    assert p.exists()
    assert p.parent == vault / "area" / "topic"
    # Folder index auto-generated.
    assert (vault / "area" / "topic" / "index.html").exists()


def test_new_page_rejects_duplicate(vault):
    w = Wiki(root=vault)
    w.new_page("dup", template="concept", meta={"title": "Dup"})
    with pytest.raises(FileExistsError):
        w.new_page("dup", template="concept", meta={"title": "Dup"})


# ── Folder index ────────────────────────────────────────────────────────


def test_folder_index_lists_pages(vault):
    w = Wiki(root=vault)
    w.new_page("a", template="concept", meta={"title": "Aye"})
    w.new_page("b", template="entity", meta={"title": "Bee"})
    readme = vault / "index.html"
    assert readme.exists()
    text = readme.read_text(encoding="utf-8")
    assert "Aye" in text
    assert "Bee" in text


# ── Search ──────────────────────────────────────────────────────────────


def test_search_finds_slot_text(vault):
    w = Wiki(root=vault)
    p = w.new_page("searchable", template="concept",
                   meta={"title": "Searchable"})
    w.write_slot(p, "body", "<p>quantum chromodynamics</p>")
    hits = w.search("quantum")
    assert any(h.title == "Searchable" for h in hits)


# ── Lint ────────────────────────────────────────────────────────────────


def test_lint_empty(vault):
    w = Wiki(root=vault)
    assert "empty vault" in w.lint()


def test_lint_clean_after_new_page(vault):
    w = Wiki(root=vault)
    w.new_page("clean", template="concept", meta={"title": "Clean"})
    report = w.lint()
    assert "Missing meta block:                 0" in report
    assert "Unknown template:                   0" in report


def test_lint_broken_link_detected(vault):
    w = Wiki(root=vault)
    p = w.new_page("source-page", template="concept",
                   meta={"title": "Source"})
    w.write_slot(p, "body", '<a href="missing.html">bad</a>')
    report = w.lint()
    assert "Broken local <a href> links:        1" in report


# ── Prompts override ────────────────────────────────────────────────────


def test_prompts_with_overrides_preserves_other_field():
    base = PromptSet()
    custom = base.with_overrides(analysis="custom analysis prompt")
    assert custom.analysis == "custom analysis prompt"
    assert custom.generation == base.generation


# ── Folder housekeeping ─────────────────────────────────────────────────


def test_folder_description_survives_rebuild(vault):
    """Writing to the folder README's description slot must not be wiped
    when a new sibling page is added (which triggers index rebuild)."""
    w = Wiki(root=vault)
    w.new_page("topic/first", template="concept", meta={"title": "First"})
    readme = vault / "topic" / "index.html"
    w.write_slot(readme, "description", "Notes on topic X.")
    assert w.slot(readme, "description") == "Notes on topic X."
    # New sibling should trigger a rebuild but preserve description.
    w.new_page("topic/second", template="concept", meta={"title": "Second"})
    assert w.slot(readme, "description") == "Notes on topic X."


def test_lint_flags_crowded_folder(vault):
    w = Wiki(root=vault)
    for i in range(10):
        w.new_page(f"swamp/p{i}", template="concept", meta={"title": f"P{i}"})
    report = w.lint()
    assert "Folders with >7 direct pages" in report
    assert "swamp" in report


def test_lint_flags_missing_description(vault):
    w = Wiki(root=vault)
    w.new_page("topic/page", template="concept", meta={"title": "P"})
    report = w.lint()
    assert "Folders without description slot:   2" in report  # root + topic


# ── Stats ───────────────────────────────────────────────────────────────


def test_stats_after_create(vault):
    w = Wiki(root=vault)
    w.new_page("s1", template="concept", meta={"title": "S1"})
    w.new_page("s2", template="entity", meta={"title": "S2"})
    s = w.stats()
    assert s["pages"] == 2
    assert s["by_template"]["concept"] == 1
    assert s["by_template"]["entity"] == 1
