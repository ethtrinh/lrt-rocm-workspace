---
name: hip-ocl-monorepo-build
description: Use when building ROCr, HIP, or OCL from the ROCm rocm-systems monorepo, creating branches/PRs, running tests, or troubleshooting CMake/build errors
---

# HIP/OCL Monorepo Build Guide

Build instructions for the ROCm rocm-systems monorepo covering ROCr runtime, HIP (AMD), OpenCL (OCL), testing, branching, CI, and common troubleshooting steps.

## When to Use This Skill

Use this skill when you need to:

- **Build ROCr runtime** from the `rocm-systems` monorepo
- **Build HIP on AMD** using the CLR (Common Language Runtime) directory structure
- **Build OpenCL (OCL)** from the monorepo
- **Build and run HIP tests** (unit tests and stress tests) against a locally built HIP
- **Create a feature branch and open a pull request** in the `rocm-systems` repo
- **Trigger CI pipelines** (Azure Pipelines / PSDB jobs) on a PR
- **Rebase your development branch** onto `develop`
- **Troubleshoot CMake or build errors** (missing LLVM, missing CppHeaderParser, etc.)

### Trigger Conditions

| Situation | This skill applies |
|---|---|
| User asks how to build HIP, ROCr, or OCL | Yes |
| User hits a CMake error mentioning LLVM or CppHeaderParser | Yes |
| User wants to run `hip-tests` catch tests or stress tests | Yes |
| User asks about branch naming or PR workflow for rocm-systems | Yes |
| User needs to trigger CI on a PR | Yes |
| User asks about general ROCm installation or package management | No — use ROCm install docs instead |

## Key Concepts

- **rocm-systems**: The monorepo that hosts ROCr, HIP, CLR, and OCL source code. All contributions follow the guidelines in `rocm-systems/CONTRIBUTING.md` on the `develop` branch.
- **CLR (Common Language Runtime)**: The directory containing shared runtime code. HIP and OCL builds both live under CLR, controlled by `-DCLR_BUILD_HIP` and `-DCLR_BUILD_OCL` CMake flags.
- **HIP_DIR / CLR_DIR / HIPTESTS_DIR**: Environment variables pointing to the `hip`, `clr`, and `hip-tests` source directories respectively.
- **ROCM_PATH**: Typically `/opt/rocm`. Used by CMake and the test harness to locate ROCm toolchain components.
- **offload-arch**: GPU target architecture string (e.g., `gfx1201`). Passed via `-DOFFLOAD_ARCH_STR` when building tests.

## GPU Architecture Selection

Before running any hip-tests build (unit tests in section 4 or stress tests in section 5), you MUST determine the user's target GPU architecture. Follow this process:

### Step 1: Check Memory

Check the Claude Code memory system for these two keys:

- `gpu_arch_prompt_enabled` — if `false`, skip to "Prompt Disabled" below. If `true` or not found, continue to Step 2.
- `gpu_arch_default` — the previously saved architecture string.

### Step 2: Prompt the User (when enabled)

Present the following architectures using `AskUserQuestion`:

| Architecture | Generation |
|---|---|
| `gfx906` | Vega 20 (MI50/MI60) |
| `gfx908` | CDNA (MI100) |
| `gfx90a` | CDNA 2 (MI200) |
| `gfx1101` | RDNA 3 |
| `gfx1201` | RDNA 4 |

After the user selects, save the choice to memory as `gpu_arch_default` and use it in the `-DOFFLOAD_ARCH_STR="--offload-arch=<selected>"` flag in the build commands below.

### Prompt Disabled

When `gpu_arch_prompt_enabled` is `false`:

1. Read `gpu_arch_default` from memory (fall back to `gfx1101` if not set).
2. Print: **"Using default GPU architecture: `<arch>`. Say 'change GPU arch' to update."**
3. Use that architecture in the build commands.

### Toggling the Prompt

- If the user says **"stop asking about GPU arch"** or **"disable GPU arch prompt"**: save `gpu_arch_prompt_enabled: false` and `gpu_arch_default: <current selection>` to memory.
- If the user says **"change GPU arch"** or **"enable GPU arch prompt"**: save `gpu_arch_prompt_enabled: true` to memory and prompt them to select an architecture.

## Quick Reference

### 1. Build ROCr Runtime

```bash
cd rocr-runtime/build
cmake .. -DCMAKE_PREFIX_PATH=/opt/rocm -DCMAKE_INSTALL_PREFIX=$PWD/install
make -j$(nproc)
make -j$(nproc) install
```

### 2. Build HIP on AMD

Set up environment variables first, then configure and build via CLR:

```bash
export HIP_DIR="$(readlink -f hip)"
export CLR_DIR="$(readlink -f clr)"
export HIPTESTS_DIR="$(readlink -f hip-tests)"
export ROCM_PATH=/opt/rocm

cd "$CLR_DIR"
mkdir -p build; cd build
cmake \
  -DHIP_COMMON_DIR=$HIP_DIR \
  -DCMAKE_PREFIX_PATH="/opt/rocm/" \
  -DCMAKE_INSTALL_PREFIX=$PWD/install \
  -DCLR_BUILD_HIP=ON \
  -DCLR_BUILD_OCL=OFF \
  -DHIP_PLATFORM=amd \
  -DCMAKE_BUILD_TYPE=Debug \
  ..
make -j$(nproc)
make install
```

### 3. Build OCL (OpenCL)

```bash
cd "$CLR_DIR"
mkdir -p build; cd build
cmake \
  -DCMAKE_PREFIX_PATH="/opt/rocm/" \
  -DCLR_BUILD_HIP=OFF \
  -DCLR_BUILD_OCL=ON \
  -DBUILD_TESTS=ON \
  ..
make -j$(nproc)
```

