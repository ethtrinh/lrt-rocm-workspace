---
name: wip
description: Use when creating a quick WIP commit checkpoint
---

Create a WIP commit:

1. Stage all changes: `git add -A`
2. Commit with message: `WIP: $ARGUMENTS`
   - If no argument, use: `WIP: checkpoint $(date +%H:%M)`
3. Show: `git log -1 --oneline`
