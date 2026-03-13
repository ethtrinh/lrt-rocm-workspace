#!/usr/bin/env python3
"""rk — TheRock superproject workflow tool.

Manages coordinated topic branches across TheRock and its submodules.
State is stored in .git/rk-state.json (never committed).
"""

import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants & colors
# ---------------------------------------------------------------------------

STATE_FILENAME = "rk-state.json"
STATE_VERSION = 1
BRANCH_PREFIX = "users"
BRANCH_NAMESPACE = "rk"

# ANSI color helpers — disabled when not a tty or NO_COLOR is set.
_USE_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ


def _sgr(code: str) -> str:
    return f"\033[{code}m" if _USE_COLOR else ""


BOLD = _sgr("1")
DIM = _sgr("2")
RED = _sgr("31")
GREEN = _sgr("32")
YELLOW = _sgr("33")
CYAN = _sgr("36")
RESET = _sgr("0")


def info(msg: str) -> None:
    print(f"{CYAN}rk:{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}rk: warning:{RESET} {msg}", file=sys.stderr)


def error(msg: str) -> None:
    print(f"{RED}rk: error:{RESET} {msg}", file=sys.stderr)


def die(msg: str) -> None:
    error(msg)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SubmoduleInfo:
    """Parsed entry from .gitmodules."""

    name: str
    path: str
    url: str
    branch: str | None = None


@dataclass
class TrackedSubmodule:
    """A submodule under topic management."""

    branch: str
    base_ref: str
    from_ref: str  # "HEAD" or "develop" — how it was started

    def to_dict(self) -> dict[str, str]:
        return {"branch": self.branch, "base_ref": self.base_ref, "from_ref": self.from_ref}

    @staticmethod
    def from_dict(d: dict[str, str]) -> "TrackedSubmodule":
        return TrackedSubmodule(branch=d["branch"], base_ref=d["base_ref"], from_ref=d["from_ref"])


@dataclass
class Topic:
    """A coordinated set of branches across repos."""

    therock_branch: str
    tracked: dict[str, TrackedSubmodule] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "therock_branch": self.therock_branch,
            "tracked": {k: v.to_dict() for k, v in self.tracked.items()},
        }

    @staticmethod
    def from_dict(d: dict) -> "Topic":
        tracked = {k: TrackedSubmodule.from_dict(v) for k, v in d.get("tracked", {}).items()}
        return Topic(therock_branch=d["therock_branch"], tracked=tracked)


@dataclass
class RkState:
    """Persisted state for rk."""

    version: int = STATE_VERSION
    username: str = ""
    active_topic: str = ""
    topics: dict[str, Topic] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "username": self.username,
            "active_topic": self.active_topic,
            "topics": {k: v.to_dict() for k, v in self.topics.items()},
        }

    @staticmethod
    def from_dict(d: dict) -> "RkState":
        topics = {k: Topic.from_dict(v) for k, v in d.get("topics", {}).items()}
        return RkState(
            version=d.get("version", STATE_VERSION),
            username=d.get("username", ""),
            active_topic=d.get("active_topic", ""),
            topics=topics,
        )


# ---------------------------------------------------------------------------
# Core utilities
# ---------------------------------------------------------------------------


def git(args: list[str], cwd: Path, *, capture: bool = True, check: bool = True) -> str:
    """Run a git command. Returns stdout when capture=True, else empty string."""
    cmd = ["git"] + [str(a) for a in args]
    try:
        if capture:
            result = subprocess.run(
                cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                check=check,
                stdin=subprocess.DEVNULL,
            )
            return result.stdout.strip()
        else:
            subprocess.run(
                cmd,
                cwd=str(cwd),
                check=check,
                stdin=subprocess.DEVNULL,
            )
            return ""
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else ""
        raise RuntimeError(
            f"git command failed: {shlex.join(cmd)}\n"
            f"  cwd: {cwd}\n"
            f"  exit code: {exc.returncode}\n"
            f"  stderr: {stderr}"
        ) from exc


