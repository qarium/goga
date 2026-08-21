**A new semantic layer between specification and implementation** — helping humans and AI agents reason about project structure at a higher level of abstraction.

A full-fledged **Specification-Driven Development (SDD)** framework built on the [**CODEMANIFEST**](https://github.com/qarium/codemanifest/blob/0.0.x/specs/en.md) specification: describe cell contracts, validate them, extract them from source code, and drive an end-to-end agent workflow — propose, brainstorm, design, plan, build, change, and accept — under the hood.

<div align="center">
  <p><strong>Languages</strong></p>
  <p>
    <img src="assets/brands/python.svg" alt="Python" width="36" height="36">&nbsp;&nbsp;&nbsp;&nbsp;
    <img src="assets/brands/javascript.svg" alt="JavaScript" width="36" height="36">&nbsp;&nbsp;&nbsp;&nbsp;
    <img src="assets/brands/kotlin.svg" alt="Kotlin" width="36" height="36">&nbsp;&nbsp;&nbsp;&nbsp;
    <img src="assets/brands/swift.svg" alt="Swift" width="36" height="36">&nbsp;&nbsp;&nbsp;&nbsp;
    <img src="assets/brands/go.svg" alt="Go" width="36" height="36">
  </p>
  <p><strong>Agents</strong></p>
  <p>
    <img src="assets/brands/claude.svg" alt="Claude" width="36" height="36">&nbsp;&nbsp;&nbsp;&nbsp;
    <img src="assets/brands/openai.svg" alt="Codex" width="36" height="36">&nbsp;&nbsp;&nbsp;&nbsp;
    <img src="assets/brands/opencode.svg" alt="OpenCode" width="36" height="36">&nbsp;&nbsp;&nbsp;&nbsp;
    <img src="assets/brands/cursor.svg" alt="Cursor" width="36" height="36">&nbsp;&nbsp;&nbsp;&nbsp;
    <img src="assets/brands/qwen.svg" alt="Qwen" width="36" height="36">
  </p>
</div>

## Why goga?

Code and contracts drift apart. Comments rot, types lie, and architecture lives only in someone's head — invisible to the agent that needs to extend it.

Goga makes the contract the source of truth. Every cell is a directory with a `CODEMANIFEST` file describing exactly what it exposes, what it imports, and how it expects to be used. Validators enforce structure. Parsers extract contracts back from source.

Goga is also an **execution engine, not just a format**. A built-in pipeline runner takes a feature from a one-line idea all the way to acceptance — propose, review, brainstorm, apply, design, plan, build, change, accept — inside an isolated container, with agent credentials forwarded automatically. No manual orchestration between stages; the pipeline runs the whole cycle for you.

The result: a project that humans and AI agents can navigate, change, and reason about at the same level of abstraction.

## Quick start

Install goga:

```bash
pipx install goga
```

Connect goga to your agent:

```bash
goga connect <agent>
```

Upgrade goga later and re-sync every connected agent — no need to call pip directly:

```bash
goga upgrade
```

Line-constrained upgrades (`--patch` / `--minor`) and the other options are covered in [`goga upgrade`](cli/upgrade.md).

Initialize a project — the interactive wizard sets up `.goga/config.yml`, language conventions, and (optionally) a `Dockerfile`:

```bash
goga init
```

### Ship a feature in two commands

Goga ships ready-to-use pipelines that run the workrounds inside an isolated container. After `goga init`, from inside your agent:

```bash
goga pipeline refinement
goga pipeline development
```

The `refinement` pipeline walks the product side — define → discover → propose → task-review — and ends with a reviewed task. The `development` pipeline picks it up and walks the engineering side stage by stage:

```
brainstorm → architecture-review → apply-architecture → code-design → design-review →
coding-plan → plan-review → commit-changes → accept-result
```

When the work does not need product elaboration, skip the early stages — for example, start `refinement` at `discover`:

```bash
goga pipeline refinement -s define
```

Four more pipelines cover the remaining lifecycles:

```bash
goga pipeline bugfix     # root-cause analysis and defect resolution
goga pipeline patch      # refactoring or minimal change with a plan
goga pipeline review     # scoped review of code, contracts, docs, then lint/format/tests
goga pipeline sync       # sync specifications and tests with the implementation
```

A pipeline-file answers **what** the pipeline does. An optional [workflow](pipelines/workflows.md) file answers **how the same pipeline should behave in this project** — per-stage agent, extra prompt context, loop expansion, stage skipping — without forking the base file. See [Pipelines](pipelines/index.md) for the full functional model.

### Drive the cycle by hand

If you want explicit control over each step instead of running the whole cycle automatically, open your agent in the project directory and describe what you want to build:

```text
/goga:propose <what you want to create>
```

> The slash-command form `/goga:<command>` works in agents that consume the goga command bundle — currently `claude`, `opencode`, and `qwen` (see [`goga connect`](cli/connect.md)). Codex and cursor do not register commands; in those agents invoke the skill directly: `goga-propose` (Codex uses the `$` prefix — `$goga-propose`). Each subsequent command takes the previous artifact as input and produces the next one. See [Workflow](workflow/index.md) for the two workrounds — refinement and development — and the entry depths each supports.

## Next steps

- [Pipelines](pipelines/index.md) — Run the agent-driven cycle automatically with `goga pipeline`
- [Getting Started](getting-started.md) — Initialize your first goga project
- [Workflow](workflow/index.md) — The agent-driven feature development cycle
- [Cell](cell/index.md) — Cell structure, usages, and CODEMANIFEST DSL reference
- [Configuration](configuration/index.md) — Configure `.goga/config.yml`
- [CLI Reference](cli/index.md) — Full command reference
- [Languages](languages/index.md) — Contract extraction per language
