# Multi-Architecture Convergence Static Analysis Report

**Date:** 2026-03-10
**Scope:** All shard-specific subprojects in TheRock (those using `THEROCK_AMDGPU_TARGETS`)
**Reference:** RFC0008 Multi-Arch Packaging — Future State: Multi-Stage Sharded Build

## Definition: Convergence

A shard-specific subproject is **convergent** if, when built independently for
disjoint subsets of DIST GPU targets, the outputs from all shards can be overlaid
onto a single filesystem to produce a complete, correct installation. Specifically:

1. **Host-side shared libraries must be identical across shards.** Every `.so`
   produced by building for `{gfx942}` must be byte-for-byte identical to
   the corresponding `.so` from building for `{gfx1100}`, differing only in
   the embedded device code sections (offload bundles).

2. **Device code objects and kernel databases must be additively composable.**
   Files containing device code for a specific GFX target must be named with
   that target (e.g., `TensileLibrary_gfx942.co`, `gfx942.kdb.bz2`) so that
   overlaying all shards' output directories produces the union of all targets'
   files without overwriting.

3. **Metadata/manifest files that catalog available targets must either:**
   - Be per-target named (each shard contributes its own), or
   - Be identical across all shards (e.g., a plan file generated for ALL
     DIST targets), or
   - Be designed for post-hoc merge (e.g., kpack recombine).

4. **No CMake-time branching on GPU_TARGETS may alter the host-side build graph**
   (e.g., enabling/disabling features, adding/removing compile definitions,
   changing linked dependencies) in ways that cause property (1) to be violated.

---

## Regenerating This Report

This report was generated via static analysis of TheRock's CMake build system. To
regenerate or extend it (e.g., after code changes or new subprojects), use the
following prompt with Claude Code from the `claude-rocm-workspace` directory:

```
Perform a deep static analysis of TheRock's multi-arch convergence properties.

CONTEXT: In TheRock's multi-arch sharded build (RFC0008), subprojects declared
with `therock_cmake_subproject_declare()` WITHOUT `USE_DIST_AMDGPU_TARGETS`,
`USE_TEST_AMDGPU_TARGETS`, or `DISABLE_AMDGPU_TARGETS` receive per-shard
GPU targets via `THEROCK_AMDGPU_TARGETS`. These are the "shard-specific"
subprojects. A "convergent" subproject produces outputs that can be overlaid
across all shards onto one filesystem without conflict.

WHAT TO CHECK for each shard-specific subproject:
1. Find its source directory from the EXTERNAL_SOURCE_DIR in the declare call
2. Grep ALL CMakeLists.txt and *.cmake files recursively for:
   GPU_TARGETS, AMDGPU_TARGETS, CMAKE_HIP_ARCHITECTURES, offload-arch, gfx
3. For each hit, classify as:
   a. PASSTHROUGH (set once for HIP compiler, no branching) → SAFE
   b. ITERATION for --offload-arch flags on library targets → SAFE (kpack split handles)
   c. ITERATION for --offload-arch on tests/benchmarks only → SAFE
   d. CONDITIONAL COMPILE DEFINITIONS (add_definitions, target_compile_definitions)
      based on GPU_TARGETS → CRITICAL if it affects library code (not just tests)
   e. CONDITIONAL LINKING (target_link_libraries gated on GPU_TARGETS) → CRITICAL
      if the linked library is static (changes host binary layout). Runtime-loaded
      shared libraries are acceptable IF they have target-specific names.
   f. OUTPUT FILES without target in filename → check if content varies by shard
   g. OUTPUT FILES with target in filename → SAFE (additive overlay)

KNOWN VIOLATION PATTERNS (from previous analysis):
- add_definitions() based on SUPPORTED_GPU_TARGETS (composable_kernel)
- target_compile_definitions() based on GPU_TARGETS (MIOpen, rccl)
- Static library linking gated on GPU_TARGETS (rccl + MSCCLPP)
- TheRock top-level feature disabling based on THEROCK_AMDGPU_TARGETS (ml-libs CK check)
- Metadata files with fixed names but shard-specific content (hipblasltExtOpLibrary.dat,
  Tensile metadata, rocfft_kernel_cache.db)

ALSO CHECK TheRock-level CMake files that configure shard-specific subprojects:
- ml-libs/CMakeLists.txt (CK enable check, MIOpen database args)
- math-libs/BLAS/CMakeLists.txt, comm-libs/CMakeLists.txt, etc.
- Look for CMAKE_ARGS that pass ${THEROCK_AMDGPU_TARGETS} or derived values

REMEDIATION TAXONOMY:
- For metadata/solution databases (Tensile, MIOpen perf DBs): plumb DIST targets
  through so all shards generate identical metadata covering all architectures
- For kernel libraries too expensive to build all-at-once (CK): split into
  per-target runtime-loaded shared libraries with target-specific names
- For feature flags (compile defs): always enable all feature paths in host code;
  vary only the device code per shard
- For statically-linked optional components (MSCCLPP): either always build and
  link (using DIST targets), or restructure as a runtime-loaded plugin

OUTPUT: A markdown report with:
- Summary table (project, verdict, severity, finding reference)
- Detailed per-project sections with file:line references
- Recommendations section with remediation per finding

The subproject list and source dirs can be found by grepping for
therock_cmake_subproject_declare in /develop/therock/**/CMakeLists.txt.
Source dirs: rocm-systems → /develop/therock/rocm-systems/projects/,
rocm-libraries → /develop/therock/rocm-libraries/projects/ (and shared/, dnn-providers/).
```

---

## Executive Summary

| Severity | Count | Description |
|----------|-------|-------------|
| **CRITICAL** | 4 | Host-side binary divergence between shards |
| **HIGH** | 2 | Metadata files with same name, shard-specific content |
| **MEDIUM** | 1 | Performance cache with same name, shard-specific content |
| **CLEAN** | 22 | No convergence issues |

### Critical Violations

