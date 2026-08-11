# Project Initialization — goga/init

## Overview

The `goga.init` package provides interactive goga project initialization —
collecting user input and generating configuration files.

## Facade

Import all types directly from `goga.init`:

```python
from goga.init import InitLogic, Questionnaire, FileGenerator, InitAnswers, GogaConfigAnswers
```

## Usage

### InitLogic — orchestrator

```python
from goga.init import InitLogic, Questionnaire, FileGenerator

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

`GogaConfigAnswers` fields:
- `language` — selected project language
- `agent` — selected AI executor (becomes `build.task_executor.agent`); None when the user declines to configure a build agent (the agent key is omitted from the generated config)
- `image` — Docker image (becomes the top-level `image`, NOT `build.image`). With a Dockerfile it is the NAME/tag of the image built from it (`docker build -t <image>`); without a Dockerfile it is the pre-built image to pull.
- `pipeline_agent` — AI executor used as `pipeline.agent` (afm client.command); None when the user declines to configure a pipeline agent. Does NOT inherit `agent`.
- `pipeline_env` — environment variables for the `pipeline` block (None → omit)
- `env` — environment variables for `build.task_executor.env`
- `codemanifest_usages` — codemanifest practice mappings
- `codemanifest_annotations` — codemanifest annotation block
- `dockerfile_path` — path to custom Dockerfile (None → skip Dockerfile creation AND omit the top-level `dockerfile` config field)
- `dockerfile_base_image` — base image for the Dockerfile `FROM` line; set only when `dockerfile_path` is set (None otherwise). Consumed solely by Dockerfile generation; never emitted to config.yml.

## Survey flow

`Questionnaire.ask_goga_config()` proceeds in this order:

1. **language** — select a language (python, golang, kotlin, swift, javascript)
2. **convention** — offer to download the base convention for the selected language
   - URL: `https://raw.githubusercontent.com/qarium/goga-lang-conventions/refs/heads/0.0.x/{language}/project.md`
   - The language identifier maps directly to the URL path segment (no mapping layer)
   - On acceptance, add `{"conventions": ".goga/usages/conventions.md"}` to codemanifest_usages
3. **codemanifest_usages** — optional additional practices
4. **codemanifest_annotations** — optional annotations
5. **agent** — confirm-gated (default No). On decline: None (no build agent configured, the agent key is omitted). On acceptance: select an AI executor (claude, codex)
6. **dockerfile** — optional custom Dockerfile creation
   - On acceptance, request the path (default: ".goga/Dockerfile")
   - The Dockerfile decision drives the image branch below (image semantics differ)
7. **image branch** — depends on step 6:
   - **With a Dockerfile** (`dockerfile_path` set): the image is BUILT from the Dockerfile, so:
     - **base image** (`dockerfile_base_image`) — the `FROM` baseline; display language-specific hints, default to the last entry; accept free-form input. Never written to config.yml.
     - **image name** (`image`) — the name/tag for the image built from the Dockerfile (`goga build` runs `docker build -t <image>`); free-form input, default `{language}-image:latest`. Captures the top-level `image` (NOT `build.image`).
     - The Dockerfile contains `FROM {dockerfile_base_image}`
   - **Without a Dockerfile** (`dockerfile_path` None): the image is a pre-built image to PULL:
     - **image** (`image`) — display language-specific hints, default to the last entry; accept free-form input. Captures the top-level `image` (NOT `build.image`).
   - Language image hints (used by both the pull image and the FROM base):
     - python: qarium/goga-python-3.10:1.1 .. qarium/goga-python-3.14:1.1
     - golang: qarium/goga-golang-1.23:1.1 .. qarium/goga-golang-1.26:1.1
     - javascript: qarium/goga-node-22:1.1 .. qarium/goga-node-24:1.1
     - kotlin: qarium/goga-kotlin-2.0:1.1 .. qarium/goga-kotlin-2.3:1.1
     - swift: qarium/goga-swift-6.0:1.1 .. qarium/goga-swift-6.2:1.1
