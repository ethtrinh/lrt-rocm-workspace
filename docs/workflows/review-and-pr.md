# Review and PR Prep — Workspace Context

You are in a review or PR preparation workflow. The goal is to review changes, address feedback, and prepare work for submission.

## Which Stage?

| Stage | Skill | When |
|---|---|---|
| Incremental review | `lrt-rocm:stage-review` | After each batch of Claude changes — review HEAD~1..HEAD |
| Address review comments | `lrt-rocm:process-review` | After user adds RVW:/RVWY: comments to code |
| Milestone review | `lrt-rocm:prep-pr` | Before PR — review all changes since main |
| Squash for PR | `lrt-rocm:squash-prep` | After milestone review is approved |

## Pipeline

```
Stage changes -> Review diffs -> Add RVW comments -> Process comments -> Repeat until clean -> Prep PR -> Squash
```

1. **Stage** — `/lrt-rocm:stage-review` opens diffs in VSCode for the user to review.
2. **Comment** — User adds `// RVW: comment` (discuss) or `// RVWY: comment` (auto-fix) inline.
3. **Process** — `/lrt-rocm:process-review` finds all comments, proposes or applies fixes.
4. **Iterate** — Repeat stages 1-3 until the user is satisfied.
5. **Milestone review** — `/lrt-rocm:prep-pr` shows the full diff since main for final review.
6. **Squash** — `/lrt-rocm:squash-prep` analyzes the commit stack and suggests a PR commit message.

## Review Comment Format

| Marker | Meaning | Action |
|---|---|---|
| `// RVW: comment` | Discuss with user | Propose fix, wait for confirmation |
| `// RVWY: comment` | YOLO mode | Make the fix without asking |

Works in any language: `# RVW:` (Python/shell), `<!-- RVW: -->` (Markdown/HTML).

## Skip

Build output, test logs, unrelated source trees — focus on the changed files only.