| # | Project | Issue | Impact |
|---|---------|-------|--------|
| C1 | composable_kernel | `add_definitions(-DCK_USE_XDL)`, `-DCK_USE_GFX94`, `-DCK_USE_WMMA`, etc. set based on `SUPPORTED_GPU_TARGETS` | libcomposable_kernel.so host code differs between shards |
| C2 | MIOpen | `target_compile_definitions(MIOpen PRIVATE CK_ENABLE_TF32)` and `CK_USE_GFX95` set based on `GPU_TARGETS` | libMIOpen.so host code differs between shards |
| C3 | ml-libs (TheRock top-level) | `THEROCK_ENABLE_COMPOSABLE_KERNEL` disabled if ANY shard target not in CK supported list | Build graph itself changes — MIOpen built with/without CK depending on shard |
| C4 | rccl | MSCCLPP statically linked into `librccl.so` gated on GPU_TARGETS; `ENABLE_MSCCLPP`/`ENABLE_WARP_SPEED` compile definitions | librccl.so host code and binary layout differ between shards |

### High-Risk Issues

| # | Project | Issue | Impact |
|---|---------|-------|--------|
| H1 | hipBLASLt | `hipblasltExtOpLibrary.dat` is generated per-arch but always installed to same path | Last-writer-wins — metadata for earlier shards' architectures lost |
| H2 | rocBLAS / hipBLASLt (Tensile) | Tensile master metadata file (`TensileLibrary.dat` or equivalent) catalogs only the building shard's architectures | Overlay produces metadata missing some architectures |

### Medium-Risk Issues

| # | Project | Issue | Impact |
|---|---------|-------|--------|
| M1 | rocFFT | `rocfft_kernel_cache.db` installed to fixed path, contains pre-compiled kernels only for shard's `GPU_TARGETS_AOT` subset | Performance degradation for targets not in winning shard's cache; functionally correct (JIT fallback) |

---

## Subproject Inventory

### Classification

Subprojects are categorized by how they receive GPU targets:

- **SHARD** — Uses `THEROCK_AMDGPU_TARGETS` (per-shard subset). These are the focus of this analysis.
- **DIST** — Uses `THEROCK_DIST_AMDGPU_TARGETS` (all targets). Not in scope.
- **TEST** — Uses `THEROCK_TEST_AMDGPU_TARGETS` (all registered). Not in scope.
- **DISABLED** — No GPU targets. Not in scope.

### Complete Shard-Specific Subproject List

| Subproject | Directory | Verdict | Finding |
|------------|-----------|---------|---------|
| **rccl** | comm-libs | **C4** | MSCCLPP static lib linked into `librccl.so` conditionally; compile defs `ENABLE_MSCCLPP`/`ENABLE_WARP_SPEED` vary by shard |
| **rccl-tests** | comm-libs | CLEAN | Passthrough only; test binaries are generic multi-target |
| **rocshmem** | comm-libs | CLEAN | Single fat binary `librocshmem.so`; configuration-only GPU_TARGETS usage |
| **rocRAND** | math-libs | CLEAN | Standard HIP compilation; no per-arch output files |
| **hipRAND** | math-libs | CLEAN | Standard HIP compilation; no per-arch output files |
| **rocPRIM** | math-libs | CLEAN | Header-heavy library; GPU_TARGETS used for compiler flags only |
| **hipCUB** | math-libs | CLEAN | Header-heavy library; GPU_TARGETS used for compiler flags only |
| **rocThrust** | math-libs | CLEAN | Header-heavy library; GPU_TARGETS used for compiler flags only |
| **rocFFT** | math-libs | **M1** | Kernel cache file at fixed path with shard-specific content |
| **hipFFT** | math-libs | CLEAN | Thin wrapper; standard HIP compilation |
| **rocWMMA** | math-libs | CLEAN | Standard HIP compilation; no per-arch output files |
| **libhipcxx** | math-libs | CLEAN | Header-only library; GPU_TARGETS syncs HIP architectures only |
| **mxDataGenerator** | math-libs/support | CLEAN | No GPU_TARGETS usage at all (host-only utility) |
| **hipBLAS-common** | math-libs/BLAS | CLEAN | No GPU_TARGETS usage (header support library) |
| **rocRoller** | math-libs/BLAS | CLEAN | No GPU_TARGETS usage (host-side optimization library) |
| **hipBLASLt** | math-libs/BLAS | **H1, H2** | ExtOp metadata and Tensile library metadata are shard-specific |
| **rocBLAS** | math-libs/BLAS | **H2** | Tensile library metadata is shard-specific |
| **rocSPARSE** | math-libs/BLAS | CLEAN | Standard HIP compilation; GPU_TARGETS for validation only |
| **hipSPARSE** | math-libs/BLAS | CLEAN | No GPU_TARGETS usage (wrapper around rocSPARSE) |
| **hipSPARSELt** | math-libs/BLAS | CLEAN | Narrow arch support (gfx942/gfx950 only); standard Tensile-like flow |
| **rocSOLVER** | math-libs/BLAS | CLEAN | Standard HIP compilation; AMDGPU_TARGETS for validation |
| **hipSOLVER** | math-libs/BLAS | CLEAN | No GPU_TARGETS usage (wrapper around rocSOLVER) |
| **hipBLAS** | math-libs/BLAS | CLEAN | No GPU_TARGETS usage (wrapper around rocBLAS) |
| **composable_kernel** | ml-libs | **C1** | Compile definitions change host-side code based on GPU_TARGETS |
| **MIOpen** | ml-libs | **C2** | Compile definitions and database installation based on GPU_TARGETS |
| **miopenprovider** | ml-libs | CLEAN | No GPU_TARGETS usage (plugin wrapper) |
| **hipblasltprovider** | ml-libs | CLEAN | No GPU_TARGETS usage (plugin wrapper) |
| **hipDNN_samples** | ml-libs | CLEAN | No GPU_TARGETS usage (test executables linking pre-built libraries) |

### Skipped Subprojects (Not In Scope)

