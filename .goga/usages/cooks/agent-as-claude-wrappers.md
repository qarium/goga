# `*-as-claude.sh` Agent Wrappers

> For a user-facing summary — baseline wrapper table, per-agent environment variables, and how to add a custom agent — see [Agents](../../../docs/configuration/agents.md) in the Configuration reference. This practice file is the container-image-author reference for wrapper internals (canonical location, wrapper classes, jq filters).

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

where `<agent>` is the agent name (e.g. `claude`, `codex`, `cursor`,
`opencode`). The suffix `-as-claude.sh` is fixed — it self-describes the
wrapper's purpose: "run `<agent>` as if it were the `claude` CLI".

The canonical baseline set is:

| `<agent>`  | Wrapper file                |
|------------|-----------------------------|
| `claude`   | `claude-as-claude.sh`       |
| `codex`    | `codex-as-claude.sh`        |
| `cursor`   | `cursor-as-claude.sh`       |
| `opencode` | `opencode-as-claude.sh`     |
| `qwen`     | `qwen-as-claude.sh`         |

Any other `<agent>` value is permitted as long as the corresponding
`/home/goga/bin/<agent>-as-claude.sh` file exists in the image; absence of
the file is surfaced by the downstream tool that tries to invoke it, not by
any wrapper-resolution layer.

## Wrapper classes

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

The codex wrapper is configured through environment variables consumed by
the underlying `codex` CLI. They are forwarded into the container through
the normal env layering (`home.env` → project `pipeline.env` /
`build.task_executor.env` → CLI `-e` / `extra_env`):

| Variable         | Required | Default                 | Purpose                                                                                                                                  |
|------------------|----------|-------------------------|------------------------------------------------------------------------------------------------------------------------------------------|
| `CODEX_MODEL`    | no       | codex default           | Model selector used by the codex CLI. `goga init` suggests this key automatically when codex is the chosen agent.                        |
| `CODEX_SANDBOX`  | no       | `danger-full-access`    | Sandbox mode. `danger-full-access` disables codex sandboxing so the agent can run builds and modify the workspace without restrictions. |
| `CODEX_VERBOSE`  | no       | `0`                     | Set to `1` to include command execution output in the codex response — useful for debugging pipeline/build failures.                     |

### Async-run wrapper — `cursor-as-claude.sh`

`cursor-as-claude.sh` adapts the Cursor **Cloud Agents API** to the claude
stream-json format. Unlike the codex/opencode format-converters, the
Cursor API is asynchronous and run-based — there is no synchronous
`/chat/completions` endpoint. The wrapper:

1. creates a no-repo Cloud Agent via `POST /v1/agents` with the prompt
   read from stdin (Cloud VM startup may take minutes — create timeout
   300s);
2. polls the run until it reaches a terminal status
   (`FINISHED`/`ERROR`/`CANCELLED`/`EXPIRED`) with a 25-minute backstop
   deadline (below the 30-minute executor idle timeout);
3. emits an assistant envelope carrying the final text, followed by a
   success `result` event — even on non-`FINISHED` outcomes, so the
   problem description is visible to the user and the executor finishes
   cleanly;
4. archives the agent best-effort (`POST /v1/agents/<id>/archive`) so a
   no-repo single-use agent does not clutter the account.

All CLI flags passed by the caller (`--model`, `--effort`,
`--dangerously-skip-permissions`, etc.) are ignored — the wrapper reads
the prompt only from stdin, matching how `claude` consumes a piped prompt.

The wrapper is configured through three environment variables:

| Variable          | Required | Default                          | Purpose                                                                                                   |
|-------------------|----------|----------------------------------|-----------------------------------------------------------------------------------------------------------|
| `CURSOR_API_KEY`  | yes      | —                                | Bearer authorization token for `api.cursor.com`. The wrapper exits with an error when this is unset.      |
| `CURSOR_BASE_URL` | no       | `https://api.cursor.com/v1`      | Base URL of the Cursor Cloud Agents API. Override for a proxy or a self-hosted gateway.                   |
| `CURSOR_MODEL`    | no       | *(unset — Cursor default)*       | `model.id` selector. An empty value or `"auto"` omits the `model` field from the create request, letting Cursor pick its default. Any other value is forwarded as `model.id`. |

Unlike claude/codex/opencode, the cursor wrapper is **env-based, not
credential-file-based** — there is no host credential file to bind-mount.
The three variables above are forwarded into the container through the
normal env layering (`home.env` → project `pipeline.env` /
`build.task_executor.env` → CLI `-e` / `extra_env`), with the same formula
documented under the Home configuration section of `docs/configuration/index.md`.

### Invocation-shape wrapper over the qwen CLI — `qwen-as-claude.sh`

`qwen-as-claude.sh` is a thin invocation-shape delegate over the `qwen` CLI (the `@qwen-code/qwen-code` npm package shipped in the goga image). It mirrors `claude-as-claude.sh`'s shape: the wrapper forwards the prompt + env to `qwen`, captures the final aggregated answer, and emits one `assistant` envelope + a `result: success` event. The agent loop — tool use, multi-turn, file writes — runs inside `qwen`, exactly as it runs inside the `claude` binary for `claude-as-claude.sh`.

The wrapper does no HTTP itself. `qwen` owns the OpenAI Chat Completions transport, which means one wrapper serves Qwen Cloud, DeepSeek, OpenRouter, OpenAI direct, and local vLLM/ollama:

| Variable          | Required | Default                     | Purpose                                                                                                                                  |
|-------------------|----------|-----------------------------|------------------------------------------------------------------------------------------------------------------------------------------|
| `OPENAI_MODEL`    | yes      | —                           | Passed to `qwen --model`. No default — server choice would be unpredictable.                                                            |
| `OPENAI_BASE_URL` | no       | qwen-code default           | Passed to `qwen --openai-base-url` only when set.                                                                                        |
| `OPENAI_API_KEY`  | no       | *(unset)*                   | Passed to `qwen --openai-api-key` only when set — covers local no-auth servers (vLLM/ollama).                                           |

The wrapper invokes `qwen --yolo` so every tool call auto-approves (otherwise the stage hangs on an interactive approval prompt that no one is there to answer in pipeline mode) and `--output-format text` so the final aggregated answer lands on stdout, where the wrapper re-envelopes it.

Like `claude-as-claude.sh`, the wrapper is a near-no-op that delegates everything to the underlying CLI — the only logic it owns is the prompt/env forwarding and the two-line stream-json envelope. Use it as a reference shape when designing a wrapper around any future agent CLI that owns its own tool-use loop.

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