> **Note:** HIP and OCL builds are mutually exclusive via the `CLR_BUILD_HIP` / `CLR_BUILD_OCL` flags. Build them in separate build directories if you need both.

### 4. Build and Run HIP Unit Tests

```bash
cd "$HIPTESTS_DIR"
mkdir -p build; cd build
export ROCM_PATH=/opt/rocm
cmake ../catch \
  -DHIP_PLATFORM=amd \
  -DCMAKE_PREFIX_PATH=$CLR_DIR/build/install \
  -DCMAKE_BUILD_TYPE=Debug \
  -DCMAKE_CXX_COMPILER=amdclang++ \
  -DCMAKE_C_COMPILER=amdclang \
  -DCMAKE_HIP_COMPILER=amdclang++ \
  -DOFFLOAD_ARCH_STR="--offload-arch=<selected-gpu-arch>"  # see GPU Architecture Selection above
make build_tests -j$(nproc)
```

### 5. Build and Run HIP Stress Tests

```bash
cd "$HIPTESTS_DIR"
mkdir -p build; cd build
export ROCM_PATH=/opt/rocm
cmake ../catch \
  -DHIP_PLATFORM=amd \
  -DCMAKE_PREFIX_PATH=$CLR_DIR/build/install \
  -DCMAKE_BUILD_TYPE=Debug \
  -DCMAKE_CXX_COMPILER=amdclang++ \
  -DCMAKE_C_COMPILER=amdclang \
  -DCMAKE_HIP_COMPILER=amdclang++ \
  -DOFFLOAD_ARCH_STR="--offload-arch=<selected-gpu-arch>" \  # see GPU Architecture Selection above
  -DBUILD_STRESS_TESTS=ON
make stress_test -j$(nproc)
```

### 6. Create a Branch and Open a PR

Branch naming convention:

```
users/<github-username>/<branch-name>
```

```bash
# Create your feature branch
git checkout -b users/<github-username>/<branch-name>

# Push to remote
git push origin users/<github-username>/<branch-name>
```

Then open a PR via the GitHub UI or CLI.

### 7. Trigger CI on a PR

Post this as a **PR comment** to trigger the PSDB job:

```
/AzurePipelines run rocm-ci-caller
```

### 8. Rebase onto develop

```bash
git checkout <dev_branch>
git remote update
git merge origin/develop
```

## Troubleshooting

### CMake cannot find LLVM (`LLVMConfig.cmake` / `llvm-config.cmake`)

**Error:**

```
CMake Error at hipamd/src/CMakeLists.txt:185 (find_package):
  Could not find a package configuration file provided by "LLVM" with any of
  the following names:
    LLVMConfig.cmake
    llvm-config.cmake
```

**Fix:** Install the ROCm LLVM development package. Run this every time you change your ROCm installation:

```bash
sudo apt install rocm-llvm-dev
```

### Missing CppHeaderParser Python module

**Error:**

```
ModuleNotFoundError: No module named 'CppHeaderParser'
CMake Error at hipamd/src/CMakeLists.txt:227 (message):
  The "CppHeaderParser" Python3 package is not installed.
```

**Fix:**

```bash
sudo apt install python3 python3-pip
pip3 install --break-system-packages CppHeaderParser
```

## Workflow Summary

```
┌─────────────────────────────────────────────────────────┐
│  1. Configure GitHub settings (see repo CONTRIBUTING.md)│
│  2. Build ROCr runtime                                  │
│  3. Build HIP (AMD) via CLR                             │
│  4. Build & run hip-tests (unit and/or stress)          │
│  5. Create branch: users/<username>/<feature>           │
│  6. Push & open PR                                      │
│  7. Trigger CI: /AzurePipelines run rocm-ci-caller      │
│  8. Rebase onto develop as needed                       │
└─────────────────────────────────────────────────────────┘
```

## Working with This Skill

### Beginners

1. Start by reading the `rocm-systems/CONTRIBUTING.md` on the `develop` branch for repo guidelines and GitHub config settings.
2. Follow the build steps in order: ROCr first, then HIP, then tests.
3. Make sure `/opt/rocm` is installed and `ROCM_PATH` is set before building.
4. If you hit CMake errors, check the [Troubleshooting](#troubleshooting) section first.

### Intermediate

- Use separate build directories for HIP and OCL builds (they are mutually exclusive via CMake flags).
- Adjust `-DOFFLOAD_ARCH_STR` to match your GPU architecture (e.g., `gfx906`, `gfx908`, `gfx90a`, `gfx1201`).
- Run stress tests (`-DBUILD_STRESS_TESTS=ON`) to validate stability under load.

### Advanced

- Integrate with local CI by using the `/AzurePipelines run rocm-ci-caller` trigger.
- When debugging build failures, check that `rocm-llvm-dev` matches your ROCm version — mismatches between ROCm packages and LLVM headers are a common source of `find_package(LLVM)` failures.
- For OCL-specific test builds, pass `-DBUILD_TESTS=ON` in the OCL cmake invocation.

## Reference Files

| File | Description | Source | Confidence |
|---|---|---|---|
| `references/ocl-monorepo-build.md` | Full build instructions for ROCr, HIP, OCL, testing, branching, CI, and troubleshooting | PDF (3 pages) | Medium |
| `references/index.md` | Documentation index and statistics | Generated index | Medium |

## Documentation Statistics

- **Total Pages**: 3
- **Code Blocks**: 10+ (extracted and formatted above)
- **Images/Diagrams**: 2 (in source PDF)
- **Key Topics**: ROCr build, HIP build, OCL build, unit tests, stress tests, branching, CI, troubleshooting

---

*Enhanced from PDF documentation source. See `references/` for raw reference material.*
