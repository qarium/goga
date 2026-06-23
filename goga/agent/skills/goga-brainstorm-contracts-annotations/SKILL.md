---
name: goga-brainstorm-contracts-annotations
description: Writing annotations at all levels for a single cell in the brainstorm contracts pipeline
---

# goga-brainstorm-contracts-annotations

## Algorithm

Write the implementation instructions for the given cell. Process every annotation target in order — cell header,
then each `Entity`/`Routine`, then each method/property — and for each one:

1. **Determine the level**: **global** (cell header), **type-level** (per `Entity`/`Routine`), or **member-level** (per
   method/property). The level selects the content — see `goga-cookbook` "When to write annotations". The **global**
   level additionally includes the **base annotations** from `goga-codemanifest-base` (the contract must comply with
   their constraints).

2. **Decide what content the annotation needs.** Do not invent content — derive it:
   - From **`[TYPE_DETAIL_REPORT]`** — responsibility, signature (params and return), methods/properties, interactions.
   - From the **usages-inline result** — the connected **Usages keys**; place each on the level where the practice applies.
   - From **`goga-cookbook`** ("Why") — the content categories that fit the level.

3. **Write the annotation** by `goga-cookbook` Annotations writing standard (elements, the `Algorithm:` placement
   rule), references, and the **sufficiency criterion**: if not sufficient for implementation, add the missing element
   (`Algorithm:` / `Requirements:` / `Constraints:`).

4. **Verify** against `goga-cookbook` Annotations — references resolve, no cross-level duplication, no implementation
   details.
