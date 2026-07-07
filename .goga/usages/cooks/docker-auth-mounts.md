# Docker Auth Mounts — Read-Only Credential Bind-Mounts

## Domain

The rule for bind-mounting AI-agent credential files (claude, codex, opencode)
read-only from the host into a container that runs the agent CLIs. Host-side
tooling that assembles `docker run` commands applies this rule to give each
in-container agent access to the same credentials the host user already has.

Target audience: anyone authoring a `docker run` invocation — or a launcher
that builds one — who needs to know which credential files to mount, where they
live on the host, and where they must appear inside the container.

## Rule

For every credential file in the path table that exists on the host, add a
read-only bind-mount flag to the `docker run` command:

```
-v <host_path>:<container_path>:ro
```

Detection is by filesystem existence only — a credential file is mounted when
its host path exists and is omitted silently when it does not. No credential
file contents are read or parsed; only the path is checked.

## Path table

| agent    | host_path                                  | container_path                             |
|----------|--------------------------------------------|--------------------------------------------|
| claude   | `~/.claude/.credentials.json`              | `/home/goga/.claude/.credentials.json`     |
| codex    | `~/.codex/auth.json`                       | `/home/goga/.codex/auth.json`              |
| opencode | `~/.local/share/opencode/auth.json`        | `/home/goga/.local/share/opencode/auth.json`|

Container paths mirror the host layout under `/home/goga/` so each in-container
CLI locates its credential through its native lookup logic.

## Invocation

A launcher iterates the path table in order and, for each entry whose host path
exists, appends a `-v <host_path>:<container_path>:ro` flag. With all three
credential files present the resulting invocation resembles:

```bash
docker run --rm \
    -v ~/.claude/.credentials.json:/home/goga/.claude/.credentials.json:ro \
    -v ~/.codex/auth.json:/home/goga/.codex/auth.json:ro \
    -v ~/.local/share/opencode/auth.json:/home/goga/.local/share/opencode/auth.json:ro \
    <image>
```

## Semantics

- **Agent-agnostic.** All three agents are considered unconditionally; the set
  of mounts is NOT filtered by the agent selected for a particular invocation.
  A launcher that supports different agents across runs must not prune
  credential mounts to a single agent.
- **Read-only mounts.** All mounts use the `:ro` suffix; credential files are
  never written to from inside the container.
- **Empty set is valid.** When no credential file exists on the host, no mount
  flags are added; the container starts without credential mounts and the
  in-container agent surfaces authentication failure through its own error path.

## Platform caveat — macOS Keychain for claude

On macOS, web-login for the claude CLI stores the token in the macOS Keychain
and **auto-deletes** `~/.claude/.credentials.json`. When that happens no claude
credential file is mounted — the Keychain cannot be bind-mounted into a Docker
container.

Workarounds for macOS users who need claude credentials inside the container:

1. Re-create `~/.claude/.credentials.json` manually with the OAuth token before
   launching the container.
2. Pass `ANTHROPIC_API_KEY` via an `-e KEY=VALUE` (or `--env-file`) option
   instead of relying on the credential file.

## Anti-patterns

- Do not mount the entire `~/.claude/` directory — mount only the credential
  file. Mounting the whole directory leaks host settings and cache into the
  container.
- Do not mount credential files read-write — the container must not modify host
  credentials.
- Do not filter credential mounts by the selected agent name — see
  "Agent-agnostic" above.
- Do not introduce a credential-mount toggle — credential files are always
  mounted when they exist; absence is the off-switch.
