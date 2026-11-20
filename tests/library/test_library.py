"""Behavior of the Library commands on a small synthetic Library."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from book_to_kb.library import commands
from book_to_kb.library.cli import main
from book_to_kb.library.model import LibraryError, load

ALPHA_CONTRIBUTION = """## In [[alpha]]

Also called: positive feedback; virtuous circle

Alpha calls it "the loop that feeds itself". Apply it when growth compounds. See [[alpha-ch01]].
"""


def book_note(slug: str, title: str) -> str:
    return f"""---
kind: book
title: "{title}"
authors: [Ann Author]
book_type: text
depth: study
sources: [{slug}.txt]
---

# {title}

A synthetic book about loops.
"""


def chapter_note(book: str, title: str, concepts: list[str]) -> str:
    links = ", ".join(f"[[{c}]]" for c in concepts)
    return f"""---
kind: chapter
book: {book}
title: "{title}"
---

# {title}

## Core Idea

Loops compound. Introduces {links}.
"""


CONCEPT_SHARED = f"""---
kind: concept
title: Reinforcing Loop
concept_kind: framework
aliases: []
---

# Reinforcing Loop

A loop where change feeds more change in the same direction. It explains compounding.

{ALPHA_CONTRIBUTION}
## In [[beta]]

Also called: Positive Feedback; feedback spiral

Beta names it "positive feedback". See [[beta-ch01]].

## Tensions

Alpha says such loops always end; Beta says some never do.

## Related

- [[balancing-loop]]
"""

CONCEPT_BETA_ONLY = """---
kind: concept
title: Balancing Loop
concept_kind: principle
aliases: [negative feedback]
---

# Balancing Loop

A loop that pushes back toward a goal.

## In [[beta]]

Also called: negative feedback