| Subproject | Reason for Skip |
|------------|-----------------|
| **rocprof-trace-decoder** | Host-only binary installer. No GPU_TARGETS, AMDGPU_TARGETS, or CMAKE_HIP_ARCHITECTURES references. No HIP compilation. Confirmed safe. |

---

## Detailed Findings

### C1: composable_kernel — Host-Side Compile Definitions Vary by Target

**Location:** `/develop/therock/rocm-libraries/projects/composablekernel/CMakeLists.txt:146-328`

**Mechanism:** CK uses `add_definitions()` to set global compile flags based on which GPU
architectures are in `SUPPORTED_GPU_TARGETS`. These definitions control which code paths
are compiled into the host-side library:

```cmake
# Line 146: DL_KERNELS enabled for gfx10 variants
if(NOT DISABLE_DL_KERNELS AND GPU_TARGETS MATCHES "gfx101|gfx103|gfx10-1|gfx10-3")
    add_definitions(-DDL_KERNELS)

# Lines 262-328: Feature flags based on architecture presence
if (SUPPORTED_GPU_TARGETS MATCHES "gfx9|gfx11|gfx12" AND NOT FORCE_DISABLE_XDL)
    add_definitions(-DCK_USE_XDL)              # All modern targets → always ON
if ((SUPPORTED_GPU_TARGETS MATCHES "gfx94" OR ...) AND NOT FORCE_DISABLE_XDL)
    add_definitions(-DCK_USE_GFX94)            # Only gfx94x/gfx95x shards
if (SUPPORTED_GPU_TARGETS MATCHES "gfx950")
    add_definitions(-DCK_USE_GFX950)           # Only gfx950 shards
if (SUPPORTED_GPU_TARGETS MATCHES "gfx11" OR ... "gfx12")
    add_definitions(-DCK_USE_WMMA)             # Only gfx11xx/gfx12xx shards
if (SUPPORTED_GPU_TARGETS MATCHES "gfx12")
    add_definitions(-DCK_USE_WMMA_FP8)         # Only gfx12xx shards
if (SUPPORTED_GPU_TARGETS MATCHES "gfx12" OR ... "gfx950")
    add_definitions(-DCK_USE_OCP_FP8)          # gfx12xx or gfx950
if (SUPPORTED_GPU_TARGETS MATCHES "gfx90a" OR ... "gfx94")
    add_definitions(-DCK_USE_FNUZ_FP8)         # gfx90a or gfx94x
if (SUPPORTED_GPU_TARGETS MATCHES "gfx950")
    add_definitions(-DCK_USE_NATIVE_MX_SUPPORT)  # gfx950 only
    add_definitions(-DCK_GFX950_SUPPORT)
```

**Divergence Example:**

| Shard | SUPPORTED_GPU_TARGETS | CK_USE_XDL | CK_USE_GFX94 | CK_USE_WMMA | CK_USE_OCP_FP8 | CK_USE_FNUZ_FP8 |
|-------|----------------------|------------|--------------|-------------|----------------|-----------------|
| A (gfx942) | gfx942 | YES | YES | NO | NO | YES |
| B (gfx1100) | gfx1100 | YES | NO | YES | NO | NO |
| C (gfx1201) | gfx1201 | YES | NO | YES | YES | NO |

Each shard produces a `libcomposable_kernel.so` with **different host-side code**. The
template instantiations are guarded by these preprocessor definitions, so a library built
for gfx942 includes GFX94-specific template specializations that the gfx1100 library
lacks (and vice versa for WMMA specializations).

**Instance Library System:** Additionally, `library/src/tensor_operation_instance/gpu/CMakeLists.txt`
filters which source files are compiled based on `SUPPORTED_GPU_TARGETS`:
- `_xdl` instances: filter out gfx900, gfx906, gfx1030
- `_wmma` instances: filter out all gfx9xx
- `_mx` instances: filter to gfx950 only
- `mha` instances: filter to gfx90a, gfx94x, gfx95x only

Each instance source is compiled with `--offload-arch` flags per its filtered target list.
The resulting object files contain multi-target device code within a single `.o`, which
is then linked into the shared library.

**Why This Violates Convergence:** The host-side template dispatch code in the `.so` differs.
A gfx942 shard's `libcomposable_kernel.so` has CK_USE_GFX94 dispatch paths that the
gfx1100 shard's library does not. These are **not just offload sections** — they are
host-side C++ function instantiations.

**Remediation Options:**
1. Always enable ALL feature flags regardless of build targets (build all host-side dispatch
   code; only vary the device code per shard)
2. Split CK into a target-neutral host library and per-target device libraries
3. Accept the violation and build CK for all DIST targets in every shard (current status quo)

---

### C2: MIOpen — Host-Side Compile Definitions Vary by Target

**Location:** `/develop/therock/rocm-libraries/projects/miopen/src/CMakeLists.txt:935-941`

**Mechanism:**

```cmake
if(GPU_TARGETS MATCHES "gfx942" OR GPU_TARGETS MATCHES "gfx950")
    target_compile_definitions(MIOpen PRIVATE CK_ENABLE_TF32)
endif()
if(GPU_TARGETS MATCHES "gfx950")
    target_compile_definitions(MIOpen PRIVATE CK_USE_GFX95)
endif()
```

**Divergence:** A gfx942 shard's `libMIOpen.so` has `CK_ENABLE_TF32` compiled in; a
gfx1100 shard's does not. The gfx950 shard additionally has `CK_USE_GFX95`.

**Why This Violates Convergence:** Same mechanism as C1 — host-side code paths differ.
The MIOpen solver dispatch logic includes/excludes CK-based solvers based on these
definitions.

**Additional GPU_TARGETS Usage in MIOpen:**

The database installation is controlled by `MIOPEN_INSTALL_GPU_DATABASES`, which TheRock
sets to `${THEROCK_AMDGPU_TARGETS}` (ml-libs/CMakeLists.txt:112):
```cmake
"-DMIOPEN_INSTALL_GPU_DATABASES=\"${THEROCK_AMDGPU_TARGETS}\""
```

