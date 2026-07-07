# `*-as-claude.sh` Agent Wrappers

## Domain

Convention for organizing shell wrapper scripts that present an arbitrary AI
agent CLI as the `claude` invocation shape expected by downstream tools that
consume Claude Code stream-json output.

Target audience: container image authors who need to install agent wrappers
into a canonical in-container location, and tool authors who reference those
wrappers by absolute path in their generated config files.

## Canonical location

All agent wrappers live in a single canonical directory inside the container:

```
/home/goga/bin/
```

This directory is added to the container user's `PATH` so the wrappers are
reachable both by absolute path (preferred for tool-generated configs) and by
bare name (for interactive invocations).

## Naming convention

Every wrapper follows the pattern:

```
<agent>-as-claude.sh
```

where `<agent>` is the agent name (e.g. `claude`, `codex`, `opencode`). The
suffix `-as-claude.sh` is fixed — it self-describes the wrapper's purpose:
"run `<agent>` as if it were the `claude` CLI".

The canonical baseline set is:

| `<agent>` | Wrapper file                |
|-----------|-----------------------------|
| `claude`  | `claude-as-claude.sh`       |
| `codex`   | `codex-as-claude.sh`        |
| `opencode`| `opencode-as-claude.sh`     |

Any other `<agent>` value is permitted as long as the corresponding
`/home/goga/bin/<agent>-as-claude.sh` file exists in the image; absence of
the file is surfaced by the downstream tool that tries to invoke it, not by
any wrapper-resolution layer.

## Two wrapper classes

### Invocation-shape wrapper — `claude-as-claude.sh`

`claude-as-claude.sh` performs **no format conversion**. It exists only to
apply ambient settings that the consumer should not own (e.g. disabling
attribution) before delegating to the `claude` binary. The argument vector
is forwarded verbatim. The wrapper does **not** remap API key environment
variables — `ANTHROPIC_API_KEY` flows through from the launcher env
directly because the goga-generated `.ralphex/config` sets
`preserve_anthropic_api_key = true`, which keeps ralphex from unsetting
the key before invoking the wrapper.

Typical body:

```bash
#!/bin/bash
exec claude \
     --setting-sources user \
     --settings '{"attribution":{"commit":"","pr":""}}' \
     "$@"
```

Note on `claude` shadowing: the file name `claude-as-claude.sh` does not
shadow the `claude` binary on `PATH`. The bare-name `claude` still resolves
to the real binary; the wrapper is reachable only via the full filename or
the absolute path.

### Format-converter wrapper — `codex-as-claude.sh`, `opencode-as-claude.sh`

`codex-as-claude.sh` and `opencode-as-claude.sh` perform **format
conversion**: the underlying agent CLI emits its own streaming JSONL output
format, and the wrapper translates it into the Claude Code stream-json
format that downstream tools consume. The conversion is implemented with
`jq` filters.

The argument vector is forwarded to the underlying agent CLI; only stdout
passes through the conversion stage.

## Runtime dependency — `jq`

The format-converter wrappers depend on `jq` being available on `PATH` in
the container. `jq` is part of the canonical base image package set — the
image build is responsible for installing it; the wrappers do not vendor
their own copy.

## Absolute-path convention

Tool-generated config files always reference wrappers by **absolute path**
under `/home/goga/bin/`, never by bare name. This avoids any `PATH`
resolution ambiguity and makes the agent selection explicit in the config.

Bare-name invocation (e.g. typing `codex-as-claude.sh` at a shell prompt)
works because `/home/goga/bin/` is on `PATH`, but this is a convenience for
interactive use, not a contract for tool-generated configs.
