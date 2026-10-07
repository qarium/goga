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

### Format-converter wrapper — `codex-as-claude.sh`, `opencode-as-claude.sh`, `qwen-as-claude.sh`, `cursor-as-claude.sh`

`codex-as-claude.sh`, `opencode-as-claude.sh`, `qwen-as-claude.sh`, and
`cursor-as-claude.sh` perform **format conversion**: the underlying agent
CLI emits its own streaming JSONL output format, and the wrapper
translates it into the Claude Code stream-json format that downstream
tools consume. The conversion is implemented with `jq` filters.

The argument vector is forwarded to the underlying agent CLI; only stdout
passes through the conversion stage.

The codex wrapper is configured through environment variables consumed by
the underlying `codex` CLI. They are forwarded into the container through
the normal env layering (`home.env` → project `pipeline.env` /
`build.task_executor.env` → CLI `-e` / `extra_env`):

| Variable         | Required | Default                 | Purpose                                                                                                                                  |
|------------------|----------|-------------------------|------------------------------------------------------------------------------------------------------------------------------------------|
| `CODEX_MODEL`    | no       | codex default           | Model selector — the full codex model id, for example `gpt-6-astra`, `gpt-6-sol`, `gpt-6-luna` or `gpt-5.6-sol`; a bare family name like `astra` is not a valid id. `goga init` suggests this key automatically when codex is the chosen agent. |
| `CODEX_REASONING` | no      | codex default           | Reasoning effort passed through as `model_reasoning_effort` — `none`, `minimal`, `low`, `medium`, `high`, `xhigh` or `max`.            |
| `CODEX_SANDBOX`  | no       | `danger-full-access`    | Sandbox mode. `danger-full-access` disables codex sandboxing so the agent can run builds and modify the workspace without restrictions. |
| `CODEX_VERBOSE`  | no       | `0`                     | Set to `1` to include command execution output in the codex response — useful for debugging pipeline/build failures.                     |

### Format-converter wrapper over the OpenCode CLI — `opencode-as-claude.sh`

