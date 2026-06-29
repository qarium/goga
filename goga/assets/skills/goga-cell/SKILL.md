---
name: goga-cell
description: DSL specification for cell structure and CODEMANIFEST files
---
# Goga Cell DSL

## Purpose

This skill provides the DSL specification that defines cell structure, CODEMANIFEST file syntax, and CODEMANIFEST file semantics. It specifies the required and optional elements within a cell and a CODEMANIFEST file.

Other skills invoke this skill to obtain context on DSL rules.

---

## Behavior

1. Read the file `dsl.md` located in the skill directory — it is the single authoritative source of the DSL specification.

2. Apply the specification to validate CODEMANIFEST correctness, covering: syntax, document structure, Imports rules, Usages, Annotations, types, mutations, and embeddings.

3. Do not restate the specification content — apply DSL rules within the context of the calling skill.