This controls which per-arch database files are installed:
- `${gfx_target}.kdb.bz2` — kernel database
- `${gfx_target}.HIP.fdb.txt` — find database
- `${gfx_target}.db` — performance database

These files ARE properly per-arch named (installed to `share/miopen/db/`), so the overlay
of databases across shards is **safe and additive**. This is not a convergence violation
for the databases themselves — the issue is the host-side library binary.

---

### C3: TheRock Top-Level CK Disable — Build Graph Changes Between Shards

**Location:** `/develop/therock/ml-libs/CMakeLists.txt:12-22`

**Mechanism:**

```cmake
if(THEROCK_ENABLE_COMPOSABLE_KERNEL)
  set(_ck_supported_gfx_targets gfx908 gfx90a gfx942 gfx950
      gfx1150 gfx1151 gfx1152 gfx1153 gfx1200 gfx1201)
  foreach(_gfx_target ${THEROCK_AMDGPU_TARGETS})
    if(NOT ${_gfx_target} IN_LIST _ck_supported_gfx_targets)
      set(THEROCK_ENABLE_COMPOSABLE_KERNEL OFF)
      set(THEROCK_MIOPEN_USE_COMPOSABLE_KERNEL OFF)
    endif()
  endforeach()
endif()
```

**Divergence:** If a shard contains ANY target not in the CK supported list (e.g.,
gfx906, gfx1030, gfx1100, gfx1101, gfx1102, gfx1103), the ENTIRE composable_kernel
build is disabled, AND MIOpen is configured without CK support.

**Targets that trigger CK disable:**
- gfx906, gfx908 — Wait, gfx908 IS in the list. Let me verify...
- Missing from `_ck_supported_gfx_targets`: gfx906, gfx1010, gfx1011, gfx1012,
  gfx1030, gfx1031, gfx1032, gfx1033, gfx1034, gfx1035, gfx1036,
  gfx1100, gfx1101, gfx1102, gfx1103

Notably, **gfx1100, gfx1101, gfx1102, gfx1103 are NOT in the supported list**.
This means a shard for `gfx1100` would disable CK entirely, while a shard for
`gfx942` would keep it enabled.

**Impact:** The build graph diverges:
- Shard A (gfx942): Builds composable_kernel + MIOpen-with-CK
- Shard B (gfx1100): Skips composable_kernel entirely + MIOpen-without-CK

MIOpen configured with `-DMIOPEN_USE_COMPOSABLEKERNEL=ON` vs `OFF` produces
completely different host-side libraries. This is the most severe convergence
violation because it affects the entire subproject dependency chain.

**Interaction with EXCLUDE_TARGET_PROJECTS:** Note that the `EXCLUDE_TARGET_PROJECTS`
mechanism in `therock_amdgpu_targets.cmake` handles per-target filtering differently.
It FILTERS targets from CK's GPU_TARGETS list but does NOT disable CK entirely.
The check in `ml-libs/CMakeLists.txt` is more aggressive — if ANY of the shard's
targets are unsupported, CK is fully disabled.

**Remediation:** The supported list needs to be expanded to include all targets that
CK can safely build for (even if some instance types are filtered out). Alternatively,
the check should be replaced with per-project EXCLUDE_TARGET_PROJECTS filtering.

---

### C4: rccl — MSCCLPP Static Library Changes Host Binary Layout

**Location:** `/develop/therock/rocm-systems/projects/rccl/CMakeLists.txt:452-488, 898-903, 1065, 1079, 1440`

**Mechanism:** RCCL conditionally builds and statically links the MSCCLPP library
based on whether the shard's GPU_TARGETS include gfx942 or gfx950:

```cmake
# Lines 452-468: MSCCLPP gated on GPU_TARGETS intersection with {gfx942, gfx950}
set(MSCCLPP_SUPPORTED_TARGETS gfx942 gfx950)
# ... intersection logic ...
if(NOT MSCCLPP_GPU_TARGETS)
    set(ENABLE_MSCCLPP_PLUGIN OFF)
endif()

# Lines 477-488: WARP_SPEED gated on gfx950 only
set(WARP_SPEED_TARGETS gfx950)
# ... intersection logic ...
if(NOT WARP_SPEED_GPU_TARGETS)
    set(ENABLE_WARP_SPEED OFF)
endif()
```

When MSCCLPP is enabled:
- Lines 898-903: MSCCLPP source files added to `SRC_FILES` (compiled into librccl.so)
- Line 1065: `target_compile_definitions(rccl PRIVATE ENABLE_MSCCLPP)`
- Line 1440: `target_link_libraries(rccl PRIVATE mscclpp_nccl)` — **static library**

When WARP_SPEED is enabled:
- Line 1079: `target_compile_definitions(rccl PRIVATE ENABLE_WARP_SPEED)`

**Why This Violates Convergence:** Static library linking changes the host binary.
Unlike a runtime-loaded `.so` (which would be fine if target-named), a static library's
code is physically embedded into `librccl.so`. The resulting binary has different:
- Symbol tables (MSCCLPP symbols present or absent)
- Code sections (MSCCLPP implementation code linked in or not)
- Compile-time behavior (ENABLE_MSCCLPP guards host-side dispatch paths)

A gfx942 shard's `librccl.so` is a fundamentally different binary from a gfx1100 shard's
version. Overlaying them produces a last-writer-wins conflict.

**Remediation:** Either always build and link MSCCLPP in all shards (gate the check
on DIST targets instead of shard targets, so the intersection always finds gfx942/gfx950),
or restructure MSCCLPP as a runtime-loaded shared library plugin.

---

### H1: hipBLASLt — hipblasltExtOpLibrary.dat File Conflict

**Location:** `/develop/therock/rocm-libraries/projects/hipblaslt/device-library/extops/CMakeLists.txt:21-96`

**Mechanism:** A `foreach(arch IN LISTS archs)` loop generates per-arch code objects
and a metadata file:

