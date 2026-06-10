# CLI Command: init

## Purpose

CLI wrapper for the interactive goga project initialization command. Runs a user questionnaire and creates configuration files.

## Syntax

```
goga init
```

## Interactive questionnaire

The command sequentially asks:

1. **Language** — project language (python, golang, kotlin, swift, javascript)
2. **Base convention** — whether to download the base convention for the selected language
3. **Codemanifest usages** — optional, additional practices
4. **Codemanifest annotations** — optional
5. **Agent** — AI-executor (claude)
6. **Docker image** — select from a list of images for the selected language
7. **Dockerfile** — optional, create a custom Dockerfile with `FROM {image}`
8. **Environment variables** — env keys are suggested based on the agent, then optional arbitrary ones

## Created files

- `.goga/config.yml` — project configuration
- `.goga/usages/conventions.md` — base convention for the language (if the user agreed)
- `Dockerfile` (or at the specified path) — custom Dockerfile (if the user requested one)

## Exit code

- 0 — success
- 1 — error (user cancellation, generation error)

## Examples

```bash
# Interactive initialization
goga init
```