`opencode-as-claude.sh` is a format-converter delegate over the `opencode`
CLI (`opencode-ai` npm package shipped in the goga image; the wrapper
itself lives in goga `scripts/`, versioned in this repository). The prompt
is accepted via `-p` or stdin, ralphex-injected `--model`/`--effort` flags
are parsed (`--effort` maps to opencode's `--variant`), and the agent runs
as `opencode run --format json` with every tool call auto-approved through
an `OPENCODE_CONFIG_CONTENT` permission merge (deep-merged, never replacing
user settings).

The `jq` translator emits Claude-contract events:

- `text` and `reasoning` parts become assistant text blocks (reasoning
  surfaced as narrative, empty ones dropped);
- `tool_use` events become `tool_use` actions **once per call** (opencode
  emits them aggregated, already in a terminal state `completed`/`error`):
  `bash` → `Bash{command}`, `edit`/`write` → `Edit{file_path}` (opencode
  uses camelCase `filePath`), every other tool under its native name with
  its input verbatim;
- the final `step_finish` (reason `stop`) becomes the terminal `result`
  event — intermediate per-turn finishes (reason `tool-calls`) are skipped
  so multi-step sessions keep streaming; the fallback `result` is emitted
  only when no terminal finish arrived, and opencode's exit code is
  preserved (a failed run no longer looks like a success);
- non-JSON stdout lines pass through untouched (the executor's non-JSON
  fallback channel), and stderr is re-emitted as assistant text after the
  stream so error/limit pattern detection keeps working.

Review mode mirrors the other adapters with an honest sequential
formulation — OpenCode has no parallel sub-agents, so the adapter tells
the model to perform each review agent's work one at a time before
applying fixes, keeping `<<<RALPHEX:...>>>` signals unchanged. The wrapper
also carries an anti-echo output-rules instruction file (appended into
`OPENCODE_CONFIG_CONTENT.instructions`) so the model never restates
`<<<RALPHEX:...>>>` strings in planning output, and it forwards SIGTERM
to the opencode child for graceful shutdown.

| Variable                 | Required | Default                        | Purpose                                                                                                    |
|--------------------------|----------|--------------------------------|------------------------------------------------------------------------------------------------------------|
| `OPENCODE_MODEL`         | no       | opencode default               | Model in `provider/model` format, e.g. `openai/gpt-4o`.                                                    |
| `OPENCODE_VARIANT`       | no       | opencode default               | Model variant / reasoning effort, e.g. `high`, `medium`, `low`.                                            |
| `OPENCODE_EFFORT`        | no       | —                              | Alias for `OPENCODE_VARIANT` when `OPENCODE_VARIANT` is unset.                                              |
| `OPENCODE_REASONING`     | no       | —                              | Alias for `OPENCODE_VARIANT` when both `OPENCODE_VARIANT` and `OPENCODE_EFFORT` are unset.                  |
| `OPENCODE_VERBOSE`       | no       | `0`                            | Set to `1` to include `[step started]` markers for each step.                                               |
| `OPENCODE_CONFIG_CONTENT`| no       | `{"permission":{"*":"allow"}}` | Inline opencode config as JSON; the wrapper deep-merges the auto-approve permission set and appends its output-rules instruction file. Also the hook for custom providers — see the agents reference for an `@ai-sdk/openai-compatible` endpoint example. |

Variant precedence: `OPENCODE_VARIANT` > `OPENCODE_EFFORT` >
`OPENCODE_REASONING`; the first set value wins.

### Format-converter wrapper over the cursor-agent CLI — `cursor-as-claude.sh`

`cursor-as-claude.sh` is a format-converter delegate over the
`cursor-agent` CLI (installed in the goga image via
`curl https://cursor.com/install -fsS | bash`, run as the `goga` user so
the binary lands in `/home/goga/.local/bin`). The prompt is read only
from stdin and `cursor-agent` runs as
`cursor-agent -p --yolo --output-format stream-json`, so every tool call
auto-approves (otherwise the stage hangs on an interactive approval
prompt that no one is there to answer in pipeline mode). The wrapper
streams cursor-agent's JSONL stdout line by line through a `jq`
translator, so events reach the consumer as they occur — not aggregated
after the run. The agent loop — tool use, multi-turn, file writes — runs
inside `cursor-agent`, exactly as it runs inside the `claude` binary for
`claude-as-claude.sh`.

The wrapper does no HTTP itself. `cursor-agent` owns the Cursor Cloud
transport and reads `CURSOR_API_KEY` natively from the environment (there
is no `--api-key` flag on the CLI). The prompt is forwarded to
`cursor-agent` as a positional argument after `--` (`cursor-agent` does
not read stdin itself, and `--` guards against prompts that start with
`-` being misparsed as flags).

| Variable         | Required | Default                   | Purpose                                                                                                                |
|------------------|----------|---------------------------|------------------------------------------------------------------------------------------------------------------------|
| `CURSOR_API_KEY` | yes      | —                         | Authorization token. `cursor-agent` reads `CURSOR_API_KEY` natively from the environment. The wrapper exits with an error when this is unset. |
| `CURSOR_MODEL`   | no       | *(unset — Cursor default)*| `cursor-agent --model` selector. An empty value or `"auto"` omits the `--model` flag; any other value is forwarded as `--model`. |

The translation is light because cursor-agent already follows the Claude
stream-json event convention; the `jq` filter only:

- passes `text` blocks through unchanged;
- converts `thinking` blocks into narrative `text` blocks (empty thinking is dropped);
- renames terminal tool calls (`run_terminal_command` — name verified in
  the cursor-agent bundle — plus `terminal` defensively) to `Bash{command}`
  and file-writing tools (`edit_file`/`write_file`) to `Edit{file_path}`;
  every other tool name passes through natively;
- passes the terminal `result` event through with its
  `subtype`/`is_error`/`result` payload intact, so execution errors reach
  the consumer instead of a masked success;
- skips `system`, `user` (tool results), and partial-message events
  (`--stream-partial-output` is deliberately not used — the consumer
  ignores `content_block_delta`, and complete assistant messages are
  sufficient).

The wrapper also carries a review-mode adapter, mirroring
`codex-as-claude.sh` and `qwen-as-claude.sh`: when the prompt contains
the `<<<RALPHEX:REVIEW_DONE>>>` sentinel, an adapter preamble is
prepended that maps ralphex "Task tool" review instructions onto
cursor-agent tooling — launch every requested review agent in parallel in
one turn when agent/subagent tooling is available, otherwise run the
requested reviews yourself per agent scope, wait for all of them before
collecting findings, and keep the `<<<RALPHEX:...>>>` signals unchanged.

A fallback `result` event is emitted only when cursor-agent ends without
its own terminal event (startup or connection failure, crash), as an
`error_during_execution` result plus an assistant text line; when
cursor-agent's own result was already forwarded, the fallback is
suppressed to avoid a duplicate result event.

Like the qwen wrapper, the cursor wrapper is **env-based, not
credential-file-based** — there is no host credential file to bind-mount.
Both variables are forwarded into the container through the normal env
layering (`home.env` → project `pipeline.env` /
`build.task_executor.env` → CLI `-e` / `extra_env`), with the same formula
documented under the Home configuration section of `docs/configuration/index.md`.

### Format-converter wrapper over the qwen CLI — `qwen-as-claude.sh`

`qwen-as-claude.sh` is a format-converter delegate over the `qwen` CLI (the `@qwen-code/qwen-code` npm package shipped in the goga image). The prompt is read only from stdin and `qwen` runs as `qwen --yolo --output-format stream-json`, so every tool call auto-approves (otherwise the stage hangs on an interactive approval prompt that no one is there to answer in pipeline mode). The wrapper streams qwen's JSONL stdout line by line through a `jq` translator, so events reach the consumer as they occur — not aggregated after the run. The agent loop — tool use, multi-turn, file writes — runs inside `qwen`, exactly as it runs inside the `claude` binary for `claude-as-claude.sh`.

The wrapper does no HTTP itself. `qwen` owns the OpenAI Chat Completions transport, which means one wrapper serves Qwen Cloud, DeepSeek, OpenRouter, OpenAI direct, and local vLLM/ollama:

| Variable          | Required | Default                     | Purpose                                                                                                                                  |
|-------------------|----------|-----------------------------|------------------------------------------------------------------------------------------------------------------------------------------|
| `OPENAI_MODEL`    | yes      | —                           | Passed to `qwen --model`. No default — server choice would be unpredictable.                                                            |
| `OPENAI_BASE_URL` | no       | qwen-code default           | Passed to `qwen --openai-base-url` only when set.                                                                                        |
| `OPENAI_API_KEY`  | no       | *(unset)*                   | Passed to `qwen --openai-api-key` only when set — covers local no-auth servers (vLLM/ollama).                                           |

The translation is light because qwen already emits Anthropic-compatible stream-json events; the `jq` filter only:

- forwards main-agent `assistant` events (`parent_tool_use_id != null` subagent messages are filtered out — only the main agent stream is shown);
- passes `text` blocks through unchanged;
- converts `thinking` blocks into narrative `text` blocks (empty thinking is dropped);
- renames shell tool calls (`run_shell_command` in qwen-code ≤ 0.21.x, `shell` in newer releases) to `Bash{command}` and file-writing tools (`edit`/`write`/`write_file` across releases) to `Edit{file_path}`; every other tool name passes through natively;
- passes the terminal `result` event through with its `subtype`/`is_error`/`result` payload intact, so `error_max_turns` and `error_during_execution` reach the consumer instead of a masked success;
- skips `system`, `user` (tool results), and partial-message events (`--include-partial-messages` is deliberately not used — the consumer ignores `content_block_delta`, and complete assistant messages are sufficient).

The wrapper also carries a review-mode adapter, mirroring `codex-as-claude.sh`: when the prompt contains the `<<<RALPHEX:REVIEW_DONE>>>` sentinel, an adapter preamble is prepended that maps ralphex "Task tool" review instructions onto qwen's built-in subagents — launch every requested review agent in parallel in one turn via the `agent` tool, use `list_agents`/`send_message` to check and continue, wait for all of them before collecting findings, and keep the `<<<RALPHEX:...>>>` signals unchanged. Unlike codex, no CLI feature flag is toggled — qwen subagents are built-in.

A fallback `result` event is emitted only when qwen ends without its own terminal event (startup or connection failure, crash), as an `error_during_execution` result plus an assistant text line; when qwen's own result was already forwarded, the fallback is suppressed to avoid a duplicate result event.

Because its native output is already Claude-shaped stream-json, `qwen-as-claude.sh` is the lightest format-converter variant — conversion reduces to tool-name remapping, thinking exposure, and subagent filtering. Use it as the reference shape when designing a wrapper around any future agent CLI with Claude-compatible native output.

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
