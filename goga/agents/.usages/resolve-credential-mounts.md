# Resolve AI-agent credential mounts for the goga container

## Domain

Detection of AI-agent credential files (claude, codex, opencode) on the host
filesystem and the host→container path pairs used to bind-mount them read-only
into the goga Docker container.

Target audience: goga cells that assemble `docker run` commands. Consumers
call this facade routine to obtain the list of credential files to mount, then
add a `-v <host>:<container>:ro` flag for each returned tuple.

## Pattern

```python
from goga.agents import resolve_credential_mounts

mounts = resolve_credential_mounts()
# When all three credential files exist on the host:
# [
#   ("/Users/wb/.claude/.credentials.json", "/home/goga/.claude/.credentials.json"),
#   ("/Users/wb/.codex/auth.json", "/home/goga/.codex/auth.json"),
#   ("/Users/wb/.local/share/opencode/auth.json", "/home/goga/.local/share/opencode/auth.json"),
# ]
# Empty list when none exist.
```

The routine takes no arguments — detection is agent-agnostic. It scans a fixed
path table covering claude, codex, and opencode; only files that exist on the
host are returned. Container paths mirror the host layout under `/home/goga/`
so the in-container CLI locates each credential through its native lookup logic.

Consumers import from `goga.agents` (the facade) — never from any deeper
module path.

## Path table

The fixed mapping the routine consults:

| agent    | host_path                                  | container_path                             |
|----------|--------------------------------------------|--------------------------------------------|
| claude   | `~/.claude/.credentials.json`              | `/home/goga/.claude/.credentials.json`     |
| codex    | `~/.codex/auth.json`                       | `/home/goga/.codex/auth.json`              |
| opencode | `~/.local/share/opencode/auth.json`        | `/home/goga/.local/share/opencode/auth.json`|

## Consumer-side mount loop

```python
from goga.agents import resolve_credential_mounts

cmd = ["docker", "run", "--rm"]
for host_path, container_path in resolve_credential_mounts():
    cmd.extend(["-v", f"{host_path}:{container_path}:ro"])
cmd.append(image)
```

Every returned tuple is an existing file — no existence re-check is needed on
the consumer side.

## Pre-conditions for the consumer

- The caller has resolved the goga Docker image and is assembling a `docker run`
  command. The result is appended to the command as read-only bind-mount flags.
- The caller tolerates an empty result: no credential file on the host means no
  mount flags are added; the container starts without credential mounts and the
  in-container agent surfaces authentication failure through its own error path.

## Side effects

Read-only filesystem access via `Path.exists()` — the routine does not modify
the host filesystem and does not parse credential file contents.

## Semantics

- **Agent-agnostic detection.** All three agents are checked unconditionally;
  the result is NOT filtered by the agent configured for a particular
  build/pipeline stage. Pipelines may use different agents across stages, and
  stage-specific filtering would break multi-stage pipelines.
- **Read-only mounts.** All mounts use the `:ro` suffix; credential files are
  never written to from inside the container.

## Platform caveat — macOS Keychain for claude

On macOS, web-login for the claude CLI stores the token in the macOS Keychain
and **auto-deletes** `~/.claude/.credentials.json`. When that happens this
routine returns no claude tuple — the Keychain cannot be bind-mounted into a
Docker container.

Workarounds for macOS users who need claude credentials inside the container:

1. Re-create `~/.claude/.credentials.json` manually with the OAuth token before
   launching goga.
2. Pass `ANTHROPIC_API_KEY` via the consumer's `-e/--env KEY=VALUE` option
   instead of relying on the credential file.

## Anti-patterns

- Do not import `resolve_credential_mounts` from any deeper module path — import
  from `goga.agents` so the facade stays the single stable import point.
- Do not filter the result by the configured agent name — see "Agent-agnostic
  detection" above.
- Do not re-check `Path.exists()` on the returned tuples — every tuple is an
  existing file by construction.
- Do not pass a credential path override — the path table is fixed; updating one
  path is a single-line edit in the cell's source.
