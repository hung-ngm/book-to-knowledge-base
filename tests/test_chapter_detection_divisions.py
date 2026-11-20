"""Chapter detection across divisions, and table rows that look like headings.

Two shapes seen in real public-domain books, reproduced with synthetic text:

* Chapter numbers that restart under a higher division ("BOOK I." holds
  "CHAPTER I."–"CHAPTER III.", then "BOOK II." starts again at "CHAPTER I.").
  Every chapter in every division is a chapter, and each gets its own range,
  titled "<division> <chapter>" (e.g. "BOOK II. CHAPTER I.").
* A numeric table whose rows repeat the row above with ditto marks
  ('170  "   "   from   "   2.') — table data, not a "170  Title" heading.
"""

from book_to_kb.utils import _chapter_number, detect_structure


def _body(tag: str) -> str:
    return f"Synthetic body text for {tag}.\nA second line of prose.\n"


def _restarting_book(with_toc: bool = False) -> str:
    parts = []
    if with_toc:
        parts.append(
            "CONTENTS\n\n"
            "BOOK I.\n"
            "CHAPTER I.\n"
            "CHAPTER II.\n"
            "CHAPTER III.\n"
            "BOOK II.\n"
            "CHAPTER I.\n"
            "CHAPTER II.\n\n\n"
        )
    for book, count in (("I", 3), ("II", 2), ("III", 2)):
        parts.append(f"BOOK {book}.\nOF SOMETHING GENERAL.\n\n\n")
        for chapter in ("I", "II", "III")[:count]:
            parts.append(
                f"CHAPTER {chapter}.\nOF A PARTICULAR THING.\n\n"
                + _body(f"book {book} chapter {chapter}")
                + "\n\n"
            )
    return "".join(parts)


def _lines(text: str) -> list[str]:
    return text.split("\n")


def test_restarting_chapter_numbers_count_every_chapter():
    result = detect_structure(_restarting_book())

    assert result["chapters_method"] == "numeric"
    assert result["chapters_detected"] == 7
    assert [r["title"] for r in result["chapter_ranges"]] == [
        "BOOK I. CHAPTER I.",
        "BOOK I. CHAPTER II.",
        "BOOK I. CHAPTER III.",
        "BOOK II. CHAPTER I.",
        "BOOK II. CHAPTER II.",
        "BOOK III. CHAPTER I.",
        "BOOK III. CHAPTER II.",
    ]


def test_restarting_chapter_ranges_start_on_their_headings():
    text = _restarting_book()
    lines = _lines(text)
    ranges = detect_structure(text)["chapter_ranges"]

    for chapter in ranges:
        assert lines[chapter["start_line"] - 1].startswith("CHAPTER ")
    # Each range stops before the next one: Book II is not swallowed by the
    # last chapter of Book I.
    for previous, following in zip(ranges, ranges[1:]):
        assert previous["end_line"] == following["start_line"] - 1
    book_two = next(i for i, line in enumerate(lines, 1) if line == "BOOK II.")
    assert ranges[2]["end_line"] < ranges[3]["start_line"]
    assert ranges[2]["start_line"] < book_two < ranges[3]["start_line"]


def test_restarting_chapters_with_toc_do_not_duplicate():
    text = _restarting_book(with_toc=True)
    lines = _lines(text)
    result = detect_structure(text)

    assert result["chapters_detected"] == 7
    titles = [r["title"] for r in result["chapter_ranges"]]
    assert len(titles) == len(set(titles)) == 7
    contents = lines.index("CONTENTS") + 1
    # The ToC rows are not boundaries; the body headings are.
    first_body_book = next(
        i for i, line in enumerate(lines, 1) if line == "BOOK I." and i > contents + 1
    )
    assert all(r["start_line"] > first_body_book for r in result["chapter_ranges"])


def test_part_division_restart_is_keyed_too():
    text = "".join(
        f"PART {part}\n\n\n"
        + "".join(f"Chapter {n}: Topic\n\n{_body(f'{part}-{n}')}\n" for n in (1, 2))
        for part in ("1", "2")
    )
    result = detect_structure(text)

    assert result["chapters_detected"] == 4
    assert [r["title"] for r in result["chapter_ranges"]] == [
        "PART 1. Chapter 1: Topic",
        "PART 1. Chapter 2: Topic",
        "PART 2. Chapter 1: Topic",
        "PART 2. Chapter 2: Topic",
    ]