def find_therock_root() -> Path:
    """Find TheRock repository root.

    Checks THEROCK_ROOT env var first, then walks up from cwd looking for
    a directory containing .gitmodules with a known TheRock submodule.
    """
    env_root = os.environ.get("THEROCK_ROOT")
    if env_root:
        root = Path(env_root)
        if (root / ".gitmodules").exists():
            return root
        die(f"THEROCK_ROOT={env_root} does not contain .gitmodules")

    cur = Path.cwd().resolve()
    while True:
        if (cur / ".gitmodules").exists() and (cur / ".git").exists():
            # Quick sanity check — look for a known TheRock submodule
            try:
                git(["config", "--file", ".gitmodules", "--get", "submodule.rocm-systems.path"], cwd=cur)
                return cur
            except RuntimeError:
                pass
        parent = cur.parent
        if parent == cur:
            break
        cur = parent
    die(
        "Cannot find TheRock root.\n"
        "  Run from inside TheRock, or set THEROCK_ROOT."
    )
    raise AssertionError("unreachable")  # for type checker


def _git_common_dir(root: Path) -> Path:
    """Return the git common dir (handles worktrees)."""
    raw = git(["rev-parse", "--git-common-dir"], cwd=root)
    p = Path(raw)
    if not p.is_absolute():
        p = (root / p).resolve()
    return p


def state_path(root: Path) -> Path:
    """Path to the state file, in the git common dir."""
    return _git_common_dir(root) / STATE_FILENAME


def load_state(root: Path) -> RkState:
    """Load state from disk. Returns empty state if file doesn't exist."""
    sp = state_path(root)
    if not sp.exists():
        return RkState()
    try:
        with open(sp) as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        die(
            f"Corrupt state file: {sp}\n"
            f"  {exc}\n"
            f"  Delete it or pass --reset-state to start fresh."
        )
    if data.get("version", 0) != STATE_VERSION:
        die(
            f"Unsupported state version {data.get('version')} in {sp}\n"
            f"  Expected version {STATE_VERSION}. Delete the file to start fresh."
        )
    return RkState.from_dict(data)


def save_state(root: Path, st: RkState) -> None:
    """Write state to disk atomically."""
    sp = state_path(root)
    tmp = sp.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(st.to_dict(), f, indent=2)
        f.write("\n")
    tmp.rename(sp)


def parse_gitmodules(root: Path) -> dict[str, SubmoduleInfo]:
    """Parse .gitmodules into a dict keyed by submodule name."""
    raw = git(["config", "--file", ".gitmodules", "--list"], cwd=root)
    modules: dict[str, dict[str, str]] = {}
    for line in raw.splitlines():
        if not line.startswith("submodule."):
            continue
        # submodule.<name>.<key>=<value>
        rest = line[len("submodule."):]
        # Find the last dot to split key from value
        eq_pos = rest.index("=")
        name_and_key = rest[:eq_pos]
        value = rest[eq_pos + 1:]
        # name may contain dots, key is the part after the last dot
        last_dot = name_and_key.rfind(".")
        if last_dot < 0:
            continue
        name = name_and_key[:last_dot]
        key = name_and_key[last_dot + 1:]
        modules.setdefault(name, {})
        modules[name][key] = value

    result: dict[str, SubmoduleInfo] = {}
    for name, attrs in modules.items():
        path = attrs.get("path", "")
        url = attrs.get("url", "")
        if not path:
            continue
        result[name] = SubmoduleInfo(
            name=name, path=path, url=url, branch=attrs.get("branch")
        )
    return result


def resolve_submodule(root: Path, query: str) -> SubmoduleInfo:
    """Resolve a user-supplied name/path to a SubmoduleInfo.

    Resolution order:
    1. Exact name match
    2. Exact path match
    3. Path basename match
    4. Substring match (error if ambiguous)
    """
    modules = parse_gitmodules(root)

    # 1. Exact name
    if query in modules:
        return modules[query]

    # 2. Exact path
    for mod in modules.values():
        if mod.path == query:
            return mod

    # 3. Path basename
    basename_matches = [m for m in modules.values() if Path(m.path).name == query]
    if len(basename_matches) == 1:
        return basename_matches[0]
    if len(basename_matches) > 1:
        names = ", ".join(m.name for m in basename_matches)
        die(f"Ambiguous submodule '{query}' matches basenames: {names}")

    # 4. Substring
    substr_matches = [m for m in modules.values() if query in m.name or query in m.path]
    if len(substr_matches) == 1:
        return substr_matches[0]
    if len(substr_matches) > 1:
        names = ", ".join(m.name for m in substr_matches)
        die(f"Ambiguous submodule '{query}' matches: {names}")

    # List available submodules
    available = ", ".join(sorted(modules.keys()))
    die(f"No submodule matching '{query}'.\n  Available: {available}")
    raise AssertionError("unreachable")


