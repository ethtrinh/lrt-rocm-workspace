# Plan: Global Fortran Enable/Disable Flag + Flang/Offload Separation

## Context

TheRock currently builds flang, MLIR, flang-rt, and offload runtimes as part of the monolithic amd-llvm sub-project. This means:
- Every build pays the cost of building flang + MLIR + flang-rt (memory and time intensive)
- Fortran support cannot be disabled for users who don't need it
- No path to packaging flang as an optional overlay
- The base amd-llvm artifact can't be swapped for a bootstrap/PGO/BOLT optimized build

Goals:
1. Introduce flags to globally enable/disable Fortran across the codebase
2. Propagate Fortran-enabled state to sub-projects that have Fortran components
3. Split flang + MLIR out of the base LLVM into `amd-llvm-flang`
4. Split offload + flang-rt out of the base LLVM into `amd-llvm-offload`

---

## Architecture

### Three compiler artifacts

```
amd-llvm (base, critical path, swappable for PGO/BOLT)
├── clang, lld, clang-tools-extra
├── compiler-rt, libunwind, libcxx, libcxxabi
├── openmp (host libomp only — offload-aware via dlsym, no link dep)
├── device-libs, spirv-llvm-translator
└── NO: flang, MLIR, flang-rt, offload

amd-llvm-flang (background, gated by THEROCK_ENABLE_FLANG)
├── flang frontend
├── MLIR (build dep for flang, not user-facing)
└── depends on: amd-llvm (uses clang to compile itself)

amd-llvm-offload (background, always built on Linux)
├── offload (libomptarget, plugins-nextgen, device RTLs)
├── Conditionally: flang-rt host+device (when THEROCK_ENABLE_FLANG=ON)
├── LIBOMPTARGET_BUILD_DEVICE_FORTRT=${THEROCK_ENABLE_FLANG}
├── Uses pre-built libomp from amd-llvm (LIBOMP_STANDALONE)
├── dist/ dir = union of amd-llvm + amd-llvm-flang (if enabled) + own outputs
└── depends on: amd-llvm + amd-llvm-flang (when FLANG enabled)
```

### Three-way toolchain system

| Mnemonic | Resolves to sub-project | Use case |
|----------|------------------------|----------|
| `amd-llvm` | `amd-llvm` | Host-only compiler/runtime. Used by compiler-internal sub-projects (amd-comgr, hipcc, amd-llvm-flang, amd-llvm-offload) and hip-clr. |
| `amd-llvm-offload` | `amd-llvm-offload` | Offload-capable compiler/runtime + flang/flang-rt when enabled. Used by pure-Fortran projects (hipfort) and OpenMP offload projects. |
| `hip-clr` | `hip-clr` | HIP CLR toolchain (includes libamdhip64). Used by math-libs and other HIP C++ projects. |

Key properties:
- `amd-llvm` keeps its current meaning — no renames, no breakage
- `hip-clr` builds with `COMPILER_TOOLCHAIN amd-llvm` (fast critical path, no offload/flang dep)
- `amd-llvm-offload` is the only new toolchain mnemonic
- Sub-projects that use `hip-clr` but also have Fortran components get their Fortran compiler via the `FORTRAN_OPTIONAL` keyword (see Part 4), which conditionally adds a dependency on `amd-llvm-offload`

### Four consumer classes

| Class | Needs | Toolchain |
|-------|-------|-----------|
| (a) C++ compiler/runtime | clang, lld, libc++ | `amd-llvm` |
| (b) Host-side OpenMP | libomp for CPU parallelism | `amd-llvm` |
| (c) Fortran compiler+runtime | flang, flang-rt | `amd-llvm-offload` |
| (d) GPU offload (C++/OpenMP) | libomptarget, device RTLs | `amd-llvm-offload` |
| (e) HIP C++ | libamdhip64, HIP runtime | `hip-clr` |
| (f) HIP C++ + Fortran wrappers | HIP runtime + Fortran compiler | `hip-clr` + `FORTRAN_OPTIONAL` |

### Dependency chains

```
THEROCK_ENABLE_FLANG=OFF:
  amd-llvm → amd-llvm-offload (no flang-rt, no device fortrt)

THEROCK_ENABLE_FLANG=ON:
  amd-llvm ──→ amd-llvm-flang (compiler)
           └─→ amd-llvm-offload (offload + flang-rt)
                 depends on amd-llvm + amd-llvm-flang
```