Beta's thermostat example. See [[beta-ch01]].
"""


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def library(tmp_path: Path) -> Path:
    root = tmp_path / "lib"
    commands.init(root, "Test Library", "en")
    write(root, "books/alpha/alpha.md", book_note("alpha", "Alpha Book"))
    write(root, "books/alpha/alpha-ch01.md", chapter_note("alpha", "Loops", ["reinforcing-loop"]))
    write(root, "books/beta/beta.md", book_note("beta", "Beta Book"))
    write(
        root,
        "books/beta/beta-ch01.md",
        chapter_note("beta", "Feedback", ["reinforcing-loop", "balancing-loop"]),
    )
    write(root, "concepts/reinforcing-loop.md", CONCEPT_SHARED)
    write(root, "concepts/balancing-loop.md", CONCEPT_BETA_ONLY)
    commands.index(load(root))
    return root


def errors(root: Path) -> list[str]:
    return [str(f) for f in commands.validate(load(root)) if f.severity == "error"]


def snapshot(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# --- init and index ---


def test_init_creates_an_empty_valid_library_and_is_safe_to_rerun(tmp_path):
    root = tmp_path / "lib"
    commands.init(root, "Mine", "vi")
    first = snapshot(root)
    commands.init(root, "Other name", "en")

    assert snapshot(root) == first
    assert json.loads((root / "library.json").read_text())["language"] == "vi"
    assert errors(root) == []
    assert "_No Books yet._" in (root / "index.md").read_text()


def test_index_twice_rewrites_nothing(library):
    before = snapshot(library)
    assert commands.index(load(library)) == []
    assert snapshot(library) == before


def test_valid_library_has_no_errors(library):
    assert errors(library) == []


def test_index_lists_books_and_concepts_by_kind(library):
    index = (library / "index.md").read_text()
    assert "[[alpha\\|Alpha Book]]" in index
    assert "### framework (1)" in index
    assert "- [[reinforcing-loop|Reinforcing Loop]] · aka positive feedback; virtuous circle; feedback spiral · 2 books" in index


def test_glossary_points_aliases_at_their_concept(library):
    glossary = (library / "glossary.md").read_text()
    assert "- **positive feedback** → see [[reinforcing-loop|Reinforcing Loop]]" in glossary
    assert "**Reinforcing Loop** (framework) → [[reinforcing-loop]]: A loop where change feeds more change in the same direction." in glossary


def test_book_note_gets_a_generated_chapter_list(library):
    book = (library / "books/beta/beta.md").read_text()
    assert "1. [[beta-ch01|Feedback]]" in book
    assert book.startswith("---\nkind: book")


def test_concepts_listing_gives_aliases_and_books(library):
    rows = commands.concept_list(load(library)).splitlines()
    assert rows[0] == "slug\tkind\ttitle\taliases\tbooks"
    assert "reinforcing-loop\tframework\tReinforcing Loop\tpositive feedback; virtuous circle; feedback spiral\talpha; beta" in rows


# --- aliases are derived from Contributions ---


def test_index_derives_aliases_from_also_called_lines(library):
    meta = load(library).concepts["reinforcing-loop"].meta
    # Contribution order, case-insensitive dedupe, title excluded.
    assert meta["aliases"] == ["positive feedback", "virtuous circle", "feedback spiral"]


def test_alias_written_by_hand_is_out_of_date(library):
    path = library / "concepts/balancing-loop.md"
    path.write_text(path.read_text().replace("  - negative feedback", "  - negative feedback\n  - heat governor"))
    assert any("balancing-loop.md: out of date" in e for e in errors(library))
    commands.index(load(library))
    assert "heat governor" not in path.read_text()


def test_alias_with_a_comma_or_colon_survives_the_round_trip(library):
    path = library / "concepts/balancing-loop.md"
    path.write_text(path.read_text().replace("Also called: negative feedback", "Also called: wages, profit: rent"))
    commands.index(load(library))
    assert load(library).concepts["balancing-loop"].meta["aliases"] == ["wages, profit: rent"]
    assert commands.index(load(library)) == []


def test_remove_book_drops_aliases_only_that_book_used(library):
    commands.remove_book(load(library), "beta")
    meta = load(library).concepts["reinforcing-loop"].meta
    assert meta["aliases"] == ["positive feedback", "virtuous circle"]
    assert errors(library) == []


# --- validate catches each broken state ---


def test_broken_wikilink_is_an_error(library):
    write(library, "books/alpha/alpha-ch01.md", chapter_note("alpha", "Loops", ["reinforcing-loop", "nope"]))
    commands.index(load(library))
    assert any("broken wikilink [[nope]]" in e for e in errors(library))


def test_alias_shared_by_two_concepts_is_an_error(library):
    text = CONCEPT_BETA_ONLY.replace("Also called: negative feedback", "Also called: positive feedback")
    write(library, "concepts/balancing-loop.md", text)
    commands.index(load(library))
    assert any("'positive feedback'" in e for e in errors(library))


def test_concept_without_contribution_is_an_error(library):
    text = CONCEPT_BETA_ONLY.replace("## In [[beta]]", "## Notes")
    write(library, "concepts/balancing-loop.md", text)
    commands.index(load(library))
    assert any("no Contribution" in e for e in errors(library))


def test_reused_filename_stem_is_an_error(library):
    write(library, "concepts/alpha.md", CONCEPT_BETA_ONLY.replace("Balancing Loop", "Alpha"))
    commands.index(load(library))
    assert any("filename stem 'alpha'" in e for e in errors(library))


def test_hand_edited_index_is_an_error(library):
    with (library / "index.md").open("a") as f:
        f.write("\nmy note\n")
    assert any("index.md: out of date" in e for e in errors(library))


def test_unknown_concept_kind_is_an_error(library):
    write(library, "concepts/balancing-loop.md", CONCEPT_BETA_ONLY.replace("principle", "idea"))
    commands.index(load(library))
    assert any("concept_kind must be one of" in e for e in errors(library))


def test_orphan_concept_is_only_a_warning(library):
    write(library, "books/beta/beta-ch01.md", chapter_note("beta", "Feedback", ["reinforcing-loop"]))
    commands.index(load(library))
    findings = commands.validate(load(library))
    assert errors(library) == []
    assert any(f.severity == "warning" and "orphan" in f.message for f in findings)


def test_cli_validate_exit_code_reflects_errors(library, capsys):
    assert main(["validate", str(library)]) == 0
    write(library, "books/alpha/alpha-ch01.md", chapter_note("alpha", "Loops", ["missing"]))
    assert main(["validate", str(library)]) == 1
    assert "broken wikilink [[missing]]" in capsys.readouterr().out


# --- remove-book ---


def test_remove_book_drops_its_contributions_and_orphaned_concepts(library):
    report = commands.remove_book(load(library), "beta")

    assert not (library / "books/beta").exists()
    assert not (library / "concepts/balancing-loop.md").exists()
    assert report.deleted_concepts == ["balancing-loop"]
    shared = (library / "concepts/reinforcing-loop.md").read_text()
    assert "## In [[beta]]" not in shared
    assert "## Tensions" not in shared
    assert ALPHA_CONTRIBUTION in shared


def test_remove_book_drops_related_lines_to_removed_notes(library):
    # Related only linked balancing-loop, which is deleted with beta.
    report = commands.remove_book(load(library), "beta")
    shared = (library / "concepts/reinforcing-loop.md").read_text()
    assert "balancing-loop" not in shared
    assert "## Related" not in shared
    assert report.stale_prose == []
    assert errors(library) == []


def test_remove_book_reports_prose_that_still_links_the_removed_book(library):
    path = library / "concepts/reinforcing-loop.md"
    path.write_text(path.read_text().replace("It explains compounding.", "Beta's [[balancing-loop]] is its twin."))
    report = commands.remove_book(load(library), "beta")
    assert report.stale_prose == ["reinforcing-loop"]
    assert any("broken wikilink [[balancing-loop]]" in e for e in errors(library))


def test_add_then_remove_returns_the_alpha_only_library(tmp_path):
    root = tmp_path / "lib"
    commands.init(root, "Test Library", "en")
    write(root, "books/alpha/alpha.md", book_note("alpha", "Alpha Book"))
    write(root, "books/alpha/alpha-ch01.md", chapter_note("alpha", "Loops", ["reinforcing-loop"]))
    alpha_only_concept = CONCEPT_SHARED.split("## In [[beta]]")[0].rstrip("\n") + "\n"
    write(root, "concepts/reinforcing-loop.md", alpha_only_concept)
    commands.index(load(root))
    alpha_only = snapshot(root)

    write(root, "books/beta/beta.md", book_note("beta", "Beta Book"))
    write(root, "books/beta/beta-ch01.md", chapter_note("beta", "Feedback", ["reinforcing-loop"]))
    write(
        root,
        "concepts/reinforcing-loop.md",
        alpha_only_concept + "\n## In [[beta]]\n\nBeta's view. See [[beta-ch01]].\n\n## Tensions\n\nThey disagree.\n",
    )
    commands.index(load(root))
    assert errors(root) == []

    commands.remove_book(load(root), "beta")
    assert snapshot(root) == alpha_only


def test_remove_unknown_book_fails_cleanly(library, capsys):
    assert main(["remove-book", str(library), "gamma"]) == 1
    assert "no Book 'gamma'" in capsys.readouterr().err


# --- parsing at the boundary ---


def test_unparseable_frontmatter_names_the_file(library):
    write(library, "concepts/bad.md", "---\nkind concept\n---\n")
    with pytest.raises(LibraryError) as exc:
        load(library)
    assert exc.value.path.name == "bad.md"


def test_missing_library_json_is_reported(tmp_path, capsys):
    assert main(["validate", str(tmp_path)]) == 1
    assert "not a Library" in capsys.readouterr().err


# --- relink ---


def test_relink_rewrites_targets_and_keeps_labels_and_headings(library):
    chapter = library / "books/alpha/alpha-ch01.md"
    write(library, "books/alpha/alpha-ch01.md", chapter.read_text() + "\nSee [[loop-x|the loop]] and [[loop-x#Why]] and [[loop-xy]].\n")
    link_map = library / "map.tsv"
    link_map.write_text("# proposed -> final\nloop-x\treinforcing-loop\n")

    assert main(["relink", str(library / "books/alpha"), str(link_map)]) == 0
    text = chapter.read_text()
    assert "[[reinforcing-loop|the loop]]" in text
    assert "[[reinforcing-loop#Why]]" in text
    assert "[[loop-xy]]" in text
    assert commands.relink(library / "books/alpha", {"loop-x": "reinforcing-loop"}) == []


def test_relink_rejects_a_malformed_map(library, capsys):
    bad = library / "map.tsv"
    bad.write_text("Loop X -> reinforcing-loop\n")
    assert main(["relink", str(library), str(bad)]) == 1
    assert "expected 'old-slug<TAB>new-slug'" in capsys.readouterr().err


# --- reader skill ---


def test_reader_skill_names_the_library_and_its_books(library, tmp_path):
    path = commands.write_reader_skill(load(library), tmp_path / "skills")
    text = path.read_text()

    assert path == (tmp_path / "skills/test-library-library/SKILL.md").resolve()
    assert text.startswith("---\nname: test-library-library\ndescription: \"Knowledge base of 2 book(s): Alpha Book; Beta Book.")
    assert "such as Reinforcing Loop, Balancing Loop." in text
    assert f"`{library.resolve()}/AGENTS.md`" in text
    assert commands.write_reader_skill(load(library), tmp_path / "skills") == path

    validator = Path(sys.executable).parent / "agentskills"
    if validator.exists():
        result = subprocess.run([str(validator), "validate", str(path.parent)], capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
