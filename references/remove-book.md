# Remove a Book

1. Confirm with the user: "Remove `<book>` and its Contributions from every Concept? Concepts that only this Book discusses will be deleted." Wait for a yes. This deletes files.
2. Run `$KB remove-book "$LIB" <book>`.
   - It deletes `books/<book>/` and this Book's Contributions.
   - It deletes Concepts left with no Contribution.
   - It drops `## Tensions` from Concepts left with a single Book.
   - It drops `## Related` bullets that point at a deleted note.
   - It rebuilds the Index Pages and each Concept's `aliases`, so the removed Book's names go too.
3. **Exit code 2** means the listed Concepts still mention the removed Book, its chapters, or a deleted Concept in their prose. Rewrite those sentences in each listed Concept: the definition, Tensions, and Related. They must no longer depend on the removed Book. Never edit another Book's Contribution, except to drop a broken link.
4. Run "After every change" from `SKILL.md` and report what was deleted and what you rewrote.