---

## Two flags

### `THEROCK_ENABLE_FLANG` — Artifact enable flag

Controls whether the `amd-llvm-flang` artifact is built and whether `amd-llvm-offload` includes flang-rt. Follows existing artifact feature pattern via BUILD_TOPOLOGY.toml.

```toml
# BUILD_TOPOLOGY.toml
[artifacts.amd-llvm-flang]
artifact_group = "compiler"
type = "target-neutral"
artifact_deps = ["amd-llvm"]
feature_name = "FLANG"
feature_group = "ALL"
disable_platforms = ["windows"]
```

This auto-generates `THEROCK_ENABLE_FLANG` via the topology-to-cmake pipeline.

### `THEROCK_FLAG_BUILD_FORTRAN_LIBS` — FLAGS.cmake flag for sub-projects

Controls whether sub-projects build their Fortran components (test clients, Fortran wrappers, hipfort, etc.). Independent of flang — on Windows, system gfortran can be used.

```cmake
# FLAGS.cmake
therock_declare_flag(
  NAME BUILD_FORTRAN_LIBS
  DEFAULT_VALUE OFF
  DESCRIPTION "Build Fortran components in sub-projects (wrappers, tests, hipfort)"
  GLOBAL_CMAKE_VARS
    ROCM_BUILD_FORTRAN_LIBS=ON
)
```

### Flag relationship

| ENABLE_FLANG | BUILD_FORTRAN_LIBS | Scenario |
|---|---|---|
| OFF | OFF | No Fortran anything |
| ON | OFF | Build Fortran compiler+runtime, but not Fortran library wrappers |
| OFF | ON | No flang, sub-projects use system gfortran (Windows) |
| ON | ON | Full Fortran stack |

---

## Part 1: Base amd-llvm changes

### Strip flang/offload from base build

**`compiler/pre_hook_amd-llvm.cmake`** changes:

```cmake
# Line 25 — remove flang:
set(LLVM_ENABLE_PROJECTS "clang;lld;clang-tools-extra" CACHE STRING "..." FORCE)

# Line 26 — remove offload:
set(LLVM_ENABLE_RUNTIMES "compiler-rt;libunwind;libcxx;libcxxabi;openmp" CACHE STRING "..." FORCE)

# CRITICAL: Leave OPENMP_ENABLE_LIBOMPTARGET at default (ON).
# This bakes dlsym hooks into libomp for offload cooperation.
# At runtime, libomp calls dlsym(RTLD_DEFAULT, "__tgt_target_sync").
# If libomptarget is not loaded, dlsym returns NULL, callbacks stay NULL,
# and all offload hooks are silently skipped (guarded by UNLIKELY(ptr != NULL)).
# When amd-llvm-offload is installed, libomptarget becomes available and
# libomp discovers it via dlsym — full async target task cooperation works.

# Remove the entire if("offload" IN_LIST ...) block (lines 27-56)
# This includes: flang-rt in runtimes, LLVM_RUNTIME_TARGETS for amdgcn,
# RUNTIMES_amdgcn-amd-amdhsa settings, LIBOMPTARGET_BUILD_DEVICE_FORTRT, etc.
# All of this moves to amd-llvm-offload.

# Add:
set(CLANG_LINK_FLANG OFF)  # Don't create flang→clang symlink
```

**`compiler/CMakeLists.txt`** changes:
- Remove `FLANG_PARALLEL_COMPILE_JOBS` handling (moves to amd-llvm-flang)
- Remove `FLANG_RUNTIME_F128_MATH_LIB` arg (moves to amd-llvm-offload)
- Remove offload-related CMAKE_ARGS:
  - `CLANG_TOOL_CLANG_LINKER_WRAPPER_BUILD`
  - `CLANG_TOOL_OFFLOAD_ARCH_BUILD`
  - `OPENMP_ENABLE_LIBOMPTARGET`
  - `LIBOMPTARGET_BUILD_DEVICE_FORTRT`
  - `OFFLOAD_EXTERNAL_PROJECT_UNIFIED_ROCR`
  - `LIBOMPTARGET_EXTERNAL_PROJECT_HSA_PATH`
  - `RUNTIMES_amdgcn-amd-amdhsa_*` settings

---

## Part 2: New sub-projects

