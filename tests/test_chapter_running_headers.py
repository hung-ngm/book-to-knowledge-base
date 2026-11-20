"""Running page headers that pdftotext keeps in the text are not chapters.

Shape seen in a real 259-page PDF: every other page opens with the page number,
wide spacing, then the running title ("26   Chapter 1: Prerequisites",
"212   Inference Glossary"). Read as a bare "<number>  <Title>" heading, each
page number became a chapter: 115 detected for a book with 8. The real chapter
openers are bare "CHAPTER N" lines.
"""

from book_to_kb.utils import detect_structure


def _book() -> str:
    parts = ["Preface opening text.\n"]
    page = 10
    for _ in range(3):
        parts.append(f"\n{page}   Preface\n\nMore preface prose.\n")
        page += 2
    for number, title in enumerate(["Inference", "Prerequisites", "Models"]):
        parts.append(f"\n     CHAPTER {number}\n\n{title} opening prose.\n")
        for _ in range(4):
            parts.append(f"\n{page}   Chapter {number}: {title}\n\nBody prose on page {page}.\n")
            page += 2
    for _ in range(3):
        parts.append(f"\n{page}   Inference Glossary\n\nTerm: definition.\n")
        page += 2
    return "".join(parts)


def test_running_page_headers_are_not_chapters():
    structure = detect_structure(_book())
    assert structure["chapters_detected"] == 3
    titles = [r["title"] for r in structure["chapter_ranges"]]
    assert [t.strip() for t in titles] == ["CHAPTER 0", "CHAPTER 1", "CHAPTER 2"]


def test_a_numbered_heading_seen_once_is_still_a_chapter():
    text = "\n1  Introduction\n\nProse.\n\n2  Methods\n\nProse.\n\n3  Results\n\nProse.\n"
    assert detect_structure(text)["chapters_detected"] == 3
