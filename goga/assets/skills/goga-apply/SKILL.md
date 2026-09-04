---
name: goga-apply
description: Materialize an architectural plan into the cells file structure
---
You are an architectural plan materialization engineer. You transform plans from the path printed by `goga history path -f arch.md` into a cells file structure (CODEMANIFEST, `.usages/`).

## Dispatch

The command invokes the skill:

- `goga-cells-by-brainstorm` — materializes the cells architecture plan

Arguments: $ARGUMENTS

## Pre-flight check: goga availability

Before proceeding, verify tool availability:

```bash
goga --help
```

If the command is unavailable — halt and notify the user.

### Resolving the architecture file

Check if the path printed by `goga history path -f arch.md` exists:

- **Does not exist** — stop and ask the user to run `/goga:brainstorm` first.
- **Exists** — proceed to Materialization.

---

## Materialization

Use the **Skill tool** to invoke `goga-cells-by-brainstorm` with the printed path as the argument.

The skill reads the plan from the path printed by `goga history path -f arch.md` and materializes it into a cells file structure (CODEMANIFEST, `.usages/`).

---
