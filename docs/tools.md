# Tools

Tools extend goga with specialized capabilities. Each tool is a separate Python package that installs skills into your AI agent and provides CLI commands.

## Installing a tool

Tools are distributed as Python packages with the `goga-tool-` prefix. Use `goga install` so the tool lands in the exact interpreter that runs goga:

```bash
# Install one tool (latest version)
goga install <tool-name>

# Install a pinned / ranged version via the four-form grammar
goga install <tool-name> --version 1.0.x

# Install every tool declared under `tools:` in .goga/config.yml in one pip call
goga install
```

See [`goga install`](cli/install.md) for the version grammar and single / bulk / empty modes. You can also install directly with pip:

```bash
pip install goga-tool-<tool-name>
```

After installing, connect the tool to your agent:

```bash
goga connect <agent>
```

`goga connect` auto-discovers all installed `goga_tool_*` packages and installs their skills centrally into `~/.goga/skills/`, then symlinks them into each connected agent's skills directory. If the package ships any pipeline `*.yml` files under `pipelines/`, those are installed into `~/.goga/pipelines/` in the same step — see [Pipelines / Shipped Pipelines](pipelines/shipped.md) for the conflict-resolution rules. The tool becomes available both as an agent skill and as a CLI command.

## Built-in tools

The following tools ship with goga out of the box — no separate install required. They are registered automatically once goga is installed and `goga connect` has been run.

| Tool | Description                                                                                             | Docs | GitHub |
|---|---------------------------------------------------------------------------------------------------------|---|---|
| **viewer** | Interactive dependency graph viewer for CODEMANIFEST cells                                              | [Documentation](https://qarium.github.io/goga-tool-viewer/) | [Source](https://github.com/qarium/goga-tool-viewer) |
| **mkdocs** | Generate and maintain MkDocs documentation from CODEMANIFEST files                                      | [Documentation](https://qarium.github.io/goga-tool-mkdocs/) | [Source](https://github.com/qarium/goga-tool-mkdocs) |
| **scriba** | The writer — translates texts between languages and reviews texts against prompt-engineering principles | [Documentation](https://qarium.github.io/goga-tool-scriba/) | [Source](https://github.com/qarium/goga-tool-scriba) |

## Using a tool

**Via CLI:**

```bash
goga tool <name> [args...]
```

**Via agent skill:**

Invoke the `/goga:tool <name>` command in your agent session. The dispatcher routes the request to the matching skill.

## Tool structure

Each tool package follows a standard layout:

```
goga_tool_<name>/
├── __init__.py        # main(args) entry point for CLI
├── skills/            # Required — at least one skill
│   └── <skill>/
│       └── SKILL.md   # Agent skill definition
└── pipelines/         # Optional — flat *.yml pipeline files
    └── <name>.yml     # Installed into ~/.goga/pipelines/ by goga connect
```

A valid tool must:

- Be named with the `goga_tool_` prefix
- Contain a `skills/` directory with at least one skill
- Each skill directory must include a `SKILL.md` file
- Expose a `main(args: list[str])` function for CLI execution

A `pipelines/` directory is **optional**. When present, `goga connect`
copies its flat `*.yml` files into `~/.goga/pipelines/` next to the
shipped pipelines, with the same conflict-resolution rules used for
tool-skill installation. See
[Pipelines / Shipped Pipelines](pipelines/shipped.md) for the full
installation algorithm.

## Skill naming

Each skill directory inside `skills/` has a base name. When `goga connect` installs the tool, the prefix `goga-tool-<skill-name>-` is automatically added to every skill and the result lives centrally under `~/.goga/skills/`.

| In package (`skills/`)      | After `goga connect` (`~/.goga/skills/`) |
|-----------------------------|------------------------------------------|
| `mkdocs/SKILL.md`          | `goga-tool-mkdocs`                       |
| `mkdocs-discovery/SKILL.md`| `goga-tool-mkdocs-discovery`             |
| `mkdocs-writer/SKILL.md`   | `goga-tool-mkdocs-writer`                |

The skill whose directory name matches the tool name becomes the entry point — the dispatcher invoked by `/goga:tool <name>`.

### Naming rules

- Use lowercase with hyphens as separators
- Name the main skill directory exactly `<tool-name>` to serve as the dispatcher entry point
- Name sub-skills descriptively using the `<tool-name>-<purpose>` pattern (e.g., `mkdocs-discovery`, `mkdocs-validator`)
- Keep names concise and indicative of the skill's responsibility