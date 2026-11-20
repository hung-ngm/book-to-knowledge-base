# Add a Book

Read `note-templates.md` first. `$LIB`, `$PY`, `$EXTRACT`, `$KB` and `$SCAN` are set in `SKILL.md`.

## 1. Re-run guard

Derive the book slug from the file name or title, then check `ls "$LIB/books"`. If the slug exists, stop and ask the user to choose:

1. **Re-add.** Run `remove-book.md` first, then continue here.
2. **Keep** the existing Book and stop.
3. **Add as a separate Book** under a new slug, such as `<slug>-2e` for another edition.

## 2. Content type

Ask: "Is this book **technical** (code, tables, formulas) or **text** (mostly prose)?" "Not sure" counts as text. Store the answer as `BOOK_TYPE`.

## 3. Extract

```bash
$EXTRACT <paths> --mode "$BOOK_TYPE" --install-missing ask
```

The run prints `Workdir ->`, `Text ->` and `Meta ->`. Use those paths, never a guessed location. Call them `WORK`, `TEXT` and `META`.

Read `META`. Confirm that `sources[].filename` names the files the user gave. Use only the top-level `chapter_ranges`: its `{title, start_line, end_line[, source]}` entries are 1-based and inclusive, and index into `TEXT`. Ignore `sources[].chapter_ranges`, which count lines in each source file, not in `TEXT`.

A range `title` is often only the label (`CHAPTER V.`). Take the full chapter title from the first lines of the range when you read it.

If `chapter_ranges` is empty, or one range covers most of a long book, locate chapters yourself with `grep -n` on `TEXT`, and say so in the report.

**Edges of the ranges.** Check what lies outside and at the end of the ranges with `grep -n -i` for headings such as `preface`, `introduction`, `appendix`, `glossary`, `references`, `acknowledg`:

- A preface or introduction that argues something gets its own Chapter Note, first in order. Skip title pages, copyright pages and the table of contents.
- If the last range runs into appendices or back matter, end it at the first appendix heading.
- A book glossary is not a note. Use it to check your definitions, and make a Concept of a glossary term only when a chapter names it.
- Skip reading lists, acknowledgements and advertisements, and say so in the Book Note.

## 4. Estimate, purpose, confirm

Show:

- the sources
- the word count and `estimated_tokens` from `META`
- the chapter count
- the output tokens: about chapters × (the midpoint of the `BOOK_TYPE` × `DEPTH` budget cell + new Concepts per chapter × 400). Assume about 6 new Concepts per chapter for `text` books and about 12 for `technical` ones
- the files to be written

Ask in the same message: "Should these notes help you **reference** the book (lean) or **study** it (deeper, with worked examples)?" Store the answer as `DEPTH`. Also ask whether to keep the extracted text in the Library's private `.sources/` folder (default no). Wait for confirmation. "Analyze only" stops here. In that case, report the title, the authors, the chapters, and the 10–20 named ideas you expect.

## 5. Read without flooding context

Read one chapter at a time, in slices of at most 300 lines, dropping blank lines:

```bash
sed -n '<start>,<start+299>p' "$TEXT" | grep -v '^[[:space:]]*$'
```

A bigger slice can exceed the host's tool-output limit, and some hosts then save the overflow, raw book text, to a file outside `WORK` that cleanup never removes. If that happens anyway, tell the user the file's path in the report. To check that a name really appears in the book, use `grep -c -i '<name>' "$TEXT"`. Never read all of `TEXT` at once.

If the text is missing code or formulas that the book shows as images, describe them in your own words. Never invent exact code.

## 6. Write the Book Note and Chapter Notes

Write `books/<book>/<book>.md`, then one Chapter Note per range, in order.

For each named idea a chapter introduces:

1. Pick a **proposed slug** (the name in slug form) and link it in the Chapter Note as `[[proposed-slug|Name]]`.
2. Append a row to `$WORK/candidates.tsv`:

```
proposed-slug<TAB>Name as written<TAB>concept_kind<TAB><book>-chNN<TAB>one-line gist
```

If a later chapter names the same idea, reuse the same proposed slug and add a row for that chapter. If the author never names an idea, title it with the standard name in the field and keep the author's wording as an alias.

## 7. Match against the Library

Run `$KB concepts "$LIB"`. For each distinct proposed slug, decide:

| Case | Action |
|---|---|
| Name equals an existing title or alias (ignoring case and plural), with the same meaning | Map to that Concept. No question |
| Different name, same idea ("positive feedback" vs "reinforcing loop") | **Concept Match**: propose it |
| Same name, different idea ("flow" in psychology vs in lean) | New Concept with a qualified slug: `flow-psychology` |
| No counterpart | New Concept under the proposed slug, unless that slug is taken |

Show every proposed Concept Match in one table: the new name, the existing Concept, and one line of evidence. Ask the user to approve or reject each one. A rejected match becomes a new Concept.

Every proposed slug that maps to an existing Concept with a different slug (`rent` to `rent-of-land`) needs a relink line too. If every final slug equals its proposed slug, skip the relink. Otherwise write `$WORK/relink.tsv` with an `old<TAB>new` line for every proposed slug whose final slug differs, then run:

```bash
$KB relink "$LIB/books/<book>" "$WORK/relink.tsv"
```

## 8. Write Concepts

**New Concept.** Create `concepts/<slug>.md`. Add a definition, this Book's Contribution, and `## Related` links to other Concepts from this Book.

**Existing Concept.** Edit the note as follows:

- Insert this Book's `## In [[<book>]]` section after the last Contribution.
- Put the names this Book uses on the `Also called:` line of its own section. Never edit `aliases` in frontmatter; `index` rebuilds it.
- Leave the definition and `## Related` alone unless the change holds for every Contributing Book. A detail or relation only this Book draws goes in its own section.
- If this Book disagrees with another, add or extend `## Tensions` in the shared Concept. Name both Books. If the disagreement is about the definition itself, keep the definition neutral and put the disagreement in `## Tensions`.
- Keep the existing `concept_kind` unless the user agrees to change it.
- Never edit another Book's Contribution.

## 9. Finish

Run "After every change" from `SKILL.md`. Fix errors in the notes until `validate` reports 0 errors.

**Raw text (opt-in).** If the user opted in, copy `TEXT` and `META` to `$LIB/.sources/<book>/`. The Library's `.gitignore` already excludes that folder.

**Clean up.** Whether or not the user opted in, remove `WORK`, the exact path the extractor printed. It holds the full book text. Never remove a path you did not create.

Report:

- the Book, chapters written, and Concepts created or merged, with the approved Concept Matches
- any Tensions added
- the `validate` and scan results
- any warnings

**Example:** "Wealth of Nations: 32 Chapter Notes, 41 Concepts created, 0 merged. Validate: 0 errors, 2 orphan warnings."