### 2a. `amd-llvm-flang` sub-project

**New file: `compiler/amd-llvm-flang/CMakeLists.txt`**

Based on the proven `users/stella/flang-unmonolith` branch version:
- `find_package(LLVM CONFIG)` + `find_package(Clang CONFIG)` from base amd-llvm
- `add_subdirectory` for MLIR (build dep, `EXCLUDE_FROM_ALL`)
- `add_subdirectory` for flang
- Generate `quadmath_wrapper.h` (upstream bug: only generated by flang-rt but needed by flang compiler)
- Dependency hacks: `add_dependencies(FortranSupport MLIRBuiltinTypeInterfacesIncGen)` etc.
- `MLIR_LINK_MLIR_DYLIB=OFF` (build MLIR as static, don't try to use installed LLVM's dylib)

**Registration in `compiler/CMakeLists.txt`:**
```cmake
if(THEROCK_ENABLE_FLANG)
  therock_cmake_subproject_declare(amd-llvm-flang
    EXTERNAL_SOURCE_DIR "amd-llvm-flang"
    BINARY_DIR "amd-llvm-flang"
    BACKGROUND_BUILD
    COMPILER_TOOLCHAIN amd-llvm
    CMAKE_ARGS
      ${_extra_flang_cmake_args}
    RUNTIME_DEPS
      amd-llvm
    INTERFACE_PROGRAM_DIRS
      lib/llvm/bin
    INSTALL_DESTINATION "lib/llvm"
  )
  therock_cmake_subproject_provide_package(amd-llvm-flang Flang lib/llvm/lib/cmake/flang)
  therock_cmake_subproject_activate(amd-llvm-flang)
endif()
```

### 2b. `amd-llvm-offload` sub-project

**New file: `compiler/amd-llvm-offload/CMakeLists.txt`**

Standalone runtimes build for offload (+ conditionally flang-rt):

```cmake
cmake_minimum_required(VERSION 3.20)
project(amd-llvm-offload C CXX ASM)

set(LLVM_MONOREPO_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../amd-llvm")

find_package(LLVM REQUIRED CONFIG)
set(PACKAGE_VERSION ${LLVM_PACKAGE_VERSION})

set(LLVM_INCLUDE_TESTS OFF)

# Core runtimes: offload always
set(_runtimes "offload")
set(_amdgcn_runtimes "openmp")  # device openmp runtime

# Conditionally add flang-rt when FLANG is enabled
if(THEROCK_ENABLE_FLANG)
  list(APPEND _runtimes "flang-rt")
  list(APPEND _amdgcn_runtimes "flang-rt")
  set(CMAKE_Fortran_COMPILER_WORKS YES CACHE BOOL "" FORCE)
  set(FLANG_RUNTIME_F128_MATH_LIB "libquadmath")
  set(LIBOMPTARGET_BUILD_DEVICE_FORTRT ON)
  set(RUNTIMES_amdgcn-amd-amdhsa_FLANG_RT_LIBC_PROVIDER "llvm")
  set(RUNTIMES_amdgcn-amd-amdhsa_FLANG_RT_LIBCXX_PROVIDER "llvm")
else()
  set(LIBOMPTARGET_BUILD_DEVICE_FORTRT OFF)
endif()

set(LLVM_ENABLE_RUNTIMES "${_runtimes}" CACHE STRING "" FORCE)

# Offload settings (from current pre_hook)
set(OPENMP_ENABLE_LIBOMPTARGET ON)
set(LIBOMPTARGET_ENABLE_DEBUG ON)
set(LIBOMPTARGET_NO_SANITIZER_AMDGPU ON)
set(OFFLOAD_EXTERNAL_PROJECT_UNIFIED_ROCR ON)

# Device targets
set(LLVM_RUNTIME_TARGETS "default;amdgcn-amd-amdhsa")
set(RUNTIMES_amdgcn-amd-amdhsa_LLVM_ENABLE_PER_TARGET_RUNTIME_DIR ON)
set(RUNTIMES_amdgcn-amd-amdhsa_LLVM_ENABLE_RUNTIMES "${_amdgcn_runtimes}")

add_subdirectory("${LLVM_MONOREPO_DIR}/runtimes" "runtimes")
```

