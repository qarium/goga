---
name: goga-codemanifest-base
description: Load project configuration from .goga/config.yml
---
# Load project configuration

## Purpose

Loads the project's base usages and annotations from the `.goga/config.yml` configuration file via `goga config` CLI commands.
These settings define project practices and instructions available to all CODEMANIFEST files.

---

## Behavior

Do not restate the content — apply the loaded usages and annotations in the context of the invoking skill.

---

## Instruction

### Step 1: Retrieve the project's base usages

Run `goga config codemanifest.usages` to retrieve the project's base usages from the `codemanifest.usages` section in `.goga/config.yml`.
These are project practices available to all CODEMANIFEST files.

### Step 2: Retrieve the project's base annotations

Run `goga config codemanifest.annotations` to retrieve the project's base annotations — text instructions
for the AI agent — from the `codemanifest.annotations` section in `.goga/config.yml`.

### Step 3: Process the result

If the commands return an "Option not found" error, the `codemanifest` section is absent from `.goga/config.yml`; no base
annotations or usages are defined — record this as a fact.

If the `codemanifest` section exists:

1. **Read the usage files** — for each usage listed in `codemanifest.usages`, read the corresponding md file
   from the `.goga/usages/` directory. These practices are mandatory when designing all CODEMANIFEST files.

2. **Analyze the base annotations** — if annotations contain instructions affecting CODEMANIFEST
   formation (e.g., structure requirements, conventions, constraints), record them as mandatory
   design constraints.

---
