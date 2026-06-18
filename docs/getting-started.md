# Getting Started

## Prerequisites

- Python 3.10 or later
- pip package manager

## Install goga

```bash
pip install goga
```

## Connect to agent

Install skills into an agent:

```bash
goga connect <agent>
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
5. **Agent** -- Select your AI executor: `claude`, `codex`
6. **Docker image** -- Choose a prebuilt language image or enter a custom one
7. **Dockerfile** -- Optionally generate a `Dockerfile` based on the selected image
8. **Environment variables** -- Set agent-specific env vars (e.g., `ANTHROPIC_API_KEY`)

### What `goga init` creates

```
.goga/
  config.yml              # Project configuration
  usages/
    conventions.md        # Language conventions (if downloaded)
Dockerfile                # Optional, if you chose to create one
```

## Develop your first feature

Goga is built around an agent-driven development cycle. You do not write CODEMANIFEST files by hand — you describe the feature, and the agent produces the architecture, the contract files, the design, and the implementation plan.

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

Start by formulating the task:

```text
/goga:propose <what you want to build>
```

The example above uses Claude Code style (`/goga:<command>`). For other agents, invoke the skill directly: `goga-propose`.

The agent walks you through an interactive dialogue, then produces `docs/tasks/<topic>.md`. From there, each subsequent command takes the previous artifact as input and produces the next one. See the [Workflow](workflow/index.md) section for the full algorithm of each step, including two shortcut paths for smaller changes.

## View

After the first task has produced cells on disk — for example, once you have run `/goga:apply` and the cell structure exists — you can visualize the project to inspect the result.

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
- [Configuration](configuration.md) -- Full config reference for `.goga/config.yml`
- [Cell](cell/index.md) -- Cell structure, usages, and CODEMANIFEST DSL reference
- [CLI Reference](cli/index.md) -- All available commands and options