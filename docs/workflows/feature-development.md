# Feature Development — Workspace Context

You are in a feature development workflow. The goal is to design, plan, implement, and deliver a new feature or significant change.

## Before You Start

Read the task file in `tasks/active/` to understand what's being built and why.

## Pipeline

```
Brainstorm -> Plan -> Isolate -> Implement -> Review -> Finish
```

1. **Brainstorm** — `lrt-rocm:brainstorming` explores the idea, clarifies requirements, and produces a spec.
2. **Plan** — `lrt-rocm:writing-plans` turns the spec into an implementation plan with bite-sized tasks.
3. **Isolate** — `lrt-rocm:using-git-worktrees` creates an isolated workspace for the feature.
4. **Implement** — `lrt-rocm:subagent-driven-development` executes the plan task by task with two-stage review (spec compliance, then code quality).
5. **Review** — Use the review pipeline (see `docs/workflows/review-and-pr.md`) to iterate on changes.
6. **Finish** — `lrt-rocm:finishing-a-development-branch` presents options: merge, PR, keep, or discard.

## Skill Chain

Each skill hands off to the next:

| Skill | Produces | Consumed by |
|---|---|---|
| `brainstorming` | Spec document | `writing-plans` |
| `writing-plans` | Implementation plan with tasks | `subagent-driven-development` |
| `subagent-driven-development` | Implemented code, tests, commits | `finishing-a-development-branch` |

## Skip

Build logs, unrelated source trees, other task files — focus on the current feature's task file and plan.