def get_pinned_commit(root: Path, submodule_path: str) -> str:
    """Get the commit a submodule is pinned to in the index (git ls-files --stage)."""
    line = git(["ls-files", "--stage", submodule_path], cwd=root)
    if not line:
        die(f"Submodule path '{submodule_path}' not found in index.")
    parts = line.split()
    if len(parts) < 2:
        die(f"Unexpected ls-files output for '{submodule_path}': {line}")
    return parts[1]


def get_username(st: RkState) -> str:
    """Resolve username: RK_USERNAME env > state > os.getlogin()."""
    env_user = os.environ.get("RK_USERNAME")
    if env_user:
        return env_user
    if st.username:
        return st.username
    try:
        return os.getlogin()
    except OSError:
        return os.environ.get("USER", "unknown")


def make_branch_name(username: str, topic: str) -> str:
    """Build the standard branch name."""
    return f"{BRANCH_PREFIX}/{username}/{BRANCH_NAMESPACE}/{topic}"


def is_skip_worktree(root: Path, path: str) -> bool:
    """Check if a path has skip-worktree flag set."""
    line = git(["ls-files", "-v", "--", path], cwd=root)
    return line.startswith("S")


def clear_skip_worktree(root: Path, path: str) -> None:
    """Clear skip-worktree flag on a path."""
    git(["update-index", "--no-skip-worktree", "--", path], cwd=root)


def set_skip_worktree(root: Path, path: str) -> None:
    """Set skip-worktree flag on a path."""
    git(["update-index", "--skip-worktree", "--", path], cwd=root)


def has_patches(root: Path, submodule_name: str) -> bool:
    """Check if a submodule has patches in patches/amd-mainline/."""
    patch_dir = root / "patches" / "amd-mainline" / submodule_name
    if not patch_dir.is_dir():
        return False
    return any(patch_dir.glob("*.patch"))


def is_dirty(cwd: Path) -> bool:
    """Check if a repo has uncommitted changes (ignoring nested submodule state)."""
    status = git(["status", "--porcelain", "--ignore-submodules=all"], cwd=cwd)
    return bool(status)


def current_branch(cwd: Path) -> str | None:
    """Get the current branch name, or None if detached."""
    try:
        return git(["symbolic-ref", "--short", "HEAD"], cwd=cwd)
    except RuntimeError:
        return None


def ahead_behind(cwd: Path, branch: str) -> tuple[int, int] | None:
    """Get ahead/behind counts relative to origin/<branch>. Returns None if no upstream."""
    try:
        raw = git(["rev-list", "--left-right", "--count", f"HEAD...origin/{branch}"], cwd=cwd)
        parts = raw.split()
        return (int(parts[0]), int(parts[1]))
    except RuntimeError:
        return None


def commit_count(cwd: Path, base: str) -> int:
    """Count commits from base to HEAD."""
    try:
        raw = git(["rev-list", "--count", f"{base}..HEAD"], cwd=cwd)
        return int(raw)
    except RuntimeError:
        return 0


