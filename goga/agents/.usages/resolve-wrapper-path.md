# Resolve an agent name to its in-container wrapper path

## Domain

Resolution of agent names declared in `.goga/config.yml`
(`build.task_executor.agent`, `pipeline.agent`) to the absolute in-container
path of the corresponding `*-as-claude.sh` wrapper script.

Target audience: goga cells that write the resolved path into a downstream
tool's config (ralphex `.ralphex/config` `claude_command`, afm
`~/.afm/config.yaml` `client.command`).

## Pattern

```python
from goga.agents import resolve_wrapper_path

path = resolve_wrapper_path(agent)
# 'codex' -> '/home/goga/bin/codex-as-claude.sh'
# 'claude' -> '/home/goga/bin/claude-as-claude.sh'
# 'cursor' -> '/home/goga/bin/cursor-as-claude.sh'
# 'opencode' -> '/home/goga/bin/opencode-as-claude.sh'
```

The routine performs no validation. `agent` is forwarded verbatim into the
path string; the result is always an absolute path under the in-container
wrappers directory `/home/goga/bin/`.

Consumers import from `goga.agents` (the facade) — never from any deeper
module path.

## Pre-conditions for the consumer

- The caller has already loaded `.goga/config.yml` and holds a non-empty
  `agent` string.
- The caller is responsible for detecting a missing wrapper file — the
  downstream tool (ralphex, afm) reports the absence via its own error path.

## Side effects

None. The routine is a pure string-building function with no filesystem access.

## Anti-patterns

- Do not import `resolve_wrapper_path` from any deeper module path — import
  from `goga.agents` so the facade stays the single stable import point.
- Do not pass a `wrappers_dir` override — the directory is fixed to
  `/home/goga/bin/` and parameterizing it would fracture the convention.
- Do not pre-validate `agent` against a whitelist before calling — that
  duplicates the downstream tool's error path and creates a drift risk.
- Do not normalize `agent` (case-fold, strip) before calling — the value is
  forwarded as-is.
