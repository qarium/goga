#!/usr/bin/env bash
# cursor-as-claude.sh — adapter from the Cursor Cloud Agents API to the claude stream-json format.
#
# The Cursor Cloud API (api.cursor.com) does NOT expose a synchronous /chat/completions — it is
# an asynchronous run-based Cloud Agents API. Instead of a single "prompt → answer" request, the
# adapter launches a Cloud Agent and waits for its result:
#
#   1. creates a no-repo Cloud Agent (POST /v1/agents) with the prompt taken from stdin;
#   2. polls the run until it reaches a terminal status (FINISHED/ERROR/CANCELLED/EXPIRED);
#   3. emits claude stream-json: an assistant envelope with the final text + a result event;
#   4. archives the agent (best-effort) so it does not clutter the account.
#
# Environment variables:
#   CURSOR_API_KEY   — authorization token (required)
#   CURSOR_BASE_URL  — base URL of the API (default: https://api.cursor.com/v1)
#   CURSOR_MODEL     — model.id (empty / "auto" → the model field is omitted → Cursor default)
#
# Notes:
#   - Creating an agent involves starting a cloud VM (enqueuing) and may take a minute
#     or more — hence the long timeout on create (300s).

set -euo pipefail

command -v curl >/dev/null 2>&1 || { echo "error: curl is required but not found" >&2; exit 1; }
command -v jq   >/dev/null 2>&1 || { echo "error: jq is required but not found" >&2; exit 1; }

# Ignore all claude CLI flags (--model, --effort, --dangerously-skip-permissions, etc.).
while [[ $# -gt 0 ]]; do
    shift
done

# Prompt is read only from stdin (just like claude does when the prompt is piped in).
if [[ -t 0 ]]; then
    echo "error: no prompt on stdin (cursor-as-claude requires prompt via stdin pipe)" >&2
    exit 1
fi
prompt=$(cat)
if [[ -z "$prompt" ]]; then
    echo "error: empty prompt" >&2
    exit 1
fi

CURSOR_BASE_URL="${CURSOR_BASE_URL:-https://api.cursor.com/v1}"
CURSOR_MODEL="${CURSOR_MODEL:-}"

if [[ -z "${CURSOR_API_KEY:-}" ]]; then
    echo "error: CURSOR_API_KEY is not set" >&2
    exit 1
fi

AUTH="Authorization: Bearer $CURSOR_API_KEY"
CT="Content-Type: application/json"

# Create body: prompt + mode "agent". no-repo (no repos/env) → a Cloud Agent without a repository.
body=$(jq -nc --arg text "$prompt" '{prompt:{text:$text}, mode:"agent"}')
# Add the model only if it is set and not "auto" — otherwise Cursor falls back to its default.
if [[ -n "$CURSOR_MODEL" && "$CURSOR_MODEL" != "auto" ]]; then
    body=$(printf '%s' "$body" | jq -c --arg m "$CURSOR_MODEL" '.model={id:$m}')
fi

# 1. Create the no-repo Cloud Agent. VM startup may take minutes — timeout 300s.
create_resp=$(curl -sS -m 300 -X POST "${CURSOR_BASE_URL}/agents" -H "$CT" -H "$AUTH" -d "$body") || {
    echo "error: cursor create agent failed (curl exit $?)" >&2
    exit 1
}
agent_id=$(printf '%s' "$create_resp" | jq -r '.agent.id // empty')
run_id=$(printf '%s' "$create_resp" | jq -r '.run.id // empty')
if [[ -z "$agent_id" || -z "$run_id" ]]; then
    echo "error: cursor create returned no agent/run id: $create_resp" >&2
    exit 1
fi

# 2. Poll the run until it reaches a terminal status. Cap ~25 min (< executor idle 30 min).
status=""
result_text=""
deadline=$(( SECONDS + 1500 ))   # 25 minutes — backstop for hung runs
while (( SECONDS < deadline )); do
    # The run may have already finished at create time — hence the immediate poll.
    if ! run_resp=$(curl -sS -m 60 "${CURSOR_BASE_URL}/agents/${agent_id}/runs/${run_id}" -H "$AUTH" 2>/dev/null); then
        sleep 3
        continue
    fi
    status=$(printf '%s' "$run_resp" | jq -r '.status // empty')
    case "$status" in
        FINISHED|ERROR|CANCELLED|EXPIRED)
            result_text=$(printf '%s' "$run_resp" | jq -r '.result // empty')
            break
            ;;
    esac
    sleep 3
done

# 3. Emit claude stream-json. assistant envelope: aggregated text of the entire response.
#    jq -nc --arg JSON-escapes the text correctly (quotes / newlines).
if [[ "$status" == "FINISHED" ]]; then
    text="${result_text:-}"
    jq -nc --arg t "$text" '{type:"assistant",message:{content:[{type:"text",text:$t}]}}'
    echo '{"type":"result","subtype":"success"}'
else
    # Not FINISHED (ERROR/CANCELLED/EXPIRED/timeout) — return as assistant text + success,
    # so the executor finishes cleanly and the problem description is visible to the user.
    msg="Cursor run ${status:-TIMEOUT}: ${result_text:-(no result)}"
    jq -nc --arg t "$msg" '{type:"assistant",message:{content:[{type:"text",text:$t}]}}'
    echo '{"type":"result","subtype":"success"}'
fi

# 4. Archive the agent (best-effort). A no-repo agent is single-use — do not clutter the account.
curl -sS -m 20 -o /dev/null -X POST "${CURSOR_BASE_URL}/agents/${agent_id}/archive" -H "$AUTH" 2>/dev/null || true
