---
name: pal-rocr-windows-build
description: Use when building CLR (HIP/OCL) with PAL and/or ROCr backends on Windows using rocm-systems — covers prerequisites, CMake flags, build configurations, and troubleshooting for d3dumddi.h and Clang discovery issues
---

# PAL + ROCr Windows Build Guide

Build guide for CLR (Compute Language Runtime) with PAL and/or ROCr backends on Windows using the rocm-systems monorepo.

> **Scope:** This skill covers Windows-only PAL/ROCr developer builds via rocm-systems. For general HIP/OCL builds, use `lrt-rocm:the-rock`. For Linux monorepo builds, use `lrt-rocm:hip-ocl-monorepo-build`.

## Required Repository Layout

The following are **not** included in a default `rocm-systems` clone and must be added manually before configuring:

```
rocm-systems/
  projects/
    clr/
    hip/
    rocr-runtime/   ← must be added to projects/
  shared/
    amdgpu-windows-interop/   ← must be added to shared/
      sc/
      hsail-compiler/
      pal/
        lib/Release/x64/      ← *.lib.dvc files, requires DVC pull (see Prerequisites)
```

> `AMD_COMPUTE_WIN` points to `amdgpu-windows-interop/` and triggers ROCr being built statically from `rocr-runtime` source. Both must be present before configuring.

## When to Use

- Building CLR with PAL and/or ROCr backends on Windows
- Configuring `ROCCLR_ENABLE_HSA`, `ROCCLR_ENABLE_PAL`, or related CMake flags
- Encountering WDK (`d3dumddi.h`) or Clang path issues during a Windows ROCm build
- Working with `rocm-systems/projects/clr` CMake targets on Windows

## Build Configurations

| # | Configuration | Description | Status |
|---|--------------|-------------|--------|
| 1 | Static PAL + ROCr | Pre-built PAL and ROCr libraries linked statically | Available |
| 2 | ROCr Backend Only | ROCr (HSA) enabled, PAL disabled | Available |

> Start with **Configuration 2 (ROCr Backend Only)** — it is the simplest working setup.

## Prerequisites

```bat
:: Visual Studio 2022 Build Tools with required components
winget install --id Microsoft.VisualStudio.2022.BuildTools --source winget --override "--add Microsoft.VisualStudio.Component.VC.Tools.x86.x64 --add Microsoft.VisualStudio.Component.VC.CMake.Project --add Microsoft.VisualStudio.Component.VC.ATL --add Microsoft.VisualStudio.Component.Windows11SDK.22621"

:: Git with command-line tools
winget install --id Git.Git -e --source winget --custom "/o:PathOption=CmdTools"

:: Build tools (CMake must be < 4.0.0)
winget install cmake -v 3.31.0
winget install ninja-build.ninja ccache python strawberryperl bloodrock.pkg-config-lite
winget install --id Iterative.DVC --silent --accept-source-agreements

:: Python packages
pip install Jinja2 ruamel.yaml
```

Additionally install:
- **WDK 28000** — Windows Driver Kit (provides `d3dumddi.h` and other driver headers)
- **SDK 28000** — Windows SDK
- **TheRock package** — Install via TheRock's artifact script:
  ```bash
  python TheRock/build_tools/install_rocm_from_artifacts.py --run-id <run_id> --amdgpu-family <family>
  ```
- **DVC** — Required to pull PAL pre-built libs (stored as DVC pointers in `amdgpu-windows-interop`):
  ```bat
  pip install "dvc[s3]"
  cd C:\code\rocm-systems
  dvc pull
  ```
  The DVC remote (`s3://therock-dvc/rocm-systems`) allows anonymous access — no credentials needed. Run this before the first build and after updating `amdgpu-windows-interop`.

> **Note:** Install Python for the current user to a path **without spaces**.

## Environment Setup

Run in **Command Prompt** (not PowerShell):

```bat
set HIP_COMMON_DIR=c:/github/rocm-systems/projects/hip
set HIPCC_BIN_DIR=c:\opt\rocm\bin
set CMAKE_BUILD_PARALLEL_LEVEL=64
:: Note: TheRock's LLVM is under lib\llvm\bin, not llvm\bin
set PATH=C:\Program Files\CMake\bin;c:\opt\rocm\lib\llvm\bin

mkdir build
cd build
```

