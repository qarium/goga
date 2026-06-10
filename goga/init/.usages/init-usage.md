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

InitAnswers — response container holding GogaConfigAnswers with fields:
language, agent, image, env, codemanifest_usages, codemanifest_annotations, dockerfile_path

## Survey flow

Questionnaire.ask_goga_config() proceeds in this order:

1. **language** — select a language (python, golang, kotlin, swift, javascript)
2. **convention** — offer to download the base convention for the selected language
   - URL: `https://raw.githubusercontent.com/qarium/goga-lang-conventions/refs/heads/0.0.x/{language}/project.md`
   - The language identifier maps directly to the URL path segment (no mapping layer)
   - On acceptance, add `{"conventions": ".goga/usages/conventions.md"}` to codemanifest_usages
3. **codemanifest_usages** — optional additional practices
4. **codemanifest_annotations** — optional annotations
5. **agent** — select an AI executor (claude, codex)
6. **image** — Docker image: display language-specific hints, default to the last entry; accept free-form input
   - python: qarium/goga-python-3.10:1.0 .. qarium/goga-python-3.14:1.0
   - golang: qarium/goga-golang-1.23:1.0 .. qarium/goga-golang-1.26:1.0
   - javascript: qarium/goga-node-22:1.0 .. qarium/goga-node-24:1.0
   - kotlin: qarium/goga-kotlin-2.0:1.0 .. qarium/goga-kotlin-2.3:1.0
   - swift: qarium/goga-swift-6.0:1.0 .. qarium/goga-swift-6.2:1.0
7. **dockerfile** — optional custom Dockerfile creation
   - On acceptance, request the path (default: "Dockerfile")
   - The Dockerfile contains `FROM {image}`
8. **env** — first propose env keys based on the selected agent (from `agent_env_defaults`):
   - claude: ANTHROPIC_DEFAULT_HAIKU_MODEL, ANTHROPIC_DEFAULT_SONNET_MODEL, ANTHROPIC_DEFAULT_OPUS_MODEL, ANTHROPIC_BASE_URL
   - codex: CODEX_MODEL
   - Collect values for each proposed key
   - Then optionally collect arbitrary key-value pairs