```cmake
foreach(arch IN LISTS archs)
    # Per-arch code object (SAFE — arch in filename)
    set(output_code_object_file "${CMAKE_CURRENT_BINARY_DIR}/extop_${arch}.co")
    # ...
    COMMAND ${CMAKE_COMMAND} -E copy "${output_code_object_file}"
            "${HIPBLASLT_TENSILE_LIBPATH}/library"

    # Metadata file (CONFLICT — same filename every iteration)
    COMMAND ${HIPBLASLT_PYTHON_COMMAND} "${ops_dir}/ExtOpCreateLibrary.py"
            --src=... --co=... --output=${output_dir} --arch=${arch}
    COMMAND ${CMAKE_COMMAND} -E copy
            "${output_dir}/hipblasltExtOpLibrary.dat"
            "${HIPBLASLT_TENSILE_LIBPATH}/library"
endforeach()
```

The `.co` files are properly per-arch named (`extop_gfx942.co`, `extop_gfx1100.co`).
The `.dat` metadata file is always named `hipblasltExtOpLibrary.dat`.

Within a single shard build, the serialized loop means the final `.dat` likely
accumulates entries for all architectures in that shard. But across shards:
- Shard A produces `hipblasltExtOpLibrary.dat` with entries for `{gfx942}`
- Shard B produces `hipblasltExtOpLibrary.dat` with entries for `{gfx1100}`
- Overlay: last-writer-wins → one shard's metadata is lost

**Install path:** `lib/hipblaslt/library/hipblasltExtOpLibrary.dat`

**Remediation:** Either name the `.dat` per-arch or design a merge step.

---

### H2: Tensile Library Metadata — Shard-Specific Catalog

**Location:**
- rocBLAS: `/develop/therock/rocm-libraries/projects/rocblas/library/src/CMakeLists.txt:74-94`
  installs to `lib/rocblas/library/`
- hipBLASLt: `/develop/therock/rocm-libraries/projects/hipblaslt/device-library/CMakeLists.txt:24-74`
  installs to `lib/hipblaslt/library/`

**Mechanism:** Tensile's `TensileCreateLibrary` is invoked with `--separate-architectures`
and `--lazy-library-loading`, producing:
- Per-arch code objects: `TensileLibrary_gfx942.co`, `TensileLibrary_gfx1100.co`, etc. (SAFE)
- A master metadata file that catalogs available solutions and maps them to architectures

The per-arch `.co` files overlay correctly (additive — different names per arch). The
metadata file (likely `TensileLibrary.dat` or similar YAML) is shard-specific — it only
catalogs the architectures that were built in that shard.

