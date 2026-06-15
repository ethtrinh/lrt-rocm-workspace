# LRT Runtime Development — Workspace Context

You are working on Language Runtime Technology (LRT): HIP runtime, OpenCL runtime, ROCr interaction, and shared runtime build/test infrastructure.

## Scoping work

Before editing code, split work into small tasks with independently testable outcomes. Prefer doing implementation work in a git worktree by default so builds, tests, and experiments stay isolated from the primary checkout.

1. Identify the affected runtime subsystem: memory, queues/streams/events, modules/programs/kernels, devices/context, peer/IPC, errors, packaging, or build integration.
2. Create a task boundary around one subsystem or behavior at a time.
3. Define the exact test, reproducer, or command that proves each task is complete.
4. Do not start implementation for a task until its verification path is known.

## Finding implementation and tests

1. Read `directory-map.md` to locate source and test checkouts.
2. Search for the affected HIP/OpenCL API or runtime component.
3. Search existing HIP tests, OpenCL tests, and focused reproducers for nearby coverage.
4. Identify the smallest runtime subsystem involved.
5. Select or add the focused failing test/reproducer before changing implementation code.

## Build routing

Use `lrt-build-routing`, `the-rock`, or `hip-ocl-monorepo-build` to choose the right build path.

Preferred order:

1. TheRock for default HIP/OpenCL builds and super-project integration.
2. rocm-systems/CLR when explicitly working in the monorepo flow.
3. Runtime test builds when adding or changing tests.
4. Installed ROCm trees only for reproduction or validation when source rebuilds are not needed.
5. Full builds only when targeted validation is insufficient.

Always record working directory, command, environment, and result.

## Test-driven development

For code changes, use TDD by default:

1. Identify one observable runtime behavior for the current scoped task.
2. Identify an existing focused test or add a small reproducer/test for that behavior.
3. Run it before implementation when practical and record the failing or baseline result.
4. Implement the smallest change needed for that behavior.
5. Run the same test to prove the task passed.
6. Repeat with the next behavior only after the current test is green.
7. Only then add broader regression validation if needed.

Prefer tests that verify public HIP/OpenCL API behavior or runtime-visible semantics. Avoid tests that only lock in private implementation shape, internal helper calls, or incidental data structures.

Mocking should be rare in runtime work. Prefer real runtime paths through focused reproducers, HIP tests, or OpenCL tests. Only replace external/system boundaries when a real dependency is impractical for the scoped test.

If TDD is not practical, document why and define the narrowest alternative verification before coding.

## Testing evidence

Capture:

- GPU architecture.
- ROCm install path.
- Relevant runtime environment variables.
- Exact test command.
- Pass/fail output.

Start with the narrowest test that exercises the changed behavior. Add broader tests for cross-subsystem changes.
