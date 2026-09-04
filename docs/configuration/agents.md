# Agents

Wherever you set `agent: <name>` — in `.goga/config.yml` (`build.task_executor.agent`, `build.review_executor.agent`, `pipeline.agent`) or in a workflow-file (`workflow.stages.<name>.agent`, `workflow.extend.<name>.agent`) — goga resolves that name into a wrapper script **inside the Docker container**. The wrapper is what actually runs the AI agent during `goga build` and `goga pipeline`; it presents the agent's CLI in a uniform shape so goga does not care which concrete agent is underneath.

Resolution is pure string concatenation — there is no whitelist and no validation. A missing wrapper surfaces as a runtime error when the container tries to invoke it, not from goga itself. The full mechanic, baseline wrappers, per-agent env variables, and the custom-agent path are covered below.

## How `agent` resolves to a wrapper

Resolution invariant:

```
<agent>  →  /home/goga/bin/<agent>-as-claude.sh
```

The `agent` field is **optional** in `build.task_executor`, `build.review_executor`, and `pipeline`: at config load, an absent / YAML-null / empty / whitespace-only value resolves to `None` (it is not an error). `resolve_wrapper_path` is invoked only for a non-`None` value — it strips surrounding whitespace and forwards the result verbatim (no case-folding or other normalization), so an empty value never reaches resolution. What `None` means differs by consumer: `goga build` raises a `ClickException` (the build needs an agent), whereas `goga pipeline` carries `None` through and lets a per-stage workflow agent or afm's own default cover the absent global agent. A `None` (or same-as-task) `build.review_executor.agent` means the review phase runs on the task executor's wrapper in the same pass — unless `build.review_executor.env` is non-empty, which also induces a second, review-only pass (on the task executor's wrapper, with the review env layered over the container environment); a differing agent runs a second, review-only pass on that agent's wrapper (its existence is validated in-container before the pass).

Edge cases:

| Edge case                                                                          | What happens                                                                                                                            | Where it surfaces                                                                                                                 |
|------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------|
| `agent: ""` / whitespace-only                                                      | Resolves to `None` at config load (the field is optional — absent/empty/whitespace all collapse to `None`). `goga build` then raises a `ClickException` when it needs an agent; `goga pipeline` does not require it (a per-stage workflow agent or afm's default covers the absent global agent). | `goga config` prints `null`; `goga build` exits non-zero before any container starts; `goga pipeline` proceeds. |
| `agent: "CodEx"` (case mismatch)                                                   | Resolves to `/home/goga/bin/CodEx-as-claude.sh`. Case-sensitive filesystem → file not found.                                            | Runtime error inside the container. goga does no case folding.                                                                   |
| Wrapper file missing in image (custom Dockerfile forgot `COPY`)                    | Path resolves but the file is absent.                                                                                                   | Runtime error inside the container. No upfront validation by goga.                                                               |
| Wrapper present but not executable (forgot `chmod +x`)                             | Permission denied.                                                                                                                      | Runtime error inside the container.                                                                                              |
| `cursor` configured without `CURSOR_API_KEY`                                       | The wrapper is env-based, not credential-file-based — there is no credential mount to fall back on.                                     | Wrapper exits with error (`CURSOR_API_KEY is required`). See [cursor](#cursor).                                                    |
| `workflow.stages.<name>.agent: <unknown>`                                          | Wrapper path is composed verbatim; no validation against a known agent set.                                                             | Runtime error inside the container. See [workflows](../pipelines/workflows.md#workflow-agent-choosing-the-cli-agent).                |

## Baseline wrappers

The image ships five baseline wrappers:

| `agent` value | Wrapper file             | Wrapper class                       |
|---------------|--------------------------|-------------------------------------|
| `claude`      | `claude-as-claude.sh`    | Invocation-shape                    |
| `codex`       | `codex-as-claude.sh`     | Format-converter (jq)               |
| `cursor`      | `cursor-as-claude.sh`    | Invocation-shape (cursor-agent CLI) |
| `opencode`    | `opencode-as-claude.sh`  | Format-converter (jq)               |
| `qwen`        | `qwen-as-claude.sh`      | Invocation-shape (qwen CLI)         |

The wrapper class describes how each wrapper produces the Claude Code stream-json output: invocation-shape wrappers forward arguments nearly verbatim to an underlying CLI binary that owns its own agent loop, and format-converter wrappers translate the agent's JSONL into stream-json via `jq`.

## Environment variables per agent

Env variables are forwarded into the container through the standard env layering (`home.env` → project `<scope>.env` → CLI `-e` / `extra_env`) — see [Home configuration](home.md#env-layering).

### claude

| Variable                          | Required | Default        | Purpose                                                                                       |
|-----------------------------------|----------|----------------|-----------------------------------------------------------------------------------------------|
| `ANTHROPIC_API_KEY`               | yes      | —              | API key for the Claude API. Absence surfaces inside the wrapper as an auth error.             |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL`   | no       | Claude default | Override for the Haiku-class model slot. `goga init` suggests this when claude is the agent.  |
| `ANTHROPIC_DEFAULT_SONNET_MODEL`  | no       | Claude default | Override for the Sonnet-class model slot. Suggested by `goga init`.                           |
| `ANTHROPIC_DEFAULT_OPUS_MODEL`    | no       | Claude default | Override for the Opus-class model slot. Suggested by `goga init`.                             |
| `ANTHROPIC_MODEL`                 | no       | Claude default | Override for the main model slot. Suggested by `goga init`.                                   |
| `ANTHROPIC_BASE_URL`              | no       | Claude default | Base URL for an Anthropic-compatible gateway or proxy. Suggested by `goga init`.              |

### codex

| Variable         | Required | Default               | Purpose                                                                                                                              |
|------------------|----------|-----------------------|--------------------------------------------------------------------------------------------------------------------------------------|
| `CODEX_MODEL`    | no       | codex default         | Model selector used by the codex CLI. `goga init` suggests this when codex is the agent.                                            |
| `CODEX_SANDBOX`  | no       | `danger-full-access`  | Sandbox mode. Default disables codex sandboxing so the agent can run builds and modify the workspace without restrictions.           |
| `CODEX_VERBOSE`  | no       | `0`                   | Set to `1` to include command execution output in the codex response — useful for debugging pipeline/build failures.                 |

### cursor

The `cursor` wrapper is a thin invocation-shape delegate over the `cursor-agent` CLI. It is the same shape as `qwen-as-claude.sh`: the wrapper forwards the prompt and env to `cursor-agent`, captures the final aggregated answer, and emits it as one `assistant` envelope + a `result: success` event. The agent loop itself — tool use, multi-turn, file writes — runs inside `cursor-agent`, exactly as it runs inside the `claude` binary for `claude-as-claude.sh`.

| Variable          | Required | Default                    | Purpose                                                                                                                                                   |
|-------------------|----------|----------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------|
| `CURSOR_API_KEY`  | yes      | —                          | Authorization token. `cursor-agent` reads `CURSOR_API_KEY` natively from the environment (no `--api-key` flag exists). The wrapper exits with an error when unset. |
| `CURSOR_MODEL`    | no       | *(unset — Cursor default)* | `cursor-agent --model` selector. Empty value or `"auto"` omits the `--model` flag; any other value is forwarded as `--model`.                              |

The cursor wrapper is **env-based, not credential-file-based** — there is no host credential file to bind-mount. Both variables are forwarded exclusively through the env layering.

The wrapper invokes `cursor-agent -p --yolo` so every tool call auto-approves. Without `--yolo`, the stage hangs on an interactive approval prompt that no one is there to answer. The `--output-format text` flag makes the final aggregated answer land on stdout, where the wrapper re-envelopes it. The prompt is read only from stdin and forwarded to `cursor-agent` as a positional argument after `--`; `cursor-agent` does not read stdin itself, and `--` guards against prompts that start with `-` being misparsed as flags.

### opencode

| Variable            | Required | Default          | Purpose                                                                                                                       |
|---------------------|----------|------------------|-------------------------------------------------------------------------------------------------------------------------------|
| `OPENCODE_MODEL`    | no       | opencode default | Model in `provider/model` format, e.g. `openai/gpt-4o`.                                                                       |
| `OPENCODE_VARIANT`  | no       | opencode default | Model variant / reasoning effort, e.g. `high`, `medium`, `low`.                                                               |
| `OPENCODE_EFFORT`   | no       | —                | Alias for `OPENCODE_VARIANT` when `OPENCODE_VARIANT` is unset.                                                                |
| `OPENCODE_REASONING`| no       | —                | Alias for `OPENCODE_VARIANT` when both `OPENCODE_VARIANT` and `OPENCODE_EFFORT` are unset.                                    |
| `OPENCODE_VERBOSE`  | no       | `0`              | Set to `1` to include tool execution events in output.                                                                        |

Variant precedence: `OPENCODE_VARIANT` > `OPENCODE_EFFORT` > `OPENCODE_REASONING`. The first set value wins; the rest are ignored.

### qwen

The `qwen` wrapper is a thin invocation-shape delegate over the `qwen` CLI (the `@qwen-code/qwen-code` npm package shipped in the goga image). It is the same shape as `claude-as-claude.sh`: the wrapper forwards the prompt and env to `qwen`, captures the final aggregated answer, and emits it as one `assistant` envelope + a `result: success` event. The agent loop itself — tool use, multi-turn, file writes, the `<execute>` protocol the system prompt expects — runs inside `qwen`, exactly as it runs inside the `claude` binary for `claude-as-claude.sh`.

Because `qwen` speaks the OpenAI Chat Completions protocol, one wrapper serves any OpenAI-compatible endpoint: Qwen Cloud, DeepSeek, OpenRouter, OpenAI direct, or a local vLLM/ollama instance. The env vars are named `OPENAI_*`, not `QWEN_*` — the wrapper name is just a goga label; the protocol is OpenAI.

| Variable          | Required | Default                     | Purpose                                                                                                                                                        |
|-------------------|----------|-----------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `OPENAI_MODEL`    | yes      | —                           | Passed to `qwen --model`. No default — a server-side default would be unpredictable. Wrapper exits non-zero when unset.                                        |
| `OPENAI_BASE_URL` | no       | qwen-code default           | Passed to `qwen --openai-base-url` only when set.                                                                                                              |
| `OPENAI_API_KEY`  | no       | *(unset)*                   | Passed to `qwen --openai-api-key` only when set. The wrapper works without it.                                                                                 |

The `qwen` wrapper is **env-based, not credential-file-based** — there is no host credential file to bind-mount. All three variables are forwarded exclusively through the env layering.

The wrapper invokes `qwen --yolo` so every tool call auto-approves (otherwise the stage hangs on an interactive approval prompt that no one is there to answer) and `--output-format text` so the final aggregated answer lands on stdout, where the wrapper re-envelopes it. The prompt is read only from stdin.

## Custom agents

Any name works as `agent: <name>` as long as `/home/goga/bin/<name>-as-claude.sh` exists in the Docker image and is executable. There is no registration step.

Two paths, both through a custom Dockerfile:

**Path A — via the `dockerfile:` field.** When `.goga/config.yml` declares a top-level `dockerfile` (see [Top-level](project.md#top-level) and [Example configuration](project.md#example-configuration)), `goga build --update` / `goga pipeline --update` build the image from that Dockerfile:

```dockerfile
FROM qarium/goga-python-<python-version>:<goga-version>   # or any baseline language image
COPY myname-as-claude.sh /home/goga/bin/myname-as-claude.sh
RUN chmod +x /home/goga/bin/myname-as-claude.sh
```

**Path B — extend a baseline image.** If `dockerfile:` is not yet set, create `.goga/Dockerfile` (via the `goga init` "Custom Dockerfile" step, or manually) with the same `FROM + COPY + chmod` shape, then register its path in the `dockerfile:` field.

**Wrapper contract.** The script must:

1. read the prompt from stdin (the way the `claude` CLI consumes a piped prompt);
2. ignore or carefully parse CLI flags that goga passes through (`--model`, `--effort`, `--dangerously-skip-permissions`, etc.);
3. emit Claude Code stream-json on stdout: an `assistant` envelope followed by a `result` event.

The simplest baseline wrapper (`claude-as-claude.sh`) is a near-no-op that just forwards arguments; the `qwen`/`cursor` wrappers are invocation-shape delegates around an underlying agent CLI that owns its own agent loop; the `codex`/`opencode` wrappers are format-converters that translate JSONL into stream-json via `jq`. Use them as reference shapes when designing your own.

If `agent: myname` is set but the wrapper is not `COPY`'d into the image or is not executable, the container fails at runtime (file not found / permission denied). goga does not validate this up front.

## Relationship to `goga connect`

> **Two different `agent` concepts.** The runtime `agent` (this section) picks which CLI binary runs **inside the goga Docker container** during `goga build` / `goga pipeline`. [`goga connect`](../cli/connect.md) is a separate, host-side mechanism that installs goga skills and commands **into** an AI agent (claude/codex/cursor/opencode/qwen) as a target. They are orthogonal: you can run `goga connect claude codex` to get goga skills inside both of your host-installed CLIs, and still set `build.task_executor.agent: codex` — in that case the codex wrapper runs inside the container, not your host-side CLI.
