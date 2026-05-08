# ROCm Development Conventions

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

## Build System

- TheRock is a super-project. The builds under the submodules (like rocm-systems) are sub-projects
- Since dependency management is handled by the super-project, refer to those build rules
- For example, in the case of ROCR-Runtime and clr, see the `core/CMakeLists.txt` file
- This is documented in docs/development/build_system.md
- Git submodules are used extensively
- When editing build configs, check both source tree and build tree caches

## Git Workflow

### Branch Naming
Use the pattern: `users/<username>/<short-description>`

### Commit Messages
- First line: Short summary (50-72 chars)
- Blank line after summary
- Detailed description explaining what and why
- Include "Changes:" section with bullet points for key modifications

### Review Workflow

We work in commit stacks. Claude commits incrementally with WIP commits, user reviews, we iterate, then squash to PR at milestones.

| Mode | When | Diff |
|------|------|------|
| **Incremental** | After each Claude batch | HEAD~1..HEAD |
| **Milestone** | Before PR/squash | main..HEAD |

### Review Comment Format

Add comments inline using `RVW:` or `RVWY:` prefix:

| Marker | Meaning |
|--------|---------|
| `RVW:` | Discuss - Claude proposes fix, waits for confirmation |
| `RVWY:` | YOLO - Claude makes the fix without asking |

Then run `/lrt-rocm:process-review` to address them.

## Design Documentation

- When writing design docs, always include an "Alternatives Considered" section
- Don't include nit-picky differences, just major architectural alternatives

## Reference

- [ROCm Documentation](https://rocm.docs.amd.com/)
- [TheRock repository](https://github.com/ROCm/TheRock)
- Adding Third-Party Dependencies — see `docs/adding-third-party-dep.md`
