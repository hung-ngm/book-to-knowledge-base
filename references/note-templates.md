# Note templates

Frontmatter is a strict YAML subset: `key: value`, `key: [a, b]`, or a block list (`key:` followed by `  - item` lines). Quote any value that contains `:` or `,`. Every filename stem in the Library is unique, so `[[stem]]` and `[[stem|label]]` always resolve. Slugs are lowercase ASCII words joined by `-`.

## Book Note: `books/<book>/<book>.md`

`<book>` is the title in slug form, shortened to 3–5 words: `wealth-of-nations`.

```markdown
---
kind: book
title: "<Full Title>"
authors: [<Author One>, <Author Two>]
year: <YYYY>
book_type: <text|technical>
depth: <reference|study>
sources: [<source file names, or the MCP provider and item id>]
added: <YYYY-MM-DD>
---

# <Full Title>

**Author**: <Author(s)> · **Year**: <YYYY> · **Chapters**: <N>

<If the sources cover only part of the book, one line first: "Excerpt: <which parts>.">

<One paragraph: what the book argues, for whom, and the 3–6 Concepts it is known for, as [[concept-slug|Name]] links.>

<!-- kb:chapters -->
<!-- /kb:chapters -->
```

Leave the `kb:chapters` block empty. `index` fills it.

## Chapter Note: `books/<book>/<book>-chNN.md`

`NN` is the two-digit order of the Chapter Notes in the book (`01`, `02`, …), including a preface note, not the book's own numbering. The title keeps the book's own numbering ("Book II, Chapter I: Of the Division of Stock").

```markdown
---
kind: chapter
book: <book>
title: "<Chapter title as the book gives it>"
source_lines: "<start>-<end>"
---

# <Chapter title>

## Core Idea
<1–2 sentences: the one thing this chapter teaches>

## Concepts Introduced
- [[<concept-slug>|<Name as the author writes it>]]: <how this chapter uses or defines it, one line>

## Argument
<The chapter's reasoning in order, as 3–8 numbered steps. Keep the author's sequence.>

## Code Examples
<technical only: the most instructive snippet, exact indentation, plus one line on what it shows>

## Reference Tables
<technical only: a decision or comparison table the chapter gives>

## Worked Example
<study depth only: one example the author works through, reconstructed compactly>

## Key Takeaways
1. <actionable insight>
<3–7 items>

## Connects To
- [[<book>-chNN]]: <why>
```

`Connects To` may link chapters of other Books in the Library. A title combines the label and the heading: "Chapter I: On Value".

Leave out any section that does not apply. Do not leave it with filler.

**Budget per Chapter Note.** Earn study depth with content: a worked example, steps for each framework, and why it fails. Budgets are targets, not minimums: a short chapter or a simple term gets a short note. Never pad.

| | reference | study |
|---|---|---|
| text | 600–1,000 tokens | 900–1,600 tokens |
| technical | 1,000–1,600 tokens | 1,800–2,800 tokens |

## Concept: `concepts/<slug>.md`

```markdown
---
kind: concept
title: <Canonical Name>
concept_kind: <framework|principle|technique|anti-pattern|term>
aliases: []
---

# <Canonical Name>

<Definition: one paragraph that every Contributing Book supports. First sentence stands alone, because the glossary quotes it.>

## In [[<book>]]

Also called: <another name this Book uses>; <original-language term, when the Library Language differs>

<That author's exact formulation (one short quote at most), when to apply it, how (steps or criteria), and where it fails. Link chapters: [[<book>-chNN]]. 120–400 tokens.>

## In [[<other-book>]]

<...>

## Tensions

<Only when Books disagree. Name each side with its Book link and state the disagreement plainly. Do not resolve it unless a Book does.>

## Related

- [[<concept-slug>]]: <a relationship every Contributing Book supports>
```

Rules:

- **A Book owns only its Contribution** (ADR 0004). Everything a Book adds lives in its `## In [[book]]` section, so removing the Book removes all of it:
  - **Names.** The `Also called:` line, first in the section, lists this Book's other names for the Concept, separated by `;`: abbreviations, synonyms, original-language terms. A generic label the author files it under ("Batching", "Caching") is not a name. Leave the line out when there are none.
  - **Aliases.** Never edit `aliases` in frontmatter. `index` rebuilds it from every `Also called:` line, and `validate` flags a hand edit.
  - **Details and relations only this Book draws** go in its Contribution, not in the definition or in `## Related`.
- **Contribution order.** Contributions come right after the definition, in the order Books were added.
- **Edits on later Books.** A later Book adds its own `## In [[book]]` section. It may also add `## Tensions`, or reword the definition and `## Related` where every Contributing Book supports the change. It never edits another Book's Contribution.
- **Concept Kind:**
  - **framework:** a named model with parts.
  - **principle:** a rule that guides decisions.
  - **technique:** a step-by-step method.
  - **anti-pattern:** what to avoid, and why.
  - **term:** a defined word with no method behind it.
