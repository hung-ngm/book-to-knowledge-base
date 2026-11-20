#!/usr/bin/env python3
"""Advisory scan for prompt injection and unsafe authority in a Library's notes."""

from __future__ import annotations

import argparse
import os
import re
import sys

# Keep __pycache__ out of an installed skill. Set before importing book_to_kb.
if __name__ == "__main__":
    sys.dont_write_bytecode = True
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


MAX_NOTE_FILES = 20_000
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
CONFIG_NAME = "library.json"
INDEX_FILENAMES = ("index.md", "glossary.md", "AGENTS.md")
BOOKS_DIR = "books"
CONCEPTS_DIR = "concepts"
SOURCES_DIR = ".sources"

# Share the extractor's invisible-character set so the two defenses agree.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from book_to_kb.sanitize import is_invisible_codepoint  # noqa: E402

_CONTENT_RULES = (
    (
        "prompt.ignore_previous",
        re.compile(
            r"\bignore\s+(?:(?:all|any|the)\s+)?(?:previous|prior)\s+"
            r"(?:instructions?|prompts?|rules?|messages?)\b",
            re.IGNORECASE,
        ),
        "contains an instruction-override phrase",
    ),
    (
        "prompt.disregard_system",
        re.compile(r"\bdisregard\s+(?:the\s+)?(?:system|developer)\b", re.IGNORECASE),
        "contains a system-instruction override phrase",
    ),
    (
        "prompt.role_reassignment",
        re.compile(r"\byou\s+are\s+now\b", re.IGNORECASE),
        "contains a role-reassignment phrase",
    ),
    (
        "prompt.fake_system_prefix",
        re.compile(r"^\s*(?:[-*]\s*)?(?:system|developer)\s*:", re.IGNORECASE),
        "contains a system-like message prefix",
    ),
    (
        "prompt.system_tag",
        re.compile(r"<\s*/?\s*system\b[^>]*>", re.IGNORECASE),
        "contains a system-message tag",
    ),
    (
        "prompt.chat_template_tag",
        re.compile(r"<\|\s*im_start\s*\|>|\[\s*INST\s*\]", re.IGNORECASE),
        "contains a model chat-template delimiter",
    ),
    (
        # Only the delimited forms — a token, not the English phrase. The
        # families below are the ones that appear in real chat templates and
        # tool-calling protocols:
        #
        #   <tool_call> … </tool_call>     Hermes / Qwen style
        #   <|tool_call|>                  special-token style
        #   [TOOL_CALL] / [/tool_call]     bracket style
        #   {{tool_call}}                  template placeholder
        #   "tool_call"                    JSON key or value
        #
        # Matching bare prose instead fired on every book that explains what a
        # tool call is — the agent and prompting books this converter is most
        # used on. A gate that always trips on a whole category teaches people
        # to wave it through, which costs more than the false positive itself.
        "prompt.tool_call_tag",
        re.compile(
            r"""<\|?\s*/?\s*tool[_ -]?call\s*\|?>      # <tool_call>, </tool_call>, <|tool_call|>
              | \[\s*/?\s*tool[_ -]?call\s*\]          # [TOOL_CALL], [/tool_call]
              | \{\{\s*/?\s*tool[_ -]?call\s*\}\}      # {{tool_call}}
              | "\s*tool[_ -]?call\s*"                 # JSON key or value
            """,
            re.IGNORECASE | re.VERBOSE,
        ),
        "contains a tool-call control token",
    ),
)

_EXFILTRATION_TERM = re.compile(r"\bexfiltrat(?:e|es|ed|ing|ion)\b", re.IGNORECASE)
_OUTBOUND_TERM = re.compile(
    r"\b(?:curl|wget|send|post|upload|transmit)\b|https?://",
    re.IGNORECASE,
)
_SENSITIVE_TERM = re.compile(
    r"(?:\.env\b|\bbase64\b|\bsecrets?\b|\bcredentials?\b|\bapi[_ -]?keys?\b)",
    re.IGNORECASE,
)


class ScanError(RuntimeError):
    """Raised when the scanner cannot inspect every note in the Library."""


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule_id: str
    message: str


def _is_invisible(codepoint: int) -> bool:
    return is_invisible_codepoint(codepoint)


def _terminal_safe(value: str) -> str:
    """Escape control and non-ASCII characters before printing untrusted paths."""
    return value.encode("unicode_escape", errors="backslashreplace").decode("ascii")


