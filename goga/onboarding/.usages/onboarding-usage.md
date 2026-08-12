# Project Onboarding — goga/onboarding

## Overview

The `goga.onboarding` package provides interactive goga project onboarding —
collecting user input and generating configuration files.

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
- Generate .goga/config.yml with minimal configuration
- If the user opted in — download .goga/usages/conventions.md
- If the user requested a custom Dockerfile — create it with `FROM {dockerfile_base_image}`;
  the top-level `image` field holds the name of the image built from it (the `docker build -t` tag)

### Data

`InitAnswers` — response container holding `GogaConfigAnswers`.

`GogaConfigAnswers` fields: `language`, `agent`, `image`, `pipeline_agent`,
`pipeline_env`, `env`, `codemanifest_usages`, `codemanifest_annotations`,
`dockerfile_path`, `dockerfile_base_image` (same semantics as before — see CODEMANIFEST).

## Survey flow

`Questionnaire.ask_goga_config()` proceeds: language → convention →
codemanifest_usages → codemanifest_annotations → agent → dockerfile → (image branch)
→ env → pipeline_agent → pipeline_env.

The image branch depends on the Dockerfile decision:
- **With a Dockerfile** (`dockerfile_path` set):
  - `ask_base_image(language)` — the `FROM` baseline (language hints, default = last entry).
  - `ask_image_name(language=None, default=<git-project-name>:latest)` — the name/tag for
    the image built from the Dockerfile. The default is resolved from the git project name
    via the shared `resolve_project_name` helper (re-exported from `goga.config`):
    `<name>:latest` when the git remote is available; **when the git name is unavailable,
    no default is offered and `image` is required**. Passing `language` retains the legacy
    `{language}-image:latest` default (backward-compatible).
- **Without a Dockerfile** (`dockerfile_path` None): `ask_image(language)` — pre-built
  image to PULL.

## Per-field survey methods

- `ask_language() -> str`
- `ask_base_convention() -> (codemanifest_usages, codemanifest_annotations)`
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

(Same as before — `language`, `image`, `dockerfile`, `build`, `pipeline`, `codemanifest`
field order; see CODEMANIFEST `FileGenerator`.)

## Anti-patterns

- Do not write `build.image` — the Docker image is the top-level `image` field.
- Do not force-emit empty `build:`/`pipeline:` blocks.
- Do not inherit `agent` into `pipeline_agent`.
