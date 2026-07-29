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

Goga makes the contract the source of truth. Every cell is a directory with a `CODEMANIFEST` file describing exactly what it exposes, what it imports, and how it expects to be used. Validators enforce structure. Parsers extract contracts back from source. An agent workflow carries a feature from a one-line proposal all the way to acceptance — without losing the thread.

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

Initialize a project — the interactive wizard sets up `.goga/config.yml`, language conventions, and (optionally) a `Dockerfile`:

```bash
goga init
```

From there, open your agent in the project directory and describe what you want to build:

```text
/goga:propose <what you want to create>
```

The example above uses Claude Code style. For other agents, invoke the skill directly: `goga-propose`.

## Next steps

- [Getting Started](getting-started.md) — Initialize your first goga project
- [Workflow](workflow/index.md) — The agent-driven feature development cycle
- [Cell](cell/index.md) — Cell structure, usages, and CODEMANIFEST DSL reference
- [Configuration](configuration/index.md) — Configure `.goga/config.yml`
- [CLI Reference](cli/index.md) — Full command reference
- [Languages](languages/index.md) — Contract extraction per language