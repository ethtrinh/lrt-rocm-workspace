# Issue #3447: Static Analysis of Hardlink Mutation (Inconclusive)

Date: 2026-02-16
Status: Smoking gun NOT found. Fix deployed (restructured flatten to post-split) but root cause unknown.

## The Bug

When `THEROCK_KPACK_SPLIT_ARTIFACTS=ON`, MIOpen_plugin intermittently fails to link against
`MIOpen/dist/lib/libMIOpen.so.1.0` with two failure variants:

1. **Truncation**: `ld.lld: error: section header table goes past the end of the file: e_shoff = 0x2e156220`
2. **SIGBUS**: Bus error in ld.lld's `hash_combine_range_impl` — mmap'd pages invalidated mid-read

Only occurs with split artifacts, never mono-arch. Timeline shows `miopen_lib` split actively
running when MIOpen_plugin's linker crashes.

## The Aliasing Chain

After stage.stamp, a single inode is aliased through 4 paths:

| # | Path | Created by |
|---|------|-----------|
| 1 | `MIOpen/stage/lib/libMIOpen.so.1.0` | cmake --install |
| 2 | `MIOpen/dist/lib/libMIOpen.so.1.0` | fileset_tool.py copy (stage step) |
| 3 | `artifacts-unsplit/miopen_lib_.../lib/libMIOpen.so.1.0` | artifact populate (os.link) |
| 4 | `dist/rocm/lib/libMIOpen.so.1.0` | artifact-flatten (os.link) |

ld.lld reads via path #2. The split step reads via path #3.

## What Was Statically Analyzed (Exhaustively)

### artifact_splitter.py — split() phases

**Phase 1: scan_prefix() → FileClassificationVisitor.visit_file()**
- `is_fat_binary()` in artifact_utils.py (line 95): reads 4 magic bytes via `open(file_path, "rb")`,
  then runs `readelf -S`. Both read-only on the unsplit file.

**Phase 2: process_database_files() (line 623)**
- `shutil.copy2(file_path, dest_path)` at line 661: reads from unsplit, writes to arch-specific
  output dir. Read-only on source. Uses `sendfile(2)` on Linux (kernel-level zero-copy read).

**Phase 3: copy_generic_artifact() (line 268)**
- `GenericCopyVisitor.visit_file()` at line 179: `shutil.copy2(file_path, dest_path)`.
  Reads from unsplit, writes to generic dir. **Creates new inode** (verified: shutil.copy2
  always creates new file, never hardlinks).

**Phase 4: process_fat_binaries() (line 295)**
- Creates `BundledBinary(binary_path)` where binary_path is in unsplit dir.
- `_detect_binary_type()`: runs `readelf -S` on unsplit file. Read-only.
- `_get_bundler_input()`: runs `objcopy --dump-section .hip_fatbin=<temp> <unsplit_file>`.
  Reads unsplit file, writes to temp. Read-only on source.
  NOTE: Called twice per binary (once for --list, once for --unbundle), no caching.
- `_list_bundled_targets()`: runs `clang-offload-bundler --list --input=<temp>`. Reads temp only.
- `_unbundle()`: runs `clang-offload-bundler --unbundle --input=<temp> --output=<temps>`.
  Reads temp, writes temps. Never touches unsplit file.
- `kernel_data = kernel_path.read_bytes()` at line 331: reads from temp dir.

**Phase 5: create_kpack_files()**
- Writes to arch-specific artifact dirs. Never touches unsplit files.

**Phase 6: inject_kpack_references() (line 485)**
- `binary_path` is in the GENERIC dir (mapped at lines 760-766 of split()).
  These are NEW inodes from Phase 3's shutil.copy2. NOT aliased to stage/dist.
- `kpack_offload_binary(input_path=binary_path, output_path=temp_output)` at line 576:
  `ElfSurgery.load()` does `bytearray(path.read_bytes())` — full read into RAM, no mmap,
  no held fd. Operates on generic copy only.
- `binary_path.unlink()` + `shutil.move(temp_output, binary_path)` at lines 586-587:
  Operates on generic copy (new inode). Does NOT touch unsplit files.

