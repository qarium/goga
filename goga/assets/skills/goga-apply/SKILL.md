---
name: goga-apply
description: Materialize an architectural plan into the cells file structure
---
You are an architectural plan materialization engineer. You transform plans from `.goga/history/<year>/<topic>/arch.md` into a cells file structure (CODEMANIFEST, `.usages/`).

## Dispatch

The command invokes the skill:

- `goga-cells-by-brainstorm` — materializes the cells architecture plan

Arguments: $ARGUMENTS

Retain the original arguments for the duration of the session.

### Resolving the architecture file

Resolve `<topic>`:

1. **Arguments supplied** — use the arguments as `<topic>`.
2. **No arguments** — scan `.goga/history/*/` topic directories for `arch.md` (year segment must be 4 digits) and present the list via **AskUserQuestion**:
    - **Directory missing or empty** — halt and report the error.
    - **Single file** — use its filename (without extension) as `<topic>`.
    - **Multiple files** — present the list via AskUserQuestion and prompt for selection.

## Pre-flight check: goga availability

Before proceeding, verify tool availability:

```bash
goga --help
```

If the command is unavailable — halt and notify the user.

---

## Materialization

Use the **Skill tool** to invoke `goga-cells-by-brainstorm` with `<topic>` as the argument.

The skill reads the plan from `.goga/history/<year>/<topic>/arch.md` and materializes it into a cells file structure (CODEMANIFEST, `.usages/`).

---
