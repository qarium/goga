# Init — API

The facade of the domain package **`goga.onboarding`** — the interactive project initialization and template scaffolding.

The signatures below are the CODEMANIFEST contract of the cell.

```python
InitLogic(questionnaire: Questionnaire, generator: FileGenerator)
Questionnaire()
FileGenerator()
```

- `InitLogic` — the orchestration: run the questionnaire, resolve the answers (template answers first, the interactive dialogue for what the template left open), and generate the project files.
- `Questionnaire` — the interactive dialogue — the questions behind `.goga/config.yml` and the optional Dockerfile.
- `FileGenerator` — the file materialization: `.goga/config.yml`, the Dockerfile, and the template scaffold application (a copier template with `goga init --upgrade` migrates an existing scaffold).

```python
InitAnswers(goga_config: GogaConfigAnswers | None = None)
GogaConfigAnswers(language: str, image: str, agent: str | None,
                  pipeline_agent: str | None, pipeline_env: dict | None,
                  env: dict | None, codemanifest_usages: dict | None,
                  codemanifest_annotations: str | None,
                  dockerfile_path: str | None, dockerfile_base_image: str | None)
```

The resolved answers: the project language and image, the build/pipeline agent settings with their env layers, the `codemanifest` section values, and the optional Dockerfile pair (path + base image). `InitAnswers` with `goga_config=None` — a template answered everything.

## Example

```python
from goga.onboarding import FileGenerator, InitLogic, Questionnaire

logic = InitLogic(questionnaire=Questionnaire(), generator=FileGenerator())
logic.run()
```
