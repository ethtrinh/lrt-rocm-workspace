---
name: lrt-build-routing
description: Use to decide whether LRT runtime work should build through TheRock, rocm-systems/CLR, test builds, or an installed ROCm tree.
---

Route LRT runtime build work deliberately. LRT covers HIP and OpenCL runtime work.

## Required inputs

Read `directory-map.md` first and identify:

- Source checkout involved.
- Build tree involved.
- ROCm install tree used for tests.
- Target GPU architecture.
- Whether the task affects HIP, OpenCL, ROCr interaction, packaging, or shared build infrastructure.

## Routing

- Use `lrt-rocm:the-rock` for the default HIP/OpenCL build path and super-project integration.
- Use `lrt-rocm:hip-ocl-monorepo-build` when the user explicitly needs rocm-systems/CLR monorepo workflows.
- Use runtime test builds when adding or running HIP/OpenCL API tests.
- Use an installed ROCm tree only for reproduction or validation when source rebuilds are not needed.
- Escalate to build-infra review when CMake, Meson, pkg-config, packaging, install/export rules, or cross-component dependencies are affected.

## Rules

- Split work into independently testable tasks before choosing build commands.
- Each task must have a targeted build/test command or a clear reason why no build is required.
- Prefer incremental component builds.
- Ask before full ROCm builds or shared GPU jobs.
- Print exact commands before running them unless the user already provided the command.
- Capture command, working directory, environment, and result per task.
