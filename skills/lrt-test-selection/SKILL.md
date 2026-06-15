---
name: lrt-test-selection
description: Use when selecting focused HIP/OpenCL tests or reproducers for an LRT runtime change or failure.
---

Select tests based on the runtime area touched.

## Process

1. Read `directory-map.md` for test, source, build, and ROCm install paths.
2. Split the work into independently testable runtime tasks if it spans multiple behaviors.
3. Identify affected APIs and runtime subsystem for the current task.
4. Search existing HIP tests, OpenCL tests, and focused reproducers for those APIs and nearby behavior.
5. Choose or add one smallest targeted failing test/reproducer for the current observable behavior before implementation.
6. Run the same test after implementation to prove the scoped task passes.
7. Repeat with the next behavior only after the current test is green.
8. Add broader tests only if the change crosses subsystems.
9. Record exact commands, environment, GPU architecture, and result per task.

## Runtime area hints

- Memory: allocation, copy, memset, map/unmap, managed memory, peer, IPC, OpenCL buffers/images/SVM where applicable.
- Queues/streams/events: HIP streams/events and OpenCL command queues/events, ordering, callbacks, waits, synchronization.
- Modules/programs/kernels: HIP modules/kernels and OpenCL programs/kernels, launch/enqueue behavior, attributes, code object or program loading.
- Devices/context: attributes, selection, reset/teardown, multi-GPU or multi-device behavior.
- Graphs: HIP graph capture, instantiate, update, launch, dependencies.
- Errors: invalid arguments, unsupported paths, async error reporting, OpenCL error-code compatibility.

If no existing test matches, propose a focused reproducer or new test location.
