"""CLI: python -m book_to_kb.library <command> <library> [options]."""

from __future__ import annotations

import argparse
import sys

sys.dont_write_bytecode = True

from pathlib import Path  # noqa: E402

from . import commands  # noqa: E402
from .model import LibraryError, load  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m book_to_kb.library")
    sub = parser.add_subparsers(dest="command", required=True)
    p_init = sub.add_parser("init", help="create a Library (safe to rerun)")
    p_init.add_argument("library", type=Path)
    p_init.add_argument("--name", default="Library")
    p_init.add_argument("--language", default="en")
    for name, help_text in (
        ("concepts", "print every Concept: slug, kind, title, aliases, books"),
        ("index", "rebuild every Index Page from the notes"),
        ("validate", "check links, schema, aliases, and freshness; exit 1 on errors"),
    ):
        sub.add_parser(name, help=help_text).add_argument("library", type=Path)
    p_rm = sub.add_parser("remove-book", help="delete a Book and its Contributions")
    p_rm.add_argument("library", type=Path)
    p_rm.add_argument("book")
    args = parser.parse_args(argv)

    try:
        if args.command == "init":
            root = commands.init(args.library, args.name, args.language)
            print(f"Library ready: {root}")
            return 0
        lib = load(args.library)
        if args.command == "concepts":
            sys.stdout.write(commands.concept_list(lib))
        elif args.command == "index":
            changed = commands.index(lib)
            print(f"{len(changed)} file(s) rewritten" + "".join(f"\n  {p.relative_to(lib.root)}" for p in changed))
        elif args.command == "validate":
            findings = commands.validate(lib)
            for f in findings:
                print(f)
            errors = sum(f.severity == "error" for f in findings)
            print(f"{errors} error(s), {len(findings) - errors} warning(s)")
            return 1 if errors else 0
        elif args.command == "remove-book":
            report = commands.remove_book(lib, args.book)
            print(f"Removed {args.book}.")
            print(f"  deleted Concepts: {', '.join(report.deleted_concepts) or 'none'}")
            print(f"  edited Concepts: {', '.join(report.edited_concepts) or 'none'}")
            if report.stale_prose:
                print(f"  REWRITE NEEDED (prose still links the removed Book): {', '.join(report.stale_prose)}")
                return 2
    except LibraryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except KeyError as exc:
        print(f"ERROR: {exc.args[0]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
