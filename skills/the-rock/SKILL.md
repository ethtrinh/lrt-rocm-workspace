---
name: the-rock
description: Use when building TheRock (ROCm) from source — covers Ubuntu/Windows dependency setup, Python venv, submodule management with DVC, full/optimized HIP/OCL build configurations, incremental rebuilds, test execution, nightly containers, and artifact downloads
---

# TheRock Build Guide

Build guide for **TheRock** — the ROCm open-source GPU compute stack build system. Covers end-to-end setup from dependencies through full builds and incremental rebuilds, with special focus on HIP/OCL optimized build configurations.

> **This is the default build skill.** When a user asks to build HIP, OCL, hip-tests, or OCL tests, always use this skill unless they explicitly request the rocm-systems monorepo approach (`lrt-rocm:hip-ocl-monorepo-build`).

## When to Use This Skill

Use this skill when you need to:

- **Set up a fresh TheRock build environment** on Linux or Windows
- **Choose between full and optimized build configurations**
- **Build HIP or OpenCL** from source
- **Run HIP or OCL tests**
- **Rebuild individual components** (e.g., HIP/hip-test) after making source changes
- **Use nightly Rock containers** or **download artifacts** from existing builds
- **Troubleshoot TheRock build issues**

### Trigger Conditions

You should invoke this skill when:
- The user mentions "TheRock" or building ROCm from source
- The user is setting up a ROCm development environment on Linux or Windows
- The user asks about HIP/OCL build flags or optimized build configurations
- The user needs to rebuild HIP or hip-test after source modifications
- The user asks about Rock nightly containers or downloading build artifacts

## OS Detection

Before following any build steps, read the **OS** field from `directory-map.md` (under the **Environment** table). This determines which dependency installation to use in Step 1:

- **linux** — Use `apt` to install dependencies
- **windows** — Use `winget` to install dependencies

If `directory-map.md` has no OS set, ask the user or run `uname -s` to detect it.

---

## Setup

### Setup — Linux (Ubuntu 24.04)

#### Step 1: Install Dependencies

```bash
sudo apt update
sudo apt install gfortran git ninja-build cmake g++ pkg-config xxd patchelf automake libtool python3-venv python3-dev libegl1-mesa-dev texinfo bison flex
```

> **Tip:** `dvc` is used for version control of pre-compiled MIOpen kernels. Not a hard requirement, but reduces compile time. Install with `snap install --classic dvc` or via pip in a venv.

#### Step 2: Clone the Repository

```bash
git clone https://github.com/ROCm/TheRock.git
cd TheRock
```

#### Step 3: Python Virtual Environment

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

#### Step 4: Download Submodules and Apply Patches

```bash
# Full sources (all components)
python3 ./build_tools/fetch_sources.py

# Optimized sources for HIP/OCL build only (faster, smaller)
python3 ./build_tools/fetch_sources.py --no-include-debug-tools --no-include-rocm-libraries --no-include-ml-frameworks --no-include-media-libs --no-include-iree-libs --no-include-math-libraries
```

### Setup — Windows 11 (VS 2022)

#### System Requirements

- 16GB+ RAM, 8+ CPU cores, 200GB+ storage
- A Dev Drive is recommended for build performance
- **Long path support required** — enable via registry (requires admin, reboot):
  ```
  reg add HKLM\SYSTEM\CurrentControlSet\Control\FileSystem /v LongPathsEnabled /t REG_DWORD /d 1 /f
  ```
- **Symlink support recommended** — enable Developer Mode and/or grant "Create symbolic links" permission
- Uninstall any preexisting HIP SDK / ROCm installs to avoid build conflicts

#### Step 1: Install Tools

Run in a command prompt with admin privileges:

