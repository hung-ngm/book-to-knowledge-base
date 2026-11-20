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

Read `META`. Confirm that `sources[].filename` names the files the user gave. `chapter_ranges` holds `{title, start_line, end_line[, source]}` entries, 1-based and inclusive, indexing into `TEXT`.

If `chapter_ranges` is empty, or one range covers most of a long book, locate chapters yourself with `grep -n` on `TEXT`, and say so in the report.

## 4. Estimate, purpose, confirm

Show:

- the sources
- the word count and `estimated_tokens` from `META`
- the chapter count
- the output tokens: about chapters × the budget midpoint + 400 per expected Concept
- the files to be written

Ask in the same message: "Should these notes help you **reference** the book (lean) or **study** it (deeper, with worked examples)?" Store the answer as `DEPTH`. Wait for confirmation. "Analyze only" stops here. In that case, report the title, the authors, the chapters, and the 10–20 named ideas you expect.

## 5. Read without flooding context

For each chapter, read only its range: `sed -n '<start>,<end>p' "$TEXT"`. To check that a name really appears in the book, use `grep -c -i '<name>' "$TEXT"`. Never read all of `TEXT` at once when `estimated_tokens` exceeds 50,000.

## 6. Write the Book Note and Chapter Notes

Write `books/<book>/<book>.md`, then one Chapter Note per range, in order.

For each named idea a chapter introduces:

1. Pick a **proposed slug** (the name in slug form) and link it in the Chapter Note as `[[proposed-slug|Name]]`.
2. Append a row to `$WORK/candidates.tsv`:

```
proposed-slug<TAB>Name as written<TAB>concept_kind<TAB><book>-chNN<TAB>one-line gist
```

If a later chapter names the same idea, reuse the same proposed slug.

## 7. Match against the Library

Run `$KB concepts "$LIB"`. For each distinct proposed slug, decide:

| Case | Action |
|---|---|
| Name equals an existing title or alias (ignoring case) | Map to that Concept. No question |
| Different name, same idea ("positive feedback" vs "reinforcing loop") | **Concept Match**: propose it |
| Same name, different idea ("flow" in psychology vs in lean) | New Concept with a qualified slug: `flow-psychology` |
| No counterpart | New Concept under the proposed slug, unless that slug is taken |

Show every proposed Concept Match in one table: the new name, the existing Concept, and one line of evidence. Ask the user to approve or reject each one. A rejected match becomes a new Concept.

Write `$WORK/relink.tsv` with an `old<TAB>new` line for every proposed slug whose final slug differs, then run:

```bash
$KB relink "$LIB/books/<book>" "$WORK/relink.tsv"
```

## 8. Write Concepts

**New Concept.** Create `concepts/<slug>.md`. Add a definition, this Book's Contribution, and `## Related` links to other Concepts from this Book.

**Existing Concept.** Edit the note as follows:

- Insert this Book's `## In [[<book>]]` section after the last Contribution.
- Add the names this Book uses to `aliases`, unless they are already the title or an alias.
- Sharpen the definition only if this Book makes it more precise.
- If this Book disagrees with another, add or extend `## Tensions`. Name both Books.
- Never edit another Book's Contribution.

## 9. Finish

Run "After every change" from `SKILL.md`. Fix errors in the notes until `validate` reports 0 errors.

**Raw text (opt-in).** If the user opted in, copy `TEXT` and `META` to `$LIB/.sources/<book>/`. The Library's `.gitignore` already excludes that folder. Then remove `WORK`, the exact path the extractor printed. Never remove a path you did not create.

Report:

- the Book, chapters written, and Concepts created or merged, with the approved Concept Matches
- any Tensions added
- the `validate` and scan results
- any warnings

**Example:** "Wealth of Nations: 32 Chapter Notes, 41 Concepts created, 0 merged. Validate: 0 errors, 2 orphan warnings."
