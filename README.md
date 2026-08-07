<div align="center">

<img src="docs/assets/goga.svg" alt="goga" width="180" />

# Goga

A new semantic layer between specification and implementation based on the [**CODEMANIFEST**](https://github.com/qarium/codemanifest/blob/0.0.x/specs/en.md) specification — helping humans and AI agents reason about project structure at a higher level of abstraction.

A full-fledged **Specification-Driven Development (SDD)** framework: describe cell contracts with a structured YAML DSL, validate them, extract contracts from source code, and drive an end-to-end agent workflow — propose, brainstorm, design, plan, build, change, and accept — under the hood.

**Languages**

<img src="docs/assets/brands/python.svg" alt="Python" width="40" height="40">&nbsp;&nbsp;&nbsp;&nbsp;
<img src="docs/assets/brands/javascript.svg" alt="JavaScript" width="40" height="40">&nbsp;&nbsp;&nbsp;&nbsp;
<img src="docs/assets/brands/kotlin.svg" alt="Kotlin" width="40" height="40">&nbsp;&nbsp;&nbsp;&nbsp;
<img src="docs/assets/brands/swift.svg" alt="Swift" width="40" height="40">&nbsp;&nbsp;&nbsp;&nbsp;
<img src="docs/assets/brands/go.svg" alt="Go" width="40" height="40">

**Agents**

<img src="docs/assets/brands/claude.svg" alt="Claude" width="40" height="40">&nbsp;&nbsp;&nbsp;&nbsp;
<img src="docs/assets/brands/openai.svg" alt="Codex" width="40" height="40">&nbsp;&nbsp;&nbsp;&nbsp;
<img src="docs/assets/brands/opencode.svg" alt="OpenCode" width="40" height="40">&nbsp;&nbsp;&nbsp;&nbsp;
<img src="docs/assets/brands/cursor.svg" alt="Cursor" width="40" height="40">&nbsp;&nbsp;&nbsp;&nbsp;
<img src="docs/assets/brands/qwen.svg" alt="Qwen" width="40" height="40">

[Documentation](https://qarium.github.io/goga/) · [Getting Started](https://qarium.github.io/goga/getting-started/) · [Workflow](https://qarium.github.io/goga/workflow/) · [Pipelines](https://qarium.github.io/goga/pipelines/) · [Configuration](https://qarium.github.io/goga/configuration/)

</div>

---

## Install

```bash
pipx install goga
```

`goga build` and `goga pipeline` launch a Docker container, so Docker must be installed and accessible on your host:

```bash
docker info
```

Connect goga to your agent

```bash
goga connect <agent>
```

To upgrade goga later and re-sync all connected agents, use:

```bash
goga upgrade
```

## Quick start

Start a new project from scratch and build your first feature end-to-end.

**1. Initialize the project** — the interactive wizard sets up `.goga/config.yml`, language conventions, and (optionally) a `Dockerfile`:

```bash
goga init
```

**2. Open your agent** — launch the agent you connected via `goga connect` (e.g., Claude Code) in the project directory. All `goga-<command>` skills are now available.

**3. Ship the first feature** — run the full SDD lifecycle in one command inside an isolated container, with agent credentials forwarded automatically:

```bash
goga pipeline feature
```

The `feature` pipeline walks all eleven stages — propose → task-review → brainstorm → architecture-review → apply-architecture → code-design → design-review → coding-plan → plan-review → commit-architecture → accept-result — pausing at every `communication` stage to ask for your input. Three more shipped pipelines cover other lifecycles:

```bash
goga pipeline bugfix       # root-cause analysis and defect resolution
goga pipeline patch        # refactoring or minimal change with a plan
goga pipeline review       # scoped review of code, contracts, docs, then lint/format/tests
```

Each pipeline is a flat YAML file; layer project-specific overrides on top via an optional [workflow](https://qarium.github.io/goga/pipelines/workflows/) file.

**4. Drive the cycle by hand (optional)** — if you want explicit control over each step instead of running the whole cycle automatically, formulate the task and step through each command manually:

```text
/goga:propose <what you want to create>
```

```
propose → brainstorm → apply → design → plan → goga build → change → accept
```

The slash-command form `/goga:<command>` works in agents that consume the goga command bundle — currently `claude`, `opencode`, and `qwen` (see [`goga connect`](https://qarium.github.io/goga/cli/connect/)). Codex and cursor do not register commands; in those agents invoke the skill directly: `goga-propose` (Codex uses the `$` prefix — `$goga-propose`). Reviews are optional at every stage. For smaller changes, use one of the shortcut paths described in the [Workflow](https://qarium.github.io/goga/workflow/) section.

**5. Visualize the result** — once `apply` has produced cells on disk, inspect the architecture:

```bash
goga schema | goga tool viewer
```

## What is a cell?

A **cell** is a directory that encapsulates a distinct responsibility domain with a well-defined API boundary. Each cell contains a `CODEMANIFEST` file describing its contract and an optional `.usages/` directory with documentation for API consumers.

```
cell/
├── CODEMANIFEST       # YAML DSL describing the API contract
└── .usages/*.md       # Practices for working with the cell
```

The rule of thumb is **one responsibility zone — one cell**. A new cell is born when logic can be decoupled, owns distinct data models, must be reused, or can be stated in a single phrase without "and".

### Anatomy of a contract

A `CODEMANIFEST` consists of three sections separated by `---`:

- **Header** — `Imports` (types and usages from other cells), `Usages` (named practices), `Annotations` (global directives)
- **Body** — entities and routines that form the cell's public API
- **Footer** — `Author`, `CreatedAt`, `Description`

Cells expose three kinds of types:

- **Entity types** — objects with state and behavior (services, configurations, data models): properties + methods
- **Routine types** — single operations (transformers, factories, validators, parsers): no state
- **Embedded types** — re-exports of imported types: `->ExternalService`

Specialization is expressed with the `::` mutation syntax. The DSL stays language-agnostic — `BaseEntity::ExtendedEntity` may be realized through inheritance, composition, an adapter, or an interface implementation in the target language.

### Example

```yaml
Imports:
  - Types:
      - AnotherCellType
    From: path/to/another_cell

Usages:
  conventions: .goga/usages/conventions.md

Annotations: |
  Use `conventions` when writing code.

---

"ParseInput(input: string) -> data:List<byte>":
  location: parser.py
  annotations: |
    Parses raw input into a byte buffer.
  
    `input`: raw request payload

"HTTPServer(name: String)":
  location: server.py
  properties:
    "host -> String": |
      Bind address for incoming connections.
  methods:
    "handleRequest(req: Request) -> resp:Response": |
      Dispatches a single HTTP request.

      Algorithm:
      1. Parse input from `req` with `ParseInput`
      2. Filter result by some logic
      3. Save filtered result in `resp`
      4. Return `resp` object

---

Author: Goga
CreatedAt: 01/01/26
Description: |
  HTTP entry point cell.
```

## Pipelines

A **pipeline** is a named YAML file describing a sequence of stages an AI agent walks through to deliver a piece of work — propose, review, brainstorm, apply, design, plan, build, change, accept. Pipelines are resolved from `<cwd>/.goga/pipelines/` (project) and `~/.goga/pipelines/` (user); the project source wins on name conflicts.

Four definitions ship with goga:

| Pipeline  | Purpose                                              |
|-----------|------------------------------------------------------|
| `feature` | End-to-end feature implementation lifecycle          |
| `bugfix`  | Root-cause analysis and resolution for a defect      |
| `patch`   | Refactoring or minimal change with a formalized plan |
| `review`  | Scoped review of code, contracts, docs, then lint/format/tests |

```bash
goga pipeline feature
```

A pipeline-file answers **what** the pipeline does. A [workflow](https://qarium.github.io/goga/pipelines/workflows/) file layers **how the same pipeline should behave in this project** — per-stage CLI agent, additional prompt context, skills overrides, loop expansion, stage skipping via `skip`, per-stage auto-approval via `approve`, and new stages via `extend` — without forking the base file.

Read the full functional model in the [Pipelines](https://qarium.github.io/goga/pipelines/) section of the docs.

## Tools

A **tool** is a separately distributed Python package that extends goga with a specialized capability — documentation generation, translation, review, visualization, anything you can encode as an agent skill. Each tool ships one or more agent skills, an optional CLI entry point, and an optional set of pipeline-files. Tools land in the exact interpreter that runs goga, so they work regardless of how goga was deployed (pipx venv, system Python, container).

### Installing a tool

Tools are distributed as Python packages under the `goga-tool-` prefix. `goga install` targets the running interpreter's pip directly and re-syncs every already-connected agent after a successful pip — the new tool's skills and pipelines appear in `~/.goga/` and in each agent's symlink tree immediately:

```bash
# Install one tool, latest version
goga install <tool-name>

# Install a pinned or ranged version (four-form grammar)
goga install <tool-name> --version 1.0.x

# Install every tool declared under tools: in .goga/config.yml in one pip call
goga install
```

`goga install` branches on whether a tool name is given:

- **Single mode** (`goga install <name>`) — install one tool, then activate. `--version` resolves through the four-form grammar (`1.0.x` → `~=1.0.0`, `1.x` → `~=1.0`, `1.0.1` → `==1.0.1`, `latest` → no specifier). The project config is ignored.
- **Bulk mode** (`goga install`) — install every tool declared in the `tools:` section of `.goga/config.yml`, in a single pip invocation in YAML insertion order, then one activation pass. Declare versions inline:

  ```yaml
  # .goga/config.yml
  tools:
    one: latest        # → no specifier (pip selects newest)
    two: 1.0.x            # → ~=1.0.0  (>=1.0.0,<1.1.0)
    three: 1.x          # → ~=1.0    (>=1.0.0,<2.0.0)
    four: 1.0.1             # → ==1.0.1  (exact pin)
  ```

- **Empty mode** (`goga install` with no `tools:` section) — no-op. Prints `Nothing to install`, exits 0; pip is not invoked.

After installing, connect the tool to your agent (only required the first time, or to connect a new agent — `goga install` re-syncs already-connected agents automatically):

```bash
goga connect <agent>
```

Pass `goga install --no-connect` to opt out of post-install activation (CI/Docker escape-hatch where a transient activation failure must not fail the install). Pass `goga install --sudo` for system-Python installs requiring root — pip runs under `sudo --preserve-env=HOME`, activation never does.

See [`goga install`](https://qarium.github.io/goga/cli/install/) for the full version-grammar rules, exit codes, and single/bulk/empty semantics.

### Using a tool

**Via CLI:**

```bash
goga tool <name> [args...]
```

**Via agent skill:**

Invoke the `/goga:tool <name>` command (or `goga-tool` skill) in your agent session (the slash-command form works in `claude`, `opencode`, `qwen`; in Codex and cursor, invoke the dispatcher skill directly — `goga-tool`, or `$goga-tool` in Codex).

### Tool package contract

Each tool is a Python package with the `goga_tool_` prefix and the following layout:

```
goga_tool_<name>/
├── __init__.py        # main(argv: list[str]) entry point for CLI
├── skills/            # Required — at least one skill
│   └── <skill>/
│       └── SKILL.md   # Agent skill definition
└── pipelines/         # Optional — flat *.yml pipeline-files
    └── <name>.yml     # Installed by goga connect as <tool>:<name>.yml
```

A valid tool **must**:

- Be named with the `goga_tool_` prefix
- Contain a `skills/` directory with at least one skill (each skill directory has a `SKILL.md`)
- Expose a `main(argv: list[str])` function for CLI execution
- A `pipelines/` directory is **optional**; when present, its flat `*.yml` files are copied into `~/.goga/pipelines/` at `goga connect` time

The entry point may optionally declare a keyword-capable `ast` parameter to receive the project AST (loaded lazily from the current project root, only when declared). A tool that does not need the AST keeps the minimal `main(argv)` form and the AST is never built. See [`goga tool`](https://qarium.github.io/goga/cli/tool/) for the entry-point forms and opt-in rules.

### Skill naming

When `goga connect` installs a tool, the prefix `goga-tool-<tool-name>-` is added to every skill and the result lives centrally under `~/.goga/skills/`:

| In package (`skills/`)       | After `goga connect` (`~/.goga/skills/`) |
|------------------------------|------------------------------------------|
| `mkdocs/SKILL.md`            | `goga-tool-mkdocs`                       |
| `mkdocs-discovery/SKILL.md`  | `goga-tool-mkdocs-discovery`             |
| `mkdocs-writer/SKILL.md`     | `goga-tool-mkdocs-writer`                |

Rules:

- Use lowercase with hyphens as separators
- Name the main skill directory exactly `<tool-name>` — it becomes the dispatcher invoked by `/goga:tool <name>` (or `goga-tool` / `$goga-tool` in agents without slash-command support)
- Name sub-skills descriptively using the `<tool-name>-<purpose>` pattern (e.g., `mkdocs-discovery`, `mkdocs-validator`)

### Pipeline namespacing

Tool pipelines are namespaced on install. A file `<name>.yml` in a tool's `pipelines/` directory is copied into `~/.goga/pipelines/` **as `<tool>:<name>.yml`**, where `<tool>` is the package name with the `goga_tool_` prefix dropped and underscores normalized to hyphens (`goga_tool_hello_world` → `hello-world`):

| Source                                    | Destination in `~/.goga/pipelines/`  | Addressable as                |
|-------------------------------------------|--------------------------------------|-------------------------------|
| Internal goga source (`goga/assets/pipelines/`) | `feature.yml` (un-prefixed)     | `goga pipeline feature`       |
| Tool package `goga_tool_acme/pipelines/deploy.yml` | `acme:deploy.yml`             | `goga pipeline acme:deploy`   |

Namespacing structurally prevents collisions — between a tool pipeline and an internal-source pipeline, and between two tools shipping the same name. Only a residual conflict on the namespaced destination is possible, resolved with the same `--force-overwrite` semantics used for tool-skill installation. See [Shipped Pipelines](https://qarium.github.io/goga/pipelines/shipped/) for the full installation algorithm.

### Built-in tools

The following tools ship with goga out of the box — no separate install required. They are registered automatically once goga is installed and `goga connect` has been run.

| Tool | Description                                                                                             |
|---|---------------------------------------------------------------------------------------------------------|
| **viewer** | Interactive dependency graph viewer for CODEMANIFEST cells                                              |
| **mkdocs** | Generate and maintain MkDocs documentation from CODEMANIFEST files                                      |
| **scriba** | The writer — translates texts between languages and reviews texts against prompt-engineering principles |

Read the full Tools model in the [Tools](https://qarium.github.io/goga/tools/) section of the docs.

## Features

- **Specification-Driven Development** — Contracts are the source of truth; the agent workflow produces architecture, code, and tests from them
- **CODEMANIFEST DSL** — Describe cell contracts with types, routines, imports, usages, and annotations
- **Agent workflow** — Built-in cycle: `propose → brainstorm → apply → design → plan → build → change → accept`, with review checkpoints and shortcut paths for smaller changes
- **Validation** — AST-based linter with 21 document-level and 3 tree-level rules
- **Language parsers** — Extract contracts from Python, Go, Kotlin, Swift, and JavaScript via tree-sitter
- **CLI toolkit** — init, lint, build, schema, connect, install, upgrade, contract extraction, and pipeline commands
- **Pipelines** — flat YAML pipeline-files describing a named sequence of stages an AI agent walks through (propose → … → accept). Ships four ready-to-use definitions — `feature`, `bugfix`, `patch`, `review` — installable via `goga connect` and overridable per-project via optional declarative [workflow](https://qarium.github.io/goga/pipelines/workflows/) files at `.goga/workflows/<name>.yml` that layer per-stage agent/prompt/skills overrides, loop-expansion, stage skipping via `skip`, per-stage auto-approval via `approve`, and new stages via `extend` on top of a pipeline at compile time (disable with `--no-workflow`); cap concurrency with `goga pipeline <name> -p N` (the maximum number of stages that may run in parallel, subject to the pipeline's dependency rules)
- **Tools** — Extensible tool packages distributed as `goga-tool-*` Python modules that ship agent skills, an optional CLI entry point (`main(argv)`, with an opt-in `ast` injection of the project AST), and optional pipeline-files; install with `goga install <tool> [--version <form>]` (single) or `goga install` (bulk from the `tools:` section of `.goga/config.yml`, one pip call; empty section is a no-op), version forms `1.0.x` / `1.x` / `1.0.1` / `latest` resolve to PEP 440 specifiers, post-install activation re-syncs every connected agent unless `--no-connect` is set; skills install under a `goga-tool-<skill>` prefix into `~/.goga/skills/` (the skill whose directory matches the tool name becomes the `/goga:tool <name>` dispatcher), tool pipelines are namespaced on install as `<tool>:<name>.yml` into `~/.goga/pipelines/` so they are addressable as `goga pipeline <tool>:<name>` and never collide with internal pipelines
- **Docker builds & pipelines** — Execute build plans via ralphex and run pipelines in isolated containers, with automatic forwarding of AI-agent credentials (claude/codex/opencode), optional HTTP proxy / `--add-host` support for corporate environments, persistent pipeline state across runs, inline `roles` overrides that customize the three authorable agent prompts (planner/executor/reviewer, mapping to the planning/implementation/review stems) per pipeline-file — the `summary` prompt is always the shipped default, and an `--update` image refresh that builds from a project `dockerfile:` when declared (else pulls)

## Documentation

Full documentation is available at [qarium.github.io/goga](https://qarium.github.io/goga/).

## Contributing

After cloning, enable the local git hooks once:

```bash
make install-hooks
```

This installs two-layer protection against `Co-Authored-By:` trailers (project policy: no co-authorship in git history):

- **commit-msg** — blocks the commit at creation time.
- **pre-push** — blocks the push if any new commit being pushed contains the trailer (catches cases where the commit-msg hook was bypassed with `--no-verify` or not installed).

Bypass in rare intentional cases with `git commit --no-verify` / `git push --no-verify`.