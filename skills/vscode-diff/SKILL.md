---
name: vscode-diff
description: Use when opening git diffs in VSCode (requires MCP extension)
---

Open diffs in VSCode. Arguments: `$ARGUMENTS` (repo alias or path, optional commit count after space, default 1)

## 1. Resolve repository

Parse arguments: first word is repo alias/path, second word (if present) is commit count N (default 1).

Run `python scripts/review.py stack <repo>` to get repo path.

## 2. Open diffs

Use MCP to open changed files in diff view:

```
mcp__vscode__openChangedFiles(repoPath=<repo_path>, fromRef="HEAD~<N>", toRef="HEAD", newWindow=true)
```

## 3. Report

Show files opened and confirm they're in diff view.