def short_sha(cwd: Path, ref: str = "HEAD") -> str:
    """Get abbreviated commit hash."""
    return git(["rev-parse", "--short", ref], cwd=cwd)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_topic_create(root: Path, args) -> None:
    """Create a new topic and branch TheRock."""
    name = args.name
    st = load_state(root)

    if name in st.topics:
        die(f"Topic '{name}' already exists.")

    # Resolve and persist username
    username = get_username(st)
    if not st.username:
        st.username = username
        info(f"Username set to '{username}' (override with RK_USERNAME env var)")

    branch = make_branch_name(username, name)

    # Check for dirty tree
    if is_dirty(root):
        die("TheRock has uncommitted changes. Commit or stash before creating a topic.")

    # Create branch
    git(["checkout", "-b", branch], cwd=root, capture=False)
    info(f"Created branch: {branch}")

    st.topics[name] = Topic(therock_branch=branch)
    st.active_topic = name
    save_state(root, st)
    info(f"Topic '{name}' is now active.")


def cmd_topic_list(root: Path, args) -> None:
    """List all topics and their tracked submodules."""
    st = load_state(root)
    if not st.topics:
        info("No topics. Create one with: rk topic create <name>")
        return

    for name, topic in st.topics.items():
        active = " (active)" if name == st.active_topic else ""
        print(f"{BOLD}{name}{RESET}{GREEN}{active}{RESET}")
        print(f"  branch: {topic.therock_branch}")
        if topic.tracked:
            print(f"  tracked submodules:")
            for sub_name, sub in topic.tracked.items():
                print(f"    {sub_name}: {sub.branch} (base: {sub.base_ref[:10]})")
        else:
            print(f"  {DIM}no tracked submodules{RESET}")
        print()


def cmd_topic_switch(root: Path, args) -> None:
    """Switch to an existing topic, restoring TheRock and submodule branches."""
    name = args.name
    st = load_state(root)

    if name not in st.topics:
        available = ", ".join(st.topics.keys()) if st.topics else "(none)"
        die(f"No topic '{name}'. Available: {available}")

    topic = st.topics[name]

    # Check for dirty state in TheRock
    if is_dirty(root):
        die("TheRock has uncommitted changes. Commit or stash before switching topics.")

    # Check submodules of *current* topic for dirt
    if st.active_topic and st.active_topic in st.topics:
        current_topic = st.topics[st.active_topic]
        dirty_subs: list[str] = []
        for sub_name, sub in current_topic.tracked.items():
            sub_info = resolve_submodule(root, sub_name)
            sub_path = root / sub_info.path
            if sub_path.exists() and is_dirty(sub_path):
                dirty_subs.append(sub_name)
        if dirty_subs:
            die(
                f"Dirty tracked submodules in current topic '{st.active_topic}':\n"
                + "".join(f"  - {s}\n" for s in dirty_subs)
                + "Commit or stash changes before switching."
            )

    # Detach current topic's submodules
    if st.active_topic and st.active_topic in st.topics:
        current_topic = st.topics[st.active_topic]
        for sub_name, sub in current_topic.tracked.items():
            sub_info = resolve_submodule(root, sub_name)
            sub_path = root / sub_info.path
            if sub_path.exists():
                pinned = get_pinned_commit(root, sub_info.path)
                git(["checkout", pinned], cwd=sub_path, capture=False)

    # Switch TheRock branch
    git(["checkout", topic.therock_branch], cwd=root, capture=False)
    info(f"Switched TheRock to: {topic.therock_branch}")

    # Restore submodule branches
    for sub_name, sub in topic.tracked.items():
        sub_info = resolve_submodule(root, sub_name)
        sub_path = root / sub_info.path
        if not sub_path.exists():
            warn(f"Submodule directory missing: {sub_info.path} — run fetch_sources.py?")
            continue
        git(["checkout", sub.branch], cwd=sub_path, capture=False)
        # Ensure skip-worktree is cleared so pointer changes are visible
        if is_skip_worktree(root, sub_info.path):
            clear_skip_worktree(root, sub_info.path)
        info(f"  {sub_name}: checked out {sub.branch}")

    st.active_topic = name
    save_state(root, st)
    info(f"Topic '{name}' is now active.")