def test_divisions_without_restart_behave_as_before():
    text = "".join(
        f"BOOK {book}.\n\n\n"
        + "".join(f"CHAPTER {n}.\n\n{_body(str(n))}\n" for n in chapters)
        for book, chapters in (("I", ("I", "II")), ("II", ("III", "IV")))
    )
    result = detect_structure(text)

    assert result["chapters_detected"] == 4
    assert [r["title"] for r in result["chapter_ranges"]] == [
        "CHAPTER I.", "CHAPTER II.", "CHAPTER III.", "CHAPTER IV."
    ]


def test_ditto_table_rows_are_not_chapter_headings():
    assert _chapter_number('  170  "       "        "        from     "    2.') is None
    assert _chapter_number('  160  "       "        "        from     "    3.') is None
    # Column-aligned numeric rows with no ditto marks are table data too.
    assert _chapter_number("  12  wheat      40      bushels      3") is None
    # Plain numbered headings still count.
    assert _chapter_number("1  Introduction") == 1
    assert _chapter_number("12  Advanced Topics") == 12


def test_ditto_table_inside_roman_chapters_adds_no_ranges():
    text = (
        "CHAPTER I.\nON VALUE.\n\n" + _body("one") + "\n"
        "  180 qrs. of corn were obtained from land No. 1.\n"
        '  170  "       "        "        from     "    2.\n'
        '  160  "       "        "        from     "    3.\n\n'
        + _body("table tail")
        + "\nCHAPTER II.\nON RENT.\n\n" + _body("two")
    )
    result = detect_structure(text)

    assert result["chapters_detected"] == 2
    assert [r["title"] for r in result["chapter_ranges"]] == [
        "CHAPTER I.", "CHAPTER II."
    ]


# Editorial misnumbering: a book inserts a chapter and labels it with the
# previous number plus a marker ("CHAPTER V." then "CHAPTER V*."), rather than
# renumbering. The marker is part of the chapter's label, so the starred
# heading is a chapter of its own; a ToC row or running header that repeats a
# label (marker included) is still the same chapter.


def _starred_book(star: str = "5*") -> str:
    return "".join(
        f"Chapter {label}\n{title}\n\n" + _body(label) + "\n\n"
        for label, title in (
            ("4", "On Price"),
            ("5", "On Wages"),
            (star, "On Profits"),
            ("6", "On Rent"),
        )
    )


def test_starred_duplicate_number_is_its_own_chapter():
    text = _starred_book()
    result = detect_structure(text)

    assert result["chapters_detected"] == 4
    ranges = result["chapter_ranges"]
    assert [r["title"] for r in ranges] == [
        "Chapter 4", "Chapter 5", "Chapter 5*", "Chapter 6"
    ]
    lines = _lines(text)
    assert lines[ranges[2]["start_line"] - 1] == "Chapter 5*"
    assert lines[ranges[1]["end_line"] - 1] != "Chapter 5*"


def test_marker_after_numeral_period_is_its_own_chapter():
    text = _starred_book("5.*")
    result = detect_structure(text)

    assert result["chapters_detected"] == 4
    assert [r["title"] for r in result["chapter_ranges"]][2] == "Chapter 5.*"


def test_running_header_repeating_chapter_and_title_stays_one_chapter():
    pages = []
    for number, title in ((4, "On Price"), (5, "On Wages"), (6, "On Rent")):
        for page in range(3):
            pages.append(
                f"CHAPTER {number} {title}\n\n" + _body(f"{number} p{page}") + "\n\f"
            )
    result = detect_structure("".join(pages))

    assert result["chapters_detected"] == 3
    assert [r["title"] for r in result["chapter_ranges"]] == [
        "CHAPTER 4 On Price", "CHAPTER 5 On Wages", "CHAPTER 6 On Rent"
    ]


def test_toc_listing_starred_chapter_adds_no_ranges():
    toc = (
        "CONTENTS\n\n"
        "Chapter 4. On Price\n"
        "Chapter 5. On Wages\n"
        "Chapter 5*. On Profits\n"
        "Chapter 6. On Rent\n\n\n"
    )
    body = (
        "Chapter 4.\nON PRICE.\n\n" + _body("4") + "\n\n"
        "Chapter 5.\nON WAGES.\n\n" + _body("5") + "\n\n"
        "Chapter 5*.\nON PROFITS.\n\n" + _body("5*") + "\n\n"
        "Chapter 6.\nON RENT.\n\n" + _body("6")
    )
    text = toc + body
    result = detect_structure(text)

    assert result["chapters_detected"] == 4
    ranges = result["chapter_ranges"]
    assert [r["title"] for r in ranges] == [
        "Chapter 4.", "Chapter 5.", "Chapter 5*.", "Chapter 6."
    ]
    toc_end = toc.count("\n")
    assert all(r["start_line"] > toc_end for r in ranges)
