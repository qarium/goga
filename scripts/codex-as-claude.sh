#!/usr/bin/env bash
# codex-as-claude.sh - wraps codex CLI to produce Claude-compatible stream-json output.
#
# this script translates codex JSONL events into the Claude stream-json format
# that the executor can parse, allowing codex to be used as a drop-in
# replacement for claude in task and review phases.
#
# config example (executor config file):
#   claude_command = /path/to/codex-as-claude.sh
#   claude_args =
#
# environment variables:
#   CODEX_MODEL          - codex model to use (default: codex default)
#   CODEX_SANDBOX        - sandbox mode (default: danger-full-access)
#   CODEX_VERBOSE        - set to 1 to include command execution output (default: 0)

set -euo pipefail

# verify jq is available (required for JSON translation)
command -v jq >/dev/null 2>&1 || { echo "error: jq is required but not found" >&2; exit 1; }

# the executor passes prompt via stdin (primary path, avoids Windows 8191-char cmd limit).
# also accept -p flag for backward compatibility with direct invocations.
# all other flags are ignored gracefully (--dangerously-skip-permissions, etc.)
prompt=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -p) prompt="${2:-}"; shift; shift 2>/dev/null || true ;;
        *)  shift ;; # ignore unknown flags
    esac
done

if [[ -z "$prompt" ]]; then
    # fall back to stdin: the executor passes prompt via pipe to avoid Windows 8191-char cmd limit.
    # only read when stdin is not a terminal to avoid blocking interactive invocations.
    if [[ ! -t 0 ]]; then
        prompt=$(cat)
    fi
fi

if [[ -z "$prompt" ]]; then
    echo "error: no prompt provided (expected -p flag or stdin)" >&2
    exit 1
fi

# configurable via environment
CODEX_MODEL="${CODEX_MODEL:-}"
CODEX_SANDBOX="${CODEX_SANDBOX:-danger-full-access}"

is_review_prompt=0
if [[ "$prompt" == *"<<<RALPHEX:REVIEW_DONE>>>"* ]]; then
    is_review_prompt=1
fi

if [[ "$is_review_prompt" == "1" ]]; then
    adapter_text=$'Ralphex review adapter for Codex:\n- Interpret review "Task tool" instructions using codex collaboration tools: spawn_agent, send_input, wait, close_agent.\n- Launch all requested review agents in parallel in one turn.\n- Wait for all spawned review agents before collecting findings and applying fixes.\n- Keep original review workflow and all <<<RALPHEX:...>>> signals unchanged.'
    prompt="$adapter_text"$'\n\n'"$prompt"
fi

# build codex arguments
codex_args=(exec --json --dangerously-bypass-approvals-and-sandbox -s "$CODEX_SANDBOX")
[[ -n "$CODEX_MODEL" ]] && codex_args+=(-m "$CODEX_MODEL")
if [[ "$is_review_prompt" == "1" ]]; then
    codex_args+=(-c "features.multi_agent=true")
fi
# prompt is passed via stdin to codex (not as CLI arg) to avoid command-line length limits.
# codex reads from stdin when no positional prompt argument is given.

# run codex with JSON output, translate events to claude stream-json format.
# only agent messages are emitted — command executions and file reads produce
# excessive noise (skill files, config reads, etc.) and are skipped.
# set CODEX_VERBOSE=1 to include command execution output.
#
# event mapping:
#   item.completed + agent_message     -> assistant (text)       -> narrative in the feed
#   item.completed + reasoning         -> assistant (text)        -> codex "thoughts"
#   item.completed + command_execution -> assistant (tool_use Bash) -> action line
#   item.completed + file_change/patch -> assistant (tool_use Edit) -> file edit
#   (CODEX_VERBOSE=1 additionally sends command output as a separate text block)
#   item.started                       -> skipped (otherwise duplicate command: in_progress)
#   turn.completed                     -> result (end of execution)
#   thread.started, turn.started       -> skipped
#
# IMPORTANT: the executor recognizes ONLY events with type=="assistant";
# content_block_delta is silently ignored.
# Previously this adapter sent content_block_delta, so codex "thoughts"
# never reached the dashboard feed — only the question dialog was visible.
# Now every agent_message AND reasoning is wrapped in an assistant envelope,
# which is parsed into agent_action(text) and shown as agent reasoning.
CODEX_VERBOSE="${CODEX_VERBOSE:-0}"
if [[ "$CODEX_VERBOSE" != "0" && "$CODEX_VERBOSE" != "1" ]]; then
    echo "warning: CODEX_VERBOSE must be 0 or 1, got '$CODEX_VERBOSE', defaulting to 0" >&2
    CODEX_VERBOSE=0
fi

printf '%s' "$prompt" | codex "${codex_args[@]}" 2>/dev/null | while IFS= read -r line; do
    echo "$line" | jq -c --argjson verbose "$CODEX_VERBOSE" '
        # the executor recognizes only assistant events: text is shown as a
        # narrative, tool_use — as a compact action line (Bash/Edit/...). Everything
        # is wrapped in {type:"assistant",message:{content:[...]}}.
        def asst($t): {type: "assistant", message: {content: [{type: "text", text: $t}]}};
        def tool($n; $inp): {type: "assistant", message: {content: [{type: "tool_use", name: $n, input: $inp}]}};
        if .type == "item.completed" then
            (.item.type) as $it
            | if $it == "agent_message" then
                asst((.item.text // "") + "\n")
            elif $it == "reasoning" then
                # reasoning item text lives in .text or .summary depending on the
                # codex CLI version; empty text is dropped (the executor ignores empty text).
                ((.item.text // .item.summary // "")) as $r
                | if ($r | length) > 0 then asst($r + "\n") else empty end
            elif $it == "command_execution" then
                # every codex command is shown as a Bash action (same as claude);
                # with CODEX_VERBOSE=1 its output is additionally sent as a text block.
                tool("Bash"; {command: (.item.command // "")}),
                (if $verbose == 1 and ((.item.aggregated_output // "") | length) > 0
                 then asst((.item.aggregated_output) + "\n") else empty end)
            elif ($it == "file_change" or $it == "patch_apply" or $it == "file_update")
                 and (.item.path != null) then
                tool("Edit"; {file_path: (.item.path)})
            else empty
            end
        elif .type == "turn.completed" then
            {type: "result", result: ""}
        else empty
        end
    ' 2>/dev/null || true
done || true

# emit fallback result event if codex exited without turn.completed
echo '{"type":"result","result":""}'