**Registration in `compiler/CMakeLists.txt`:**
```cmake
# amd-llvm-offload: always built on non-Windows
if(NOT WIN32)
  set(_offload_deps amd-llvm)
  if(THEROCK_ENABLE_FLANG)
    list(APPEND _offload_deps amd-llvm-flang)
  endif()

  therock_cmake_subproject_declare(amd-llvm-offload
    USE_DIST_AMDGPU_TARGETS
    EXTERNAL_SOURCE_DIR "amd-llvm-offload"
    BINARY_DIR "amd-llvm-offload"
    BACKGROUND_BUILD
    COMPILER_TOOLCHAIN amd-llvm
    CMAKE_ARGS
      -DTHEROCK_ENABLE_FLANG=${THEROCK_ENABLE_FLANG}
      -DLIBOMPTARGET_EXTERNAL_PROJECT_HSA_PATH=${THEROCK_ROCM_SYSTEMS_SOURCE_DIR}/projects/rocr-runtime
    RUNTIME_DEPS
      ${_offload_deps}
    INSTALL_DESTINATION "lib/llvm"
  )
  therock_cmake_subproject_activate(amd-llvm-offload)
endif()
```

### 2c. Artifacts and BUILD_TOPOLOGY.toml

**BUILD_TOPOLOGY.toml additions:**
```toml
[artifacts.amd-llvm-flang]
artifact_group = "compiler"
type = "target-neutral"
artifact_deps = ["amd-llvm"]
feature_name = "FLANG"
feature_group = "ALL"
disable_platforms = ["windows"]

[artifacts.amd-llvm-offload]
artifact_group = "compiler"
type = "target-neutral"
artifact_deps = ["amd-llvm"]
disable_platforms = ["windows"]
# No feature_name — always enabled on Linux
```

**New file: `compiler/artifact-amd-llvm-offload.toml`**
```toml
[components.lib."compiler/amd-llvm-offload/stage"]
force_include = ["lib/llvm/lib/clang/**"]

[components.run."compiler/amd-llvm-offload/stage"]
include = ["lib/llvm/bin/**"]
```

**New file: `compiler/artifact-amd-llvm-flang.toml`**
```toml
[components.run."compiler/amd-llvm-flang/stage"]
include = ["lib/llvm/bin/**"]

[components.dev."compiler/amd-llvm-flang/stage"]
include = ["lib/llvm/include/**"]
```

**Modify: `compiler/artifact-amd-llvm.toml`** — remove offload/flang components that moved out.

**Update `therock_provide_artifact` in `compiler/CMakeLists.txt`:**
```cmake
therock_provide_artifact(amd-llvm
  TARGET_NEUTRAL
  DESCRIPTOR artifact-amd-llvm.toml
  COMPONENTS dbg dev doc lib run
  SUBPROJECT_DEPS
    amd-llvm
    hipcc
    amd-comgr
)

# Separate offload artifact
therock_provide_artifact(amd-llvm-offload
  TARGET_NEUTRAL
  DESCRIPTOR artifact-amd-llvm-offload.toml
  COMPONENTS dbg lib run
  SUBPROJECT_DEPS
    amd-llvm-offload
)

if(THEROCK_ENABLE_FLANG)
  therock_provide_artifact(amd-llvm-flang
    TARGET_NEUTRAL
    DESCRIPTOR artifact-amd-llvm-flang.toml
    COMPONENTS dbg dev run
    SUBPROJECT_DEPS
      amd-llvm-flang
  )
endif()
```

---

## Part 3: Toolchain resolution

### Changes to `therock_subproject.cmake`

**Add `amd-llvm-offload` mnemonic** to `_therock_cmake_subproject_setup_toolchain`:

```cmake
# In _therock_cmake_subproject_setup_toolchain (line ~1509):
if(compiler_toolchain STREQUAL "amd-hip")
  set(_toolchain_subproject "hip-clr")
elseif(compiler_toolchain STREQUAL "amd-llvm-offload")
  set(_toolchain_subproject "amd-llvm-offload")
else()
  # "amd-llvm" — resolves to amd-llvm (unchanged from today)
  set(_toolchain_subproject "amd-llvm")
endif()
```

No changes to existing `amd-llvm` or `hip-clr` resolution. The only addition is the new `amd-llvm-offload` case.

### Who uses which toolchain

