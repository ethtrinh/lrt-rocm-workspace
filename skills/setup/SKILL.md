---
name: setup
description: Use when setting up the lrt-rocm workspace for the first time, or when a new team member installs the plugin
---

Set up the ROCm development workspace. This skill discovers ROCm repositories on the filesystem, generates a directory map, and scaffolds the workspace structure.

## 1. Check if already set up

Look for `directory-map.md` in the current working directory.
- If it exists and has populated paths, ask: "Workspace already configured. Re-run setup to update paths?"
- If user declines, stop.

## 2. Find ROCm repositories

Search for TheRock and rocm-systems directories. Check these locations in order:

```bash
# Common locations to search
for dir in /develop /home/$USER /opt /workspace ~/src ~/projects ~/code; do
  find "$dir" -maxdepth 3 -name "TheRock" -type d 2>/dev/null
  find "$dir" -maxdepth 4 -name "rocm-systems" -type d 2>/dev/null
done
```

Also check if TheRock has submodules already checked out:
```bash
# If TheRock found at <path>, check for submodules
ls <therock_path>/rocm-systems/
ls <therock_path>/base/rocm-kpack/
ls <therock_path>/rocm-libraries/
```

### If TheRock is found:

Report the discovered paths and ask user to confirm:
> "Found TheRock at `<path>`. Is this the correct repository?"

### If TheRock is NOT found:

Ask the user:
> "I couldn't find a TheRock repository on this system. Would you like to:
> 1. Clone it now (I'll need a target directory)
> 2. Provide the path manually
> 3. Skip for now (you can update directory-map.md later)"

If cloning:
```bash
cd <user-chosen-dir>
git clone https://github.com/ROCm/TheRock.git
cd TheRock
git submodule update --init
```

## 3. Find or create build directory

Ask the user:
> "Where is your build directory? (default: `<therock_path>-build`)"

If it doesn't exist, ask if they want to create it.

## 4. Detect GPU architecture

```bash
# Try to detect GPU
rocminfo 2>/dev/null | grep "Name:" | head -5
```

If rocminfo is available, show detected GPUs and ask user to confirm the target architecture.
If not available, ask the user to specify their target GPU family (e.g., gfx1201, gfx942, gfx90a).

## 5. Scaffold workspace

Copy template files into the current working directory:

```bash
PLUGIN_ROOT="<path to this plugin>"

# Core files
cp "$PLUGIN_ROOT/templates/CLAUDE.md" ./CLAUDE.md
cp "$PLUGIN_ROOT/templates/ACTIVE-TASKS.md" ./ACTIVE-TASKS.md
cp "$PLUGIN_ROOT/templates/PYTHON-STYLE-GUIDE.md" ./PYTHON-STYLE-GUIDE.md
cp "$PLUGIN_ROOT/templates/adding-third-party-dep.md" ./adding-third-party-dep.md

# Task management structure
mkdir -p tasks/active tasks/completed
cp "$PLUGIN_ROOT/templates/example-task.md" ./tasks/active/example-task.md

# Workflows
mkdir -p workflows
cp "$PLUGIN_ROOT/workflows/build-pipeline.md" ./workflows/
cp "$PLUGIN_ROOT/workflows/debugging-tips.md" ./workflows/
```

## 6. Generate directory-map.md

Using the discovered paths, write `directory-map.md` with populated values:

```markdown
# ROCm Directory Map

## Repository Aliases

| Alias | Path | Notes |
|-------|------|-------|
| therock | <discovered_therock_path> | Main ROCm build repo |
| rocm-systems | <therock_path>/rocm-systems | ROCm Systems Superrepo (submodule) |
| rocm-libraries | <therock_path>/rocm-libraries | ROCm Libraries Superrepo (submodule) |
| rocm-kpack | <therock_path>/base/rocm-kpack | Kernel packaging tools (submodule) |
| workspace | <cwd> | This meta-workspace |

## Build Trees

### Active Builds
- **Main build:** `<build_dir>`
  - Configuration: Release
  - Target architecture: [<detected_gpu>]
  - Built ROCm installation is under `dist/rocm`
```

## 7. Update CLAUDE.md paths

Replace placeholder paths in `CLAUDE.md` with the discovered values:
- `<build-dir>` with the actual build directory
- `<therock-dir>` with the actual TheRock path
- `<your-gpu-family>` with the detected/chosen GPU family

## 8. VSCode integration (optional)

Ask: "Do you use VSCode for code review? The plugin includes an MCP extension for opening diffs directly in VSCode."

If yes:
1. Determine VSCode extensions path:
   - Remote: `~/.vscode-server/extensions/`
   - Local: `~/.vscode/extensions/`
2. Symlink the extension:
   ```bash
   ln -s "$PLUGIN_ROOT/vscode-plugins/stella-ide-mcp" <extensions_path>/stella-ide-mcp
   ```
3. Tell user to reload VSCode
4. Configure MCP: `claude mcp add --transport sse vscode http://127.0.0.1:3742/sse`

## 9. Summary

Report what was set up:
- TheRock path
- Build directory
- Target GPU architecture
- Files created/updated
- VSCode integration status

Say: "Workspace setup complete. Run `/lrt-rocm:setup` again anytime to update paths."