def _frontmatter_line_numbers(lines: Sequence[str]) -> set[int]:
    if not lines or lines[0].strip() != "---":
        return set()
    for index, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            return set(range(2, index))
    return set()


def _walk_markdown(directory: Path, *, skip_root_dirs: frozenset[str] = frozenset()) -> list[Path]:
    """Collect ``*.md`` under ``directory`` at any depth, ignoring symlinks.

    ``os.walk(followlinks=False)`` rather than ``Path.rglob``: before Python 3.13
    ``rglob`` descends into symlinked directories, which would let a Library
    walk the scanner outside its own tree. Symlinked *files* are left in the
    list and rejected later by :func:`_read_notes`, so a planted symlink is
    reported as an error rather than silently skipped. Directories named in
    ``skip_root_dirs`` are pruned when they sit directly under ``directory``.
    """
    found: list[Path] = []
    for walk_root, dirnames, filenames in os.walk(directory, followlinks=False):
        if skip_root_dirs and Path(walk_root) == directory:
            dirnames[:] = [name for name in dirnames if name not in skip_root_dirs]
        for filename in filenames:
            if filename.lower().endswith(".md"):
                found.append(Path(walk_root) / filename)
    return found


def _library_root(path: Path) -> Path:
    requested = path.expanduser()
    if requested.is_symlink():
        raise ScanError("the Library directory must not be a symbolic link")
    try:
        root = requested.resolve(strict=True)
    except OSError as exc:
        raise ScanError("the Library directory does not exist") from exc
    if not root.is_dir():
        raise ScanError("the Library path is not a directory")
    config = root / CONFIG_NAME
    if config.is_symlink():
        raise ScanError(f"{CONFIG_NAME} must be a real file, not a symbolic link")
    if not config.is_file():
        raise ScanError(f"not a Library (no {CONFIG_NAME})")
    return root


def unscanned_markdown(path: Path) -> list[str]:
    """Markdown files present in the Library but outside the scan scope.

    The scope is bounded to the notes an agent reads (the Index Pages,
    ``books/`` and ``concepts/``), so unrelated files in the folder are not
    scanned and cannot raise false findings. The risk is the *reporting*:
    printing "scan passed" while files an agent might read went unopened is a
    false assurance. Listing them keeps the bounded scope honest.

    ``.sources/`` is left out of this list as well: it holds the opt-in raw
    extracted text, which agents never read as notes. The CLI says so.
    """
    root = _library_root(path)
    scanned = set(_collect_notes(root))
    return sorted(
        candidate.relative_to(root).as_posix()
        for candidate in _walk_markdown(root, skip_root_dirs=frozenset({SOURCES_DIR}))
        if candidate not in scanned
    )


def _real_dir(root: Path, name: str) -> Path | None:
    directory = root / name
    if directory.is_symlink():
        raise ScanError(f"{name} must be a real directory, not a symbolic link")
    if not directory.exists():
        return None
    if not directory.is_dir():
        raise ScanError(f"{name} must be a real directory")
    return directory


def _collect_notes(path: Path) -> list[Path]:
    root = _library_root(path)

    candidates: set[Path] = set()
    for filename in INDEX_FILENAMES:
        index_page = root / filename
        if index_page.is_symlink():
            raise ScanError(f"{filename} must be a real file, not a symbolic link")
        if index_page.exists():
            if not index_page.is_file():
                raise ScanError(f"{filename} must be a real file")
            candidates.add(index_page)

    books = _real_dir(root, BOOKS_DIR)
    if books is not None:
        candidates.update(_walk_markdown(books))

    concepts = _real_dir(root, CONCEPTS_DIR)
    if concepts is not None:
        # Flat on purpose: Concepts live directly in concepts/. Anything nested
        # deeper is not a Concept and is reported as unscanned instead.
        candidates.update(
            entry
            for entry in concepts.iterdir()
            if entry.name.lower().endswith(".md") and (entry.is_file() or entry.is_symlink())
        )

    files = sorted(candidates, key=lambda item: item.relative_to(root).as_posix().lower())
    if len(files) > MAX_NOTE_FILES:
        raise ScanError(
            f"Library has {len(files):,} Markdown notes; maximum is {MAX_NOTE_FILES:,}"
        )
    return files


