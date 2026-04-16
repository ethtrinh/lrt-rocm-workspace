# ROCm Directory Map

This document maps out where all ROCm-related directories live on this system.
It is auto-populated by `/lrt-rocm:setup` or can be edited manually.

## Environment

| Setting | Value |
|---------|-------|
| OS | |

## Repository Aliases

These aliases are used by `/lrt-rocm:stage-review` and other commands to resolve short names to paths.

| Alias | Path | Notes |
|-------|------|-------|
| therock | | Main ROCm build repo (builds in-tree) |
| workspace | | This meta-workspace |

<!-- Uncomment below if you also work with rocm-systems directly -->
<!-- | rocm-systems | | ROCm Systems Superrepo (submodule) | -->
<!-- | rocm-libraries | | ROCm Libraries Superrepo (submodule) | -->
<!-- | rocm-kpack | | Kernel packaging tools (submodule) | -->

<!-- Uncomment below if you use rocm-systems build directories -->
<!--
## Build Trees

### Active Builds
- **CLR build:** `projects/clr/build`
  - For: HIP and OCL runtime builds
  - Configuration: Release
  - Target architecture: []
  - Built ROCm installation is under `dist/rocm`
- **hip-tests build:** `projects/hip-tests/build`
  - For: HIP unit tests and stress tests
  - Configuration: Debug
  - Target architecture: []
-->
