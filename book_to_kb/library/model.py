"""Parse a Library on disk into typed notes.

Layout (every note's filename stem is unique, so ``[[stem]]`` always resolves):

    <library>/library.json
    <library>/books/<book>/<book>.md          Book Note
    <library>/books/<book>/<book>-chNN.md     Chapter Notes
    <library>/concepts/<concept>.md           Concepts

A Concept's Books come from its Contribution headings (``## In [[<book>]]``),
and its aliases from each Contribution's ``Also called:`` line.
A Chapter Note's Concepts come from its body wikilinks. Neither is repeated
in frontmatter, so there is nothing to keep in sync.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_NAME = "library.json"
BOOKS_DIR = "books"
CONCEPTS_DIR = "concepts"
CONCEPT_KINDS = ("framework", "principle", "technique", "anti-pattern", "term")
BOOK_TYPES = ("text", "technical")
DEPTHS = ("reference", "study")

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CHAPTER_STEM_RE = re.compile(r"^(?P<book>[a-z0-9-]+)-ch(?P<num>\d{2,3})$")
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
CONTRIBUTION_RE = re.compile(r"^## In \[\[([^\]|#]+)(?:\|[^\]]*)?\]\]\s*$", re.M)
ALSO_CALLED = "Also called:"


class LibraryError(Exception):
    """A file in the Library does not parse. Carries the path."""

    def __init__(self, path: Path, message: str):
        super().__init__(f"{path}: {message}")
        self.path = path


@dataclass(frozen=True)
class Config:
    name: str
    language: str


@dataclass
class Note:
    path: Path
    stem: str
    meta: dict
    body: str
    links: list[str] = field(default_factory=list)


@dataclass
class BookNote(Note):
    pass


@dataclass
class ChapterNote(Note):
    book: str = ""
    number: int = 0


@dataclass
class ConceptNote(Note):
    contributions: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)


@dataclass
class Library:
    root: Path
    config: Config
    books: dict[str, BookNote]
    chapters: dict[str, ChapterNote]
    concepts: dict[str, ConceptNote]

    def chapters_of(self, book: str) -> list[ChapterNote]:
        return sorted(
            (c for c in self.chapters.values() if c.book == book),
            key=lambda c: c.number,
        )

    def all_notes(self) -> list[Note]:
        return [*self.books.values(), *self.chapters.values(), *self.concepts.values()]


# --- frontmatter: a strict YAML subset (scalars, flow lists, block lists) ---


def _scalar(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    return raw


def _flow_list(raw: str) -> list[str]:
    inner = raw.strip()[1:-1]
    items, buf, quote = [], "", ""
    for ch in inner:
        if quote:
            buf += ch
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
            buf += ch
        elif ch == ",":
            items.append(buf)
            buf = ""
        else:
            buf += ch
    if buf.strip():
        items.append(buf)
    return [_scalar(i) for i in items if i.strip()]


def split_frontmatter(path: Path, text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        raise LibraryError(path, "missing frontmatter (file must start with '---')")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise LibraryError(path, "frontmatter is not closed with '---'")
    meta: dict = {}
    key = None
    for lineno, line in enumerate(text[4:end].splitlines(), start=2):
        if not line.strip():
            continue
        if line.lstrip().startswith("- ") and key is not None and isinstance(meta[key], list):
            meta[key].append(_scalar(line.split("- ", 1)[1]))
            continue
        match = re.match(r"^([a-z_]+):(.*)$", line)
        if not match:
            raise LibraryError(path, f"line {lineno}: expected 'key: value', got {line!r}")
        key, raw = match.group(1), match.group(2).strip()
        if raw.startswith("["):
            if not raw.endswith("]"):
                raise LibraryError(path, f"line {lineno}: unclosed list for {key!r}")
            meta[key] = _flow_list(raw)
        elif raw == "":
            meta[key] = []
        else:
            meta[key] = _scalar(raw)
    return meta, text[end + 5 :]


def wikilinks(text: str) -> list[str]:
    return [m.strip() for m in WIKILINK_RE.findall(text)]


def contribution_aliases(body: str, title: str) -> list[str]:
    """Names from every Contribution's leading `Also called:` line, in order.

    Deduped ignoring case; the title itself is never an alias.
    """
    seen, out = {title.casefold()}, []
    for heading, text in sections(body):
        if not CONTRIBUTION_RE.match(heading):
            continue
        first = next((line.strip() for line in text.splitlines() if line.strip()), "")
        if not first.startswith(ALSO_CALLED):
            continue
        for name in (n.strip() for n in first[len(ALSO_CALLED):].split(";")):
            if name and name.casefold() not in seen:
                seen.add(name.casefold())
                out.append(name)
    return out


def sections(body: str) -> list[tuple[str, str]]:
    """Split a body into (heading, text) per '## ' section.

    Text before the first '## ' comes back with heading ''.
    """
    out = []
    for part in re.split(r"(?m)^(?=## )", body):
        if part.startswith("## "):
            heading, _, rest = part.partition("\n")
            out.append((heading.rstrip(), rest))
        elif part:
            out.append(("", part))
    return out


# --- loading ---


def load_config(root: Path) -> Config:
    path = root / CONFIG_NAME
    if not path.is_file():
        raise LibraryError(path, "not a Library (no library.json); run 'init' first")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LibraryError(path, f"invalid JSON: {exc}") from exc
    return Config(name=str(data.get("name", root.name)), language=str(data.get("language", "en")))


def _read(path: Path) -> tuple[dict, str]:
    return split_frontmatter(path, path.read_text(encoding="utf-8"))


def load(root: Path) -> Library:
    """Parse every note. Raises LibraryError on the first unparseable file."""
    root = root.expanduser().resolve()
    config = load_config(root)
    books: dict[str, BookNote] = {}
    chapters: dict[str, ChapterNote] = {}
    concepts: dict[str, ConceptNote] = {}

    for path in sorted((root / BOOKS_DIR).glob("*/*.md")):
        meta, body = _read(path)
        stem = path.stem
        links = wikilinks(body)
        if meta.get("kind") == "book":
            books[stem] = BookNote(path, stem, meta, body, links)
        elif meta.get("kind") == "chapter":
            match = CHAPTER_STEM_RE.match(stem)
            number = int(match.group("num")) if match else 0
            chapters[stem] = ChapterNote(
                path, stem, meta, body, links, book=str(meta.get("book", "")), number=number
            )
        else:
            raise LibraryError(path, f"kind must be 'book' or 'chapter', got {meta.get('kind')!r}")

    for path in sorted((root / CONCEPTS_DIR).glob("*.md")):
        meta, body = _read(path)
        if meta.get("kind") != "concept":
            raise LibraryError(path, f"kind must be 'concept', got {meta.get('kind')!r}")
        concepts[path.stem] = ConceptNote(
            path,
            path.stem,
            meta,
            body,
            wikilinks(body),
            contributions=[c.strip() for c in CONTRIBUTION_RE.findall(body)],
            aliases=contribution_aliases(body, str(meta.get("title", ""))),
        )

    return Library(root, config, books, chapters, concepts)
