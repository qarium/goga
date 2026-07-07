# Docker Auth Mounts — Read-Only Credential Bind-Mounts

## Domain

The rule for bind-mounting AI-agent credential files (claude, codex, opencode)
read-only from the host into the goga Docker container. Host-side docker
launchers apply this rule when assembling `docker run` commands.

Target audience: goga cells that assemble `docker run` commands and need to know
which credential files to mount, where they live on the host, and where they
must appear inside the container.

## Rule

For every known AI-agent credential file that exists on the host, add a
read-only bind-mount flag to the `docker run` command:

```
-v <host_path>:<container_path>:ro
```

Detection is performed by the `resolve_credential_mounts()` facade routine —
the consumer calls the routine and iterates the returned list. Every returned
tuple is an existing file by construction; the consumer does not re-check
existence.

## Path table

| agent    | host_path                                  | container_path                             |
|----------|--------------------------------------------|--------------------------------------------|
| claude   | `~/.claude/.credentials.json`              | `/home/goga/.claude/.credentials.json`     |
| codex    | `~/.codex/auth.json`                       | `/home/goga/.codex/auth.json`              |
| opencode | `~/.local/share/opencode/auth.json`        | `/home/goga/.local/share/opencode/auth.json`|

Container paths mirror the host layout under `/home/goga/` so each in-container
CLI locates its credential through its native lookup logic.

## Semantics

- **Agent-agnostic detection.** All three agents are checked unconditionally;
  the result is NOT filtered by the agent configured for a particular
  build/pipeline stage. Pipelines may use different agents across stages, and
  stage-specific filtering would break multi-stage pipelines.
- **Read-only mounts.** All mounts use the `:ro` suffix; credential files are
  never written to from inside the container.
- **Empty result is valid.** When no credential file exists on the host, no
  mount flags are added; the container starts without credential mounts and
  the in-container agent surfaces authentication failure through its own error
  path.

## Consumer pattern

```python
from goga.agents import resolve_credential_mounts

cmd = ["docker", "run", "--rm"]
for host_path, container_path in resolve_credential_mounts():
    cmd.extend(["-v", f"{host_path}:{container_path}:ro"])
cmd.append(image)
```

## Platform caveat — macOS Keychain for claude

On macOS, web-login for the claude CLI stores the token in the macOS Keychain
and **auto-deletes** `~/.claude/.credentials.json`. When that happens no claude
credential file is mounted — the Keychain cannot be bind-mounted into a Docker
container.

Workarounds for macOS users who need claude credentials inside the container:

1. Re-create `~/.claude/.credentials.json` manually with the OAuth token before
   launching goga.
2. Pass `ANTHROPIC_API_KEY` via the consumer's `-e/--env KEY=VALUE` option
   instead of relying on the credential file.

## Anti-patterns

- Do not mount the entire `~/.claude/` directory — mount only the credential
  file. Mounting the whole directory leaks host settings and cache into the
  container.
- Do not mount credential files read-write — the container must not modify host
  credentials.
- Do not filter credential mounts by the configured agent name — see
  "Agent-agnostic detection" above.
- Do not introduce a `--mount-credentials` CLI toggle — credential mounts are
  always added when the corresponding file exists; absence is the off-switch.
