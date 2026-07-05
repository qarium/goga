# Autonomous execution of plans with ralphex

## Tool

**ralphex** is a CLI utility for autonomous execution of plans via Claude Code. It orchestrates Claude Code sessions, executing tasks one by one with automatic commits and code review.

Repository: https://github.com/umputun/ralphex

## Plan format

Plans are markdown files with task sections. Each task contains checkboxes that Claude marks as they are completed.

```markdown
# Plan: Feature name

## Overview
Description of what needs to be implemented.

## Validation Commands
- `pytest tests/`
- `ruff check goga/`

### Task 1: Description of the first task
- [ ] Step 1
- [ ] Step 2
- [ ] Add tests

### Task 2: Description of the second task
- [ ] Step 1
- [ ] Step 2
```

**Rules:**
- Task headers: `### Task N:` or `### Iteration N:`
- Checkboxes: `- [ ]` (not done) / `- [x]` (done)
- The `## Validation Commands` section contains verification commands (tests, linters)
- Plans are placed in `docs/plans/`

## Usage in the goga project

### Starting execution

```bash
# Full cycle: tasks + review
ralphex docs/plans/my-feature.md

# Tasks only (without review)
ralphex --tasks-only docs/plans/my-feature.md

# Review only (without executing tasks)
ralphex --review docs/plans/my-feature.md

```

ralphex automatically:
1. Creates a branch from the plan file name
2. Executes tasks one by one
3. Runs validation after each task
4. Makes a commit after each completed task
5. Conducts code review (5 agents → codex → 2 agents)
6. Moves the plan to `completed/` on success

### Progress monitoring

```bash
# Web dashboard in browser
ralphex --serve docs/plans/my-feature.md
# will open http://localhost:8080

# Real-time execution log
tail -f progress-my-feature.txt
```

### Resuming after a failure

Completed tasks are already committed. Just restart:

```bash
ralphex docs/plans/my-feature.md
```

ralphex will find the first incomplete task (`- [ ]`) and continue from there.

### Adjusting execution progress

- **Change behavior** — edit `CLAUDE.md`, changes will take effect on the next task
- **Change structure** — stop (Ctrl+C), edit the plan, restart

## CLI options

| Flag                 | Description                                     | Default      |
|----------------------|-------------------------------------------------|--------------|
| `-m, --max-iterations`| Maximum task iterations                        | 50           |
| `-r, --review`       | Review only (without executing tasks)           | false        |
| `-e, --external-only`| External review only (codex/custom)             | false        |
| `-t, --tasks-only`   | Tasks only (without review)                     | false        |
| `--plan`             | Interactive plan creation                       | —            |
| `-s, --serve`        | Start web dashboard                             | false        |
| `-p, --port`         | Web dashboard port (with `--serve`)             | 8080         |
| `-d, --debug`        | Debug output                                    | false        |
| `--no-color`         | Disable colored output                          | false        |

## Configuration

ralphex uses `~/.config/ralphex/` (global) or `.ralphex/` in the project root (local).

**Priority:** CLI flags > local `.ralphex/` > global `~/.config/ralphex/` > built-in values

### Configuration structure

```
~/.config/ralphex/
├── config              # main config (INI format)
├── prompts/            # custom prompts
│   ├── task.txt
│   ├── review_first.txt
│   ├── review_second.txt
│   └── codex.txt
└── agents/             # custom review agents (*.txt)
```

### Key settings

| Option              | Description                          | Default      |
|---------------------|--------------------------------------|--------------|
| `claude_command`    | Claude CLI command (accepts any absolute path to a `*-as-claude.sh` wrapper script under `/home/goga/bin/`, not just the bare `claude` command) | `claude`     |
| `plans_dir`         | Directory with plans                 | `docs/plans` |
| `codex_enabled`     | Enable codex review phase            | `true`       |
| `task_retry_count`  | Number of retries per task           | `1`          |
| `finalize_enabled`  | Final step after review              | `false`      |

## Review agents

By default, ralphex launches 5 parallel agents:

| Agent               | Purpose                                  |
|---------------------|------------------------------------------|
| `quality`           | Bugs, security, race conditions          |
| `implementation`    | Code alignment with plan goals           |
| `testing`           | Test coverage and quality                |
| `simplification`    | Detecting over-engineering               |
| `documentation`     | Documentation update needs               |

Agents are customizable — you can add, remove, and modify them via `~/.config/ralphex/agents/`.

## Anti-patterns

- Do not run ralphex outside the root of a git repository
- Do not run on a branch with uncommitted changes (except the plan file) — either commit them or run `git stash`
- Do not run full plans on a non-master/main branch — ralphex will create a feature branch itself
- Do not forget the `## Validation Commands` section in the plan — without it, tasks are not verified