**Phase 7: write_artifact_manifest()**
- Writes manifest to generic dir. Irrelevant.

### binutils.py — BundledBinary

- `Toolchain.exec()`: `subprocess.check_output()` — standard subprocess, nothing unusual.
- `Toolchain.exec_capture_text()`: same.
- `UnbundledContents`: context manager that optionally deletes temp dir on close. No source mutation.

### elf/kpack_transform.py — kpack_offload_binary()

- `ElfSurgery.load(input_path)` at line 264: `bytearray(path.read_bytes())` — reads entire
  file into memory. No mmap, no held file descriptor. Only called on generic copies.
- `surgery.save_preserving_mode(output_path, original_mode)` at line 387: writes to output only.

### elf/surgery.py — ElfSurgery

- `load()` at line 148: `data = bytearray(path.read_bytes())`. Full copy to RAM.
- `save()`: `path.write_bytes(self._data)`. Writes to output path only.
- All modifications (add_section, write_bytes_at_offset, etc.) operate on the in-memory
  bytearray, never on the source file.

### pattern_match.py — copy_to()

- With `remove_dest=False` (used by artifact populate and flatten):
  - Same-inode check at line 173-176: skips if already hardlinked. Read-only metadata check.
  - `os.unlink(destpath)` at line 188: unlinks DESTINATION, not source. Safe for source inode.
  - `os.link(direntry.path, destpath)` at line 201: creates new directory entry pointing to
    same inode. Metadata-only operation. Does not modify file data.
  - Fallback `shutil.copy2` at line 216: reads source, writes new dest.

### artifact_builder.py — write_artifact()

- `pm.copy_to(destdir=destdir, remove_dest=False)` at line 284: creates hardlinks from
  stage/ to artifacts-unsplit/. Same as above — metadata only.

### fileset_tool.py — do_artifact()

- `shutil.rmtree(output_dir)` at line 68: removes artifacts-unsplit/ component dir before
  recreating. Unlinks files there (decrements link count), does NOT affect other hardlinks
  (stage/, dist/). On first build, this is a no-op (dir doesn't exist).

### artifacts.py — ArtifactPopulator

- `pm.copy_to(destdir=destdir, verbose=self.verbose, remove_dest=False)` at line 206:
  Creates hardlinks for flatten. Same safe pattern as above.

## shutil.copy2 on Linux

Python's `shutil.copy2` → `shutil.copyfile` → `_fastcopy_sendfile` → `os.sendfile(outfd, infd, offset, blocksize)`.
This is the Linux `sendfile(2)` syscall — kernel-level zero-copy from source fd to dest fd.
The source fd is opened read-only. The kernel reads pages from the page cache. This cannot
modify the source file.

## What Was NOT Analyzed

- **Kernel-level interactions**: Could overlayfs copy-up, page cache eviction under memory
  pressure, or concurrent sendfile + mmap on the same inode cause issues? Unknown.
- **Docker/container filesystem behavior**: CI runs in Docker containers on Azure VMs.
  The exact filesystem stack (overlayfs upper/lower, underlying block device) wasn't investigated.
- **ccache interactions**: ccache is active but shouldn't touch installed files.
- **cmake --install internals**: Uses `file(INSTALL)` which copies from build/ to stage/.
  On first build this creates new files; on rebuild it may replace. But the stage step
  completes (touches stage.stamp) before any of this concurrent activity begins.
- **Concurrent os.link + mmap**: While theoretically safe (link is metadata-only),
  the specific interaction of creating many hardlinks to an inode that's simultaneously
  mmap'd by ld.lld hasn't been tested in isolation.

## Conclusion

Every file operation on the shared inode is provably read-only through static analysis.
The mutation source is invisible at the Python/tool level. The fix (restructuring flatten
to post-split, reading from new inodes) breaks the aliasing chain regardless of root cause.

If the bug recurs after the fix, investigation should focus on:
1. Filesystem-level tracing (ftrace/bpftrace on the specific inode)
2. Reproducing with `strace -f -e trace=write,truncate,ftruncate` on the split process
3. Checking if the CI container's filesystem has any unusual mount options
4. Whether the issue correlates with memory pressure or I/O contention
