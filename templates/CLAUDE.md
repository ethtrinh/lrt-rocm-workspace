# ROCm Build Infrastructure Project

## Overview

This workspace is for build infrastructure work on ROCm (Radeon Open Compute) via the TheRock repository and related projects.

Project repository: https://github.com/ROCm/TheRock

## Working Environment

**Important:** See `directory-map.md` for all directory locations.

This is a meta-workspace. Actual source and build directories are scattered across the filesystem and referenced by absolute paths.

## Task Routing

Use this table to determine what to read and which skills to invoke based on the current task.

| Work area | Context (read first) | Skills | Skip |
|---|---|---|---|
| **Building TheRock** | `directory-map.md`, `docs/workflows/building.md` (plugin) | `lrt-rocm:the-rock` | tasks/, design docs |
| **Building via rocm-systems** | `directory-map.md`, `docs/workflows/building.md` (plugin) | `lrt-rocm:hip-ocl-monorepo-build` | tasks/, design docs |
| **Building on Windows** | `directory-map.md`, `docs/workflows/building.md` (plugin) | `lrt-rocm:pal-rocr-windows-build` | tasks/, design docs |
| **Debugging test failures** | `docs/workflows/debugging.md` (plugin) | `lrt-rocm:systematic-debugging`, then `lrt-rocm:regression-bisect-hip-ocl` if regression | unrelated source trees |
| **Fixing a bug** | `docs/workflows/debugging.md` (plugin) | `lrt-rocm:systematic-debugging` -> `lrt-rocm:test-driven-development` | unrelated source trees |
| **Implementing a feature** | task file in `tasks/active/`, `docs/workflows/feature-development.md` (plugin) | `lrt-rocm:brainstorming` -> `lrt-rocm:writing-plans` -> `lrt-rocm:subagent-driven-development` | unrelated source trees |
| **Reviewing code** | `docs/workflows/review-and-pr.md` (plugin) | `lrt-rocm:stage-review` -> `lrt-rocm:process-review` | build output |
| **Preparing a PR** | `docs/workflows/review-and-pr.md` (plugin) | `lrt-rocm:prep-pr`, `lrt-rocm:squash-prep` | build output |
| **Build system changes** | `docs/adding-third-party-dep.md` (plugin), CMakeLists.txt | `lrt-rocm:the-rock` (for context) | test output |
| **Submodule coordination** | `directory-map.md`, `.gitmodules` | `rk.py` for topic/branch management | build output |

## Project Context

### What is ROCm?
ROCm is AMD's open-source platform for GPU computing. It includes:
- HIP (Heterogeneous-Interface for Portability) - CUDA alternative
- ROCm runtime and drivers
- Math libraries (rocBLAS, rocFFT, etc.)
- Developer tools and compilers

### Build Infrastructure Focus
As a build infra team member, typical work involves:
- CMake build system configuration
- CI/CD pipeline maintenance
- Build dependency management
- Cross-platform build support
- Build performance optimization
- Package generation and distribution

## Naming Conventions

Use these patterns so files are findable without searching:

| File type | Pattern | Example |
|---|---|---|
| Task files | `tasks/active/<name>.md` | `tasks/active/fix-hip-linking.md` |
| Completed tasks | `tasks/completed/<name>.md` | `tasks/completed/fix-hip-linking.md` |
| Plans | `docs/lrt/plans/YYYY-MM-DD-<name>.md` | `docs/lrt/plans/2026-05-08-kpack-integration.md` |
| Design docs | `docs/<name>.md` | `docs/hip-test-harness-design.md` |
| Build logs | `logs/YYYY-MM-DD-<build-type>.log` | `logs/2026-05-08-therock-full.log` |
| Patches | `patches/<component>-<description>.patch` | `patches/clr-fix-memcpy-alignment.patch` |

## Conventions

### Build System
- TheRock is a super-project. The builds under the submodules (like rocm-systems) are sub-projects
- Since dependency management is handled by the super-project, refer to those build rules
- For example, in the case of ROCR-Runtime and clr, see the `core/CMakeLists.txt` file
- This is documented in docs/development/build_system.md
- Git submodules are used extensively
- When editing build configs, check both source tree and build tree caches

### Git Workflow

#### Branch Naming
Use the pattern: `users/<username>/<short-description>`

#### Commit Messages
- First line: Short summary (50-72 chars)
- Blank line after summary
- Detailed description explaining what and why
- Include "Changes:" section with bullet points for key modifications

#### Review Workflow

We work in commit stacks. Claude commits incrementally with WIP commits, user reviews, we iterate, then squash to PR at milestones.

| Mode | When | Diff |
|------|------|------|
| **Incremental** | After each Claude batch | HEAD~1..HEAD |
| **Milestone** | Before PR/squash | main..HEAD |

#### Review Comment Format

Add comments inline using `RVW:` or `RVWY:` prefix:

| Marker | Meaning |
|--------|---------|
| `RVW:` | Discuss - Claude proposes fix, waits for confirmation |
| `RVWY:` | YOLO - Claude makes the fix without asking |

Then run `/lrt-rocm:process-review` to address them.

### Design Documentation
- When writing design docs, always include an "Alternatives Considered" section
- Don't include nit-picky differences, just major architectural alternatives

## Reference

- [ROCm Documentation](https://rocm.docs.amd.com/)
- [TheRock repository](https://github.com/ROCm/TheRock)
- Adding Third-Party Dependencies — see `docs/adding-third-party-dep.md` in the lrt-rocm plugin

## Notes

<!-- Add your ongoing notes, discoveries, and context here as you work -->
