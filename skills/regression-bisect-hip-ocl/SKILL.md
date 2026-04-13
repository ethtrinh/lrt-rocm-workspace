---
name: regression-bisect-hip-ocl
description: Use when a HIP or OCL test that previously passed is now failing and you need to find which commit introduced the regression — drives git bisect with automated build and test at each step
---

# Regression Bisect for HIP/OCL

Automate git bisect in the rocm-systems monorepo to find the exact commit that introduced a HIP or OCL regression. Generates a bisect script for unattended execution, falls back to interactive mode when needed.

**REQUIRED BACKGROUND:** Use lrt-rocm:hip-ocl-monorepo-build for all build commands. Do not invent build flags or steps — follow that skill exactly.

## When to Use

| Situation | This skill applies |
|---|---|
| User says a test "used to pass" or "started failing" | Yes |
| User asks to "find which commit broke X" or "bisect" | Yes |
| User reports a regression in HIP or OCL functionality | Yes |
| User wants to debug why a test fails (not when it started) | No — use systematic-debugging |
| User wants to build HIP/OCL from scratch | No — use hip-ocl-monorepo-build |
| User wants to fix a known regression | No — use systematic-debugging after this skill identifies the commit |

## Scope

- **In scope:** CLR, HIP, hip-tests — finding the culprit commit
- **Out of scope:** Fixing the regression, ROCr-only bisecting, OCL-specific test infrastructure
- **Handoff:** Once the commit is identified, this skill is done. Suggest systematic-debugging if the user wants to fix it.

## Workflow

Four phases, executed sequentially:

```
Phase 1: Triage → Phase 2: Script Generation → Phase 3: Execution → Phase 4: Report
                                                    ↓ (if script fails)
                                              Interactive fallback
```

## Phase 1: Triage

Establish inputs before bisecting. Do not skip any step.

### Step 1 — Identify the oracle test

If the user already knows the failing test, confirm it and get the exact command to reproduce.

If not, help them find one:

1. Ask what symptom they're seeing (crash, wrong result, hang, build error)
2. Search hip-tests for relevant test binaries by keyword:
   ```bash
   find $HIPTESTS_DIR/catch/unit -name "*.cc" | xargs grep -l "<keyword>"
   ```
3. Run the candidate test to confirm it currently fails:
   ```bash
   cd $HIPTESTS_DIR/build/catch_tests/unit/<category>/
   ./<test_binary> "<test_pattern>"
   ```

The oracle test must:
- **Fail** at the bad commit
- Be deterministic (not flaky)
- Complete in a reasonable time (under 5 minutes per run)

### Step 2 — Establish the bad commit

Ask the user. Usually HEAD, but they may have already narrowed it.

```bash
cd /home/ethan-trinh/code/rocm-systems/projects
git log --oneline -1  # confirm current HEAD
```

### Step 3 — Establish the good commit

Ask the user when it last worked. Help them find it:

- **Specific SHA:** Use directly
- **Tag or release:** e.g., `rocm-6.3.0`
- **Approximate time:** Use git log to suggest candidates:
  ```bash
  git log --oneline --since="2 weeks ago" --until="1 week ago" | head -20
  ```
  User picks one. **Verify** the test passes at that commit:
  ```bash
  git stash  # if needed
  git checkout <good_candidate>
  # rebuild CLR per hip-ocl-monorepo-build section 2
  # run the oracle test
  # confirm it passes
  git checkout -  # return to previous branch
  git stash pop  # if needed
  ```

**If the test also fails at the "good" commit:** Stop. The good commit isn't good. Ask the user to go further back or pick a different test.

**After verification:** Return to the bad commit and rebuild CLR (and hip-tests if in scope) before proceeding to Phase 2.

### Step 4 — Determine rebuild scope

Check which projects changed in the bisect range:

```bash
git log --stat --oneline <good>..<bad> -- projects/clr/ projects/hip/ projects/hip-tests/
```

- If only `projects/clr/` and/or `projects/hip/` changed: rebuild CLR only at each step, reuse existing test binary
- If `projects/hip-tests/` also changed: rebuild tests at each step too
- Report this to the user and let them override

### Step 5 — Estimate bisect steps

```bash
git rev-list --count <good>..<bad>
```

Report: "N commits in range, approximately log2(N) = M bisect steps. Each step requires a rebuild (~X minutes). Estimated total: ~Y minutes."

## Phase 2: Script Generation

Generate a self-contained bisect script tailored to the specific regression. Present it to the user for review before running.

### Script Template

Generate the script and write it to `~/claude-rocm-workspace/scripts/bisect-<timestamp>.sh`:

```bash
#!/bin/bash
# Auto-generated bisect script for <test_name>
# Good: <good_sha>  Bad: <bad_sha>
# Estimated steps: <N>
# Generated: <timestamp>

PROJECTS_DIR="/home/ethan-trinh/code/rocm-systems/projects"
export HIP_DIR="$(readlink -f $PROJECTS_DIR/hip)"
export CLR_DIR="$(readlink -f $PROJECTS_DIR/clr)"
export HIPTESTS_DIR="$(readlink -f $PROJECTS_DIR/hip-tests)"
export ROCM_PATH=/opt/rocm

bisect_test() {
    # 1. Build CLR (incremental)
    cd "$CLR_DIR/build"
    if ! make -j$(nproc) || ! make install; then
        echo "CLR BUILD FAILED — skipping"
        exit 125  # git bisect skip
    fi

    # 2. Build hip-tests (only if in scope — conditionally included)
    cd "$HIPTESTS_DIR/build"
    if ! make build_tests -j$(nproc); then
        echo "HIP-TESTS BUILD FAILED — skipping"
        exit 125
    fi

    # 3. Run the oracle test
    if <test_command>; then
        exit 0   # good
    else
        exit 1   # bad
    fi
}

bisect_test
```

