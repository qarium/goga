# Docker Auth Mounts — Mounting Your Own Agent Credentials

## Domain

Self-served mounting of AI-agent credential files (claude, codex, opencode) into a container
that runs the agent CLIs. goga launchers add no credential mounts — you mount what you need,
where you need it.

Target audience: goga users who run pipelines or builds in the goga Docker container and want
the in-container agents to use the same credentials the host user already has.

## Primary channel — home.docker.run

Add volume tokens to the `docker.run` list of the home configuration (~/.goga/config.yml). The
tokens join every `docker run` goga launches; the accepted token shape and the layering rules
live in the `home-configuration` usage of the config cell. Example:

    docker:
      run:
        - "-v ~/.claude/.credentials.json:/home/goga/.claude/.credentials.json:ro"
        - "-v ~/.codex/auth.json:/home/goga/.codex/auth.json:ro"

## Path table

Mount each credential file to the container path its CLI looks up natively — the container
layout mirrors the host layout under /home/goga/:

| agent    | host_path                                  | container_path                             |
|----------|--------------------------------------------|--------------------------------------------|
| claude   | `~/.claude/.credentials.json`              | `/home/goga/.claude/.credentials.json`     |
| codex    | `~/.codex/auth.json`                       | `/home/goga/.codex/auth.json`              |
| opencode | `~/.local/share/opencode/auth.json`        | `/home/goga/.local/share/opencode/auth.json`|

## Alternative — environment variables

When a CLI accepts an API-key variable, pass it with the launcher's `-e/--env KEY=VALUE`
option (for example `ANTHROPIC_API_KEY=...`). The entry joins the container environment
verbatim.

## Recommendations

- Mount credential files read-only (`:ro`) — the container must never modify host credentials.
- Mount only the credential file, never the whole agent directory — a directory mount leaks
  host settings and caches into the container.
- An absent credential file is not an error: the in-container agent surfaces authentication
  failure through its own error path.

## Platform caveat — macOS Keychain for claude

On macOS, web-login for the claude CLI stores the token in the macOS Keychain and
auto-deletes `~/.claude/.credentials.json`. The Keychain cannot be bind-mounted. Re-create
`~/.claude/.credentials.json` manually with the OAuth token before launching goga, or pass
`ANTHROPIC_API_KEY` via `-e/--env` instead.