8. **env** — propose env keys based on the selected `agent` (drives `build.task_executor.env`); a None `agent` skips the suggested-keys block and only offers arbitrary key-value pairs
   - claude: ANTHROPIC_DEFAULT_HAIKU_MODEL, ANTHROPIC_DEFAULT_SONNET_MODEL, ANTHROPIC_DEFAULT_OPUS_MODEL, ANTHROPIC_BASE_URL
   - codex: CODEX_MODEL
   - Collect values for each proposed key
   - Then optionally collect arbitrary key-value pairs
9. **pipeline_agent** — confirm-gated (default No). On decline: None (no pipeline agent configured, the pipeline agent key is omitted). Does NOT inherit `agent` from step 5. On acceptance: select an AI executor (claude, codex)
   - Drives `pipeline.agent` (afm client.command inside the container)
10. **pipeline_env** — propose env keys based on `pipeline_agent` from step 9 (drives `pipeline.env`); a None `pipeline_agent` skips the suggested-keys block and only offers arbitrary key-value pairs
    - claude: ANTHROPIC_DEFAULT_HAIKU_MODEL, ANTHROPIC_DEFAULT_SONNET_MODEL, ANTHROPIC_DEFAULT_OPUS_MODEL, ANTHROPIC_BASE_URL
    - codex: CODEX_MODEL
    - Collect values for each proposed key
    - Then optionally collect arbitrary key-value pairs

### Per-field survey methods

`Questionnaire` exposes each survey step as a public method; `ask_goga_config()` calls them in order and assembles the results into `GogaConfigAnswers`:

- `ask_language() -> str`
- `ask_base_convention() -> (codemanifest_usages, codemanifest_annotations)` — pre-fill pair for the two codemanifest fields
- `ask_codemanifest_usages(prefill: dict | None = None) -> dict | None`
- `ask_codemanifest_annotations(prefill: str | None = None) -> str | None`
- `ask_agent() -> str | None` (confirm-gated, default No; None when the user declines)
- `ask_dockerfile_path() -> str | None`
- `ask_image(language: str) -> str` — pre-built image to PULL (no-Dockerfile branch)
- `ask_base_image(language: str) -> str` — FROM baseline (Dockerfile branch); populates `dockerfile_base_image`
- `ask_image_name(language: str) -> str` — name/tag for the image built from the Dockerfile (Dockerfile branch)
- `ask_env(agent: str | None) -> dict | None`
- `ask_pipeline_agent() -> str | None` (confirm-gated, default No; None when the user declines; does NOT inherit `agent`)
- `ask_pipeline_env(pipeline_agent: str | None) -> dict | None`

## Generated .goga/config.yml structure

```yaml
language: python
image: qarium/goga-python-3.12:latest
dockerfile: .goga/Dockerfile    # only when dockerfile_path is set (omit when None)
build:                         # only when it carries content (a non-None agent and/or a non-empty env); omitted by default
  task_executor:
    agent: claude              # omitted when agent is None
    env: {...}                 # omitted when env is None or empty
  worktree: false         # other build fields only when provided
pipeline:                      # only when it carries content (a non-None pipeline_agent and/or a non-empty pipeline_env); omitted by default
  agent: claude                # omitted when pipeline_agent is None
  env: {...}                   # omitted when pipeline_env is None or empty
codemanifest:             # omitted when both inner fields are empty
  usages: {...}
  annotations: |
    ...
```

**Field order:** `language`, `image`, `dockerfile`, `build`, `pipeline`, `codemanifest`.

## Anti-patterns

- Do not write `build.image` — the Docker image is the top-level `image` field, shared by build and pipeline.
- Do not force-emit empty `build:`/`pipeline:` blocks — emit each block only when it carries content (a non-None agent and/or a non-empty env). A freshly-initialized project with no agent/env omits both blocks; the consumer commands raise a clean `ClickException` when an agent is actually needed.
- Do not inherit `agent` into `pipeline_agent` — the survey collects them via independent confirm-gates (each defaults to No), so build and pipeline can diverge or both be unset.
- Do not silently drop `pipeline_env` into `build.task_executor.env` — they are separate blocks driven by separate survey answers.
