#!/usr/bin/env bash
# qwen-as-claude.sh — wraps the qwen CLI to produce Claude-compatible stream-json output.
#
# qwen runs with --output-format stream-json and its JSONL events are streamed
# line by line through a jq translator, so events reach the executor as they
# occur (not aggregated after the run). The agent loop itself — tool use,
# multi-turn, file writes — runs inside qwen, exactly as it runs inside the
# claude binary for claude.
#
# output contract: the executor parseStreamEvent parses ONLY the
# {type:"assistant", message:{...}} envelope and the terminal {type:"result"}
# event. Intermediate content_block_* stream events are ignored, so
# --include-partial-messages is NOT used — complete assistant messages are
# sufficient and cheaper.
#
# environment variables (forwarded to qwen — qwen-code also reads OPENAI_*
# natively, the explicit flags are for explicitness):
#   OPENAI_API_KEY   — Authorization: Bearer <key>. Optional for no-auth servers (vLLM/ollama).
#   OPENAI_BASE_URL  — base URL of any OpenAI-compatible endpoint (default: qwen-code's own).
#   OPENAI_MODEL     — qwen --model value. REQUIRED.

set -euo pipefail

command -v qwen >/dev/null 2>&1 || { echo "error: qwen CLI is required but not found" >&2; exit 1; }
command -v jq   >/dev/null 2>&1 || { echo "error: jq is required but not found" >&2; exit 1; }

# Drop claude CLI flags the executor passes through (--model, --effort, etc.).
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

is_review_prompt=0
if [[ "$prompt" == *"<<<RALPHEX:REVIEW_DONE>>>"* ]]; then
    is_review_prompt=1
fi

if [[ "$is_review_prompt" == "1" ]]; then
    adapter_text=$'Ralphex review adapter for Qwen:\n- Interpret review "Task tool" instructions using qwen built-in subagents: the agent tool to launch, list_agents/send_message to check and continue.\n- Launch all requested review agents in parallel in one turn.\n- Wait for every launched review agent to finish (inline result or completion notification) before collecting findings and applying fixes.\n- Keep original review workflow and all <<<RALPHEX:...>>> signals unchanged.'
    prompt="$adapter_text"$'\n\n'"$prompt"
fi
# qwen subagents are built-in — unlike codex, no feature flag is toggled here.

# --yolo = auto-approve every tool call. Without it, qwen blocks on interactive
# approval prompts and the pipeline stage hangs until afm's executor timeout.
# --output-format stream-json = JSONL events on stdout, translated below.
qwen_args=(--yolo --sandbox=off --output-format stream-json --model "$OPENAI_MODEL")

# Optional OpenAI endpoint overrides — only pass when set, so the qwen binary's
# own defaults apply cleanly when neither is configured.
if [[ -n "${OPENAI_BASE_URL:-}" ]]; then
    qwen_args+=(--openai-base-url "$OPENAI_BASE_URL")
fi
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
    qwen_args+=(--openai-api-key "$OPENAI_API_KEY")
fi

# run qwen with stream-json output and translate events to claude stream-json
# format as they arrive. qwen already emits Anthropic-compatible events, so the
# translation is light:
#   assistant (parent_tool_use_id == null):
#     content text                -> passthrough                 -> narrative in the feed
#     content thinking            -> text block                  -> qwen "thoughts" made visible
#     content tool_use shell      -> tool_use Bash{command}      -> action line
#     content tool_use edit|write -> tool_use Edit{file_path}    -> file edit
#     (shell = run_shell_command|shell; edit|write = edit|write|write_file
#     across qwen-code releases)
#     content tool_use <other>    -> passthrough under its native name
#   assistant (parent_tool_use_id != null) -> skipped (subagent messages;
#     only the main agent stream is shown, mirroring the codex adapter)
#   result -> passthrough unchanged (richer than the codex bare result:
#     subtype/is_error/result preserved for the executor)
#   system, user (tool_result), stream_event, control_* -> skipped
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
                # shell tools: "run_shell_command" (qwen-code <= 0.21.x,
                # gemini-canonical) and "shell" (newer releases).
                if .name == "run_shell_command" or .name == "shell" then
                    {type: "tool_use", id: .id, name: "Bash",
                     input: {command: (.input.command // "")}}
                # file-writing tools: "edit"/"write_file" (<= 0.21.x)
                # and "edit"/"write" (newer releases).
                elif .name == "edit" or .name == "write" or .name == "write_file" then
                    {type: "tool_use", id: .id, name: "Edit",
                     input: {file_path: (.input.file_path // "")}}
                else .
                end
            else .
            end;

        if .type == "assistant" and .parent_tool_use_id == null then
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
done < <(printf '%s' "$prompt" | qwen "${qwen_args[@]}" 2>/dev/null)

# emit a fallback result event only if qwen exited without its terminal result
# event (startup or connection failure, crash). the codex adapter always emits
# this fallback and the executor tolerates the duplicate; here it is suppressed
# when qwen's own (richer) result was already forwarded.
if [[ "$saw_result" -eq 0 ]]; then
    jq -nc '{type:"assistant",message:{content:[{type:"text",text:"qwen produced no output and emitted no result event (likely a startup or connection failure)"}]}}'
    echo '{"type":"result","subtype":"error_during_execution","is_error":true,"result":"qwen exited without a result event"}'
fi
