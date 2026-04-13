---
name: vscode-mode
description: Use when setting VSCode integration mode (local or remote)
---

Set VSCode integration mode. Argument: `$ARGUMENTS` (local | remote)

## Usage

- `/lrt-rocm:vscode-mode local` - Call `code` directly (same machine)
- `/lrt-rocm:vscode-mode remote` - Use file watcher (SSH/remote development)

## Action

1. Create `.state/` directory if needed: `mkdir -p .state`
2. Write mode to `.state/vscode-mode`:
   - If argument is "local": write "local"
   - If argument is "remote": write "remote"
   - If no arg or invalid: show current mode and usage

## Output

Confirm the mode was set. If remote, remind user to start the watcher:
```
./scripts/vscode-watcher.sh
```
