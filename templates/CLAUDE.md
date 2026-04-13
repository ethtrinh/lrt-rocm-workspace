# ROCm Build Infrastructure Project

## Overview

This workspace is for build infrastructure work on ROCm (Radeon Open Compute) via the TheRock repository and related projects.

Project repository: https://github.com/ROCm/TheRock

## Working Environment

**Important:** See `directory-map.md` for all directory locations.

This is a meta-workspace. Actual source and build directories are scattered across the filesystem and referenced by absolute paths.

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

## Common Tasks

### Building
- Builds typically happen in separate build trees (see directory-map.md)
- Out-of-tree builds are standard practice
- Multiple build configurations (Release, Debug, RelWithDebInfo) often maintained simultaneously

How we build depends on what kind of task we are doing:

#### Developing Build Infra

Good for making changes to the build infra when we aren't expecting to need to do C++ debugging.

1. CMake configure (update paths from your directory-map.md):

```
cmake -B <build-dir> -S <therock-dir> -GNinja -DTHEROCK_AMDGPU_FAMILIES=<your-gpu-family> \
  -DCMAKE_C_COMPILER_LAUNCHER=ccache \
  -DCMAKE_CXX_COMPILER_LAUNCHER=ccache
```

2. Build entire project (very time consuming)

```
cd <build-dir> && ninja
```

#### Working on specific components

Often we have to work on specific subsets of ROCm. We do this with -DTHEROCK_ENABLE_* flags as described in TheRock/README.md. Once the project is configured for the proper subset, it is typical to iterate by expunging and rebuilding a specific named project. Example:

```
cd <build-dir>
ninja clr+expunge && ninja clr+dist
```

### Source Navigation
- Source code is across multiple repositories and worktrees
- Git submodules are used extensively
- When editing build configs, check both source tree CMakeLists.txt and build tree caches

### Testing
- Unit tests, integration tests, and packaging tests
- Tests may run on different GPU architectures (gfx906, gfx908, gfx90a, etc.)

## Conventions & Gotchas

### Python Coding Standards

**When writing Python code, follow the [Python Style Guide](PYTHON-STYLE-GUIDE.md).**

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

Key commands:
- `/lrt-rocm:stage-review [repo]` - Stage changes and open in VSCode
- `/lrt-rocm:vscode-diff [repo] [N]` - Open diffs in VSCode
- `/lrt-rocm:process-review [repo]` - Find and fix RVW comments
- `/lrt-rocm:prep-pr [repo]` - Full milestone review before PR

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
- [Adding Third-Party Dependencies](adding-third-party-dep.md)

## Notes

<!-- Add your ongoing notes, discoveries, and context here as you work -->