```cmd
winget install --id Microsoft.VisualStudio.2022.BuildTools --source winget --override "--add Microsoft.VisualStudio.Component.VC.Tools.x86.x64 --add Microsoft.VisualStudio.Component.VC.CMake.Project --add Microsoft.VisualStudio.Component.VC.ATL --add Microsoft.VisualStudio.Component.Windows11SDK.22621"
winget install --id Git.Git -e --source winget --custom "/o:PathOption=CmdTools"
winget install cmake -v 3.31.0
winget install ninja-build.ninja ccache python strawberryperl bloodrock.pkg-config-lite
winget install --id Iterative.DVC --silent --accept-source-agreements
```

> **Important:** CMake must be < 4.0.0 on Windows. Install Python for the current user to a path **without spaces**.

#### Step 2: Configure Git

```bash
git config --global core.symlinks true
git config --global core.longpaths true
```

#### Step 3: Clone the Repository

Open **x64 Native Tools Command Prompt for VS 2022**, then:

```bash
git clone https://github.com/ROCm/TheRock.git
cd TheRock
chcp 65001  # Required for non-English systems
```

#### Step 4: Python Virtual Environment

```bash
python -m venv .venv
.venv\Scripts\Activate.bat
pip install --upgrade pip
pip install -r requirements.txt
```

#### Step 5: Download Submodules and Apply Patches

```bash
python ./build_tools/fetch_sources.py
```

> **Note:** DVC is used for pulling large files. If DVC is not installed, you will see errors during this step.

#### Validate Environment (Optional)

```powershell
.\build_tools\validate_windows_install.ps1
```

Checks RAM, disk space, long path support, symlink capability, MSVC, CMake, Ninja, Git, Python, DVC, Strawberry Perl/gfortran, ccache, and git configuration.

---

## Building HIP (Windows and Linux)

HIP binaries install at `TheRock/build/core/clr/stage`. hip-tests binaries install at `TheRock/build/core/hip-tests/stage`. Rock installs all dependent packages in the stage folder.

### Initial Build

```bash
cmake -B build -GNinja . -DTHEROCK_ENABLE_ALL=OFF -DTHEROCK_ENABLE_HIP_RUNTIME=ON -DTHEROCK_AMDGPU_TARGETS="gfx1201" -DTHEROCK_BUILD_TESTING=ON -DTHEROCK_DIST_AMDGPU_FAMILIES="gfx1201"
cmake --build build --target therock-archives therock-dist -- -k 0
```

> **Note:** Replace `gfx1201` with your target GPU architecture.

### Incremental Rebuilds (After Source Changes)

```bash
# Rebuild hip-runtime only
cmake --build build --target hip-clr

# Rebuild hip-test only
cmake --build build --target core/hip-tests
```

---

## Executing HIP Tests

```bash
# If using artifacts from a ROCK build
export THEROCK_BIN_DIR=/path/to/TheRock/therock-build/bin                # Linux
# set THEROCK_BIN_DIR=C:\path\to\TheRock\therock-build\bin               # Windows

# If using binaries from a local build
export THEROCK_BIN_DIR=/path/to/TheRock/build/core/hip-tests/dist/bin    # Linux
# set THEROCK_BIN_DIR=C:\path\to\TheRock\build\core\hip-tests\dist\bin   # Windows

cd TheRock
python build_tools/github_actions/test_executable_scripts/test_hiptests.py
```

---

## Building OpenCL (Windows and Linux)

OpenCL binaries install at `TheRock/build/core/ocl-clr/stage`. Rock installs all dependent packages in the stage folder.

### Initial Build

```bash
cmake -B build -GNinja . -DTHEROCK_ENABLE_ALL=OFF -DTHEROCK_ENABLE_OCL_RUNTIME=ON -DTHEROCK_DIST_AMDGPU_FAMILIES="gfx950" -DTHEROCK_BUILD_TESTING=ON
cmake --build build --target therock-archives therock-dist -- -k 0
```

> **Note:** Replace `gfx950` with your target GPU architecture.

---

## Executing OCL Tests (ocltst)