| Toolchain | Sub-projects |
|-----------|-------------|
| `amd-llvm` | amd-comgr, hipcc, amd-llvm-flang, amd-llvm-offload, hip-clr, and any other host-only consumers |
| `amd-llvm-offload` | hipfort (future), OpenMP offload test projects |
| `hip-clr` | All math-libs, rocm-libraries, etc. (unchanged from today) |

hip-clr itself builds with `COMPILER_TOOLCHAIN amd-llvm` — no dependency on amd-llvm-offload, keeping the critical path short.

---

## Part 4: Fortran toolchain keywords + sub-project gating

### Declarative Fortran keywords

Sub-projects declare their Fortran needs with keywords instead of conditional cmake spew:

```cmake
# "I have optional Fortran components"
therock_cmake_subproject_declare(rocblas
  COMPILER_TOOLCHAIN hip-clr
  FORTRAN_OPTIONAL
  CMAKE_ARGS
    -DROCBLAS_ENABLE_FORTRAN=${ROCM_BUILD_FORTRAN_LIBS}
  ...
)

# "I am a Fortran project, I require a Fortran compiler"
therock_cmake_subproject_declare(hipfort
  COMPILER_TOOLCHAIN amd-llvm-offload
  FORTRAN_REQUIRED
  ...
)
```

### Resolution logic (in `therock_subproject.cmake`)

Centralized in `therock_cmake_subproject_declare`, written once:

```cmake
# Parse FORTRAN_OPTIONAL and FORTRAN_REQUIRED as new keywords

if(_has_fortran_optional AND NOT THEROCK_FLAG_BUILD_FORTRAN_LIBS)
  # No-op. No dep edge, no Fortran compiler, nothing.

elseif(_has_fortran_optional OR _has_fortran_required)
  # Need a Fortran compiler.
  if(NOT WIN32 AND THEROCK_ENABLE_FLANG)
    # Linux with flang: use our built flang from amd-llvm-offload
    # → sets CMAKE_Fortran_COMPILER to flang in amd-llvm-offload dist dir
    # → adds build dependency on amd-llvm-offload sub-project
    set(_fortran_toolchain_subproject "amd-llvm-offload")

  elseif(WIN32)
    # Windows: let CMake find system gfortran
    # No toolchain dep added, no CMAKE_Fortran_COMPILER set
    # CMake's enable_language(Fortran) will find gfortran on PATH

  else()
    # Linux, no flang built
    if(_has_fortran_required)
      message(FATAL_ERROR
        "Sub-project ${name} requires Fortran but THEROCK_ENABLE_FLANG is OFF")
    endif()
    # FORTRAN_OPTIONAL on Linux without flang: silently skip (no-op)
  endif()
endif()

# If _fortran_toolchain_subproject is set:
#   1. Add it to the sub-project's build deps
#   2. Set CMAKE_Fortran_COMPILER = <dist_dir>/lib/llvm/bin/flang-new
#      in the sub-project's toolchain file
```

### Properties

- **Zero conditional cmake spew at declaration sites** — just a keyword
- **Resolution logic written and tested once** in `therock_subproject.cmake`
- **The `amd-llvm-offload` name appears in one place** (the resolver), not scattered across math-lib declarations
- **Dependency edge on amd-llvm-offload only exists when `BUILD_FORTRAN_LIBS=ON`** — otherwise hip-clr math-libs stay on the fast path
- **Platform-aware**: Linux uses our flang, Windows uses system gfortran, no per-project logic needed
- **Future-proof**: if toolchain changes (system flang, different packaging), it's one place to update

### FLAGS.cmake

```cmake
therock_declare_flag(
  NAME BUILD_FORTRAN_LIBS
  DEFAULT_VALUE OFF
  DESCRIPTION "Build Fortran components in sub-projects (wrappers, tests, hipfort)"
  GLOBAL_CMAKE_VARS
    ROCM_BUILD_FORTRAN_LIBS=ON
)
```

### Sub-project declarations

Each sub-project adds `FORTRAN_OPTIONAL` and its own internal toggle:

| Project | Keyword | CMAKE_ARGS addition |
|---------|---------|---------------------|
| rocRAND | `FORTRAN_OPTIONAL` | `-DBUILD_FORTRAN_WRAPPER=${ROCM_BUILD_FORTRAN_LIBS}` |
| hipRAND | `FORTRAN_OPTIONAL` | `-DBUILD_FORTRAN_WRAPPER=${ROCM_BUILD_FORTRAN_LIBS}` |
| rocBLAS | `FORTRAN_OPTIONAL` | `-DROCBLAS_ENABLE_FORTRAN=${ROCM_BUILD_FORTRAN_LIBS}` |
| hipBLAS | `FORTRAN_OPTIONAL` | `-DBUILD_FORTRAN_CLIENTS=${ROCM_BUILD_FORTRAN_LIBS}` |
| rocSOLVER | — | Already covered by `BUILD_CLIENTS_TESTS` |
| hipSOLVER | — | Already covered by `BUILD_CLIENTS_TESTS` |
| hipSPARSELt | — | Already `HIPSPARSELT_ENABLE_FETCH=OFF` |
| hipfort (future) | `FORTRAN_REQUIRED` | (inherently Fortran) |

**Files to modify:** `math-libs/CMakeLists.txt`, `math-libs/BLAS/CMakeLists.txt`

---

## Key technical findings (from static analysis)

### flang-rt is fully self-contained
- Zero compile-time dependencies on openmp or offload
- `LLVM_ENABLE_RUNTIMES="flang-rt"` alone builds successfully
- Dependencies flow ONE WAY: openmp/offload optionally depend on flang-rt, never reverse

### libomp is independent of offload
- `LLVM_ENABLE_RUNTIMES="openmp"` without `"offload"` builds libomp correctly
- `OPENMP_ENABLE_LIBOMPTARGET` only controls a `#define` in `kmp_config.h`
- With `ENABLE_LIBOMPTARGET=1` (default ON for Linux): libomp calls `dlsym(RTLD_DEFAULT, "__tgt_target_sync")` at init. If libomptarget.so is not loaded, returns NULL. All callsites guarded by `if(UNLIKELY(ptr != NULL))` — silently skipped.
- When offload overlay is installed later, dlsym finds libomptarget and cooperation works.

### LIBOMPTARGET_BUILD_DEVICE_FORTRT
- Only checked in offload code (2 locations), never in flang-rt
- Controls: (1) linking PluginCommon against flang_rt.runtime for Fortran IO emissary, (2) adding FortranRuntime as a build dependency for offload
- When OFF: offload builds cleanly without flang-rt, Fortran GPU IO unavailable
- When ON: full-featured including Fortran IO from GPU kernels

### offload supports pre-built libomp
- `offload/CMakeLists.txt:340-348`: `find_library(LIBOMP_STANDALONE NAMES omp)` code path exists
- In standalone runtimes build, offload finds libomp from amd-llvm's dist dir

---

## Implementation Order

1. **Flags** — Add `BUILD_FORTRAN_LIBS` to FLAGS.cmake, add `amd-llvm-flang` and `amd-llvm-offload` to BUILD_TOPOLOGY.toml
2. **Fortran keywords** — Implement `FORTRAN_OPTIONAL`/`FORTRAN_REQUIRED` in `therock_subproject.cmake`
3. **Sub-project Fortran gating** — Add `FORTRAN_OPTIONAL` keyword + CMAKE_ARGS to math-lib sub-project declarations
4. **Strip flang+offload from base amd-llvm** — Modify pre_hook and CMakeLists
5. **Create amd-llvm-flang** — New CMakeLists.txt (from flang-unmonolith), registration, artifact toml
6. **Create amd-llvm-offload** — New CMakeLists.txt (standalone runtimes), registration, artifact toml
7. **Toolchain resolution** — Add `amd-llvm-offload` mnemonic to `therock_subproject.cmake`

Parts 1-3 can be done and tested independently of 4-7 (flags + keywords are additive, existing build unchanged).

---

## Verification

### Parts 1-3 (flags + keywords + sub-project gating):
```bash
cmake -B /develop/therock-build -S /develop/therock -GNinja \
  -DTHEROCK_AMDGPU_FAMILIES=gfx1201 \
  -DTHEROCK_FLAG_BUILD_FORTRAN_LIBS=OFF
# Verify: flag report shows BUILD_FORTRAN_LIBS=OFF
# Verify: sub-projects do NOT get ROCM_BUILD_FORTRAN_LIBS in project_init.cmake
# Verify: no FORTRAN_OPTIONAL dep edges added (no amd-llvm-offload deps on math-libs)

cmake -B /develop/therock-build -S /develop/therock -GNinja \
  -DTHEROCK_AMDGPU_FAMILIES=gfx1201 \
  -DTHEROCK_FLAG_BUILD_FORTRAN_LIBS=ON
# Verify: sub-projects get ROCM_BUILD_FORTRAN_LIBS=ON
# Verify: FORTRAN_OPTIONAL sub-projects have dep edge on amd-llvm-offload
# Verify: CMAKE_Fortran_COMPILER set in their toolchain files
```

