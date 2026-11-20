#!/usr/bin/env python3
"""Phase 5 checks on a real two-Book Library, rerunnable from the shell.

    e2e_check.py snapshot        LIB BOOK STATE.json   # after adding the first Book
    e2e_check.py verify-merged   LIB BOOK STATE.json   # after adding the second Book
    e2e_check.py verify-removed  LIB BOOK STATE.json   # after removing the second Book

BOOK is always the first Book (the one whose Contributions must never change).
Exit 0 when every check passes; each failed check prints one FAIL line.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from book_to_kb.library import commands  # noqa: E402
from book_to_kb.library.model import CONTRIBUTION_RE, load, sections  # noqa: E402


def contributions_of(lib, book: str) -> dict[str, str]:
    out = {}
    for slug, concept in lib.concepts.items():
        for heading, text in sections(concept.body):
            match = CONTRIBUTION_RE.match(heading)
            if match and match.group(1).strip() == book:
                out[slug] = (heading + "\n" + text).rstrip("\n")
    return out


def notes_of(lib) -> list[str]:
    return sorted(str(n.path.relative_to(lib.root)) for n in lib.all_notes())


def gates(root: Path) -> list[str]:
    fails = []
    errors = [f for f in commands.validate(load(root)) if f.severity == "error"]
    fails += [f"validate: {f}" for f in errors]
    scan = subprocess.run(
        [sys.executable, str(ROOT / "tools/scan_library.py"), str(root)], capture_output=True, text=True
    )
    if scan.returncode != 0:
        fails.append(f"scan exit {scan.returncode}: {scan.stdout.strip()[-400:]}")
    return fails


def main(argv: list[str]) -> int:
    command, root, book, state_path = argv[0], Path(argv[1]), argv[2], Path(argv[3])
    lib = load(root)
    fails = gates(root)

    if command == "snapshot":
        state = {"contributions": contributions_of(lib, book), "notes": notes_of(lib)}
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        print(f"snapshot: {len(state['notes'])} notes, {len(state['contributions'])} {book} Contributions")
    else:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        now = contributions_of(lib, book)
        changed = sorted(s for s, text in state["contributions"].items() if now.get(s) != text)
        fails += [f"{book} Contribution changed or lost in concepts/{s}.md" for s in changed]
        if command == "verify-merged":
            merged = sorted(s for s, c in lib.concepts.items() if len(set(c.contributions)) >= 2)
            tensions = sorted(
                s for s, c in lib.concepts.items() if any(h == "## Tensions" for h, _ in sections(c.body))
            )
            print(f"merged Concepts ({len(merged)}): {', '.join(merged)}")
            print(f"Concepts with Tensions ({len(tensions)}): {', '.join(tensions)}")
            if not merged:
                fails.append("no Concept has Contributions from both Books")
            if not tensions:
                fails.append("no Tension recorded")
        elif command == "verify-removed":
            extra = sorted(set(notes_of(lib)) - set(state["notes"]))
            missing = sorted(set(state["notes"]) - set(notes_of(lib)))
            fails += [f"note left after removal: {p}" for p in extra]
            fails += [f"note lost after removal: {p}" for p in missing]
        else:
            fails.append(f"unknown command {command!r}")

    for fail in fails:
        print(f"FAIL {fail}")
    print("PASS" if not fails else f"{len(fails)} check(s) failed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
