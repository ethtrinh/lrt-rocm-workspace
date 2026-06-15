# ROCm Development Workspace

This workspace is for development work on ROCm (Radeon Open Compute) via TheRock and related projects.

## Workspace model

This is a Claude Code meta-workspace. The workspace root is for shared Claude configuration, docs, task notes, and helper scripts. Source code changes happen in the repositories listed in `directory-map.md`, not in the workspace root unless you are intentionally editing workspace configuration.

## Git rules

- Make source code changes in the actual repository from `directory-map.md`.
- Never push, force-push, amend commits, delete branches, or discard user changes without explicit approval.
- Before editing a source repo, inspect its `git status` and avoid overwriting unrelated work.
- Prefer creating or using a git worktree for non-trivial implementation work, experiments, or build/test-heavy changes. If a worktree is not practical, state why.

## Environment

See `directory-map.md` for all repository locations and build paths.

## Project Focus

<!-- Describe what you're working on in this workspace. Examples: -->
<!-- - Build infrastructure for TheRock -->
<!-- - HIP runtime development via rocm-systems -->
<!-- - GPU test harness for gfx1201 -->

## Notes

<!-- Your ongoing notes, discoveries, and context as you work -->
