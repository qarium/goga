---
name: goga-lang-disp
description: Language rule router
---
# Language Rule Router

Detects the project language and dispatches execution to the matching language-specific skill.
Apply this specification within the calling skill's context. Do not restate the contents — use them
for decision-making.

---

## How it works

1. Run `goga config language` to retrieve the project language
2. Dispatch to the matching language skill per the dispatch table
3. If the language is unsupported — halt and report to the user

## Dispatch table

| `language`   | `skill`                |
|--------------|------------------------|
| `python`     | `goga-cell-python`     |
| `javascript` | `goga-cell-javascript` |
| `golang`     | `goga-cell-go`         |
| `kotlin`     | `goga-cell-kotlin`     |
| `swift`      | `goga-cell-swift`      |
| `cpp`        | `goga-cell-cpp`        |

Invoke the target <`skill`> using the **Skill tool**.
