---
name: task
description: Use when switching to working on a specific task (project)
---

Switch to working on task `$ARGUMENTS`:

1. List `tasks/active/*.md` and confirm `tasks/active/$ARGUMENTS.md` exists.
2. Read the task file at `tasks/active/$ARGUMENTS.md`.
3. Write the task name to `.claude/active-task` (just the name, e.g., "ci-pipeline-shard").
4. If the task has YAML frontmatter, note any `repositories:`, `build_paths:`, `test_paths:`, or `verification:` fields.

Review the task context including:
- Current status and goals
- Previous investigation notes
- Any blockers or open questions
- Next steps
- **Repositories involved** (from frontmatter, if present)
- **Build/test paths** (from frontmatter or task body, if present)
- **Verification target** for the current task, if specified
- Whether a git worktree should be created or used for implementation work

Do not write `.claude/active-task` if the task file does not exist. Then ask me what I'd like to work on for this task, including the recommended next step and worktree setup when appropriate.
