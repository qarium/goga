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

5. **Build Agent** -- Confirm-gated (defaults to **No**). Decline to skip configuring a build agent (the `agent` key is then omitted from the generated config; `goga build` raises a clean `ClickException` if it later needs one). Accept to select an AI executor: `claude`, `codex`.

6. **Docker Image** -- Select a Docker image for the build environment. Available images depend on the chosen language:

   | Language | Images |
   |---|---|
   | python | `qarium/goga-python-3.10:1.1` ... `qarium/goga-python-3.14:1.1` |
   | golang | `qarium/goga-golang-1.23:1.1` ... `qarium/goga-golang-1.26:1.1` |
   | javascript | `qarium/goga-node-22:1.1`, `qarium/goga-node-24:1.1` |
   | kotlin | `qarium/goga-kotlin-2.0:1.1` ... `qarium/goga-kotlin-2.3:1.1` |
   | swift | `qarium/goga-swift-6.0:1.1` ... `qarium/goga-swift-6.2:1.1` |

7. **Custom Dockerfile** -- Optionally create a custom Dockerfile based on the selected image. When accepted, the suggested path is `.goga/Dockerfile` (saved inside the project-scoped `.goga/` directory); press Enter to accept it or type a different path.

8. **Environment Variables** -- Configure environment variables for the build. Suggested keys are offered per agent (e.g., `ANTHROPIC_DEFAULT_HAIKU_MODEL`, `ANTHROPIC_DEFAULT_SONNET_MODEL`, `ANTHROPIC_DEFAULT_OPUS_MODEL`, `ANTHROPIC_BASE_URL` for Claude; `CODEX_MODEL` for Codex). You can also add arbitrary custom variables.

9. **Pipeline Agent** -- Confirm-gated (defaults to **No**). Decline to skip configuring a pipeline agent (the `pipeline.agent` key is omitted; a per-stage workflow agent or afm's own default then covers the absent global agent). Accept to select an AI executor: `claude`, `codex`. Does **not** inherit the build agent from step 5 — build and pipeline are collected via independent confirm-gates, so they can diverge or both be left unset.

10. **Pipeline Environment Variables** -- Configure environment variables for the pipeline container. Suggested keys are offered per agent (same shape as step 8). You can also add arbitrary `KEY=VALUE` variables. Omitted entirely when nothing is collected.

### Generated Files

After the questionnaire completes, `goga init` creates:

- **`.goga/config.yml`** -- Project configuration. Fields, in order: `language`, top-level `image`, optional `dockerfile` (when a custom Dockerfile is requested), `build` (emitted only when it carries content — a non-None agent and/or a non-empty env), `pipeline` (likewise emitted only when it carries content), and optional `codemanifest`. A freshly-initialized project with no agent and no env omits both `build` and `pipeline`; the consumer commands raise a clean `ClickException` when an agent is actually needed.
- **`.goga/usages/conventions.md`** -- (If base convention was downloaded) Language-specific code conventions.
- **`.goga/Dockerfile`** -- (If requested) A Dockerfile derived from the selected image, written at the suggested path inside `.goga/`. When created, a top-level `dockerfile:` entry (defaulting to `.goga/Dockerfile`) is also written to `.goga/config.yml`, so `goga build --update` / `goga pipeline --update` build the image locally instead of pulling it.

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
