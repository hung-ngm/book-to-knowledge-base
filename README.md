# book-to-knowledge-base

An Agent Skill that turns books into one shared Library of linked markdown notes. You browse the Library in a viewer such as Obsidian. Your agents search it with grep.

Each Book you add writes Chapter Notes in the author's order. Each named idea becomes a Concept note that every Book shares. When two Books discuss the same idea, both write to the same Concept note, and the note records where the authors disagree.

It reads PDF, EPUB, DOCX, HTML, Markdown, TXT, RTF, and MOBI/AZW files. It can also read a book through an MCP book search, such as `libgen-mcp`, without saving the raw text.

## What a Library looks like

```
~/library/
├── library.json      # name and note language
├── index.md          # every Book and Concept (generated)
├── glossary.md       # every Concept with its aliases (generated)
├── AGENTS.md         # how an agent should search this Library (generated)
├── books/<book>/     # one Book Note plus its Chapter Notes
└── concepts/         # one note per Concept, shared across Books
```

Notes are plain markdown with `[[wikilinks]]` and YAML frontmatter. The skill never hand-edits the generated files. `scripts/kb.py index` rebuilds them from the notes.

## Install

You need Python 3.9 or later and an agent host that supports [Agent Skills](https://github.com/agentskills/agentskills).

1. Clone the repository into the cross-agent skills folder. Codex, Copilot CLI, Amp, and OpenCode read this folder:

	```bash
	git clone https://github.com/hung-ngm/book-to-knowledge-base.git ~/.agents/skills/book-to-knowledge-base
	```

2. For Claude Code, link the skill into `~/.claude/skills`, because Claude Code reads only that folder:

	```bash
	mkdir -p ~/.claude/skills && ln -sfn ~/.agents/skills/book-to-knowledge-base ~/.claude/skills/book-to-knowledge-base
	```

3. Check which extractors are installed:

	```bash
	python3 ~/.agents/skills/book-to-knowledge-base/scripts/extract.py --check
	```

	Most formats fall back to a standard-library parser. The report prints the `pip` command for the better extractors. MOBI and AZW files need [Calibre](https://calibre-ebook.com/download). The skill also offers to install a missing extractor the first time it needs one.

4. Start a new agent session so the host loads the skill.

### Skills folder for each host

Each host scans its own skills folders. One clone in `~/.agents/skills` covers most hosts:

| Host | Folder it reads |
|---|---|
| Codex, Amp | `~/.agents/skills` |
| Copilot CLI | `~/.agents/skills` or `~/.copilot/skills` |
| OpenCode | `~/.agents/skills` or `~/.config/opencode/skills` |
| OpenClaw | `~/.agents/skills` with the default state folder. Otherwise `$OPENCLAW_STATE_DIR/skills` |
| Hermes Agent | `${HERMES_HOME:-$HOME/.hermes}/skills/<category>` |
| Claude Code | `~/.claude/skills` only. Link it as in step 2 |

For a host that does not read `~/.agents/skills`, link the clone into that host's folder:

```bash
ln -sfn ~/.agents/skills/book-to-knowledge-base <host skills folder>/book-to-knowledge-base
```

### Install for one project

To make the skill available only inside one project, put it in that project's `.agents/skills` folder instead:

```bash
cd <your project>
git clone https://github.com/hung-ngm/book-to-knowledge-base.git .agents/skills/book-to-knowledge-base
```

For Claude Code, link it into the project's `.claude/skills` folder:

```bash
mkdir -p .claude/skills && ln -sfn ../../.agents/skills/book-to-knowledge-base .claude/skills/book-to-knowledge-base
```

The Library still goes to `$BOOK_KB_LIBRARY` or `~/library`, not into the project, unless you name a path.

To have an agent install it, give the agent this repository URL and ask it to follow the **Install** section of this README.

## Use

Call the skill by name, then say what you want:

```text
/book-to-knowledge-base ~/books/wealth-of-nations.epub     # add a Book
/book-to-knowledge-base ~/books/*.pdf                      # add several Books
/book-to-knowledge-base analyze ~/books/ricardo.pdf        # preview chapters and cost, write nothing
/book-to-knowledge-base search "Inference Engineering"     # find a book over MCP and add it
/book-to-knowledge-base remove ricardo-principles          # remove a Book and its Contributions
/book-to-knowledge-base check                              # validate the Library
/book-to-knowledge-base reader-skill                       # let agents in other projects read the Library
```

The skill writes to the path you name. Without one, it uses `$BOOK_KB_LIBRARY`, then `~/library`. If no Library exists there, the skill asks for a name and a note language, then creates it.

Before it writes, the skill shows the chapter count and an output-token estimate and waits for your yes. It asks before it merges two differently named ideas into one Concept. Every change ends with `index`, `validate`, and a prompt-injection scan of the notes.

## Give other agents your Library

The `reader-skill` command writes a small read-only skill, `<library-name>-library`, that points any agent at your Library. Its description lists your Books and the most shared Concepts, so the host knows when to load it. By default it goes to `~/.agents/skills`, with the same Claude Code link as in **Install**. Rerun it after you add or remove a Book.

## Privacy

The Library is private by default. The skill never copies raw book text into notes, and a quote is at most one sentence. Extracted text stays in a temporary work folder unless you ask to keep it in the Library's git-ignored `.sources/` folder. Search over MCP never saves the raw text. Do not publish a Library built from books you do not own the rights to.

## Repository layout

```
SKILL.md              # entry point the agent reads
references/           # step-by-step workflows the agent loads on demand
scripts/extract.py    # book → clean text plus chapter ranges
scripts/kb.py         # Library commands: init, index, validate, remove-book, reader-skill
tools/scan_library.py # prompt-injection scan of a Library
book_to_kb/           # Python package behind both scripts
tests/                # pytest suite
```

Run the tests with `python3 -m pytest`.

## License

MIT. See [LICENSE.md](LICENSE.md). The license covers this code, not the books you process with it.
