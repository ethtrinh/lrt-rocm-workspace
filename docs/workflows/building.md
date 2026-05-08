# Building — Workspace Context

You are in a build workflow. The goal is to compile ROCm components (HIP, OCL, ROCr, PAL) from source.

## Before You Start

Read `directory-map.md` to resolve:
- TheRock or rocm-systems repo location
- Target GPU architecture (gfx906, gfx90a, gfx942, gfx1201, etc.)
- OS (Linux or Windows)

## Which Build System?

| Scenario | Skill | Notes |
|---|---|---|
| Default for HIP/OCL | `lrt-rocm:the-rock` | Builds happen in-tree under TheRock |
| Explicitly using rocm-systems | `lrt-rocm:hip-ocl-monorepo-build` | Only if user says "rocm-systems" or "monorepo" |
| Windows with PAL/ROCr backends | `lrt-rocm:pal-rocr-windows-build` | Requires VS 2022, WDK 28000 |

## Pipeline

```
Configure (CMake) -> Build -> Test -> Iterate
```

1. **Configure** — Set CMake flags for target GPU and build type. Check both source tree and build tree caches.
2. **Build** — Full build first time, incremental after. Watch for submodule pointer mismatches.
3. **Test** — Run relevant tests (hip-tests, OCL tests). If failures, switch to the debugging workflow.
4. **Iterate** — Fix, rebuild incrementally, re-test.

## Common Gotchas

- TheRock is a super-project with submodules. Dependency management lives in the super-project (e.g., `core/CMakeLists.txt`), not in submodules.
- Always check submodule state after switching branches: `git submodule update --init`
- Build failures after branch switch often mean stale CMake cache — delete `CMakeCache.txt` and reconfigure.
- For submodule-level changes, use `rk.py` to coordinate topic branches.

## Skip

Build output from unrelated components, task files, design docs — not relevant during builds.
