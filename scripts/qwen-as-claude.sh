#!/usr/bin/env bash
# qwen-as-claude.sh — invocation-shape wrapper around the `qwen` CLI.
#
# Delegates the agent loop (tool use, multi-turn, file writes) to qwen-code
# exactly the way claude-as-claude.sh delegates to the claude binary. The
# wrapper only:
#   1. forwards the prompt from stdin to `qwen`
#   2. captures qwen's final aggregated answer
#   3. emits the two-line stream-json that afm's executor parses
#
# Output contract: ralphex's executor parseStreamEvent parses ONLY the
# {type:"assistant", message:{...}} envelope and the terminal {type:"result"}
# event. Intermediate content_block_* stream events are ignored, so the wrapper
# emits ONE assistant envelope with the aggregated text + ONE result event.
# (Mirror of afm/scripts/openai-as-claude.sh and scripts/cursor-as-claude.sh.)
#
# Environment variables (forwarded to qwen — qwen-code also reads OPENAI_*
# natively, the explicit flags are for explicitness):
#   OPENAI_API_KEY   — Authorization: Bearer <key>. Optional for no-auth servers (vLLM/ollama).
#   OPENAI_BASE_URL  — base URL of any OpenAI-compatible endpoint (default: qwen-code's own).
#   OPENAI_MODEL     — qwen --model value. REQUIRED.

set -euo pipefail

command -v qwen >/dev/null 2>&1 || { echo "error: qwen CLI is required but not found" >&2; exit 1; }
command -v jq   >/dev/null 2>&1 || { echo "error: jq is required but not found" >&2; exit 1; }

# Drop claude CLI flags goga/ralphex pass through (--model, --effort, etc.).
while [[ $# -gt 0 ]]; do
    shift
done

# Prompt is read only from stdin (same contract as claude with a piped prompt).
if [[ -t 0 ]]; then
    echo "error: no prompt on stdin (qwen-as-claude requires prompt via stdin pipe)" >&2
    exit 1
fi
prompt=$(cat)
if [[ -z "$prompt" ]]; then
    echo "error: empty prompt" >&2
    exit 1
fi

if [[ -z "${OPENAI_MODEL:-}" ]]; then
    echo "error: OPENAI_MODEL is required" >&2
    exit 1
fi

# --yolo = auto-approve every tool call. Without it, qwen blocks on interactive
# approval prompts and the pipeline stage hangs until afm's executor timeout.
# --output-format text = aggregated final answer on stdout (we re-envelope it).
qwen_args=(--yolo --output-format text --model "$OPENAI_MODEL")

# Optional OpenAI endpoint overrides — only pass when set, so the qwen binary's
# own defaults apply cleanly when neither is configured.
if [[ -n "${OPENAI_BASE_URL:-}" ]]; then
    qwen_args+=(--openai-base-url "$OPENAI_BASE_URL")
fi
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
    qwen_args+=(--openai-api-key "$OPENAI_API_KEY")
fi

# Capture qwen's final aggregated answer. Pipe prompt in via stdin (qwen's
# canonical input path). 2>/dev/null suppresses qwen's connection-error noise;
# the wrapper still surfaces failure via the assistant text below.
set +e
text=$(printf '%s' "$prompt" | qwen "${qwen_args[@]}" 2>/dev/null)
qwen_rc=$?
set -e

if [[ "$qwen_rc" -ne 0 ]]; then
    text="qwen request failed (qwen exit ${qwen_rc})"
fi
text="${text:-}"

# Emit exactly the two lines afm's executor parses (mirror of
# afm/scripts/openai-as-claude.sh:74-77).
jq -nc --arg t "$text" \
    '{type:"assistant", message:{content:[{type:"text", text:$t}]}}'

echo '{"type":"result","subtype":"success"}'
