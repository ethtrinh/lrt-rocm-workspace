---
name: prep-pr
description: Use when preparing commit stack for PR with milestone review
---

Prepare for PR with milestone review. Argument: `$ARGUMENTS` (optional repo alias)

## 1. Show commit stack

```bash
python scripts/review.py stack $ARGUMENTS
```

Parse the JSON and display the commits since main, showing what will be in the PR.

## 2. Get merge base for diff

```bash
cd <repo_path>
git merge-base HEAD main
```

## 3. Open milestone diff in VSCode

Use MCP to open all changed files since main in diff view:

```
mcp__vscode__openChangedFiles(repoPath=<repo_path>, fromRef=<merge_base>, toRef="HEAD", newWindow=true)
```

## 4. Report

Show:
- Number of commits
- Number of files changed
- Summary stats

Say: "Staged full diff for milestone review. After approval, I can help squash into logical commits for PR."

**STOP and wait for user review.**
