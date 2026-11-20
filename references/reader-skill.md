# Reader Skill

A Reader Skill is a small Agent Skill that lets an agent in any project read this Library. It only reads. The script generates it from the Library, and its description lists the Books and the most shared Concepts, so hosts know when to load it.

1. **Pick the skills root:**
   - `~/.agents/skills` by default. Codex, Copilot CLI, Amp and OpenCode scan it.
   - A project's `.agents/skills` or `.claude/skills` when the user wants it scoped to that project.
2. **Write the skill:** `$KB reader-skill "$LIB" <skills root>`. It writes `<root>/<library-name>-library/SKILL.md` and is safe to rerun.
3. **Claude Code.** Claude Code reads only `~/.claude/skills`. For a personal install, link the skill there, then read the link back:

```bash
ln -sfn "<root>/<name>" "$HOME/.claude/skills/<name>" && readlink "$HOME/.claude/skills/<name>"
```

   If `~/.claude/skills/<name>` is a real folder, ask before replacing it.
4. **Rerun after every Book you add or remove.** The description lists the current Books.
5. **Report** the path and which hosts will find it. Tell the user to start a new session so the host loads it.