### Script Generation Rules

- Build commands must match `hip-ocl-monorepo-build` sections 2 and 4 exactly
- Exit 125 = build failure (git bisect skip), exit 0 = good, exit 1 = bad
- If hip-tests are not in scope (Phase 1, Step 4), remove the hip-tests build block entirely
- If the build dir doesn't exist, include the full cmake configure step before make
- In interactive mode (Mode B), detect CMakeLists.txt changes at a bisect step — if changed, re-run cmake configure instead of just make. In script mode, the script uses incremental make only; if configure changes cause failures, the script will skip and you can fall back to interactive.

### Before Running

1. Write the script to disk
2. Show the user the complete script
3. Ask: "Script ready. Run it, or edit first?"
4. Make the script executable: `chmod +x ~/claude-rocm-workspace/scripts/bisect-<timestamp>.sh`

## Phase 3: Execution

### Mode A: Script (default)

Run the generated script with git bisect:

```bash
cd /home/ethan-trinh/code/rocm-systems/projects
git bisect start <bad> <good>
git bisect run ~/claude-rocm-workspace/scripts/bisect-<timestamp>.sh
```

Monitor output for:
- Normal progress: `Bisecting: N revisions left to test after this (roughly M steps)`
- Excessive skips: If more than 50% of steps return exit 125, warn the user and suggest switching to interactive mode or narrowing the range
- Completion: `<sha> is the first bad commit`

When bisect completes, move to Phase 4.

### Mode B: Interactive fallback

Switch to interactive mode when:
- Script approach fails (too many skips, ambiguous results)
- User explicitly requests it
- Test is flaky (passes/fails inconsistently at the same commit)

In interactive mode, drive each step manually:

1. Note the current bisect commit:
   ```bash
   git log --oneline -1
   ```
2. Build CLR per hip-ocl-monorepo-build section 2 (and hip-tests if in scope)
3. Run the oracle test, capture full output
4. Analyze the result:
   - Clear pass → `git bisect good`
   - Clear fail (same failure as original) → `git bisect bad`
   - Different failure than expected → pause and ask the user whether to mark good/bad/skip
   - Build failure → `git bisect skip`
5. Repeat until bisect identifies the commit

### Switching Modes

If the user interrupts the script (Ctrl+C) during Mode A, the bisect state is preserved. Offer to continue interactively:

> "Bisect interrupted. The bisect state is still active — I can continue interactively from here, or reset with `git bisect reset`. What would you like?"

## Phase 4: Report

Once git bisect identifies the culprit commit, produce a summary.

### Report Template

```
## Bisect Result

**Culprit commit:** <full SHA>
**Author:** <name> (<email>)
**Date:** <date>
**Message:** <commit message>

### What changed
<output of `git show --stat <sha>`>

### Likely cause
<Claude's analysis of the diff — which specific change most likely caused the regression>

### Bisect path
- Steps taken: <N>
- Steps skipped: <M>
- Mode: <script | interactive | hybrid>

### Suggested next steps
- <recommendation based on diff analysis>
```

### Producing the Report

1. Run `git show --stat <culprit_sha>` to see what changed
2. Run `git show <culprit_sha>` and read the diff
3. Identify which specific change is most likely responsible:
   - If the commit is small (<100 lines changed), show the relevant portion of the diff
   - If large, highlight the files/hunks most related to the failing test
4. Suggest next steps based on the diff:
   - Unintentional side effect → "Consider reverting this commit"
   - Deliberate refactor → "The test or code may need updating to match the new behavior"
   - Multi-area commit → "Regression is likely in the <specific file> change — consider splitting this commit"

### Cleanup

Always run cleanup, even if the user aborts mid-bisect:

```bash
git bisect reset
```

Report: "Bisect complete. Ran `git bisect reset` — you're back on `<branch_name>`."

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Starting bisect without verifying the test passes at "good" commit | Phase 1 Step 3 requires verification — never skip it |
| Forgetting to rebuild after checkout | Script handles this automatically; interactive mode must always rebuild |
| Bisecting with a flaky test | If the test fails at "good" or passes at "bad", warn the user and ask for a more reliable oracle |
| Not resetting bisect after completion or abort | Phase 4 always runs `git bisect reset`; if aborting early, run it manually |
| Bisecting across a CMake configure change | Detect CMakeLists.txt in the changed files at a step — re-run cmake configure, not just make |
| Using `set -e` in the bisect script | This causes the script to exit on build failures instead of returning 125. Never use `set -e`. |

## Red Flags

Stop and reassess if you see any of these during execution:

- **>50% of steps skipped** — the commit range may span a period where the project didn't build. Suggest narrowing the range.
- **Test produces a different failure** — you may be chasing the wrong regression. Pause and confirm the failure signature with the user.
- **Bisect points to a merge commit** — the actual culprit is one of the individual commits in the merge. Investigate with `git log <merge>^..<merge>` and consider bisecting within the merge.
- **Test passes at both good and bad commits** — the regression may be intermittent or environment-dependent. This skill cannot reliably bisect flaky tests.
- **Build takes >30 minutes per step** — warn the user about total estimated time and suggest narrowing the range or using a faster test.