def _read_notes(root: Path, files: Iterable[Path]) -> Iterable[tuple[str, str]]:
    total_bytes = 0
    for path in files:
        if path.is_symlink():
            raise ScanError("Library contains a symbolic-link Markdown note")
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise ScanError(
                f"{_terminal_safe(path.name)} is {size:,} bytes; maximum scanned file size is "
                f"{MAX_FILE_BYTES:,} bytes"
            )
        total_bytes += size
        if total_bytes > MAX_TOTAL_BYTES:
            raise ScanError(
                f"Library Markdown exceeds the {MAX_TOTAL_BYTES:,}-byte scan limit"
            )
        relative = path.relative_to(root).as_posix()
        try:
            yield relative, path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ScanError(f"{_terminal_safe(relative)} is not valid UTF-8") from exc
        except OSError as exc:
            raise ScanError(f"could not read {_terminal_safe(relative)}") from exc


def _scan_text(relative_path: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = text.splitlines()
    frontmatter_lines = _frontmatter_line_numbers(lines)

    for line_number, line in enumerate(lines, start=1):
        invisible = sorted({ord(char) for char in line if _is_invisible(ord(char))})
        if invisible:
            codepoints = ", ".join(f"U+{value:04X}" for value in invisible)
            findings.append(
                Finding(
                    relative_path,
                    line_number,
                    "unicode.invisible",
                    f"contains invisible Unicode code point(s): {codepoints}",
                )
            )

        for rule_id, pattern, message in _CONTENT_RULES:
            if pattern.search(line):
                findings.append(Finding(relative_path, line_number, rule_id, message))

        if _EXFILTRATION_TERM.search(line) or (
            _OUTBOUND_TERM.search(line) and _SENSITIVE_TERM.search(line)
        ):
            findings.append(
                Finding(
                    relative_path,
                    line_number,
                    "tool.exfiltration_shape",
                    "contains exfiltration-shaped tool or sensitive-data language",
                )
            )

        if line_number in frontmatter_lines:
            if re.match(r"^\s*allowed-tools\s*:", line, re.IGNORECASE):
                findings.append(
                    Finding(
                        relative_path,
                        line_number,
                        "frontmatter.allowed_tools",
                        "note frontmatter declares or widens tool authority",
                    )
                )
            if re.match(
                r"^\s*disable-model-invocation\s*:\s*"
                r"[\"']?(?:false|no|0)[\"']?\s*(?:#.*)?$",
                line,
                re.IGNORECASE,
            ):
                findings.append(
                    Finding(
                        relative_path,
                        line_number,
                        "frontmatter.model_invocation_enabled",
                        "note frontmatter explicitly enables model invocation",
                    )
                )

    return findings


def scan_library(path: Path) -> list[Finding]:
    root = _library_root(path)
    findings: list[Finding] = []
    for relative_path, text in _read_notes(root, _collect_notes(root)):
        findings.extend(_scan_text(relative_path, text))
    return sorted(findings, key=lambda item: (item.path.lower(), item.line, item.rule_id))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="Library root (the folder holding library.json)")
    args = parser.parse_args(argv)

    try:
        root = _library_root(Path(args.path))
        findings = scan_library(root)
        skipped = unscanned_markdown(root)
    except ScanError as exc:
        print(f"ERROR Library scan incomplete: {exc}", file=sys.stderr)
        return 2

    if (root / SOURCES_DIR).is_dir():
        # Not a Finding and not a skip: raw text is input to note-writing, not
        # a note, so agents reading the Library never open it.
        print(
            f"Note: {SOURCES_DIR}/ (opt-in raw source text, never read as notes) "
            "is excluded from the scan."
        )

    if skipped:
        # Advisory only, and deliberately not a Finding: the bounded scope is
        # intentional, so these files must not change the exit code. But the
        # user has to know the "passed" line below does not cover them.
        print(
            f"Note: {len(skipped)} Markdown file(s) in the Library are outside "
            "the note scope and were NOT scanned:"
        )
        for relative in skipped:
            print(f"  SKIP {_terminal_safe(relative)}")
        print(
            "  Scope is index.md, glossary.md, AGENTS.md, books/, and concepts/*.md. "
            "Move Library content there to have it scanned."
        )

    if findings:
        print(f"Library scan found {len(findings)} advisory finding(s):")
        for finding in findings:
            print(
                f"  WARN {_terminal_safe(finding.path)}:{finding.line} "
                f"[{finding.rule_id}] {finding.message}"
            )
        print("Review the flagged notes before an agent reads, shares, or publishes the Library.")
        print(
            "Rules are intentionally broad and may match legitimate AI/LLM or "
            "systems-topic text; review each finding in context."
        )
        print("No files were modified by this scan.")
        return 1

    scope = " in the scanned scope" if skipped else ""
    print(
        f"Library scan passed: no known injection or authority patterns "
        f"found{scope}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