```bash
# If using artifacts from a ROCK build
export THEROCK_BIN_DIR=/path/to/TheRock/therock-build/bin                # Linux
# set THEROCK_BIN_DIR=C:\path\to\TheRock\therock-build\bin               # Windows

# If using binaries from a local build
export THEROCK_BIN_DIR=/path/to/TheRock/build/core/ocl-clr/dist/bin      # Linux
# set THEROCK_BIN_DIR=C:\path\to\TheRock\build\core\ocl-clr\dist\bin     # Windows

cd TheRock
python build_tools/github_actions/test_executable_scripts/test_ocltst.py
```

---

## Nightly Rock Container

Rock replaces the legacy `rocm-ci` docker images. Nightly images are available from the harbor registry.

### Image Format

```
registry-sc-harbor.amd.com/rocm-nightly/rocm-runtime:<distro>-<gpu>-dcgpu-<version>
```

Replace the version suffix (e.g., `7.12.0a20260217`) with the specific nightly build date you need. The date portion (e.g., `20260217`) corresponds to the build date.

### Example

```bash
# Pull and run a nightly container
docker run -it --network=host --ipc=host \
  --device=/dev/kfd --device=/dev/dri \
  --group-add video --cap-add=SYS_PTRACE \
  --security-opt seccomp=unconfined \
  -v /home/$USER/workspace:/dockerx \
  registry-sc-harbor.amd.com/rocm-nightly/rocm-runtime:ubuntu24.04-gfx950-dcgpu-7.12.0a20260310
```

### Additional Packages for HIP/OCL on Nightly Container

The nightly container needs extra packages for building HIP/OCL:

```bash
sudo apt update
apt install sudo cmake libopengl-dev libglx-dev libglu1-mesa-dev freeglut3-dev mesa-utils ocl-icd-libopencl1 ocl-icd-opencl-dev pkg-config xxd -y
```

---

## Download Artifacts from Existing Builds

### From Main ROCK Builds

```bash
python build_tools/install_rocm_from_artifacts.py --run-id <run_id> --amdgpu-family gfx94X-dcgpu --tests
```

### From rocm-systems Builds Through ROCK

```bash
python build_tools/install_rocm_from_artifacts.py --run-id <run_id> --amdgpu-family gfx94X-dcgpu --tests --run-github-repo ROCm/rocm-systems
```

---

## Quick Reference Tables

### Build Exclusion Flags (for `fetch_sources.py`)

| Flag | Effect |
|---|---|
| `--no-include-debug-tools` | Excludes debug tools |
| `--no-include-rocm-libraries` | Excludes ROCm libraries |
| `--no-include-ml-frameworks` | Excludes machine learning frameworks |
| `--no-include-media-libs` | Excludes media libraries |
| `--no-include-iree-libs` | Excludes IREE libraries |
| `--no-include-math-libraries` | Excludes math libraries |

### Build Output Locations

| Component | Build Output Path |
|---|---|
| HIP runtime | `build/core/clr/stage` |
| hip-tests | `build/core/hip-tests/stage` |
| hip-tests dist binaries | `build/core/hip-tests/dist/bin` |
| OpenCL runtime | `build/core/ocl-clr/stage` |
| OpenCL dist binaries | `build/core/ocl-clr/dist/bin` |

### CMake Build Targets

| Target | Purpose |
|---|---|
| `therock-archives therock-dist` | Full initial build |
| `hip-clr` | Rebuild HIP runtime only |
| `core/hip-tests` | Rebuild hip-tests only |

---

## Related Skills

- **`lrt-rocm:hip-ocl-monorepo-build`** — Alternative monorepo-based build for HIP/OCL via rocm-systems (only when explicitly requested)
- **`lrt-rocm:regression-bisect-hip-ocl`** — For bisecting HIP/OCL test regressions
- **`lrt-rocm:test-driven-development`** — For implementing features with test-first methodology in the ROCm ecosystem
