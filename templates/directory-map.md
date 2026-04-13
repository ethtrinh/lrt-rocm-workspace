# ROCm Directory Map

This document maps out where all ROCm-related directories live on this system.
It is auto-populated by `/lrt-rocm:setup` or can be edited manually.

## Repository Aliases

These aliases are used by `/lrt-rocm:stage-review` and other commands to resolve short names to paths.

| Alias | Path | Notes |
|-------|------|-------|
| therock | | Main ROCm build repo |
| rocm-systems | | ROCm Systems Superrepo (submodule) |
| rocm-libraries | | ROCm Libraries Superrepo (submodule) |
| rocm-kpack | | Kernel packaging tools (submodule) |
| workspace | | This meta-workspace |

## Build Trees

### Active Builds
- **Main build:** ``
  - Configuration: Release
  - Target architecture: []
  - CMake flags:
  - Built ROCm installation is under `dist/rocm`
