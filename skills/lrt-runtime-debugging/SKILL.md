---
name: lrt-runtime-debugging
description: Use for diagnosing HIP or OpenCL runtime failures, regressions, incorrect API behavior, hangs, crashes, or runtime test failures.
---

Debug LRT runtime issues methodically. LRT covers HIP and OpenCL runtime work.

## Required workflow

1. Read `directory-map.md` and the active task file if one exists.
2. Capture the environment:
   - OS and host.
   - GPU architecture and `rocminfo` summary if available.
   - ROCm install path and runtime source/build paths.
   - Relevant environment variables such as `ROCM_PATH`, `HIP_PATH`, `LD_LIBRARY_PATH`, `HIP_VISIBLE_DEVICES`, `ROCR_VISIBLE_DEVICES`, and OpenCL ICD variables when applicable.
3. Capture the exact failing command and output.
4. Identify the smallest affected API or runtime subsystem.
5. Split the investigation/fix into independently testable tasks if multiple behaviors are involved.
6. Search existing implementation and tests before proposing a fix.
7. Identify or add one focused failing test/reproducer for the observable runtime behavior before changing implementation code.
8. Reduce the failure to the smallest reproducer or test case practical.
9. Fix only the scoped behavior under investigation with the smallest implementation change.
10. Verify with the same targeted reproducer/test before broader tests, refactoring, or the next task.

## Runtime areas

- HIP: streams, events, graphs, modules, kernels, memory, devices, contexts, peer/IPC, error handling.
- OpenCL: platforms, devices, contexts, command queues, events, programs, kernels, memory objects, ICD behavior, error handling.
- Shared runtime: ROCr interaction, loader behavior, synchronization, multi-GPU behavior, thread safety, build/runtime packaging boundaries.

## Stop and ask

Ask before launching long builds, GPU jobs, or broad test suites. Escalate if expected behavior depends on undocumented compatibility requirements or if TDD is not practical for the scoped fix.
