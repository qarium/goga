#!/usr/bin/env bash
# cursor-as-claude.sh — invocation-shape wrapper around the `cursor-agent` CLI.
#
# Delegates the agent loop (tool use, multi-turn, file writes) to cursor-agent
# exactly the way qwen-as-claude.sh delegates to the qwen binary. The wrapper
# only:
#   1. forwards the prompt from stdin to `cursor-agent`
#   2. captures cursor-agent's final aggregated answer
#   3. emits the two-line stream-json that afm's executor parses
#
# Output contract: ralphex's executor parseStreamEvent parses ONLY the
# {type:"assistant", message:{...}} envelope and the terminal {type:"result"}
# event. Intermediate content_block_* stream events are ignored, so the wrapper
# emits ONE assistant envelope with the aggregated text + ONE result event.
# (Mirror of afm/scripts/openai-as-claude.sh and scripts/qwen-as-claude.sh.)
#
# Environment variables:
#   CURSOR_API_KEY   — Authorization: Bearer <key>. REQUIRED. Forwarded to
#                      cursor-agent natively (cursor-agent reads CURSOR_API_KEY
#                      from the environment; no --api-key flag exists).
#   CURSOR_MODEL     — `cursor-agent --model` value. Optional. When unset or
#                      "auto" the flag is omitted and cursor-agent picks its
#                      default model.

set -euo pipefail

command -v cursor-agent >/dev/null 2>&1 || { echo "error: cursor-agent CLI is required but not found" >&2; exit 1; }
command -v jq           >/dev/null 2>&1 || { echo "error: jq is required but not found" >&2; exit 1; }

# Drop claude CLI flags goga/ralphex pass through (--model, --effort, etc.).
while [[ $# -gt 0 ]]; do
    shift
done

# Prompt is read only from stdin (same contract as claude with a piped prompt).
if [[ -t 0 ]]; then
    echo "error: no prompt on stdin (cursor-as-claude requires prompt via stdin pipe)" >&2
    exit 1
fi
prompt=$(cat)
if [[ -z "$prompt" ]]; then
    echo "error: empty prompt" >&2
    exit 1
fi

if [[ -z "${CURSOR_API_KEY:-}" ]]; then
    echo "error: CURSOR_API_KEY is required" >&2
    exit 1
fi

# cursor-agent does NOT read the prompt from stdin — it takes the prompt as a
# positional argument. So we forward the captured stdin prompt after `--`, which
# marks end-of-options and protects prompts that start with `-` (a diff line,
# an option-looking example, a lone stdin marker) from being misparsed as flags.
#
# -p / --print      = non-interactive headless mode.
# --yolo            = auto-approve every tool call. Without it, cursor-agent
#                     blocks on interactive approval and the pipeline stage
#                     hangs until afm's executor timeout.
# --output-format text = aggregated final answer on stdout (we re-envelope it).
cursor_args=(-p --yolo --output-format text)

# Optional model override — only pass when set and not "auto", otherwise
# cursor-agent's own default applies.
if [[ -n "${CURSOR_MODEL:-}" && "${CURSOR_MODEL}" != "auto" ]]; then
    cursor_args+=(--model "$CURSOR_MODEL")
fi

# Capture cursor-agent's final aggregated answer. cursor-agent reads
# CURSOR_API_KEY directly from the environment (no --api-key flag exists),
# so the wrapper does not pass it on the argv. 2>/dev/null suppresses
# cursor-agent's stderr noise (auth diagnostics, progress chatter); the
# wrapper still surfaces failure via the assistant text below.
set +e
text=$(cursor-agent "${cursor_args[@]}" -- "$prompt" 2>/dev/null)
cursor_rc=$?
set -e

if [[ "$cursor_rc" -ne 0 ]]; then
    text="cursor-agent request failed (cursor-agent exit ${cursor_rc})"
fi
text="${text:-}"

# Emit exactly the two lines afm's executor parses.
jq -nc --arg t "$text" \
    '{type:"assistant", message:{content:[{type:"text", text:$t}]}}'

echo '{"type":"result","subtype":"success"}'