def cmd_track(root: Path, args) -> None:
    """Put a submodule under topic management."""
    st = load_state(root)
    if not st.active_topic:
        die("No active topic. Create one first: rk topic create <name>")

    topic = st.topics[st.active_topic]
    sub_info = resolve_submodule(root, args.submodule)

    if sub_info.name in topic.tracked:
        die(f"'{sub_info.name}' is already tracked in topic '{st.active_topic}'.")

    sub_path = root / sub_info.path
    if not sub_path.exists():
        die(f"Submodule directory missing: {sub_info.path}\n  Run fetch_sources.py first.")

    username = get_username(st)
    branch = make_branch_name(username, st.active_topic)
    from_ref = args.start or "HEAD"

    # Determine start point
    if from_ref == "HEAD":
        # Branch from the pinned commit
        start_commit = get_pinned_commit(root, sub_info.path)
    elif from_ref == "develop":
        # Fetch upstream first
        upstream = sub_info.branch or "develop"
        info(f"Fetching origin/{upstream} in {sub_info.path}...")
        git(["fetch", "origin", upstream], cwd=sub_path, capture=False)
        start_commit = f"origin/{upstream}"
        warn(
            f"Starting from upstream '{upstream}' — the submodule pointer in TheRock will diverge.\n"
            f"  You'll need to update it when ready."
        )
    else:
        start_commit = from_ref

    base_ref = git(["rev-parse", "--short", start_commit], cwd=sub_path)

    # Warn about patches
    if has_patches(root, sub_info.name):
        warn(
            f"'{sub_info.name}' has patches in patches/amd-mainline/.\n"
            f"  Your topic branch starts from {'the pinned commit' if from_ref == 'HEAD' else from_ref},\n"
            f"  which may or may not include applied patches. Be aware of conflicts."
        )

    # Create or checkout branch in submodule
    branch_exists = git(["branch", "--list", branch], cwd=sub_path)
    if branch_exists:
        git(["checkout", branch], cwd=sub_path, capture=False)
        info(f"Checked out existing branch in {sub_info.name}: {branch}")
    else:
        git(["checkout", "-b", branch, start_commit], cwd=sub_path, capture=False)
        info(f"Created branch in {sub_info.name}: {branch}")

    # Clear skip-worktree so pointer changes are visible
    if is_skip_worktree(root, sub_info.path):
        clear_skip_worktree(root, sub_info.path)
        info(f"Cleared skip-worktree on {sub_info.path}")

    topic.tracked[sub_info.name] = TrackedSubmodule(
        branch=branch, base_ref=base_ref, from_ref=from_ref
    )
    save_state(root, st)
    info(f"Now tracking '{sub_info.name}' in topic '{st.active_topic}'.")


def cmd_untrack(root: Path, args) -> None:
    """Remove a submodule from topic management, returning to pinned detached HEAD."""
    st = load_state(root)
    if not st.active_topic:
        die("No active topic.")

    topic = st.topics[st.active_topic]
    sub_info = resolve_submodule(root, args.submodule)

    if sub_info.name not in topic.tracked:
        die(f"'{sub_info.name}' is not tracked in topic '{st.active_topic}'.")

    sub_path = root / sub_info.path

    # Check for uncommitted changes
    if sub_path.exists() and is_dirty(sub_path):
        die(f"'{sub_info.name}' has uncommitted changes. Commit or stash first.")

    # Return to detached HEAD at pinned commit
    if sub_path.exists():
        pinned = get_pinned_commit(root, sub_info.path)
        git(["checkout", pinned], cwd=sub_path, capture=False)
        info(f"Detached {sub_info.name} at pinned commit {pinned[:10]}")

    # Restore skip-worktree if submodule has patches
    if has_patches(root, sub_info.name):
        set_skip_worktree(root, sub_info.path)
        info(f"Restored skip-worktree on {sub_info.path} (has patches)")

    del topic.tracked[sub_info.name]
    save_state(root, st)
    info(f"Untracked '{sub_info.name}' from topic '{st.active_topic}'.")


