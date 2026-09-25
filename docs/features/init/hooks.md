# Init — Hooks

The init domain exposes **two hook actions** for tool packages — the onboarding session participation:

| Address | Error class | Fires |
|---|---|---|
| `onboarding / declare_session` | soft | Before the survey — the tool declares its questions and skip requests. |
| `onboarding / amend_config` | soft | After the survey — the tool amends the collected answers and contributes config files. |

A tool reaches the session through an invitation: `goga init -t <tool-name>` (repeatable). A subscribed tool that was **not** invited still receives both contexts, but with `invited=False` — the expected behavior is to return immediately and stay silent. An invited name that is not installed produces a warning; the session continues.

## `declare_session` — the moment before the survey

The hook receives a `ToolDeclaration` context:

- `invited` — the invitation marker; check it first.
- `declare(item)` — buffer one `Question` or a one-level `QuestionGroup` (simple children only). The engine asks the buffered records itself after the delivery completes — **a hook is never called to survey**. Structural violations (a nested group, a non-record object) are refused with a warning; the element is not buffered.
- `skip(path)` — buffer one skip path: an unprefixed path addresses a core question (`"docker_image.base_image"`), a `<tool>.`-prefixed path addresses another tool's block. Unresolvable paths are a no-op with a warning.

The buffered questions are asked after the core sections under a `--- Tool: <tool> ---` attribution heading; the answers nest under the tool's key.

## `amend_config` — the moment after the survey

The hook receives a `ToolContribution` context:

- `invited` — the invitation marker.
- `answers` — an isolated read-only view of the collected answers: the core answers plus the tool's own under local names.
- `answer(id, value)` — amend an answer (e.g. `answer("tools", {...})`); amendments are committed via a recursive merge after the moment completes.
- `write_config(file, data)` — buffer one config file; the engine writes it under `.goga/tools/<tool>/<file>` — **a tool never writes its own config**.

Delivery is staged per tool: a tool's whole contribution (amendments and files) commits only after all its hooks succeed. A failing hook is soft — the tool's contribution is discarded with a stderr warning naming the tool, the action, and the reason; the session continues and the exit code never changes because of a tool.

The platform mechanism behind every hook action is covered in [Hooks](../hooks/index.md); the registration contract for tool authors in [Hooks — The registration contract](../hooks/hooks.md).
