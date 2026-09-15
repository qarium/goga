# goga init

Interactive project initialization wizard, with optional template scaffolding.

## Synopsis

```bash
goga init [TPL] [-t NAME]... [--ref REF]
goga init --upgrade [--ref REF]
```

## Description

`goga init` initializes a new goga project. It runs in one of three modes depending on the arguments:

- **Bare onboarding** (`goga init`) — launches an interactive questionnaire that walks you through setting up a new goga project. It collects configuration values and generates the necessary project files. Refuses to run when `.goga/` already exists ("Project already initialized").
- **Scaffold then onboarding** (`goga init <tpl>`) — scaffolds boilerplate from a [copier](https://copier.readthedocs.io/) template first (a git URL, optionally carrying a `#ref` fragment), then runs the onboarding questionnaire. Copier interactively asks template questions that are not answered programmatically. Onboarding is filesystem-conditional: questions whose artifacts the template already brought (`.goga/config.yml`, `.goga/usages/conventions.md`) are skipped. The already-initialized guard does **not** fire in this mode — a template may be applied to an existing tree.
- **Upgrade only** (`goga init --upgrade`) — migrates a previously scaffolded project to a newer template version via copier `run_update`. No onboarding runs. The template source is read from the `.goga/scaffold.yml` state file written by an earlier `goga init <tpl>`; if that file is absent the command exits nonzero.

`<tpl>` and `--upgrade` are mutually exclusive: `--upgrade` updates state tied to a specific repository already recorded in `.goga/scaffold.yml`. `--ref` is meaningful only with `<tpl>` or `--upgrade` (a bare `--ref` is rejected).

Both modes that run onboarding accept **tool invitations**: `goga init -t <tool-name>` (repeatable) invites installed tool packages into the session. An invited tool declares its own questions (asked after the core sections under a `--- Tool: <tool> ---` heading), may skip core questions it replaces, and contributes config files written under `.goga/tools/<tool>/`. A repeated name deduplicates into one invitation preserving the flag order. An invited but not installed name produces a warning — the session continues. A failing tool hook never changes the exit code. See [Init — Hooks](hooks.md) for the tool-author contract.

### Interactivity

The bare wizard is fully interactive. Press `Ctrl+C` at any time to abort.

With a template (`goga init <tpl>`), copier asks every template question that has no programmatic answer interactively. The project name is resolved from the git remote, falling back to a prompt, and supplied programmatically. A template question with neither a programmatic answer nor a default **must** be answered by the user — generation does not fail on it. The survey requires a TTY: in a non-interactive environment (CI, pipe) copier fails and the error cause is echoed to stderr. On migration (`--upgrade`) the survey is bypassed (`defaults=True`) — a new required template question without a default fails migration with a nonzero exit.

### Modes

`goga init` branches on the presence of `<tpl>` and `--upgrade`:

| Invocation | Mode | Behavior |
|---|---|---|
| `goga init` | Bare onboarding | Interactive questionnaire; refuses if `.goga/` exists. |
| `goga init [-t NAME]...` | Bare onboarding + tools | The questionnaire plus the invited tools' question blocks and config files. |
| `goga init <tpl> [--ref REF] [-t NAME]...` | Scaffold then onboarding | Copier `run_copy` from `<tpl>`, then the conditional questionnaire. |
| `goga init --upgrade [--ref REF]` | Upgrade | Copier `run_update`; no onboarding. Requires `.goga/scaffold.yml`. |

### Questionnaire Flow

The wizard proceeds through the following steps in order. **The entire session is skipped when `.goga/config.yml` already exists** (for example, when a copier template brought its own config) — no question is asked and no file is (re)written.

1. **Language** -- Select the primary programming language.
   Choices: `python`, `golang`, `kotlin`, `swift`, `javascript`.

2. **Base Convention** -- Optionally download the default code conventions for the selected language from the [goga-lang-conventions](https://github.com/qarium/goga-lang-conventions) repository. Accepting pre-fills the codemanifest step (a `conventions` usage entry and a starter annotation). **Skipped when `.goga/usages/conventions.md` already exists** (for example, when a template brought its own conventions); the prefill is treated as `(None, None)`.

3. **Codemanifest Usages** -- Add additional named usages (code practice documentation entries). Each usage has a name and a file path. The convention prefill entries are offered first when step 2 was accepted.

4. **Codemanifest Annotations** -- Add custom annotations (global directives for the AI agent) that will be stored in the configuration; a custom annotation appends to the pre-filled text when step 2 was accepted.

5. **Build Agent and Environment** -- Confirm-gated (defaults to **No**). Decline to skip configuring a build agent (the `build` key is then omitted from the generated config; `goga build` raises a clean `ClickException` if it later needs one). Accept to select an AI executor — `claude`, `codex`, `cursor`, `opencode`, or `qwen` — then collect its environment variables: the suggested keys of the selected agent are offered first (e.g., `ANTHROPIC_BASE_URL`, `ANTHROPIC_DEFAULT_HAIKU_MODEL`, `ANTHROPIC_DEFAULT_SONNET_MODEL`, `ANTHROPIC_DEFAULT_OPUS_MODEL`, `ANTHROPIC_MODEL` for Claude; `CODEX_MODEL` for Codex), arbitrary `KEY=VALUE` pairs after.

6. **Docker Image** -- The Dockerfile decision:

   - **Create Dockerfile?** (defaults to **No**) — when accepted, the image is **built from it**, so you are asked for three things:
     - **Dockerfile path** -- the suggested path is `.goga/Dockerfile` (saved inside the project-scoped `.goga/` directory); press Enter to accept it or type a different path.
     - **Base image (FROM)** -- the baseline the Dockerfile extends. Available images depend on the chosen language (table below). This is written to the Dockerfile's `FROM` line only; it is not stored in `config.yml`.
     - **Built image name** -- the name/tag for the image built from your Dockerfile (`goga build` runs `docker build -t <image>`). Free-form; defaults to `<project-name>:latest`, where `<project-name>` is derived from your git `origin` remote URL (basename with `.git` stripped). When no git remote is available, no default is offered and the image name is required. Stored as the top-level `image` in `config.yml`.
   - **If you decline**, the image is a **pre-built image to pull**. Select it from the language-specific list (table below); it is stored as the top-level `image` in `config.yml`.

   The `:<tag>` suffix of every offered image is the minor line of the installed goga (e.g. `1.3` while on goga 1.3.x) — the offered hints always match your installed version line.

   | Language | Images |
   |---|---|
   | python | `qarium/goga-python-3.10:<tag>` ... `qarium/goga-python-3.14:<tag>` |
   | golang | `qarium/goga-golang-1.23:<tag>` ... `qarium/goga-golang-1.26:<tag>` |
   | javascript | `qarium/goga-node-22:<tag>`, `qarium/goga-node-24:<tag>` |
   | kotlin | `qarium/goga-kotlin-2.0:<tag>` ... `qarium/goga-kotlin-2.3:<tag>` |
   | swift | `qarium/goga-swift-6.0:<tag>` ... `qarium/goga-swift-6.2:<tag>` |

7. **Pipeline Agent and Environment** -- Confirm-gated (defaults to **No**). Decline to skip configuring a pipeline agent (the `pipeline` key is omitted; a per-stage workflow agent or the pipeline's own default then covers the absent global agent). Accept to select an AI executor and collect its environment variables (same shape as step 5). Does **not** inherit the build agent — build and pipeline are collected via independent confirm-gates, so they can diverge or both be left unset.

8. **Tools** -- Confirm-gated (defaults to **No**). Collect `name → version` pairs recorded as the top-level `tools` list of `config.yml` (consumed by `goga install` bulk mode). Version forms: `latest`, `N.x` (newest within major N), `N.M.x` (newest patch within N.M), `N.M` or `N.M.K` (exact pin); an empty version reads as `latest`.

9. **Usages Records** -- Confirm-gated (defaults to **No**). Collect git dependency records — group, dependency name, git URL, optional ref and root — recorded as the top-level `usages` tree of `config.yml` (consumed by `goga usages sync`).

10. **Tool Blocks** -- For every invited tool (`-t`), the questions the tool declared are asked under a `--- Tool: <tool> ---` heading; the answers configure the tool's own files. A tool may also have skipped core questions it replaces — those are never asked.

### Generated Files

After the questionnaire completes, `goga init` creates (each path is echoed as `created <path>` in the run report — tool files as `created <path> (tool: <name>)`):

- **`.goga/config.yml`** -- Project configuration. Fields, in order: `language`, top-level `image`, optional `dockerfile` (when a custom Dockerfile is requested), `build` (emitted only when it carries content — a non-None agent and/or a non-empty env), `pipeline` (likewise emitted only when it carries content), optional `codemanifest`, optional `tools` (the step 8 collection), and optional `usages` (the step 9 records). A freshly-initialized project with no agent and no env omits both `build` and `pipeline`; the consumer commands raise a clean `ClickException` when an agent is actually needed.
- **`.goga/usages/conventions.md`** -- (If base convention was downloaded) Language-specific code conventions.
- **`.goga/Dockerfile`** -- (If requested) A Dockerfile whose `FROM` line is the selected base image, written at the suggested path inside `.goga/`. When created, a top-level `dockerfile:` entry (defaulting to `.goga/Dockerfile`) is also written to `.goga/config.yml`, and the top-level `image` holds the **name of the image built from it** (the `docker build -t` tag) — so `goga build --update` / `goga pipeline --update` build the image locally instead of pulling it.
- **`.goga/tools/<tool>/<file>`** -- (Per invited tool) The config files the tool's `amend_config` hook buffered, written by the engine — a tool never writes its own config. Tool amendments may also substitute collected answers (e.g. the `tools` record).

When `goga init <tpl>` is used, copier additionally writes:

- **`.goga/scaffold.yml`** -- copier's state file recording the template source and the answers used. `goga init --upgrade` reads this file to re-apply the recorded template, and exits nonzero if it is absent.

## Examples

Run the initialization wizard:

```bash
goga init
```

Run the wizard with invited tool packages (repeatable; duplicates deduplicate):

```bash
goga init -t my-tool -t viewer
```

Scaffold a project from a copier template, then run the conditional questionnaire:

```bash
# Latest commit on the template's default branch
goga init https://github.com/qarium/my-template.git

# Pin a specific ref via the URL fragment
goga init https://github.com/qarium/my-template.git#v1.0

# Override the ref explicitly (--ref wins over a fragment)
goga init https://github.com/qarium/my-template.git#v1.0 --ref main

# Scaffold and invite a tool into the session
goga init https://github.com/qarium/my-template.git -t my-tool
```

Migrate a previously scaffolded project to a newer template version:

```bash
# Re-apply the recorded template at its current ref
goga init --upgrade

# Migrate to a specific target ref
goga init --upgrade --ref v2.0
```

## Options

| Option/Argument | Type | Default | Purpose |
|---|---|---|---|
| `TPL` (positional, optional) | string | None | Copier template source — a git URL, optionally carrying a `#ref` fragment. Triggers scaffold-then-onboarding mode. Mutually exclusive with `--upgrade`. |
| `-t`, `--tool NAME` (repeatable) | string | None | Invite the named tool package into the onboarding session. Acts in both modes that run onboarding (bare and `<tpl>`-given); a repeated name deduplicates into one invitation and one block, preserving the flag order. The names are opaque to the command — the onboarding domain warns for invited-but-not-installed names. Rejected with `--upgrade`. |
| `--upgrade` | flag | False | Migrate a previously scaffolded project via copier `run_update`; no onboarding. Mutually exclusive with `<tpl>`. |
| `--ref REF` | string | None | Override the git ref. With `<tpl>` it overrides the URL fragment; with `--upgrade` it sets the migration target ref. Requires `<tpl>` or `--upgrade` (a bare `--ref` is rejected). |

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success — files generated (onboarding), template scaffolded, or migration applied. A failing tool hook never changes the exit code. |
| `1` | Error or user abort (`Ctrl+C`). Includes: project already initialized (bare `init` with `.goga/` present); `<tpl>` and `--upgrade` given together (mutually exclusive); `-t/--tool` given with `--upgrade` (an invitation needs an onboarding session); `--ref` given without `<tpl>` or `--upgrade`; copier scaffold/upgrade failure (bad template URL, git error, missing `.goga/scaffold.yml` on upgrade); or onboarding failure (a nonzero exit code from a delegate — `Scaffold.generate`/`Scaffold.upgrade`, `InitLogic.run` — is propagated verbatim). |