def cmd_status(root: Path, args) -> None:
    """Show cross-project status overview."""
    st = load_state(root)

    # TheRock status
    branch = current_branch(root) or "(detached)"
    dirty = " (dirty)" if is_dirty(root) else ""
    ab = ""
    if branch != "(detached)":
        counts = ahead_behind(root, branch)
        if counts:
            ahead, behind = counts
            parts = []
            if ahead:
                parts.append(f"ahead {ahead}")
            if behind:
                parts.append(f"behind {behind}")
            if parts:
                ab = f" ({', '.join(parts)})"

    clean_str = f"{GREEN}clean{RESET}" if not dirty else f"{YELLOW}dirty{RESET}"
    print(f"{BOLD}TheRock:{RESET} {branch}{ab}, {clean_str}")

    if st.active_topic:
        print(f"{BOLD}Topic:{RESET} {st.active_topic}")
    else:
        print(f"{DIM}No active topic{RESET}")
        return

    topic = st.topics.get(st.active_topic)
    if not topic:
        return

    # Tracked submodules
    if topic.tracked:
        print(f"\n{BOLD}Tracked:{RESET}")
        for sub_name, sub in topic.tracked.items():
            try:
                sub_info = resolve_submodule(root, sub_name)
            except SystemExit:
                print(f"  {RED}{sub_name}: cannot resolve submodule{RESET}")
                continue
            sub_path = root / sub_info.path
            if not sub_path.exists():
                print(f"  {RED}{sub_name}: directory missing{RESET}")
                continue

            sub_branch = current_branch(sub_path) or "(detached)"
            sub_dirty = is_dirty(sub_path)
            commits = commit_count(sub_path, sub.base_ref)

            # Check if pointer is in sync
            pinned = get_pinned_commit(root, sub_info.path)
            sub_head = git(["rev-parse", "HEAD"], cwd=sub_path)
            pin_sync = pinned == sub_head

            print(f"  {BOLD}{sub_name}{RESET}  {sub_branch}")
            commit_info = f"    {commits} commit{'s' if commits != 1 else ''} on topic (base: {sub.base_ref})"
            print(commit_info)
            if pin_sync:
                print(f"    pin: in sync {GREEN}\u2713{RESET}")
            else:
                print(f"    pin: {YELLOW}diverged{RESET} (pinned: {pinned[:10]}, HEAD: {sub_head[:10]})")
            if sub_dirty:
                print(f"    {YELLOW}dirty{RESET}")
            else:
                print(f"    {GREEN}clean{RESET}")

    # Untracked submodules summary
    modules = parse_gitmodules(root)
    untracked_names = sorted(set(modules.keys()) - set(topic.tracked.keys()))
    if untracked_names:
        patched = [n for n in untracked_names if has_patches(root, n)]
        print(f"\n{DIM}Untracked: {len(untracked_names)} submodules, all pinned{RESET}")
        if patched:
            for n in patched:
                print(f"  {DIM}{modules[n].path}: pinned (has patches){RESET}")


def cmd_push(root: Path, args) -> None:
    """Push submodules, bump pointers, push TheRock."""
    st = load_state(root)
    if not st.active_topic:
        die("No active topic.")

    topic = st.topics[st.active_topic]
    dry_run = args.dry_run
    only = args.only
    no_bump = args.no_bump

    # Filter tracked submodules
    tracked_items = list(topic.tracked.items())
    if only:
        sub_info = resolve_submodule(root, only)
        tracked_items = [(n, s) for n, s in tracked_items if n == sub_info.name]
        if not tracked_items:
            die(f"'{only}' is not tracked in topic '{st.active_topic}'.")

    if not tracked_items and not topic.therock_branch:
        die("Nothing to push.")

    # Phase 1: Push submodules
    pushed_subs: list[tuple[str, SubmoduleInfo]] = []
    for sub_name, sub in tracked_items:
        sub_info = resolve_submodule(root, sub_name)
        sub_path = root / sub_info.path
        cmd_str = f"git push origin {sub.branch}"

        if dry_run:
            info(f"[dry-run] ({sub_info.path}) {cmd_str}")
        else:
            info(f"Pushing {sub_name}...")
            git(["push", "origin", sub.branch], cwd=sub_path, capture=False)
        pushed_subs.append((sub_name, sub_info))

    # Phase 2: Bump pointers in TheRock
    pointer_changed = False
    if not no_bump and pushed_subs:
        for sub_name, sub_info in pushed_subs:
            if dry_run:
                info(f"[dry-run] (TheRock) git add {sub_info.path}")
            else:
                git(["add", sub_info.path], cwd=root)
                pointer_changed = True

        # Check if there are actual changes to commit
        if not dry_run:
            staged = git(["diff", "--cached", "--name-only"], cwd=root)
            if staged:
                bump_names = ", ".join(n for n, _ in pushed_subs)
                commit_msg = f"Bump tracked submodules for {st.active_topic}: {bump_names}"
                if dry_run:
                    info(f"[dry-run] (TheRock) git commit -m '{commit_msg}'")
                else:
                    git(["commit", "-m", commit_msg], cwd=root, capture=False)
                    info(f"Committed pointer bump.")
            else:
                info("No pointer changes to commit.")
                pointer_changed = False
        else:
            info(f"[dry-run] (TheRock) git commit -m 'Bump tracked submodules for {st.active_topic}'")

    # Phase 3: Push TheRock
    if dry_run:
        info(f"[dry-run] (TheRock) git push origin {topic.therock_branch}")
    else:
        info(f"Pushing TheRock...")
        git(["push", "origin", topic.therock_branch], cwd=root, capture=False)

    if dry_run:
        info("Dry run complete — no changes made.")
    else:
        info("Push complete.")


