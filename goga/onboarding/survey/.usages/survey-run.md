# Survey run — goga/onboarding/survey

## Domain

Assembling the onboarding survey plan and running it interactively: the
core question tree, the tool question blocks, the skip requests, and the
click-driven survey. Target audience: the session orchestrator that builds
a plan and collects answers into the answer space.

## Public API

    from goga.onboarding import core_questions, assemble_session_plan, apply_skips, Questionnaire

- `core_questions(image_tag, project_name, convention_exists) -> QuestionGroup`
  — the eight core sections in survey order; image hints carry
  `image_tag`; the convention section is omitted when the file exists.
- `assemble_session_plan(core, declarations) -> SessionPlan` — one root:
  core children, then one group per declaring tool in enumeration order.
  A repeated local name within a tool drops that element with a warning;
  the rest of the declaration stands. The core section names are reserved —
  a tool identity colliding with one drops the tool's whole block with a
  warning; the tool keeps its amendment rights.
- `apply_skips(plan, skips) -> SessionPlan` — removes the addressed
  subtrees; unprefixed paths address the core tree or the declaring
  tool's own block, `<tool>.`-prefixed paths address that tool's block;
  unknown paths are a no-op with a warning; pairs are addressed only as a
  whole.
- `Questionnaire().run(plan, answers)` — the interactive survey: session
  header, core sections, tool blocks with attribution headings; values are
  recorded into the answer space at their plan paths.

## Ready-to-use pattern

### Build the plan and run the survey

```python
from goga.onboarding import (
    SessionAnswers, Questionnaire, apply_skips, assemble_session_plan, core_questions,
)

core = core_questions(image_tag="1.3", project_name="my-app", convention_exists=False)
plan = assemble_session_plan(core, declarations)          # declarations: from tool participation
plan = apply_skips(plan, skips)                           # skips: (tool, raw path) pairs
answers = SessionAnswers()
Questionnaire().run(plan, answers)
```

## Notes for the consumer

- Skips are applied to the assembled plan as one set — order-independent;
  run the survey only after `apply_skips`.
- The core survey keeps its conditional patterns: the Dockerfile branch
  decides the image questions; a confirm-gated collection asks its gate
  first.
- Questions are declarative data — the engine asks them; nothing calls a
  tool hook to survey.
