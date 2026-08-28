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

See [`goga install`](cli/install.md) for the version grammar and single / bulk / empty modes.

After installing, connect the tool to your agent:

```bash
goga connect <agent>
```

If you have already connected an agent, `goga install` automatically re-syncs every connected agent after a successful pip, so the new tool's skills and pipelines appear immediately — no separate `goga connect` call is needed. `goga connect` is only required the first time (or to connect a new agent); pass `goga install --no-connect` to opt out of activation.

`goga connect` auto-discovers all installed `goga_tool_*` packages and installs their skills centrally into `~/.goga/skills/`, then symlinks them into each connected agent's skills directory. If the package ships any pipeline `*.yml` files under `pipelines/`, those are installed into `~/.goga/pipelines/` in the same step, **namespaced as `<tool>:<name>.yml`** so they are addressable as `goga pipeline <tool>:<name>` (internal pipelines stay un-prefixed) — see [Pipelines / Shipped Pipelines](pipelines/shipped.md) for the namespacing and residual-conflict rules. The tool becomes available both as an agent skill and as a CLI command.

## Removing a tool

`goga uninstall` removes exactly one tool package from the running interpreter's pip. It asks for confirmation first — Enter removes (the default is Y), `n` cancels:

```bash
# Remove one tool (interactive confirmation, Enter = yes)
goga uninstall <tool-name>

# Skip the confirmation — the scripted/CI form
goga uninstall <tool-name> --yes
goga uninstall <tool-name> -y

# Remove from a system-Python install requiring root
goga uninstall <tool-name> --sudo

# Remove and re-sync another user's goga installation
goga uninstall <tool-name> --user alice
```

After a successful pip uninstall, every connected agent is re-synced: the removed tool's skills and pipelines disappear from `~/.goga/` and from each agent's symlink tree. A tool removed by hand with plain pip leaves those artifacts behind until the next re-sync.

See [`goga uninstall`](cli/uninstall.md) for the full confirmation, sudo/user, and exit-code semantics.

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

Invoke the `/goga:tool <name>` command in your agent session. The dispatcher routes the request to the matching skill. The slash-command form works in agents that consume the goga command bundle (`claude`, `opencode`, `qwen`); in Codex and cursor, invoke the dispatcher skill directly — `goga-tool` (Codex: `$goga-tool`).

## Tool structure

Each tool package follows a standard layout:

```
goga_tool_<name>/
├── __init__.py        # main(argv) entry point for CLI
├── skills/            # Required — at least one skill
│   └── <skill>/
│       └── SKILL.md   # Agent skill definition
└── pipelines/         # Optional — flat *.yml pipeline files
    └── <name>.yml     # Installed by goga connect as <tool>:<name>.yml
```

A valid tool must:

- Be named with the `goga_tool_` prefix
- Contain a `skills/` directory with at least one skill
- Each skill directory must include a `SKILL.md` file
- Expose a `main(argv: list[str])` function for CLI execution

A tool **may** additionally expose an `install(user: str | None = None)`
callable in its facade package — the post-install hook. `goga install` calls
it after a successful pip, passing the initiating user (`SUDO_USER` when goga
itself runs under sudo, else the current OS user) only when the parameter is
declared keyword-capable; otherwise the hook is called with no arguments. A
missing or non-callable `install` is skipped quietly. See
[`goga install` — Post-install hooks](cli/install.md#post-install-hooks).

A `pipelines/` directory is **optional**. When present, `goga connect`
copies its flat `*.yml` files into `~/.goga/pipelines/` **namespaced as
`<tool>:<name>.yml`** (where `<tool>` is the package name with the
`goga_tool_` prefix dropped and underscores normalized to hyphens, so
`goga_tool_hello_world` becomes `hello-world`), next to the un-prefixed
internal-source pipelines. Namespacing structurally prevents collisions with internal
pipelines and between two tools shipping the same name; only a residual
conflict on the namespaced destination is possible, resolved with the
same `--force-overwrite` semantics used for tool-skill installation. See
[Pipelines / Shipped Pipelines](pipelines/shipped.md) for the full
installation algorithm.

## Optional injections

`main` may optionally declare a keyword-capable `ast` parameter to receive the
project AST (loaded lazily from the current project root, only when declared).
A tool that does not need the AST keeps the minimal `main(argv)` form and the
AST is never built. Validation errors in the loaded tree pass through to the
tool unchanged. See [goga tool — Optional injections](cli/tool.md#optional-injections)
for the entry-point forms and opt-in rules.

## Skill naming

Each skill directory inside `skills/` has a base name. When `goga connect` installs the tool, the prefix `goga-tool-<skill-name>-` is automatically added to every skill and the result lives centrally under `~/.goga/skills/`.

| In package (`skills/`)      | After `goga connect` (`~/.goga/skills/`) |
|-----------------------------|------------------------------------------|
| `mkdocs/SKILL.md`          | `goga-tool-mkdocs`                       |
| `mkdocs-discovery/SKILL.md`| `goga-tool-mkdocs-discovery`             |
| `mkdocs-writer/SKILL.md`   | `goga-tool-mkdocs-writer`                |

The skill whose directory name matches the tool name becomes the entry point — the dispatcher invoked by `/goga:tool <name>` (or `goga-tool` / `$goga-tool` in agents without slash-command support).

### Naming rules

- Use lowercase with hyphens as separators
- Name the main skill directory exactly `<tool-name>` to serve as the dispatcher entry point
- Name sub-skills descriptively using the `<tool-name>-<purpose>` pattern (e.g., `mkdocs-discovery`, `mkdocs-validator`)
- Keep names concise and indicative of the skill's responsibility

## Pipeline naming

Each pipeline file inside `pipelines/` has a base stem (the filename without `.yml`). When `goga connect` installs the tool, the prefix `<tool>:` is automatically added to every pipeline and the result lives centrally under `~/.goga/pipelines/`.

| In package (`pipelines/`)   | After `goga connect` — pipeline name         |
|-----------------------------|----------------------------------------------|
| `deploy.yml`                | `acme:deploy`                                |
| `release-notes.yml`         | `acme:release-notes`                         |
| `check.yml` (tool `hello-world`) | `hello-world:check`                     |

The `<tool>` prefix is the canonical hyphenated tool name — the package name with the `goga_tool_` prefix dropped and underscores replaced with hyphens (`goga_tool_hello_world` → `hello-world`). A namespaced pipeline is run as `goga pipeline <tool>:<name>` (e.g., `goga pipeline acme:deploy`); internal goga pipelines stay un-prefixed (e.g., `goga pipeline feature`). Each tool occupies its own `<tool>:` stem, distinct from internal pipelines and from other tools' stems.

### Naming rules

- Name pipeline files with lowercase and hyphens as separators
- Use flat `*.yml` files directly under `pipelines/` — no subdirectories
- Rely on the automatic `<tool>:` prefix for namespacing; never bake the tool name into the filename yourself
- A residual conflict on the namespaced destination (the same `<tool>:<name>.yml` already exists) is resolved with `goga connect --force-overwrite` — see [Pipelines / Shipped Pipelines](pipelines/shipped.md)