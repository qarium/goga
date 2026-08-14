# Project Onboarding — goga/onboarding

## Overview

The `goga.onboarding` package provides interactive goga project onboarding —
collecting user input and generating configuration files. Onboarding is
filesystem-conditional: sections whose artefacts already exist are skipped
(relevant when an external template generator has run first).

## Facade

Import all types directly from `goga.onboarding`:

```python
from goga.onboarding import InitLogic, Questionnaire, FileGenerator, InitAnswers, GogaConfigAnswers
```

## Usage

### InitLogic — orchestrator

```python
from goga.onboarding import InitLogic, Questionnaire, FileGenerator

questionnaire = Questionnaire()
generator = FileGenerator()
logic = InitLogic(questionnaire=questionnaire, generator=generator)

exit_code = logic.run()
```

### InitLogic.run()

Run an interactive user survey and generate project files.

**Returns:** exit_code (0 — success, 1 — error)

**Behavior:**
- Create the .goga/ directory if it does not exist
- Generate .goga/config.yml with minimal configuration — SKIPPED when goga_config is None (the file already exists)
- If the user opted in — download .goga/usages/conventions.md
- If the user requested a custom Dockerfile — create it with `FROM {dockerfile_base_image}`;
  the top-level `image` field holds the name of the image built from it (the `docker build -t` tag)

### Data

`InitAnswers` — response container holding `GogaConfigAnswers`.
`goga_config`: `GogaConfigAnswers | None`. `None` = do not write .goga/config.yml
(used when the file already exists).

`GogaConfigAnswers` fields: `language`, `agent`, `image`, `pipeline_agent`,
`pipeline_env`, `env`, `codemanifest_usages`, `codemanifest_annotations`,
`dockerfile_path`, `dockerfile_base_image` (see CODEMANIFEST).

## Survey flow

`Questionnaire.ask_goga_config()` returns `GogaConfigAnswers | None`: If
.goga/config.yml already exists -> returns None (the whole config survey is
skipped). Otherwise proceeds: language → convention →
codemanifest_usages → codemanifest_annotations → agent → dockerfile → (image branch)
→ env → pipeline_agent → pipeline_env.

The image branch depends on the Dockerfile decision:
- **With a Dockerfile** (`dockerfile_path` set):
  - `ask_base_image(language)` — the `FROM` baseline (language hints, default = last entry).
  - `ask_image_name(language=None, default=<git-project-name>:latest)` — the name/tag for
    the image built from the Dockerfile. The default is resolved from the git project name
    (falling back to no default when the name is unavailable):
    `<name>:latest` when the git remote is available; **when the git name is unavailable,
    no default is offered and `image` is required**. Passing `language` uses the
    `{language}-image:latest` default.
- **Without a Dockerfile** (`dockerfile_path` None): `ask_image(language)` — pre-built
  image to PULL.

## Conditional onboarding

When onboarding runs after an external template generator has produced
`.goga/config.yml` and/or `.goga/usages/conventions.md`, onboarding detects
the existing artefacts and skips the corresponding survey sections instead
of asking twice. This is composition, not arbitration: an existing
`.goga/config.yml` is not rewritten — whoever created it first wins.

## Per-field survey methods

- `ask_language() -> str`
- `ask_base_convention() -> (codemanifest_usages, codemanifest_annotations)` — skipped when .goga/usages/conventions.md exists
- `ask_codemanifest_usages(prefill: dict | None = None) -> dict | None`
- `ask_codemanifest_annotations(prefill: str | None = None) -> str | None`
- `ask_agent() -> str | None`
- `ask_dockerfile_path() -> str | None`
- `ask_image(language: str) -> str` — pre-built image to PULL (no-Dockerfile branch)
- `ask_base_image(language: str) -> str` — FROM baseline (Dockerfile branch)
- `ask_image_name(language: str | None = None, default: str | None = None) -> str` — name/tag for the built image (Dockerfile branch)
- `ask_env(agent: str | None) -> dict | None`
- `ask_pipeline_agent() -> str | None`
- `ask_pipeline_env(pipeline_agent: str | None) -> dict | None`

## Generated .goga/config.yml structure

(`language`, `image`, `dockerfile`, `build`, `pipeline`, `codemanifest`
field order; see CODEMANIFEST `FileGenerator`.)

## Anti-patterns

- Do not write `build.image` — the Docker image is the top-level `image` field.
- Do not force-emit empty `build:`/`pipeline:` blocks.
- Do not inherit `agent` into `pipeline_agent`.
- Do not regenerate .goga/config.yml when goga_config is None — None means skip.
