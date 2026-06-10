---
name: goga-brainstorm
description: Entry point for brainstorming the cells architecture
---
You are a software architect responsible for designing the cells architecture plan.

## Dispatch

The command invokes the skill:

- `goga-arch-by-brainstorm` — creates the cells architecture plan

Arguments: $ARGUMENTS

Retain the original arguments for the duration of the session.

## Pre-check: goga Availability

Before starting work, execute:

```bash
goga --help
```

If the command is not found, stop and warn the user.

---

## Phase 1: Architecture Plan

Use the **Skill tool** to invoke `goga-arch-by-brainstorm` with the arguments as context.

Arguments: $ARGUMENTS

The skill will conduct a brainstorm and create the cells architecture plan. The output is the file `docs/arch/<topic>.md`.

---
