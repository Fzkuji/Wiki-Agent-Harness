"""Smoke tests for wiki_agent_harness."""
import tempfile
from pathlib import Path
import pytest

from wiki_agent_harness import Wiki


@pytest.fixture()
def vault(tmp_path):
    """Temporary vault directory."""
    return tmp_path / "vault"


def test_instantiation(vault):
    w = Wiki(root=vault)
    assert w.root == vault.resolve() or w.root == vault
    assert vault.exists()


def test_tree_empty(vault):
    w = Wiki(root=vault)
    result = w.tree()
    # Empty vault — tree returns empty string
    assert isinstance(result, str)


def test_lint_empty(vault):
    w = Wiki(root=vault)
    result = w.lint()
    assert "Wiki lint report" in result
    assert "empty vault" in result


def test_iter_pages_finds_md(vault):
    w = Wiki(root=vault)
    # Write a content page
    page = vault / "TestPage.md"
    page.write_text("---\ntype: concept\n---\nHello world.\n", encoding="utf-8")

    found = list(w.iter_pages())
    assert any(p.name == "TestPage.md" for p in found)


def test_lint_with_page(vault):
    w = Wiki(root=vault)
    page = vault / "TestPage.md"
    page.write_text("---\ntype: concept\n---\nContent here.\n", encoding="utf-8")

    result = w.lint()
    assert "Pages: 1" in result


def test_governance_pages_excluded(vault):
    w = Wiki(root=vault)
    # Governance pages should not appear in iter_pages
    (vault / "index.md").write_text("# Index\n", encoding="utf-8")
    (vault / "MyPage.md").write_text("---\ntype: entity\n---\nHi.\n", encoding="utf-8")

    found = [p.name for p in w.iter_pages()]
    assert "index.md" not in found
    assert "MyPage.md" in found


def test_tree_shows_pages(vault):
    w = Wiki(root=vault)
    (vault / "Alpha.md").write_text("---\ntype: concept\n---\n", encoding="utf-8")

    result = w.tree()
    assert "Alpha.md" in result


def test_find_page(vault):
    w = Wiki(root=vault)
    (vault / "Foo.md").write_text("---\ntype: entity\n---\n", encoding="utf-8")

    p = w.find("Foo")
    assert p is not None
    assert p.stem == "Foo"


def test_read_page(vault):
    w = Wiki(root=vault)
    (vault / "Bar.md").write_text("---\ntype: concept\n---\nbar content\n", encoding="utf-8")

    text = w.read("Bar")
    assert text is not None
    assert "bar content" in text


def test_backlinks_empty(vault):
    w = Wiki(root=vault)
    (vault / "Solo.md").write_text("---\ntype: concept\n---\nno links here\n", encoding="utf-8")

    result = w.backlinks("Solo")
    assert isinstance(result, list)
    assert result == []


def test_backlinks_found(vault):
    w = Wiki(root=vault)
    (vault / "Target.md").write_text("---\ntype: concept\n---\n", encoding="utf-8")
    (vault / "Source.md").write_text(
        "---\ntype: concept\n---\nSee [[Target]] for details.\n", encoding="utf-8"
    )

    result = w.backlinks("Target")
    assert len(result) == 1
    assert "Source.md" in result[0]["page"]
