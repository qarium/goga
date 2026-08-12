# Getting Started

## Prerequisites

- Python 3.10 or later
- pipx package manager

## Install goga

```bash
pipx install goga
```

## Connect to agent

Install skills into an agent:

```bash
goga connect <agent>
```

## Upgrade goga

Move to a new goga release and re-sync every connected agent in one step — no need to call pip directly:

```bash
goga upgrade
```

## Initialize a project

Run the interactive initialization wizard:

```bash
goga init
```

The wizard will prompt you for:

1. **Language** -- Select your project language: `python`, `golang`, `kotlin`, `swift`, or `javascript`
2. **Convention** -- Optionally download language-specific conventions from the goga-lang-conventions repository
3. **Codemanifest usages** -- Optional named practices (key-value pairs) for your project
4. **Codemanifest annotations** -- Optional free-text instructions for AI agents
5. **Agent** -- Confirm-gated (defaults to No). Decline to skip the build agent, or accept and choose `claude` or `codex`
6. **Custom Dockerfile** -- Optionally create a custom Dockerfile (suggested path `.goga/Dockerfile`). This decision drives the next step: image semantics differ between the two branches.
7. **Docker image** (depends on step 6):
   - **If you create a Dockerfile**, the image is **built from it**, so you provide two values: the **base image** for the `FROM` line (chosen from the language-specific list), and a **built image name/tag** (what `goga build` tags with `docker build -t`). The built image name defaults to `<project-name>:latest`, where `<project-name>` is derived from your git `origin` remote URL; when no git remote is available, no default is offered and the name is required.
   - **If you skip the Dockerfile**, you pick a **pre-built image to pull** from the language-specific list (or enter a custom one).
8. **Environment variables** -- Set agent-specific env vars (e.g., `ANTHROPIC_API_KEY`)
9. **Pipeline agent** -- Confirm-gated (defaults to No). Decline to skip the pipeline agent, or accept and choose `claude` or `codex`. Does not inherit the build agent from step 5 — the two are collected independently
10. **Pipeline environment variables** -- Set env vars for the pipeline container (e.g., `ANTHROPIC_API_KEY`)

### What `goga init` creates

```
.goga/
  config.yml              # Project configuration
  usages/
    conventions.md        # Language conventions (if downloaded)
  Dockerfile              # Optional, if you chose to create one (default location)
```

## Develop your first feature

Goga is built around an agent-driven development cycle. You do not write CODEMANIFEST files by hand — you describe the feature, and the agent produces the architecture, the contract files, the design, and the implementation plan. The cycle can be driven in two ways: run it automatically with a single pipeline command, or step through it manually for full control over each artifact.

The full cycle:

```
propose → review(task)
   → brainstorm → review(arch)
      → apply → design → review(design)
         → plan → review(plan)
            → goga build
               → change (bugfix loop)
                  → accept
```

### Automated cycle

The fastest path. Goga ships ready-to-use pipelines that run the full cycle inside an isolated container, with agent credentials forwarded automatically. Run the `feature` pipeline from your agent:

```bash
goga pipeline feature
```

The pipeline walks all eleven stages — propose → task-review → brainstorm → architecture-review → apply-architecture → code-design → design-review → coding-plan → plan-review → commit-architecture → accept-result — and pauses at every `communication` stage to ask for your input before moving on. Three more shipped pipelines cover other lifecycles:

```bash
goga pipeline bugfix     # root-cause analysis and defect resolution
goga pipeline patch      # refactoring or minimal change with a plan
goga pipeline review     # scoped review of code, contracts, docs, then lint/format/tests
```

See [Pipelines](pipelines/index.md) for the full functional model, and [Shipped Pipelines](pipelines/shipped.md) for the per-pipeline walkthrough.

### Manual cycle

If you want explicit control over each step instead of running the whole cycle automatically, formulate the task by hand:

```text
/goga:propose <what you want to build>
```

> The slash-command form `/goga:<command>` works in agents that consume the goga command bundle — currently `claude`, `opencode`, and `qwen` (see [`goga connect`](cli/connect.md)). Codex and cursor do not register commands; in those agents invoke the skill directly: `goga-propose` (Codex uses the `$` prefix — `$goga-propose`).

The agent walks you through an interactive dialogue, then produces `docs/tasks/<topic>.md`. From there, each subsequent command takes the previous artifact as input and produces the next one. See the [Workflow](workflow/index.md) section for the full algorithm of each step, including two shortcut paths for smaller changes.

## View

After the first task has produced cells on disk — for example, once you have run `goga-apply` (or `/goga:apply` in a command-capable agent — see [above](#manual-cycle)) and the cell structure exists — you can visualize the project to inspect the result.

Get a textual hierarchy of all cells:

```bash
goga schema
```

Open an interactive dependency graph in the browser via the built-in `viewer` tool:

```bash
goga schema | goga tool viewer
```

The graph shows cells, their imports, and the connections between them — useful for verifying that the materialized architecture matches what you designed.

## Next steps

- [Workflow](workflow/index.md) -- The agent-driven feature development cycle
- [Configuration](configuration/index.md) -- Full config reference for `.goga/config.yml`
- [Cell](cell/index.md) -- Cell structure, usages, and CODEMANIFEST DSL reference
- [CLI Reference](cli/index.md) -- All available commands and options