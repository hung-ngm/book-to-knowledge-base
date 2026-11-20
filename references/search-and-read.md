# Search & Read a Book over MCP

Use this route when the user asks to `search <query>`, or names a book with no local file. It reads a book through an MCP book provider and adds it to the Library. Raw book text is never saved: not as `full_text.txt`, and not as `.sources/`.

**Helpers.** The helpers in `book_to_kb.remote` are offline and stdlib-only. Call them through Python with the skill root on the path:

```bash
PYTHONPATH="$SKILL_ROOT" $PY -B -c 'from book_to_kb.remote import discovery; ...'
```

The `-B` stops Python writing `__pycache__` into the skill.

## R0. Provider and policy

1. **Find a provider.** Look for an MCP server in your toolset that exposes `search`, `get_details` and `read`, such as `libgen-mcp` (github.com/jmrplens/libgen-mcp). If there is none, stop and say so. Offer two options:
   - Help register a provider. Do this only on the user's explicit yes, and never overwrite an existing MCP server entry.
   - Add a local file instead.
2. **Check policy.** Load it with `policy.load_policy()`, which honors `BOOK_KB_REMOTE_POLICY`. Then run `policy.check_provider_allowed(provider, policy)`. Stop if the provider is not allowed.
3. **Get a query.** If the user gave no query, ask for a title, author, ISBN, or DOI.

## R1. Find the book

1. **Search.** Call MCP `search`. For `libgen-mcp`, pass `"extra_sources": "always"` and `"topics": ["nonfiction"]`.
2. **Group results.** Pass the results through `discovery.normalize_search_results(raw, provider=...)`, then `discovery.group_duplicate_editions(...)`. Show `discovery.format_candidate_selection_table(...)`.
3. **Pick.** The user picks one numbered candidate. Never pick for them. Prefer EPUB or PDF, and open-access editions.
4. **Details.** Call MCP `get_details`, then `discovery.normalize_work_details(...)`. Prefer `read(doi=...)` when an open-access DOI exists.

## R2. Consent gate

Show `policy.build_access_copyright_notice(candidate, policy)`. Pass the user's reply to `policy.verify_user_confirmation(reply, candidate, policy)`. If it returns `False`, stop without calling `read`. A search command is not consent.

## R3. Set up

1. **Re-run guard and type.** Run steps 1 and 2 of `add-book.md`.
2. **Checkpoint.** Create a private work folder (`mkdir -m 700`). Write a checkpoint with `checkpoint.init_remote_session(...)` and `checkpoint.save_remote_session(session, workdir)`. It never holds book prose.
3. **Resume.** To resume after an interruption, call `checkpoint.load_remote_session(workdir)` and process only `checkpoint.pending_chapters(session)`.

## R4. Read chapter by chapter

1. **Get the outline.** Call MCP `read` in outline mode, then `reader.parse_outline_response(raw)`. If it returns `sequential_fallback`, tell the user that chapter boundaries are inferred.
2. **Show the estimate.** Run step 4 of `add-book.md` (estimate, depth, confirm), using the outline's chapter count.
3. **Read each pending chapter:**
   - Read it page by page through `reader.process_section_page(...)`, or `reader.read_section_from_pages(...)`. Both sanitize every chunk and stop on cursor loops and request caps.
   - Write its Chapter Note and `candidates.tsv` rows, as in step 6 of `add-book.md`.
   - Drop the raw text from memory.
   - Record progress with `checkpoint.update_chapter_progress(...)` and `checkpoint.save_remote_session(...)`.
4. **Truncated or failed chapters.** If a chapter comes back `truncated`, `incomplete` or `failed`, put a warning line at the top of its Chapter Note. Never present it as complete. If a mirror shows a challenge or CAPTCHA, do not try to get past it. Offer another edition or a local file instead.

## R5. Finish

1. **Match and write.** Run steps 7–8 of `add-book.md`: matching, relink, and Concepts.
2. **Provenance.** Compute `coverage.build_coverage_report(session)` and `provenance.build_remote_provenance(candidate, session, policy, coverage=coverage)`. Append a `## Provenance` section to the Book Note with `provenance.render_provenance_markdown(provenance)`. Set `sources` in its frontmatter to `[<provider>:<item_id>]`.
3. **Check.** Run "After every change" from `SKILL.md`.
4. **Clean up.**
   - If coverage is `complete`, remove the work folder.
   - Otherwise, keep it and give the user its path so they can resume.
5. **Report.** Report as in step 9 of `add-book.md`, plus `coverage.format_coverage_summary(coverage)`.