# ---------------------------------------------------------------------------
# Argparse
# ---------------------------------------------------------------------------


def build_parser() -> "argparse.ArgumentParser":
    import argparse

    parser = argparse.ArgumentParser(
        prog="rk",
        description="TheRock superproject workflow tool",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="TheRock root directory (default: auto-detect or THEROCK_ROOT)",
    )
    parser.add_argument(
        "--reset-state",
        action="store_true",
        help="Delete state file and start fresh",
    )
    sub = parser.add_subparsers(dest="command")

    # topic
    topic_parser = sub.add_parser("topic", help="Manage topics")
    topic_sub = topic_parser.add_subparsers(dest="topic_command")

    create_p = topic_sub.add_parser("create", help="Create a new topic")
    create_p.add_argument("name", help="Topic name (e.g., kpack-integration)")

    topic_sub.add_parser("list", help="List topics")

    switch_p = topic_sub.add_parser("switch", help="Switch to an existing topic")
    switch_p.add_argument("name", help="Topic name")

    # track
    track_p = sub.add_parser("track", help="Track a submodule in the active topic")
    track_p.add_argument("submodule", help="Submodule name or path")
    track_p.add_argument(
        "--from",
        dest="start",
        default="HEAD",
        help="Start point: HEAD (pinned commit, default), develop (upstream), or a ref",
    )

    # untrack
    untrack_p = sub.add_parser("untrack", help="Untrack a submodule")
    untrack_p.add_argument("submodule", help="Submodule name or path")

    # status
    sub.add_parser("status", help="Cross-project status overview")

    # push
    push_p = sub.add_parser("push", help="Push submodules and TheRock")
    push_p.add_argument("--dry-run", "-n", action="store_true", help="Show what would be done")
    push_p.add_argument("--no-bump", action="store_true", help="Don't bump submodule pointers")
    push_p.add_argument("--only", help="Push only this submodule")

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    root = args.root or find_therock_root()

    if args.reset_state:
        sp = state_path(root)
        if sp.exists():
            sp.unlink()
            info(f"Deleted state file: {sp}")

    dispatch: dict[str, object] = {
        "status": cmd_status,
        "track": cmd_track,
        "untrack": cmd_untrack,
        "push": cmd_push,
    }

    if args.command == "topic":
        if not hasattr(args, "topic_command") or not args.topic_command:
            # Print topic subcommand help
            parser.parse_args(["topic", "--help"])
            return
        topic_dispatch = {
            "create": cmd_topic_create,
            "list": cmd_topic_list,
            "switch": cmd_topic_switch,
        }
        handler = topic_dispatch.get(args.topic_command)
        if handler:
            handler(root, args)
        else:
            die(f"Unknown topic subcommand: {args.topic_command}")
    else:
        handler = dispatch.get(args.command)
        if handler:
            handler(root, args)
        else:
            die(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
