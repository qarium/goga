# goga init

Interactive project initialization wizard.

## Synopsis

```bash
goga init
```

## Description

`goga init` launches an interactive questionnaire that walks you through setting up a new goga project. It collects configuration values and generates the necessary project files.

### Questionnaire Flow

The wizard proceeds through the following steps in order:

1. **Language** -- Select the primary programming language.
   Choices: `python`, `golang`, `kotlin`, `swift`, `javascript`.

2. **Base Convention** -- Optionally download the default code conventions for the selected language from the [goga-lang-conventions](https://github.com/qarium/goga-lang-conventions) repository.

3. **Codemanifest Usages** -- Add additional named usages (code practice documentation entries). Each usage has a name and a file path.

4. **Codemanifest Annotations** -- Add custom annotations (global directives for the AI agent) that will be stored in the configuration.

5. **AI Agent** -- Select the AI agent that will build the implementation. Supported: `claude`, `codex`.

6. **Docker Image** -- Select a Docker image for the build environment. Available images depend on the chosen language:

   | Language | Images |
   |---|---|
   | python | `qarium/goga-python-3.10:1.0` ... `qarium/goga-python-3.14:1.0` |
   | golang | `qarium/goga-golang-1.23:1.0` ... `qarium/goga-golang-1.26:1.0` |
   | javascript | `qarium/goga-node-22:1.0`, `qarium/goga-node-24:1.0` |
   | kotlin | `qarium/goga-kotlin-2.0:1.0` ... `qarium/goga-kotlin-2.3:1.0` |
   | swift | `qarium/goga-swift-6.0:1.0` ... `qarium/goga-swift-6.2:1.0` |

7. **Custom Dockerfile** -- Optionally create a custom Dockerfile based on the selected image.

8. **Environment Variables** -- Configure environment variables for the build. Suggested keys are offered per agent (e.g., `ANTHROPIC_DEFAULT_HAIKU_MODEL`, `ANTHROPIC_DEFAULT_SONNET_MODEL`, `ANTHROPIC_DEFAULT_OPUS_MODEL`, `ANTHROPIC_BASE_URL` for Claude; `CODEX_MODEL` for Codex). You can also add arbitrary custom variables.

9. **Pipeline Agent** -- Select the AI agent for `goga pipeline` execution. Defaults to the agent chosen in step 5. Supported: `claude`, `codex`.

10. **Pipeline Environment Variables** -- Configure environment variables for the pipeline container. Suggested keys are offered per agent (same shape as step 8). You can also add arbitrary `KEY=VALUE` variables. Omitted entirely when nothing is collected.

### Generated Files

After the questionnaire completes, `goga init` creates:

- **`.goga/config.yml`** -- Project configuration. Fields, in order: `language`, top-level `image`, optional `dockerfile` (when a custom Dockerfile is requested), `build` (with `task_executor`), a required `pipeline` block (agent + optional env), and optional `codemanifest`.
- **`.goga/usages/conventions.md`** -- (If base convention was downloaded) Language-specific code conventions.
- **`Dockerfile`** -- (If requested) A Dockerfile derived from the selected image. When created, a top-level `dockerfile:` entry is also written to `.goga/config.yml`, so `goga build --update` / `goga pipeline --update` build the image locally instead of pulling it.

## Examples

Run the initialization wizard:

```bash
goga init
```

The wizard is fully interactive. Press `Ctrl+C` at any time to abort.

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success -- all files generated |
| `1` | Error or user abort (`Ctrl+C`) |
