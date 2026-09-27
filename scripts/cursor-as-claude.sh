#!/usr/bin/env bash
# cursor-as-claude.sh — wraps the cursor-agent CLI to produce Claude-compatible
# stream-json output.
#
# cursor-agent runs with -p --output-format stream-json and its JSONL events
# are streamed line by line through a jq translator, so events reach the
# executor as they occur (not aggregated after the run). The agent loop
# itself — tool use, multi-turn, file writes — runs inside cursor-agent,
# exactly as it runs inside the claude binary for claude.
#
# output contract: the executor parseStreamEvent parses ONLY the
# {type:"assistant", message:{...}} envelope and the terminal {type:"result"}
# event. Intermediate content_block_* stream events are ignored, so
# --stream-partial-output is NOT used — complete assistant messages are
# sufficient and cheaper.
#
# environment variables:
#   CURSOR_API_KEY   — Authorization: Bearer <key>. REQUIRED. cursor-agent
#                      reads it from the environment (no --api-key flag
#                      exists), so the wrapper never passes it on the argv.
#   CURSOR_MODEL     — `cursor-agent --model` value. Optional. When unset or
#                      "auto" the flag is omitted and cursor-agent picks its
#                      default model.

set -euo pipefail

command -v cursor-agent >/dev/null 2>&1 || { echo "error: cursor-agent CLI is required but not found" >&2; exit 1; }
command -v jq           >/dev/null 2>&1 || { echo "error: jq is required but not found" >&2; exit 1; }

# Drop claude CLI flags the executor passes through (--model, --effort, etc.).
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

is_review_prompt=0
if [[ "$prompt" == *"<<<RALPHEX:REVIEW_DONE>>>"* ]]; then
    is_review_prompt=1
fi

if [[ "$is_review_prompt" == "1" ]]; then
    adapter_text=$'Ralphex review adapter for Cursor:\n- Interpret review "Task tool" instructions with cursor-agent tooling: launch every requested review agent in parallel in one turn using your available agent/subagent tools.\n- If parallel agent tooling is unavailable, run the requested reviews yourself, one per agent scope, before collecting findings.\n- Wait until every review has returned results before collecting findings and applying fixes.\n- Keep original review workflow and all <<<RALPHEX:...>>> signals unchanged.'
    prompt="$adapter_text"$'\n\n'"$prompt"
fi

# -p / --print       = non-interactive headless mode.
# --yolo             = auto-approve every tool call. Without it, cursor-agent
#                      blocks on interactive approval and the pipeline stage
#                      hangs until afm's executor timeout.
# --output-format stream-json = JSONL events on stdout, translated below.
cursor_args=(-p --yolo --output-format stream-json)

# Optional model override — only pass when set and not "auto", otherwise
# cursor-agent's own default applies.
if [[ -n "${CURSOR_MODEL:-}" && "${CURSOR_MODEL}" != "auto" ]]; then
    cursor_args+=(--model "$CURSOR_MODEL")
fi

# run cursor-agent with stream-json output and translate events to claude
# stream-json format as they arrive. cursor-agent already follows the Claude
# stream-json event convention, so the translation is light:
#   assistant:
#     content text     -> passthrough                 -> narrative in the feed
#     content thinking -> text block                  -> cursor "thoughts" made visible
#     content tool_use run_terminal_command|terminal
#                       -> tool_use Bash{command}     -> action line
#     content tool_use edit_file|write_file|edit|write
#                       -> tool_use Edit{file_path}   -> file edit
#     content tool_use <other> -> passthrough under its native name
#   result -> passthrough unchanged (subtype/is_error/result preserved for
#     the executor)
#   system, user (tool results), stream_event, control_* -> skipped
#
# cursor-agent does NOT read the prompt from stdin — it is forwarded as a
# positional argument after `--`, which marks end-of-options and protects
# prompts that start with `-` from being misparsed as flags.
saw_result=0
while IFS= read -r line; do
    [[ -n "$line" ]] || continue
    out=$(printf '%s' "$line" | jq -c '
        def asst($blocks): {type: "assistant", message: {content: $blocks}};

        def map_block:
            select(type == "object")
            | if .type == "text" then
                .
            elif .type == "thinking" then
                (.thinking // "") as $t
                | select($t | length > 0)
                | {type: "text", text: ($t + "\n")}
            elif .type == "tool_use" then
                # shell tools: "run_terminal_command" (name verified in the
                # cursor-agent bundle); "terminal" kept for defensive coverage.
                if .name == "terminal" or .name == "run_terminal_command" then
                    {type: "tool_use", id: .id, name: "Bash",
                     input: {command: (.input.command // "")}}
                # file-writing tools: "edit_file"/"write_file" (cursor agent
                # convention) plus "edit"/"write" for defensive coverage.
                elif .name == "edit_file" or .name == "write_file" or .name == "edit" or .name == "write" then
                    {type: "tool_use", id: .id, name: "Edit",
                     input: {file_path: (.input.file_path // .input.path // "")}}
                else .
                end
            else .
            end;

        if .type == "assistant" then
            (.message.content // [])
            | if type == "array" then . else [] end
            | map(map_block)
            | select(length > 0)
            | asst(.)
        elif .type == "result" then
            ({type: "result"} + .)
        else empty
        end
    ' 2>/dev/null) || out=""
    [[ -n "$out" ]] || continue
    printf '%s\n' "$out"
    # track the terminal event so the fallback below is not double-emitted
    case "$out" in
        '{"type":"result"'*) saw_result=1 ;;
    esac
done < <(cursor-agent "${cursor_args[@]}" -- "$prompt" 2>/dev/null)

# emit a fallback result event only if cursor-agent exited without its
# terminal result event (startup or connection failure, crash). the codex
# adapter always emits its fallback and the executor tolerates the duplicate;
# here it is suppressed when cursor-agent's own (richer) result was already
# forwarded.
if [[ "$saw_result" -eq 0 ]]; then
    jq -nc '{type:"assistant",message:{content:[{type:"text",text:"cursor-agent produced no output and emitted no result event (likely a startup or connection failure)"}]}}'
    echo '{"type":"result","subtype":"error_during_execution","is_error":true,"result":"cursor-agent exited without a result event"}'
fi
