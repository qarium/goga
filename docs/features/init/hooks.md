# Init — Hooks

The init domain exposes **two hook actions** for tool packages — the onboarding session participation.

## The actions

| Address | Error class | Fires |
|---|---|---|
| `onboarding / declare_session` | soft | Before the survey — the tool declares its questions and skip requests. |
| `onboarding / amend_config` | soft | After the survey — the tool amends the collected answers and contributes config files. |

A tool reaches the session through an invitation: `goga init -t <tool-name>` (repeatable). A subscribed tool that was **not** invited still receives both contexts, but with `invited=False` — the expected behavior is to return immediately and stay silent. An invited name that is not installed produces a warning; the session continues.

## The contexts

### `declare_session` — `ToolDeclaration` (soft)

One view per tool; a crashing hook drops the tool's whole contribution with a warning.

| Read | Type | Meaning |
|---|---|---|
| `tool` | `str` | Your tool identity. |
| `invited` | `bool` | The invitation marker — check it first. |
| `questions` | <code>list[Question \| QuestionGroup]</code> | The buffered records, in declaration order. |
| `skips` | `list[str]` | The buffered skip paths, in declaration order. |

| Method | Effect |
|---|---|
| `declare(item)` | Buffers one `Question` or a one-level `QuestionGroup` (simple children only). Structural violations — a nested group, a non-record object — are refused with a warning, never raised; the element is not buffered. |
| `skip(path)` | Buffers one skip path — an unprefixed path addresses the core tree or your own block, a `<tool>.`-prefixed path addresses another tool's block. Unresolvable paths are a no-op with a warning. |

```python
from goga.onboarding import Question, QuestionGroup


def declare_session(context):
    if not context.invited:
        return  # contract rule: return immediately
    context.declare(Question(id="token", kind="input", prompt="Service token"))
    context.declare(
        QuestionGroup(
            id="reporting",
            prompt="Reporting",
            children=[Question(id="enabled", kind="confirm", prompt="Enable reporting?", default=False)],
        )
    )
    context.skip("docker_image.base_image")  # unprefixed — core tree or own block
```

The context is read-only — attribute assignment is blocked (the platform proxy enforces it); `declare` / `skip` are the only write channels. The engine asks the buffered records itself after the delivery completes — **a hook is never called to survey**. The buffered questions are asked after the core sections under a `--- Tool: <tool> ---` attribution heading; the answers nest under the tool's key.

### `amend_config` — `ToolContribution` (soft)

One view per tool; the contribution commits only after all the tool's hooks succeed.

| Read | Type | Meaning |
|---|---|---|
| `tool` | `str` | Your tool identity. |
| `invited` | `bool` | The invitation marker — check it first. |
| `answers` | `dict` | An isolated read-only view of the collected answers — the core answers plus your own under local names; other tools' answers are never present. |
| `amendments` | <code>list[tuple[str, str \| bool \| dict]]</code> | The buffered answer amendments — path and value, in call order. |
| `files` | `list[tuple[str, dict]]` | The buffered config files — file name and data, in call order. |

| Method | Effect |
|---|---|
| `answer(id, value)` | Buffers one amendment by dot-path (value: `str`/`bool`/`dict`, e.g. `answer("tools", {...})`); committed by a recursive merge after the moment completes. |
| `write_config(file, data)` | Buffers one config file — the engine writes it under `.goga/tools/<tool>/<file>` — **a tool never writes its own config**. |

```python
def amend_config(context):
    if not context.invited:
        return
    if context.answers.get("reporting", {}).get("enabled"):
        context.answer("pipeline.env", {"REPORT_URL": "https://example.com"})
        context.answer("tools", {"my-tool": "latest"})
        context.write_config("service.yml", {"token_source": "env", "interval": 60})
```

The context is read-only — attribute assignment is blocked (the platform proxy enforces it); `answer` / `write_config` are the only write channels. Delivery is staged per tool: a tool's whole contribution (amendments and files) commits only after all its hooks succeed. A failing hook is soft — the tool's contribution is discarded with a stderr warning naming the tool, the action, and the reason; the session continues and the exit code never changes because of a tool.

## Integration scenarios

- **Conditional onboarding questions** — declare your block in `declare_session` guarded by `context.invited` (and your own detection of what the project already carries); the engine asks it under your tool's heading only when the session invited you.
- **Derived config files** — in `amend_config`, read `context.answers[...]` and buffer `context.write_config(...)`; the engine writes the file under `.goga/tools/<tool>/`, so a tool never writes its own config.

The platform mechanism behind every hook action is covered in [Hooks](../hooks/index.md); the registration contract for tool authors in [Hooks — The registration contract](../hooks/hooks.md).

## The fact records

| Record | Fields |
|---|---|
| `Question` | `id` (unique among the siblings of its tree position), `kind` (choice, input, confirm, or pairs), `prompt`, `choices`: <code>list[str] \| None</code> (the offered values of the choice kind), `default`: <code>str \| bool \| None</code> (the preselected value or the input default; a bool for the confirm kind), `keys`: <code>list[str] \| None</code> (the proposed keys of the pairs kind). |
| `QuestionGroup` | `id`, `prompt`: <code>str \| None</code> (the optional section heading; a purely structural node carries none), `children`: <code>list[Question \| QuestionGroup]</code> — one level only, no nested groups. |
