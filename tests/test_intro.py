"""The extractor names itself once, on stderr, and nothing more."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_kb import utils


def test_intro_names_the_tool_on_stderr(capsys):
    utils.print_intro()

    captured = capsys.readouterr()
    assert "book-to-knowledge-base" in captured.err
    assert captured.out == ""


def test_intro_has_no_upstream_credit_or_funding_link(capsys):
    utils.print_intro()

    err = capsys.readouterr().err.lower()
    assert "book-to-skill" not in err
    assert "sponsor" not in err
