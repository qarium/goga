# Build

Execute an approved plan — the bridge between the workflow and actual
code. The build engine reads the plan and produces the implementation,
one task per iteration, inside an isolated Docker container.

## Synopsis

```bash
goga build <plan> [OPTIONS]
```

The full reference — options, configuration, exit codes, and the
step-by-step algorithm — lives in the
[`goga build` CLI reference](../features/build/cli.md).

## What happens during a build

1. The host side validates preconditions: Docker is reachable, the
   `build` configuration is present with an agent, no `CODEMANIFEST`
   files are left uncommitted, and the host and image goga versions
   agree (see [Runtime — Pre-launch version check](../features/pipelines/runtime.md#pre-launch-version-check)).
2. The image is refreshed only with `--update`; a declared project
   Dockerfile is built once automatically on the first run even without
   it.
3. The build launches inside the configured image. Persistent build
   state lives under `~/.goga/runtime/builds/<project>/<branch>/` on the
   host — never inside the project directory — and survives across runs,
   so an interrupted build can be resumed (`--clean` wipes it for a
   fresh start).
4. Inside the container, the build engine executes the plan: one task
   per iteration, following the execution protocol (declaration →
   contract tests → implementation → interface verification → logic
   tests → debugging → contract re-verification → lint → completion →
   review → approval → next task). CODEMANIFEST files remain
   **read-only** throughout the build.
5. After a successful final pass, the plan moves to
   `<plan_dir>/completed/<plan_name>`. A failed run leaves it in place
   for resumption.

A single full-cycle pass runs by default. `--skip-review` runs a
tasks-only pass; a review executor that differs from the task executor
(or declares its own `env`) runs two passes — tasks, then review.

## When to use

- After `plan` and `review(plan)`, when the plan is approved.
- Whenever an execution plan exists under `.goga/history/` and is ready to be executed.

## Inputs and outputs

| | |
|---|---|
| **Input** | `.goga/history/<year>/<topic>/plan.md` — the execution plan |
| **Output** | Implemented code in the project tree; after a successful run the plan itself moves to `.goga/history/<year>/<topic>/completed/plan.md` |

## Examples

```bash
goga build .goga/history/<year>/json-export/plan.md
goga build .goga/history/<year>/json-export/plan.md --dry-run
goga build .goga/history/<year>/json-export/plan.md --clean   # fresh state
```

## What happens next

- The completed plan now lives in `.goga/history/<year>/<topic>/completed/` — nothing further reads it, but it stays for reference.
- Test the produced implementation manually.
- If bugs or defects are found — fix them with [`change`](change.md).
- Once the implementation is stable — run [`accept`](accept.md) for final sign-off.
