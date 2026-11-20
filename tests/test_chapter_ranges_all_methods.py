"""Numeric and structural chapter detection emit `chapter_ranges` too.

Library notes cite the chapter they came from, so every detection method must
give 1-based inclusive line ranges: per source (into that source's text) and
top level (into full_text.txt, SOURCE banners included).
"""

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


def _extract(tmp_path: Path, *paths: Path) -> tuple[dict, list[str]]:
    workdir = tmp_path / "output"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT_DIR / "scripts" / "extract.py"),
            *map(str, paths),
            "--mode",
            "text",
            "--install-missing",
            "no",
        ],
        env=dict(os.environ, BOOK_KB_WORKDIR=str(workdir)),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    metadata = json.loads((workdir / "metadata.json").read_text(encoding="utf-8"))
    full_text = (workdir / "full_text.txt").read_text(encoding="utf-8")
    return metadata, full_text.split("\n")


def _slice(lines: list[str], chapter: dict) -> list[str]:
    """`sed -n 'START,ENDp'` over newline-split lines."""
    return lines[chapter["start_line"] - 1:chapter["end_line"]]


def test_numeric_chapters_get_ranges(tmp_path):
    book = tmp_path / "numeric.txt"
    book.write_text(
        "Contents\n"
        "Chapter 1 Beginnings\n"
        "Chapter 2 Middles\n"
        "Chapter 3 Endings\n"
        "\n"
        "Chapter 1 Beginnings\n"
        "The first chapter opens here.\n"
        "It has a second line.\n"
        "\n"
        "Chapter 2 Middles\n"
        "The second chapter, as we saw in\n"
        "Chapter 1 earlier, continues the story.\n"
        "\n"
        "Chapter 3 Endings\n"
        "The last chapter closes the book.\n",
        encoding="utf-8",
    )
    metadata, _ = _extract(tmp_path, book)
    source = metadata["sources"][0]

    assert source["chapters_method"] == "numeric"
    assert source["chapters_detected"] == 3
    # The body headings bound the chapters, not the ToC rows above them, and
    # the prose cross-reference on line 12 is not a boundary.
    assert source["chapter_ranges"] == [
        {"title": "Chapter 1 Beginnings", "start_line": 6, "end_line": 9},
        {"title": "Chapter 2 Middles", "start_line": 10, "end_line": 13},
        {"title": "Chapter 3 Endings", "start_line": 14, "end_line": 15},
    ]


def test_heading_only_markdown_gets_ranges(tmp_path):
    book = tmp_path / "guide.md"
    book.write_text(
        "# Field Guide\n"
        "\n"
        "## Intro\n"
        "Opening words.\n"
        "\n"
        "```\n"
        "## Not a chapter\n"
        "```\n"
        "\n"
        "## Methods\n"
        "How it is done.\n"
        "\n"
        "## Results\n"
        "What happened.\n",
        encoding="utf-8",
    )
    metadata, lines = _extract(tmp_path, book)
    source = metadata["sources"][0]

    assert source["chapters_method"] == "structural"
    assert source["chapters_detected"] == 3
    assert source["chapter_headings_sample"] == ["## Intro", "## Methods", "## Results"]
    assert source["chapter_ranges"] == [
        {"title": "Intro", "start_line": 3, "end_line": 9},
        {"title": "Methods", "start_line": 10, "end_line": 12},
        {"title": "Results", "start_line": 13, "end_line": 14},
    ]
    assert len(metadata["chapter_ranges"]) == metadata["chapters_detected"] == 3
    for chapter in metadata["chapter_ranges"]:
        assert chapter["source"] == "guide.md"
        assert _slice(lines, chapter)[0] == f"## {chapter['title']}"


def test_two_sources_top_level_ranges_index_full_text(tmp_path):
    first = tmp_path / "first.md"
    first.write_text(
        "# First Book\n\n## Seeds\nSeed text.\n\n## Roots\nRoot text.\nMore roots.\n",
        encoding="utf-8",
    )
    second = tmp_path / "second.md"
    second.write_text(
        "# Second Book\n\n## Leaves\nLeaf text.\n\n## Fruit\nFruit text.\n",
        encoding="utf-8",
    )
    metadata, lines = _extract(tmp_path, first, second)

    top = metadata["chapter_ranges"]
    assert [(c["source"], c["title"]) for c in top] == [
        ("first.md", "Seeds"),
        ("first.md", "Roots"),
        ("second.md", "Leaves"),
        ("second.md", "Fruit"),
    ]
    assert len(top) == metadata["chapters_detected"]
    for chapter in top:
        body = _slice(lines, chapter)
        assert body[0] == f"## {chapter['title']}"
        # A range never runs into the next source's SOURCE banner.
        assert not any(line.startswith("SOURCE: ") for line in body)
    assert [c["start_line"] for c in top] == sorted(c["start_line"] for c in top)
    assert top[-1]["end_line"] == len(lines)

    # Per-source ranges index into each source's own text.
    for source, path in zip(metadata["sources"], (first, second)):
        source_lines = path.read_text(encoding="utf-8").split("\n")
        assert len(source["chapter_ranges"]) == source["chapters_detected"] == 2
        for chapter in source["chapter_ranges"]:
            assert _slice(source_lines, chapter)[0] == f"## {chapter['title']}"
