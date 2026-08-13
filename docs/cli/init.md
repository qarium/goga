# goga init

Interactive project initialization wizard, with optional template scaffolding.

## Synopsis

```bash
goga init [TPL] [--ref REF]
goga init --upgrade [--ref REF]
```

## Description

`goga init` initializes a new goga project. It runs in one of three modes depending on the arguments:

- **Bare onboarding** (`goga init`) — launches an interactive questionnaire that walks you through setting up a new goga project. It collects configuration values and generates the necessary project files. Refuses to run when `.goga/` already exists ("Project already initialized").
- **Scaffold then onboarding** (`goga init <tpl>`) — scaffolds boilerplate from a [copier](https://copier.readthedocs.io/) template first (a git URL, optionally carrying a `#ref` fragment), then runs the onboarding questionnaire. Onboarding is filesystem-conditional: questions whose artifacts the template already brought (`.goga/config.yml`, `.goga/usages/conventions.md`) are skipped. The already-initialized guard does **not** fire in this mode — a template may be applied to an existing tree.
- **Upgrade only** (`goga init --upgrade`) — migrates a previously scaffolded project to a newer template version via copier `run_update`. No onboarding runs. The template source is read from the `.goga/scaffold.yml` state file written by an earlier `goga init <tpl>`; if that file is absent the command exits nonzero.

`<tpl>` and `--upgrade` are mutually exclusive: `--upgrade` updates state tied to a specific repository already recorded in `.goga/scaffold.yml`. `--ref` is meaningful only with `<tpl>` or `--upgrade` (a bare `--ref` is rejected).

### Modes

`goga init` branches on the presence of `<tpl>` and `--upgrade`:

| Invocation | Mode | Behavior |
|---|---|---|
| `goga init` | Bare onboarding | Interactive questionnaire; refuses if `.goga/` exists. |
| `goga init <tpl> [--ref REF]` | Scaffold then onboarding | Copier `run_copy` from `<tpl>`, then the conditional questionnaire. |
| `goga init --upgrade [--ref REF]` | Upgrade | Copier `run_update`; no onboarding. Requires `.goga/scaffold.yml`. |

### Questionnaire Flow

The wizard proceeds through the following steps in order. **The entire survey is skipped when `.goga/config.yml` already exists** (for example, when a copier template brought its own config) — `ask_goga_config` short-circuits and no file is (re)written.

1. **Language** -- Select the primary programming language.
   Choices: `python`, `golang`, `kotlin`, `swift`, `javascript`.

2. **Base Convention** -- Optionally download the default code conventions for the selected language from the [goga-lang-conventions](https://github.com/qarium/goga-lang-conventions) repository. **Skipped when `.goga/usages/conventions.md` already exists** (for example, when a template brought its own conventions); the prefill is treated as `(None, None)`.

3. **Codemanifest Usages** -- Add additional named usages (code practice documentation entries). Each usage has a name and a file path.

4. **Codemanifest Annotations** -- Add custom annotations (global directives for the AI agent) that will be stored in the configuration.

5. **Build Agent** -- Confirm-gated (defaults to **No**). Decline to skip configuring a build agent (the `agent` key is then omitted from the generated config; `goga build` raises a clean `ClickException` if it later needs one). Accept to select an AI executor: `claude`, `codex`.

6. **Custom Dockerfile** -- Optionally create a custom Dockerfile. When accepted, the suggested path is `.goga/Dockerfile` (saved inside the project-scoped `.goga/` directory); press Enter to accept it or type a different path. The Dockerfile decision drives the next step (image semantics differ).

7. **Docker Image** (depends on step 6):

   - **If you created a Dockerfile**, the image is **built from it**, so you are asked for two things:
     - **Base image (FROM)** -- the baseline the Dockerfile extends. Available images depend on the chosen language (table below). This is written to the Dockerfile's `FROM` line only; it is not stored in `config.yml`.
     - **Built image name** -- the name/tag for the image built from your Dockerfile (`goga build` runs `docker build -t <image>`). Free-form; defaults to `<project-name>:latest`, where `<project-name>` is derived from your git `origin` remote URL (basename with `.git` stripped). When no git remote is available, no default is offered and the image name is required. Stored as the top-level `image` in `config.yml`.
   - **If you did not create a Dockerfile**, the image is a **pre-built image to pull**. Select it from the language-specific list (table below); it is stored as the top-level `image` in `config.yml`.

   | Language | Images |
   |---|---|
   | python | `qarium/goga-python-3.10:1.1` ... `qarium/goga-python-3.14:1.1` |
   | golang | `qarium/goga-golang-1.23:1.1` ... `qarium/goga-golang-1.26:1.1` |
   | javascript | `qarium/goga-node-22:1.1`, `qarium/goga-node-24:1.1` |
   | kotlin | `qarium/goga-kotlin-2.0:1.1` ... `qarium/goga-kotlin-2.3:1.1` |
   | swift | `qarium/goga-swift-6.0:1.1` ... `qarium/goga-swift-6.2:1.1` |

8. **Environment Variables** -- Configure environment variables for the build. Suggested keys are offered per agent (e.g., `ANTHROPIC_DEFAULT_HAIKU_MODEL`, `ANTHROPIC_DEFAULT_SONNET_MODEL`, `ANTHROPIC_DEFAULT_OPUS_MODEL`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL` for Claude; `CODEX_MODEL` for Codex). You can also add arbitrary custom variables.

9. **Pipeline Agent** -- Confirm-gated (defaults to **No**). Decline to skip configuring a pipeline agent (the `pipeline.agent` key is omitted; a per-stage workflow agent or afm's own default then covers the absent global agent). Accept to select an AI executor: `claude`, `codex`. Does **not** inherit the build agent from step 5 — build and pipeline are collected via independent confirm-gates, so they can diverge or both be left unset.

10. **Pipeline Environment Variables** -- Configure environment variables for the pipeline container. Suggested keys are offered per agent (same shape as step 8). You can also add arbitrary `KEY=VALUE` variables. Omitted entirely when nothing is collected.

### Generated Files

After the questionnaire completes, `goga init` creates:

- **`.goga/config.yml`** -- Project configuration. Fields, in order: `language`, top-level `image`, optional `dockerfile` (when a custom Dockerfile is requested), `build` (emitted only when it carries content — a non-None agent and/or a non-empty env), `pipeline` (likewise emitted only when it carries content), and optional `codemanifest`. A freshly-initialized project with no agent and no env omits both `build` and `pipeline`; the consumer commands raise a clean `ClickException` when an agent is actually needed.
- **`.goga/usages/conventions.md`** -- (If base convention was downloaded) Language-specific code conventions.
- **`.goga/Dockerfile`** -- (If requested) A Dockerfile whose `FROM` line is the selected base image, written at the suggested path inside `.goga/`. When created, a top-level `dockerfile:` entry (defaulting to `.goga/Dockerfile`) is also written to `.goga/config.yml`, and the top-level `image` holds the **name of the image built from it** (the `docker build -t` tag) — so `goga build --update` / `goga pipeline --update` build the image locally instead of pulling it.

When `goga init <tpl>` is used, copier additionally writes:

- **`.goga/scaffold.yml`** -- copier's state file recording the template source and the answers used. `goga init --upgrade` reads this file to re-apply the recorded template, and exits nonzero if it is absent.

## Examples

Run the initialization wizard:

```bash
goga init
```

Scaffold a project from a copier template, then run the conditional questionnaire:

```bash
# Latest commit on the template's default branch
goga init https://github.com/qarium/my-template.git

# Pin a specific ref via the URL fragment
goga init https://github.com/qarium/my-template.git#v1.0

# Override the ref explicitly (--ref wins over a fragment)
goga init https://github.com/qarium/my-template.git#v1.0 --ref main
```

Migrate a previously scaffolded project to a newer template version:

```bash
# Re-apply the recorded template at its current ref
goga init --upgrade

# Migrate to a specific target ref
goga init --upgrade --ref v2.0
```

The bare wizard is fully interactive. Press `Ctrl+C` at any time to abort. Copier template questions are bypassed (answers supplied programmatically with `defaults=True`).

## Options

| Option/Argument | Type | Default | Purpose |
|---|---|---|---|
| `TPL` (positional, optional) | string | None | Copier template source — a git URL, optionally carrying a `#ref` fragment. Triggers scaffold-then-onboarding mode. Mutually exclusive with `--upgrade`. |
| `--upgrade` | flag | False | Migrate a previously scaffolded project via copier `run_update`; no onboarding. Mutually exclusive with `<tpl>`. |
| `--ref REF` | string | None | Override the git ref. With `<tpl>` it overrides the URL fragment; with `--upgrade` it sets the migration target ref. Requires `<tpl>` or `--upgrade` (a bare `--ref` is rejected). |

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success — files generated (onboarding), template scaffolded, or migration applied. |
| `1` | Error or user abort (`Ctrl+C`). Includes: project already initialized (bare `init` with `.goga/` present); `<tpl>` and `--upgrade` given together (mutually exclusive); `--ref` given without `<tpl>` or `--upgrade`; copier scaffold/upgrade failure (bad template URL, git error, missing `.goga/scaffold.yml` on upgrade); or onboarding failure. |
| other | A nonzero exit code returned by a delegate (`Scaffold.generate`/`Scaffold.upgrade`, `InitLogic.run`) is propagated verbatim. |
