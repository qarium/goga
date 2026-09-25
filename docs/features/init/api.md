# Init — API

The facade of the domain package **`goga.onboarding`** — the interactive project initialization and the invited-tool session.

The signatures below are the CODEMANIFEST contract of the cells.

```python
InitLogic(questionnaire: Questionnaire, generator: FileGenerator,
          participation: ToolParticipation)
Questionnaire()
FileGenerator()
ToolParticipation(invited: list[str])
```

The facade re-exports the full contract surface:

```python
from goga.onboarding import (
    CreatedFile, FileGenerator, InitLogic, Question, QuestionGroup,
    Questionnaire, SessionAnswers, SessionPlan, ToolContribution,
    ToolDeclaration, ToolParticipation, apply_skips, assemble_session_plan,
    core_questions,
)
```

- `InitLogic` — the orchestrator: guard on the existing config, derive the image tag from the installed version, deliver both tool moments, run the survey, generate the artifacts, render the attributed file report.
- `Questionnaire` — the survey engine: asks the plan's core sections and tool blocks, records every value at its plan path.
- `FileGenerator` — the artifact generator: `.goga/config.yml`, the Dockerfile, the conventions download, and the tool configs under `.goga/tools/<tool>/`.
- `ToolParticipation` — the mediator delivering the two onboarding hook moments to the invited tools.
- `ToolDeclaration` / `ToolContribution` — the two hook-context surfaces a subscribed tool receives at those moments (see [Hooks](hooks.md)).
- `Question` / `QuestionGroup` — the declarative question records; `SessionAnswers` — the answer accumulator; `SessionPlan` / `assemble_session_plan` / `apply_skips` — the plan layer; `core_questions` — the core tree builder; `CreatedFile` — one report entry with tool attribution.

## Example

```python
from goga.onboarding import FileGenerator, InitLogic, Questionnaire, ToolParticipation

logic = InitLogic(
    questionnaire=Questionnaire(),
    generator=FileGenerator(),
    participation=ToolParticipation(invited=["my-tool", "viewer"]),
)
exit_code = logic.run()
```

**Returns:** exit code — `0` on success, nonzero on a session error or a user abort. A failing tool is soft: its contribution is discarded with a warning and the session still returns `0`. An existing `.goga/config.yml` ends the session immediately — no questions, no tool events, no artifacts.
