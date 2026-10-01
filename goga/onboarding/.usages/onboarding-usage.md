# Project Onboarding — goga/onboarding

## Domain

Interactive initialization of a goga project: one session that surveys the
core configuration and the invited tool questions, applies the tool
amendments, and writes the project artifacts. Target audience: the init
command and embedding code.

## Facade

Import all types directly from `goga.onboarding`:

```python
from goga.onboarding import (
    CreatedFile,
    FileGenerator,
    InitLogic,
    Question,
    QuestionGroup,
    Questionnaire,
    SessionAnswers,
    SessionPlan,
    ToolParticipation,
    apply_skips,
    assemble_session_plan,
    core_questions,
)
```

## Usage

### Run a session with invited tools

```python
from goga.onboarding import FileGenerator, InitLogic, Questionnaire, ToolParticipation

logic = InitLogic(
    questionnaire=Questionnaire(),
    generator=FileGenerator(),
    participation=ToolParticipation(invited=["my-tool", "viewer"]),
)
exit_code = logic.run()
```

**Returns:** exit code (0 — success, nonzero — a session error).

**Session flow:** an existing `.goga/config.yml` ends the session
immediately — no questions, no tool events, no artifacts; otherwise the
session reads the installed version (clean error when unreadable),
collects the tool declarations, surveys the core tree and the tool blocks
with attribution, collects and commits the tool contributions, generates
`.goga/config.yml`, the Dockerfile, and the tool configs, and reports the
created files with tool attribution.

### Behavior guarantees

- A failing tool is soft: its contribution is discarded with a warning
  naming the tool and the reason; the session continues and returns 0.
- An invited but not installed tool name is a warning; the session
  continues.
- Session errors are single clean messages without a traceback: a broken
  package import (named), an unreadable installed version, an empty
  required `language` at generation (named).
- The image hints carry the minor tag of the installed goga version.

## Notes for the consumer

- Onboarding is filesystem-conditional: an existing `.goga/config.yml` is
  never rewritten — whoever created it first wins.
- Pass the deduplicated invited names in flag order to
  `ToolParticipation`; without invitations the session contains no tool
  blocks and matches the plain behavior.
