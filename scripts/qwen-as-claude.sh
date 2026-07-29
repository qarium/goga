#!/usr/bin/env bash
# qwen-as-claude.sh — adapter from any OpenAI Chat Completions-compatible HTTP
# endpoint to the claude stream-json format.
#
# Unlike codex/opencode (which translate a CLI's JSONL output), this wrapper
# speaks HTTP directly: a single streaming POST to
# ${OPENAI_BASE_URL}/chat/completions, with each SSE delta.content chunk
# re-emitted as a content_block_delta event.
#
# Environment variables (OPENAI_*, not QWEN_* — the name is just a goga label,
# the protocol is OpenAI):
#   OPENAI_API_KEY   — Authorization: Bearer <key>. Omitted when empty (vLLM/ollama).
#   OPENAI_BASE_URL  — base URL of any OpenAI-compatible endpoint (default: https://api.openai.com/v1).
#   OPENAI_MODEL     — model name sent in the request body. REQUIRED (no default — server choice would be unpredictable).

set -euo pipefail

command -v curl >/dev/null 2>&1 || { echo "error: curl is required but not found" >&2; exit 1; }
command -v jq   >/dev/null 2>&1 || { echo "error: jq is required but not found" >&2; exit 1; }

# Ignore all claude CLI flags (--model, --effort, --dangerously-skip-permissions, --output-format, --verbose).
while [[ $# -gt 0 ]]; do
    shift
done

# Prompt is read only from stdin (same as claude with a piped prompt).
if [[ -t 0 ]]; then
    echo "error: no prompt on stdin (qwen-as-claude requires prompt via stdin pipe)" >&2
    exit 1
fi
prompt=$(cat)
if [[ -z "$prompt" ]]; then
    echo "error: empty prompt" >&2
    exit 1
fi

OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://api.openai.com/v1}"
if [[ -z "${OPENAI_MODEL:-}" ]]; then
    echo "error: OPENAI_MODEL is required" >&2
    exit 1
fi

CT="Content-Type: application/json"
body=$(jq -nc --arg model "$OPENAI_MODEL" --arg text "$prompt" \
    '{model:$model, messages:[{role:"user", content:$text}], stream:true}')

# Authorization header only when the key is non-empty (vLLM/ollama serve without auth).
auth_args=()
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
    auth_args=(-H "Authorization: Bearer ${OPENAI_API_KEY}")
fi

# Single streaming request. -N disables curl output buffering so SSE chunks flush immediately.
# -m 1500 = 25 min, below the 30-min ralphex executor idle timeout (matches cursor-as-claude.sh).
# ${auth_args[@]+"${auth_args[@]}"} is the Bash 3.2-safe expansion of an empty array — it
# expands to nothing when auth_args is unset/empty, avoiding set -u's "unbound variable" trap.
#
# set +e around the pipeline is critical for two reasons:
#   1. pipefail would propagate curl's non-zero exit and trip set -e before we can capture it.
#   2. On Bash 3.2 (macOS), `cmd || true` overwrites PIPESTATUS to (0) — so the `|| true`
#      workaround the cursor wrapper uses is unsafe here. Toggling set -e preserves PIPESTATUS.
set +e
curl -sS -N -m 1500 -X POST "${OPENAI_BASE_URL}/chat/completions" \
     -H "$CT" ${auth_args[@]+"${auth_args[@]}"} -d "$body" \
| while IFS= read -r line; do
    # Trim leading/trailing whitespace so we tolerate "data:[DONE]" (no space) and
    # trailing CRs from non-conforming servers.
    case "$line" in
        'data: [DONE]'|'data:[DONE]') break ;;
        'data: '*|'data:'*)
            payload="${line#data:}"
            payload="${payload# }"            # strip one leading space if present
            # Extract delta.content; skip role-only, reasoning, finish_reason, usage chunks.
            chunk=$(printf '%s' "$payload" | jq -r '.choices[0].delta.content // empty' 2>/dev/null || true)
            if [[ -n "$chunk" ]]; then
                jq -cn --arg t "$chunk" \
                    '{type:"content_block_delta", delta:{type:"text_delta", text:$t}}'
            fi
            ;;
    esac
done
# PIPESTATUS[0] is curl's exit status. Must be read immediately after the pipeline —
# the next command would overwrite PIPESTATUS.
curl_rc=${PIPESTATUS[0]}
set -e

if [[ "$curl_rc" -ne 0 ]]; then
    # Emit one assistant envelope carrying the error text + result: success,
    # so the ralphex executor finishes cleanly and the failure reason is visible.
    jq -nc --arg t "qwen request failed (curl exit ${curl_rc})" \
        '{type:"assistant", message:{content:[{type:"text", text:$t}]}}'
fi

# Terminal event — always emitted so the ralphex executor finishes cleanly.
echo '{"type":"result","subtype":"success"}'
