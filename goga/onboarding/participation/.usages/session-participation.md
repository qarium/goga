# Session participation — goga/onboarding/participation

## Domain

Mediating the tool participation in one onboarding session: the invitation
set, the declaration moment before the survey, the amendment moment after
it, and the staged commit of the surviving contributions. Target
audience: the session orchestrator.

## Public API

    from goga.onboarding import ToolParticipation

- `ToolParticipation(invited)` — the mediator of one session; `invited` is
  the deduplicated list of tool names from the command line, in flag
  order.
- `collect_declarations() -> list[ToolDeclaration]` — deliver
  `onboarding/declare_session` per tool. Warns for every invited name not
  among the installed tool packages; a failing hook of a tool drops that
  tool's whole declaration; an invited tool without a subscription
  participates silently.
- `collect_contributions(answers) -> list[ToolContribution]` — deliver
  `onboarding/amend_config` per tool after the survey. A failing hook
  discards the tool's whole contribution (amendments and files); the
  surviving contributions are committed: amendments apply to `answers` in
  delivery order, files are collected for generation.

## Ready-to-use pattern

### Run both moments around the survey

```python
from goga.onboarding import SessionAnswers, ToolParticipation

participation = ToolParticipation(invited=["my-tool", "viewer"])
declarations = participation.collect_declarations()  # moment one — before the survey
# ... assemble the plan, run the survey into answers ...
contributions = participation.collect_contributions(answers)  # moment two — after
```

## Notes for the consumer

- One registry per session — build and both deliveries share it; a broken
  package import is the single fatal case (a clean error naming the
  package).
- Tool failures are soft — every warning names the tool, the action, and
  the reason; the session and the other tools continue.
- The returned contributions carry the committed file buffers — hand them
  to the artifact generation.