## CMake Flags Reference

| Flag | Purpose | Default |
|------|---------|---------|
| `CLR_BUILD_HIP` | Build HIP runtime | `ON` |
| `CLR_BUILD_OCL` | Build OpenCL runtime | `ON` |
| `ROCCLR_ENABLE_HSA` | Enable ROCr (HSA) backend | `ON` |
| `ROCCLR_ENABLE_PAL` | Enable PAL backend | `ON` or `OFF` |
| `ROCR_DLL_LOAD` | ROCr DLL loading behavior | `OFF` |
| `__HIP_ENABLE_PCH` | Precompiled headers for HIP | `OFF` |
| `__HIP_ENABLE_RTC` | Runtime compilation for HIP | `ON` |
| `USE_PROF_API` | Profiling API support | `OFF` |
| `AMD_COMPUTE_WIN` | Path to AMDGPU Windows interop dir | Relative path |
| `BUILD_TESTS` | Build test targets | `ON` |
| `OPENCL_ICD_LIB` | Build OpenCL ICD loader library | `ON` |

## Build Commands

### ROCr Backend Only — HIP (Release)

```bat
cmake ../rocm-systems/projects/clr ^
  -DCMAKE_BUILD_TYPE=Release ^
  -DCLR_BUILD_HIP=ON ^
  -DHIP_COMMON_DIR=%HIP_COMMON_DIR% ^
  -DHIPCC_BIN_DIR=%HIPCC_BIN_DIR% ^
  -DCMAKE_INSTALL_PREFIX=..\install ^
  -D__HIP_ENABLE_PCH=OFF ^
  -DROCCLR_ENABLE_HSA=ON ^
  -DROCCLR_ENABLE_PAL=OFF ^
  -D__HIP_ENABLE_RTC=ON ^
  -DUSE_PROF_API=OFF ^
  -DROCR_DLL_LOAD=OFF ^
  -DAMD_COMPUTE_WIN=../../../shared/amdgpu-windows-interop/
```

### ROCr Backend Only — OCL (Debug with Tests)

```bat
cmake ../rocm-systems/projects/clr ^
  -DCMAKE_BUILD_TYPE=Debug ^
  -DCLR_BUILD_OCL=ON ^
  -DCMAKE_INSTALL_PREFIX=..\install ^
  -DROCCLR_ENABLE_HSA=ON ^
  -DROCCLR_ENABLE_PAL=OFF ^
  -DROCR_DLL_LOAD=OFF ^
  -DAMD_COMPUTE_WIN=../../../shared/amdgpu-windows-interop/ ^
  -DBUILD_TESTS=ON ^
  -DOPENCL_ICD_LIB=ON
```

### Build and Install

```bat
cmake --build . --config Release -j 6 --target install
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `'d3dumddi.h': No such file or directory` | Install WDK 28000 with all required components |
| `Could not find ClangConfig.cmake / clang-config.cmake` | Add `lib\llvm\bin` to PATH **before** running cmake: `set PATH=C:\Program Files\CMake\bin;c:\opt\rocm\lib\llvm\bin` |
| Clang not found despite `CMAKE_PREFIX_PATH` | `CMAKE_PREFIX_PATH` does not work for Clang — must be on `PATH` before cmake configure runs; TheRock's LLVM is at `lib\llvm\bin`, not `llvm\bin` |
| `LNK1181: cannot open pal.lib` | PAL `.lib` files are DVC pointers — run `dvc pull` from `rocm-systems/` root |

## Known Limitations

1. Clang must be on `PATH` before cmake configure runs — `CMAKE_PREFIX_PATH` does not work.
2. TheRock's LLVM is at `lib\llvm\bin\`, not `llvm\bin\` — ensure PATH uses the correct subdirectory.
3. PAL `.lib` files are DVC pointers — `dvc pull` must be run before the first build and after updating `amdgpu-windows-interop`.
4. `rocr-runtime` and `amdgpu-windows-interop` must be manually added to `rocm-systems/projects/` and `rocm-systems/shared/` respectively — they are not included in a default clone.
5. These build configurations are not yet enabled in TheRock (rocm-systems only).
6. Users can switch between PAL and ROCr backends at runtime via an environment variable.
