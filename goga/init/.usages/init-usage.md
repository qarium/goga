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
- If the user requested a custom Dockerfile — create it with `FROM {image}`

### Data

`InitAnswers` — response container holding `GogaConfigAnswers`.

`GogaConfigAnswers` fields:
- `language` — selected project language
- `agent` — selected AI executor (becomes `build.task_executor.agent`)
- `image` — Docker image (becomes the top-level `image`, NOT `build.image`)
- `pipeline_agent` — AI executor used as `pipeline.agent` (afm client.command)
- `pipeline_env` — environment variables for the `pipeline` block (None → omit)
- `env` — environment variables for `build.task_executor.env`
- `codemanifest_usages` — codemanifest practice mappings
- `codemanifest_annotations` — codemanifest annotation block
- `dockerfile_path` — path to custom Dockerfile (None → skip Dockerfile creation AND omit the top-level `dockerfile` config field)

## Survey flow

`Questionnaire.ask_goga_config()` proceeds in this order:

1. **language** — select a language (python, golang, kotlin, swift, javascript)
2. **convention** — offer to download the base convention for the selected language
   - URL: `https://raw.githubusercontent.com/qarium/goga-lang-conventions/refs/heads/0.0.x/{language}/project.md`
   - The language identifier maps directly to the URL path segment (no mapping layer)
   - On acceptance, add `{"conventions": ".goga/usages/conventions.md"}` to codemanifest_usages
3. **codemanifest_usages** — optional additional practices
4. **codemanifest_annotations** — optional annotations
5. **agent** — select an AI executor (claude, codex)
6. **image** — Docker image: display language-specific hints, default to the last entry; accept free-form input
   - Captures the top-level `image` (NOT `build.image`)
   - python: qarium/goga-python-3.10:1.0 .. qarium/goga-python-3.14:1.0
   - golang: qarium/goga-golang-1.23:1.0 .. qarium/goga-golang-1.26:1.0
   - javascript: qarium/goga-node-22:1.0 .. qarium/goga-node-24:1.0
   - kotlin: qarium/goga-kotlin-2.0:1.0 .. qarium/goga-kotlin-2.3:1.0
   - swift: qarium/goga-swift-6.0:1.0 .. qarium/goga-swift-6.2:1.0
7. **dockerfile** — optional custom Dockerfile creation
   - On acceptance, request the path (default: ".goga/Dockerfile")
   - The Dockerfile contains `FROM {image}`
8. **env** — propose env keys based on the selected `agent` (drives `build.task_executor.env`)
   - claude: ANTHROPIC_DEFAULT_HAIKU_MODEL, ANTHROPIC_DEFAULT_SONNET_MODEL, ANTHROPIC_DEFAULT_OPUS_MODEL, ANTHROPIC_BASE_URL
   - codex: CODEX_MODEL
   - Collect values for each proposed key
   - Then optionally collect arbitrary key-value pairs
9. **pipeline_agent** — select an AI executor (claude, codex); default = `agent` from step 5
   - Drives `pipeline.agent` (afm client.command inside the container)
10. **pipeline_env** — propose env keys based on `pipeline_agent` from step 9 (drives `pipeline.env`)
    - claude: ANTHROPIC_DEFAULT_HAIKU_MODEL, ANTHROPIC_DEFAULT_SONNET_MODEL, ANTHROPIC_DEFAULT_OPUS_MODEL, ANTHROPIC_BASE_URL
    - codex: CODEX_MODEL
    - Collect values for each proposed key
    - Then optionally collect arbitrary key-value pairs

## Generated .goga/config.yml structure

```yaml
language: python
image: qarium/goga-python-3.12:latest
dockerfile: .goga/Dockerfile    # only when dockerfile_path is set (omit when None)
build:
  task_executor:
    agent: claude
    env: {...}
  worktree: false         # other build fields only when provided
pipeline:
  agent: claude           # always emitted — init-config must be self-contained so `goga pipeline` works out-of-the-box
  env: {...}              # omitted when pipeline_env is None or empty
codemanifest:             # omitted when both inner fields are empty
  usages: {...}
  annotations: |
    ...
```

**Field order:** `language`, `image`, `dockerfile`, `build`, `pipeline`, `codemanifest`.

## Anti-patterns

- Do not write `build.image` — the Docker image is the top-level `image` field, shared by build and pipeline.
- Do not omit the `pipeline:` block — the init-config must be self-contained so `goga pipeline` works out-of-the-box without manual config edits; always emit at least `pipeline.agent`.
- Do not reuse `agent` for both build and pipeline without confirming `pipeline_agent` — the survey explicitly collects `pipeline_agent` (defaulted to `agent`) so that build and pipeline can diverge.
- Do not silently drop `pipeline_env` into `build.task_executor.env` — they are separate blocks driven by separate survey answers.
