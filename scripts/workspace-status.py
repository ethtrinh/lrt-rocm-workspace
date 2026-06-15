#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Alias:
    name: str
    path: Path | None
    notes: str
    placeholder: str | None = None


def parse_aliases(directory_map: Path) -> list[Alias]:
    if not directory_map.exists():
        raise FileNotFoundError(f"missing directory map: {directory_map}")

    aliases: list[Alias] = []
    row_re = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|")
    for line in directory_map.read_text(encoding="utf-8").splitlines():
        match = row_re.match(line)
        if not match:
            continue
        name, raw_path, notes = (part.strip() for part in match.groups())
        if name.lower() in {"alias", "---"} or set(name) == {"-"}:
            continue
        clean_path = raw_path.strip("`")
        placeholder = clean_path if clean_path.startswith("<") else None
        if not clean_path or clean_path == "Path" or set(clean_path) == {"-"} or placeholder:
            path = None
        else:
            path = Path(clean_path)
        aliases.append(Alias(name=name, path=path, notes=notes, placeholder=placeholder))
    return aliases


def git_summary(path: Path) -> str:
    if not (path / ".git").exists():
        return "not a git repo"
    branch = subprocess.run(
        ["git", "-C", str(path), "branch", "--show-current"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "-C", str(path), "status", "--short"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    ).stdout.strip()
    state = "clean" if not status else "modified"
    return f"git:{branch or 'detached-or-unborn'}:{state}"


def find_default_directory_map(repo_root: Path) -> Path:
    for candidate in [Path.cwd(), *Path.cwd().parents]:
        directory_map = candidate / "directory-map.md"
        if directory_map.exists():
            return directory_map
    return repo_root / "templates" / "directory-map.md"


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Show configured ROCm workspace paths.")
    parser.add_argument("--directory-map", type=Path, default=find_default_directory_map(repo_root), help="Path to directory-map.md")
    args = parser.parse_args()

    aliases = parse_aliases(args.directory_map)
    if not aliases:
        raise RuntimeError(f"no aliases found in {args.directory_map}")

    print(f"Workspace status from {args.directory_map}")
    print()
    for alias in aliases:
        if alias.placeholder:
            print(f"{alias.name:16} PLACEHOLDER {alias.placeholder}")
            continue
        if alias.path is None:
            print(f"{alias.name:16} UNSET")
            continue
        exists = alias.path.exists()
        detail = git_summary(alias.path) if exists and alias.path.is_dir() else "missing"
        print(f"{alias.name:16} {'OK' if exists else 'MISSING':7} {alias.path}  {detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
