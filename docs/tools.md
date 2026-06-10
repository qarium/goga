# Tools

Tools extend goga with specialized capabilities. Each tool is a separate Python package that installs skills into your AI agent and provides CLI commands.

## Installing a tool

Tools are distributed as Python packages with the `goga-tool-` prefix:

```bash
pip install goga-tool-<tool-name>
```

After installing, connect the tool to your agent:

```bash
goga connect <agent>
```

`goga connect` auto-discovers all installed `goga_tool_*` packages and copies their skills into the agent's skills directory. The tool becomes available both as an agent skill and as a CLI command.

## Using a tool

**Via CLI:**

```bash
goga tool <name> [args...]
```

**Via agent skill:**

Invoke the `/goga:tool <name>` command in your agent session. The dispatcher routes the request to the matching skill.

## Available tools

| Tool | Description | Docs | GitHub |
|---|---|---|---|
| **viewer** | Interactive dependency graph viewer for CODEMANIFEST cells | [Documentation](https://qarium.github.io/goga-tool-viewer/) | [Source](https://github.com/qarium/goga-tool-viewer) |
| **mkdocs** | Generate and maintain MkDocs documentation from CODEMANIFEST files | [Documentation](https://qarium.github.io/goga-tool-mkdocs/) | [Source](https://github.com/qarium/goga-tool-mkdocs) |
| **scriba** | Translate DSL keywords between languages | [Documentation](https://qarium.github.io/goga-tool-scriba/) | [Source](https://github.com/qarium/goga-tool-scriba) |

## Tool structure

Each tool package follows a standard layout:

```
goga_tool_<name>/
├── __init__.py        # main(args) entry point for CLI
└── skills/
    └── <skill>/
        └── SKILL.md   # Agent skill definition
```

A valid tool must:

- Be named with the `goga_tool_` prefix
- Contain a `skills/` directory with at least one skill
- Each skill directory must include a `SKILL.md` file
- Expose a `main(args: list[str])` function for CLI execution