**Overlay behavior:** When shards overlay:
- All per-arch `.co` files are present (union of all shards' outputs)
- The metadata file from the last shard overwrites all others
- At runtime, Tensile attempts to load kernels for the detected GPU but the metadata
  may not reference code objects from other shards

**Note:** This requires verification of the exact metadata file format. If Tensile's
lazy loading can discover `.co` files by filename convention without consulting the
metadata, the practical impact may be reduced.

---

### M1: rocFFT — Kernel Cache File Conflict

**Location:** `/develop/therock/rocm-libraries/projects/rocfft/library/src/CMakeLists.txt:546-571`

**Mechanism:**

```cmake
set( GPU_TARGETS_AOT ${GPU_TARGETS} )
# Filters out older/less-common architectures...
list( REMOVE_ITEM GPU_TARGETS_AOT gfx803 gfx900 gfx906 ... gfx1200 )

add_custom_command(
    OUTPUT rocfft_kernel_cache.db
    COMMAND "${CMAKE_CURRENT_BINARY_DIR}/rocfft_aot_helper"
            \"${ROCFFT_BUILD_KERNEL_CACHE_PATH}\"
            ${ROCFFT_KERNEL_CACHE_PATH}
            $<TARGET_FILE:rocfft_rtc_helper>
            ${GPU_TARGETS_AOT}
)
```

**Install path:** `lib/rocfft/rocfft_kernel_cache.db`

The `rocfft_aot_helper` pre-compiles kernels for `GPU_TARGETS_AOT` (a filtered subset
of the shard's GPU_TARGETS). Each shard produces a cache file containing pre-compiled
kernels only for its targets.

**Overlay behavior:** Last-writer-wins. Functionally correct because rocFFT JIT-compiles
any kernel not found in the cache at runtime. Performance impact: missing pre-compiled
kernels for some architectures causes first-use latency.

**Remediation:** Either:
1. Name the cache per-arch (e.g., `rocfft_kernel_cache_gfx942.db`)
2. Build the cache for ALL DIST targets in every shard (same content → no conflict)
3. Merge caches in a post-build step

---

## Detailed Per-Project Analysis

### comm-libs Group

#### rccl

**Source:** `/develop/therock/rocm-systems/projects/rccl`
**GPU_TARGETS references:** CMakeLists.txt lines 132, 139, 167, 177, 182-183, 189, 452-468, 477-488, 898-903, 1065, 1079, 1379, 1440, 1561; src/CMakeLists.txt line 819

See finding **C4** below.

**Usage patterns:**
- **Configuration/validation** (lines 132, 182-189): Standard `rocm_check_target_ids()` flow
- **ASAN xnack+ suffixing** (lines 139-177): Appends `:xnack+` to targets for sanitizer builds
- **MSCCLPP filtering** (lines 452-468): Intersects GPU_TARGETS with `{gfx942, gfx950}` to determine if MSCCLPP is built. **MSCCLPP is a static library** (`mscclpp_nccl`) that gets linked into `librccl.so` (line 1440: `target_link_libraries(rccl PRIVATE mscclpp_nccl)`). When linked, compile definitions are added (line 1065: `target_compile_definitions(rccl PRIVATE ENABLE_MSCCLPP)`). This changes the host binary layout and code paths.
- **WARP_SPEED filtering** (lines 477-488): Only for `{gfx950}`. Adds `target_compile_definitions(rccl PRIVATE ENABLE_WARP_SPEED)` (line 1079). Also changes host code.
- **MSCCLPP source files** (lines 898-903): MSCCLPP-related source files conditionally added to `SRC_FILES` — these are compiled directly into `librccl.so`.
- **Debug assembly dumps** (lines 1379-1382, src/:819-822): Creates `librccl.${GPUARCH}.s` files per target. Build-only artifacts (not installed).

**Output:** Single `librccl.so` fat binary. No per-arch installed files.

**Why This Violates Convergence:** MSCCLPP is a **static library** linked into `librccl.so`,
not a runtime-loaded shared library. Static linking changes the host binary layout (symbol
table, section sizes, code content). A gfx942 shard's `librccl.so` contains MSCCLPP code
and has `ENABLE_MSCCLPP` compiled in; a gfx1100 shard's `librccl.so` does not contain
MSCCLPP at all. Additionally, `ENABLE_WARP_SPEED` adds further host-side code path
divergence for gfx950-only shards. These are not additive — they produce fundamentally
different host binaries.

**Divergence Example:**

| Shard | GPU_TARGETS | MSCCLPP linked | ENABLE_MSCCLPP | ENABLE_WARP_SPEED |
|-------|-------------|---------------|----------------|-------------------|
| A (gfx942) | gfx942 | YES | YES | NO |
| B (gfx950) | gfx950 | YES | YES | YES |
| C (gfx1100) | gfx1100 | NO | NO | NO |

**Verdict:** CRITICAL (C4)

#### rccl-tests

**Source:** `/develop/therock/rocm-systems/projects/rccl-tests`
**GPU_TARGETS references:** CMakeLists.txt lines 61, 65-66, 72-73

Passthrough configuration only. No iteration, no conditionals, no per-arch output.

**Verdict:** CLEAN

#### rocshmem

**Source:** `/develop/therock/rocm-systems/projects/rocshmem`
**GPU_TARGETS references:** CMakeLists.txt lines 132-143

Configuration and validation only. Single `librocshmem.so` fat binary. No per-arch output.

**Verdict:** CLEAN

---

### math-libs Group

#### rocRAND

**Source:** `/develop/therock/rocm-libraries/projects/rocrand`
**GPU_TARGETS references:** CMakeLists.txt:116-136, Summary.cmake:60, benchmark/tuning/CMakeLists.txt:59

Standard HIP compilation. Benchmark tuning iterates GPU_TARGETS for `--offload-arch`
flags (build-time only). No per-arch installed output files.

**Verdict:** CLEAN

#### hipRAND

**Source:** `/develop/therock/rocm-libraries/projects/hiprand`
**GPU_TARGETS references:** CMakeLists.txt:132-149, cmake/Summary.cmake:81

Configuration only. NVCC setup for CUDA targets (not AMD).

**Verdict:** CLEAN

#### rocPRIM

**Source:** `/develop/therock/rocm-libraries/projects/rocprim`
**GPU_TARGETS references:** CMakeLists.txt:146-173, cmake/Dependencies.cmake:170, cmake/Summary.cmake:84-86, test/rocprim/CMakeLists.txt:348

Configuration and validation. The `amdgcnspirv` check (line 173) affects
`BUILD_OFFLOAD_COMPRESS` but this is a build optimization, not an output difference.
Test exclusion for SPIR-V targets. Passes GPU_TARGETS to embedded rocRAND (safe).

**Verdict:** CLEAN

#### hipCUB

**Source:** `/develop/therock/rocm-libraries/projects/hipcub`
**GPU_TARGETS references:** CMakeLists.txt:133-163, cmake/Summary.cmake:84-89

Same pattern as rocPRIM. `amdgcnspirv` check. No per-arch output.

**Verdict:** CLEAN

#### rocThrust

**Source:** `/develop/therock/rocm-libraries/projects/rocthrust`
**GPU_TARGETS references:** CMakeLists.txt:135-158, cmake/Benchmarks.cmake:42, cmake/Dependencies.cmake:414, examples/CMakeLists.txt:28, testing/CMakeLists.txt:34, test/CMakeLists.txt:246

Benchmark, example, and test targets iterate GPU_TARGETS for `--offload-arch` flags.
Test exclusion for gfx950 with CODE_COVERAGE. No library-level per-arch output.

**Verdict:** CLEAN

#### rocFFT

**Source:** `/develop/therock/rocm-libraries/projects/rocfft`
**GPU_TARGETS references:** CMakeLists.txt:124-176, library/src/CMakeLists.txt:548-571

See finding **M1** above. The kernel cache is the only concern.

Additional detail: `GPU_TARGETS_AOT` is derived from GPU_TARGETS by removing:
gfx803, gfx900, gfx906, gfx940, gfx941, gfx1101, gfx1102, gfx1150, gfx1151,
gfx1152, gfx1153, gfx1200. These filtered-out targets fall back to JIT compilation.

Solution map files in `library/solution_map/` (e.g., `gfx908_rocfft_solution_map.dat`)
are static source files, not build-generated. These are per-arch named and safe.

**Verdict:** MEDIUM risk (M1)

#### hipFFT

**Source:** `/develop/therock/rocm-libraries/projects/hipfft`
**GPU_TARGETS references:** CMakeLists.txt:166, clients/tests/CMakeLists.txt:219

Validation via `rocm_check_target_ids()`. Test foreach for `--offload-arch` flags.

**Verdict:** CLEAN

#### rocWMMA

**Source:** `/develop/therock/rocm-libraries/projects/rocwmma`
**GPU_TARGETS references:** CMakeLists.txt:110-161

Complex target selection with ASAN constraints and fallback logic. All targets
used for standard HIP compilation. No per-arch installed output files.

**Verdict:** CLEAN

#### libhipcxx

**Source:** `/develop/therock/math-libs/libhipcxx`
**GPU_TARGETS references:** CMakeLists.txt:97-108

Syncs AMDGPU_TARGETS/GPU_TARGETS with CMAKE_HIP_ARCHITECTURES. Header-only library.
Test compilation uses HIP multi-architecture support.

**Verdict:** CLEAN

#### mxDataGenerator

**Source:** `/develop/therock/rocm-libraries/shared/mxdatagenerator`
**GPU_TARGETS references:** None

Host-side utility. No GPU code.

**Verdict:** CLEAN (host-only)

---

### math-libs/BLAS Group

#### hipBLAS-common

**Source:** `/develop/therock/rocm-libraries/projects/hipblas-common`
**GPU_TARGETS references:** None

Header support library.

**Verdict:** CLEAN

#### rocRoller

**Source:** `/develop/therock/rocm-libraries/shared/rocroller`
**GPU_TARGETS references:** None

Host-side GPU optimization library.

**Verdict:** CLEAN

#### hipBLASLt

**Source:** `/develop/therock/rocm-libraries/projects/hipblaslt`
**GPU_TARGETS references:** CMakeLists.txt:99-106, device-library/CMakeLists.txt:16, device-library/matrix-transform/CMakeLists.txt:26-46, device-library/extops/CMakeLists.txt:10-96

See findings **H1** and **H2** above.

Additional detail on extops:
- `extop_${arch}.co` — per-arch code objects (SAFE — arch in filename)
- `hipblasltTransform.hsaco` — single file compiled with all archs via multi-target
  `--offload-arch` flags (device code only; SAFE — kpack split handles this)
- `hipblasltExtOpLibrary.dat` — metadata cataloging available extops per-arch (CONFLICT)

**Tensile integration:**
- Uses `--merge-files`, `--separate-architectures`, `--lazy-library-loading`
- Per-arch `.co` files properly namespaced
- Master metadata (`TensileLibrary.dat`) shard-specific

**Install path:** `lib/hipblaslt/library/` (contains all Tensile + extop output)

**Verdict:** HIGH risk (H1 + H2)

#### rocBLAS

**Source:** `/develop/therock/rocm-libraries/projects/rocblas`
**GPU_TARGETS references:** CMakeLists.txt:80-146, library/src/CMakeLists.txt:74-94

See finding **H2** above.

Configuration and validation at top level. Delegates kernel generation to Tensile.
Tensile invoked via `TensileCreateLibraryFiles()` with same flags as hipBLASLt.

**Install path:** `lib/rocblas/library/` (Tensile output)

**Verdict:** HIGH risk (H2)

#### rocSPARSE

**Source:** `/develop/therock/rocm-libraries/projects/rocsparse`
**GPU_TARGETS references:** CMakeLists.txt:152-193

Configuration and validation. Standard HIP compilation.

**Verdict:** CLEAN

#### hipSPARSE

**Source:** `/develop/therock/rocm-libraries/projects/hipsparse`
**GPU_TARGETS references:** None

Wrapper around rocSPARSE.

**Verdict:** CLEAN

#### hipSPARSELt

**Source:** `/develop/therock/rocm-libraries/projects/hipsparselt`
**GPU_TARGETS references:** CMakeLists.txt:79-90

Narrow architecture support: gfx942, gfx950 only. Similar Tensile-like flow
but with very limited target scope.

**Verdict:** CLEAN (limited target scope reduces risk)

#### rocSOLVER

**Source:** `/develop/therock/rocm-libraries/projects/rocsolver`
**GPU_TARGETS references:** CMakeLists.txt:164-203

Uses AMDGPU_TARGETS for validation. Standard HIP compilation. The
`roclapack_getf2_small_db.cpp` is a source-code template instantiation, not a
generated per-arch database.

**Verdict:** CLEAN

#### hipSOLVER

**Source:** `/develop/therock/rocm-libraries/projects/hipsolver`
**GPU_TARGETS references:** None

Wrapper around rocSOLVER.

**Verdict:** CLEAN

#### hipBLAS

**Source:** `/develop/therock/rocm-libraries/projects/hipblas`
**GPU_TARGETS references:** None

Wrapper around rocBLAS.

**Verdict:** CLEAN

---

### ml-libs Group

#### composable_kernel

**Source:** `/develop/therock/rocm-libraries/projects/composablekernel`
**GPU_TARGETS references:** CMakeLists.txt:146-328, library/src/tensor_operation_instance/gpu/CMakeLists.txt:51-215

See finding **C1** above.

Instance library system creates object libraries per instance type, each compiled
with filtered `--offload-arch` flags. The filtering is:
- XDL instances: exclude gfx900, gfx906, gfx1030
- WMMA instances: exclude all gfx9xx
- MX instances: gfx950 only
- MHA instances: gfx90a, gfx94x, gfx95x only
- FP8 variants: architecture-specific support

The per-instance filtering is fine (it only controls which device architectures
get compiled into the object). The problem is the `add_definitions()` calls that
change the HOST-side dispatch code.

**Verdict:** CRITICAL (C1)

#### MIOpen

**Source:** `/develop/therock/rocm-libraries/projects/miopen`
**GPU_TARGETS references:** src/CMakeLists.txt:935-941, CMakeLists.txt:155-672

See findings **C2** and **C3** above.

Database files:
- `${gfx_target}.kdb.bz2` — kernel database (per-arch named, SAFE)
- `${gfx_target}.HIP.fdb.txt` — find database (per-arch named, SAFE)
- `${gfx_target}.db` — performance database (per-arch named, SAFE)
- All installed to `share/miopen/db/`

The per-arch database naming means the database overlay is additive and SAFE.
Only the host-side library binary is the problem.

**Verdict:** CRITICAL (C2, C3)

#### miopenprovider

**Source:** `/develop/therock/rocm-libraries/dnn-providers/miopen-provider`
**GPU_TARGETS references:** None

Plugin wrapper around MIOpen.

**Verdict:** CLEAN

#### hipblasltprovider

**Source:** `/develop/therock/rocm-libraries/dnn-providers/hipblaslt-provider`
**GPU_TARGETS references:** None

Plugin wrapper around hipBLASLt.

**Verdict:** CLEAN

#### hipDNN_samples

**Source:** `/develop/therock/rocm-libraries/projects/hipdnn/samples`
**GPU_TARGETS references:** None

Simple test executables linking pre-built libraries.

**Verdict:** CLEAN

---

## Recommendations

### Remediation Taxonomy

Different violation types require different remediation strategies:

| Pattern | Strategy | Example |
|---------|----------|---------|
| **Metadata/solution databases** | Plumb DIST targets so all shards generate identical metadata covering all architectures | Tensile metadata, hipBLASLt ExtOp metadata |
| **Expensive kernel libraries** | Split into per-target runtime-loaded shared libraries with target-specific names | composable_kernel |
| **Feature flags / compile defs** | Always enable all host-side feature paths; vary only device code per shard | MIOpen CK_ENABLE_TF32, CK_USE_GFX95 |
| **Statically-linked optional components** | Either always build+link (using DIST targets) or restructure as a runtime-loaded plugin | RCCL MSCCLPP |
| **Top-level build graph gating** | Replace all-or-nothing checks with per-target filtering | ml-libs CK disable check |

### Immediate Actions (Required for Multi-Arch Builds)

1. **Fix C3 (TheRock CK disable):** Replace the all-or-nothing check in
   `ml-libs/CMakeLists.txt:12-22` with per-project `EXCLUDE_TARGET_PROJECTS`
   filtering. CK should always be enabled if ANY of the shard's targets are
   CK-supported, with unsupported targets filtered at the CK project level.

2. **Fix C1 (CK compile definitions):** CK is split across shards precisely
   because it is too expensive to build all at once. The remediation is NOT to
   enable all feature flags (that would still produce divergent host code). Instead,
   CK needs to be restructured so that per-architecture kernel libraries are
   separate runtime-loaded shared libraries (e.g., `libcomposable_kernel_gfx942.so`,
   `libcomposable_kernel_gfx1100.so`) with a thin target-neutral host dispatch
   library. This way each shard produces per-target `.so` files that overlay
   additively.

3. **Fix C2 (MIOpen compile definitions):** Remove the GPU_TARGETS-dependent
   `target_compile_definitions` for CK_ENABLE_TF32 and CK_USE_GFX95. Always
   compile MIOpen with all CK feature support enabled in host code. Runtime
   detection of GPU capabilities should gate feature usage, not compile-time
   defines. This is the "feature flag" pattern — it's inexpensive to always
   compile the host-side dispatch paths.

4. **Fix C4 (RCCL MSCCLPP static link):** MSCCLPP is a static library linked
   into `librccl.so` conditionally based on GPU_TARGETS. Options:
   - **Always build and link MSCCLPP** (use DIST targets for the gating check
     so MSCCLPP is included in every shard's build). The runtime already selects
     the MSCCLPP path based on detected GPU, so including it in all shards is
     functionally correct.
   - **Restructure MSCCLPP as a runtime-loaded plugin** (separate `.so` with
     target-specific name, loaded via `dlopen` when needed). More invasive but
     cleaner separation.
   - Same applies to `ENABLE_WARP_SPEED`: either always define it (and let
     runtime detect gfx950) or gate it on DIST targets.

### Near-Term Actions (Before Multi-Arch CI)

5. **Fix H1 (hipBLASLt ExtOp metadata):** Plumb DIST targets for metadata
   generation so all shards produce identical `hipblasltExtOpLibrary.dat`
   covering all architectures. Alternatively, name the metadata per-arch:
   `hipblasltExtOpLibrary_${arch}.dat`.

6. **Fix H2 (Tensile metadata):** Plumb DIST targets into Tensile's metadata
   generation so the master metadata file catalogs all architectures (identical
   across shards). The per-arch `.co` files are already properly named and
   overlay correctly — only the catalog needs to be made shard-invariant.
   Verify whether Tensile's lazy-loading can discover `.co` files by filename
   convention without consulting the metadata.

7. **Fix M1 (rocFFT kernel cache):** Either:
   - Build the cache for ALL DIST targets (all shards produce identical cache)
   - Or split the cache per-arch: `rocfft_kernel_cache_${gfx_target}.db`
   - Or merge caches in post-build

---

## Methodology

### Search Strategy

Four parallel analysis agents scanned all subproject source trees for:
- `GPU_TARGETS`, `AMDGPU_TARGETS`, `CMAKE_HIP_ARCHITECTURES` references
- `foreach` loops iterating over GPU targets
- `if` conditions branching on GPU targets
- File naming patterns containing `gfx*`
- Database generation or solver metadata files
- Python scripts invoked by CMake that receive target lists
- `add_library`/`add_executable` calls conditional on targets

Additionally, TheRock-level CMake files (`ml-libs/CMakeLists.txt`,
`math-libs/CMakeLists.txt`, `math-libs/BLAS/CMakeLists.txt`,
`comm-libs/CMakeLists.txt`) were manually analyzed for GPU_TARGETS usage
that could affect subproject configuration.

### Files Analyzed

- All `CMakeLists.txt` and `*.cmake` files in 29 subproject source trees
- TheRock super-project CMake files in `cmake/`, `ml-libs/`, `math-libs/`,
  `comm-libs/`, `profiler/`
- Selected Python build scripts (Tensile, CK codegen, rocFFT)

### Limitations

1. **Tensile metadata format:** The exact format and role of Tensile's master
   metadata file was not fully verified. The H2 finding is based on the
   `--separate-architectures` flag behavior and may be more or less severe
   depending on runtime discovery mechanisms.

2. **hipBLASLt ExtOpCreateLibrary.py:** The exact behavior of this script
   (append vs overwrite) was not verified by reading the Python source.
   The finding assumes each invocation produces a complete metadata file
   for its architecture.

3. **Runtime behavior:** This analysis is purely static (CMake-level). Some
   convergence issues may be mitigated or exacerbated by runtime library
   loading behavior that was not analyzed.
