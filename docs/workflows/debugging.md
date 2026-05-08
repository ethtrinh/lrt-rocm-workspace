# Debugging — Workspace Context

You are in a debugging workflow. The goal is to find and fix the root cause of a test failure or unexpected behavior.

## Before You Start

Gather:
- The exact error message or test output
- Which component is failing (HIP, OCL, ROCr, build system)
- Whether this is a regression (worked before) or a new feature failure

## Which Skill?

| Scenario | Skill | Notes |
|---|---|---|
| Any bug or test failure | `lrt-rocm:systematic-debugging` | Always start here — root cause before fixes |
| Regression (used to pass) | `lrt-rocm:regression-bisect-hip-ocl` | After systematic-debugging confirms it's a regression |
| Fix identified, need to implement | `lrt-rocm:test-driven-development` | Write failing test first, then fix |

## Pipeline

```
Reproduce -> Investigate -> Hypothesize -> Test -> Fix -> Verify
```

1. **Reproduce** — Run the failing test and capture exact output. No guessing.
2. **Investigate** — Read the failing code path. Check recent changes with `git log`.
3. **Hypothesize** — Form a specific theory about the root cause.
4. **Test the hypothesis** — Add logging, inspect state, narrow down.
5. **Fix** — Write a failing test first (TDD), then make it pass with minimal changes.
6. **Verify** — Run the full test suite, not just the fixed test.

## Common Patterns

- **Build failure after merge** — Stale CMake cache or submodule pointer mismatch. Clean and reconfigure.
- **Test passes locally, fails in CI** — Check GPU architecture differences, environment variables, path differences.
- **Flaky test** — Timing issue or uninitialized state. Run in a loop to confirm flakiness before investigating.
- **Regression** — Use `rk.py status` to check which submodules changed, then `regression-bisect-hip-ocl` to find the culprit commit.

## Skip

Build configuration files, design docs, PR history — not relevant during debugging unless the investigation leads there.