### Parts 4-7 (artifact separation):
```bash
cmake -B /develop/therock-build -S /develop/therock -GNinja \
  -DTHEROCK_AMDGPU_FAMILIES=gfx1201 \
  -DTHEROCK_ENABLE_FLANG=ON

# Build base (should NOT contain flang/MLIR/offload/flang-rt)
ninja amd-llvm+dist
# Verify: no flang binary, no MLIR libs, no libomptarget

# Build flang (should contain flang binary + MLIR build artifacts)
ninja amd-llvm-flang+dist

# Build offload (should contain libomptarget + flang-rt)
ninja amd-llvm-offload+dist

# Test without flang:
cmake ... -DTHEROCK_ENABLE_FLANG=OFF
ninja amd-llvm-offload+dist
# Verify: libomptarget present, no flang-rt, no device fortrt
```

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `FLAGS.cmake` | Declare BUILD_FORTRAN_LIBS flag |
| `BUILD_TOPOLOGY.toml` | Add amd-llvm-flang + amd-llvm-offload artifact definitions |
| `cmake/therock_subproject.cmake` | Add FORTRAN_OPTIONAL/REQUIRED keywords + amd-llvm-offload toolchain |
| `compiler/CMakeLists.txt` | Register new sub-projects, modify amd-llvm artifact |
| `compiler/pre_hook_amd-llvm.cmake` | Strip flang/offload from base LLVM |
| `compiler/amd-llvm-flang/CMakeLists.txt` | **New** — Separate flang+MLIR build |
| `compiler/amd-llvm-offload/CMakeLists.txt` | **New** — Separate offload+flang-rt build |
| `compiler/artifact-amd-llvm-flang.toml` | **New** — Flang artifact descriptor |
| `compiler/artifact-amd-llvm-offload.toml` | **New** — Offload artifact descriptor |
| `compiler/artifact-amd-llvm.toml` | **Modify** — Remove offload/flang components |
| `math-libs/CMakeLists.txt` | Add FORTRAN_OPTIONAL + gating for rocRAND/hipRAND |
| `math-libs/BLAS/CMakeLists.txt` | Add FORTRAN_OPTIONAL + gating for BLAS sub-projects |

## Alternatives Considered

- **Keep offload in base amd-llvm**: Simpler but prevents swapping base amd-llvm for PGO/BOLT builds, and keeps flang-rt coupled to the critical path when Fortran is enabled.
- **Single flang artifact containing flang+flang-rt+offload**: The unmonolith approach. Mixes concerns — offload is needed even without Fortran. Separate artifacts for compiler (amd-llvm-flang) and runtimes (amd-llvm-offload) is cleaner.
- **OPENMP_ENABLE_LIBOMPTARGET=OFF in base**: Would produce a libomp without dlsym hooks for target task cooperation. Functionally degrades async GPU task synchronization when offload overlay is installed later. Not acceptable.
- **Use FLAGS.cmake for FLANG enable**: The FLANG enable flag is more naturally an artifact feature (integrates with CI sharding and source set management via BUILD_TOPOLOGY.toml).
- **Rename amd-llvm to amd-llvm-base**: Would require updating dozens of references across the codebase for no functional benefit. The bareword `amd-llvm` keeps its current meaning (host-only compiler), avoiding unnecessary churn.
- **Compound toolchain names (hip-clr-offload)**: Mixes C/CXX toolchain and Fortran compiler concerns into one mnemonic. Leads to combinatorial explosion as new capability axes are added. The orthogonal `FORTRAN_OPTIONAL`/`FORTRAN_REQUIRED` keyword approach keeps concerns separated and the resolution logic centralized.
- **Conditional toolchain selection at each declaration site**: Requires each sub-project to manually check flags and set toolchain deps. The keyword approach (`FORTRAN_OPTIONAL`) eliminates this boilerplate — sub-projects declare intent, infrastructure resolves it.
