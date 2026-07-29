#!/usr/bin/env bash
# qwen-as-claude_test.sh — bash test suite for qwen-as-claude.sh.
#
# Runs the wrapper against a stubbed HTTP endpoint and asserts on its stdout.
# The stub server is a small Python http.server.BaseHTTPRequestHandler so the
# suite is portable across macOS (BSD nc) and Linux (traditional nc) — nc -l
# flag syntax differs between the two, and Python's BaseHTTPRequestHandler is
# uniform on both. Each test that needs a stub spawns its own server on a
# distinct port and tears it down before the next test.
#
# Usage: bash scripts/qwen-as-claude_test.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/qwen-as-claude.sh"

fail=0
check() {
    local name="$1" expected="$2" actual="$3"
    if [[ "$expected" == "$actual" ]]; then
        echo "ok   - $name"
    else
        echo "FAIL - $name"
        echo "       expected: $expected"
        echo "       actual:   $actual"
        fail=1
    fi
}

# Test 1: empty stdin → non-zero exit, readable error on stderr.
out=$(echo -n "" | bash "$SCRIPT" 2>&1 >/dev/null || true)
check "empty stdin errors" "error: empty prompt" "$out"

# Test 2: OPENAI_MODEL unset → non-zero exit, readable error on stderr.
out=$(echo "hi" | env -u OPENAI_MODEL bash "$SCRIPT" 2>&1 >/dev/null || true)
check "missing OPENAI_MODEL errors" "error: OPENAI_MODEL is required" "$out"

# --- Stub HTTP endpoint -------------------------------------------------------
# A small Python http.server.BaseHTTPRequestHandler one-shot server. Each call
# to spawn_stub starts a fresh process on a distinct port; the server replies
# with the canned SSE body to the next POST and then exits. Portable across
# macOS (BSD nc) and Linux — we avoid nc -l entirely because its flag syntax
# differs between platforms.
spawn_stub() {
    local port="$1"; shift
    local body="$1"; shift
    python3 - "$port" "$body" <<'PY' &
import sys, http.server, socketserver
port = int(sys.argv[1])
body = sys.argv[2].encode().decode('unicode_escape')
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        ln = int(self.headers.get('Content-Length', 0))
        self.rfile.read(ln)
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body.encode())
    def log_message(self, *a): pass
class TS(socketserver.TCPServer):
    allow_reuse_address = True
with TS(("127.0.0.1", port), H) as s:
    s.handle_request()
PY
    STUB_PID=$!
}

STUB_PORT=18080
stub_sse_ok='data: {"choices":[{"delta":{"content":"hello"}}]}\n\ndata: {"choices":[{"delta":{"content":" world"}}]}\n\ndata: [DONE]\n\n'

# Test 3: two delta chunks → two content_block_delta events with concatenated text.
spawn_stub "$STUB_PORT" "$stub_sse_ok"
sleep 0.3
out=$(echo "hi" | OPENAI_MODEL="qwen-test" OPENAI_BASE_URL="http://127.0.0.1:${STUB_PORT}/v1" bash "$SCRIPT" 2>/dev/null || true)
kill "$STUB_PID" 2>/dev/null || true

got_deltas=$(printf '%s' "$out" | grep -c '"type":"content_block_delta"' || true)
check "two deltas emitted" "2" "$got_deltas"

# Test 4: signal passthrough — <<<RALPHEX:ALL_TASKS_DONE>>> survives verbatim inside a delta.
# Note: the JSON \\n is a JSON escape (backslash + n); it must NOT be decoded into a real newline
# by the stub or the data: line would be split mid-event. The outer \n\n is the SSE terminator
# and DOES decode to a real blank line.
stub_sse_signal='data: {"choices":[{"delta":{"content":"work done\\n<<<RALPHEX:ALL_TASKS_DONE>>>"}}]}\n\ndata: [DONE]\n\n'
spawn_stub "$STUB_PORT" "$stub_sse_signal"
sleep 0.3
out=$(echo "hi" | OPENAI_MODEL="qwen-test" OPENAI_BASE_URL="http://127.0.0.1:${STUB_PORT}/v1" bash "$SCRIPT" 2>/dev/null || true)
kill "$STUB_PID" 2>/dev/null || true

# Extract the concatenated text field from all emitted deltas. jq -j joins
# without newlines between records but still decodes \n escapes inside each text.
got_text=$(printf '%s' "$out" | grep '"type":"content_block_delta"' | jq -j '.delta.text' 2>/dev/null)
check "signal passthrough" $'work done\n<<<RALPHEX:ALL_TASKS_DONE>>>' "$got_text"

# Test 5: data: [DONE] terminates the loop and the final result event is emitted.
spawn_stub "$STUB_PORT" "$stub_sse_ok"
sleep 0.3
out=$(echo "hi" | OPENAI_MODEL="qwen-test" OPENAI_BASE_URL="http://127.0.0.1:${STUB_PORT}/v1" bash "$SCRIPT" 2>/dev/null || true)
kill "$STUB_PID" 2>/dev/null || true

got_result=$(printf '%s' "$out" | grep -c '"type":"result","subtype":"success"' || true)
check "result event emitted" "1" "$got_result"

# Test 6: no-auth path — OPENAI_API_KEY unset + stub server ignores auth → succeeds, no Authorization sent.
# (We assert indirectly: the request succeeds and produces deltas. Header inspection needs a richer stub;
#  a dedicated header-capturing stub is out of scope for the minimal test — document as a manual check.)
spawn_stub "$STUB_PORT" "$stub_sse_ok"
sleep 0.3
out=$(echo "hi" | env -u OPENAI_API_KEY OPENAI_MODEL="qwen-test" OPENAI_BASE_URL="http://127.0.0.1:${STUB_PORT}/v1" bash "$SCRIPT" 2>/dev/null || true)
kill "$STUB_PID" 2>/dev/null || true

got_deltas=$(printf '%s' "$out" | grep -c '"type":"content_block_delta"' || true)
check "no-auth path works" "2" "$got_deltas"

# Test 7: curl exits non-zero → final assistant envelope + result: success.
# Point OPENAI_BASE_URL at a port nothing listens on so curl fails fast (connection refused).
out=$(echo "hi" | OPENAI_MODEL="qwen-test" OPENAI_BASE_URL="http://127.0.0.1:9/v1" bash "$SCRIPT" 2>/dev/null || true)
got_assistant=$(printf '%s' "$out" | grep -c '"type":"assistant"' || true)
got_result=$(printf '%s' "$out" | grep -c '"type":"result","subtype":"success"' || true)
check "curl failure emits assistant envelope" "1" "$got_assistant"
check "curl failure emits result" "1" "$got_result"

# Test 8: role-only delta + finish_reason chunk → skipped, no spurious events.
stub_sse_skip='data: {"choices":[{"delta":{"role":"user"}}]}\n\ndata: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: {"choices":[{"delta":{"content":"only-me"}}]}\n\ndata: [DONE]\n\n'
spawn_stub "$STUB_PORT" "$stub_sse_skip"
sleep 0.3
out=$(echo "hi" | OPENAI_MODEL="qwen-test" OPENAI_BASE_URL="http://127.0.0.1:${STUB_PORT}/v1" bash "$SCRIPT" 2>/dev/null || true)
kill "$STUB_PID" 2>/dev/null || true

got_deltas=$(printf '%s' "$out" | grep -c '"type":"content_block_delta"' || true)
check "role-only and finish_reason skipped" "1" "$got_deltas"

exit $fail
