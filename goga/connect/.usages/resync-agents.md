# Agent Re-Sync API — goga/connect

## Overview

`resync_registered_agents` re-applies the agent connection to every agent
recorded in the registry (`connect.yml` inside the passed goga home), each
with its own persisted `force_overwrite`. It is the shared post-change hook
for any command that adds, upgrades, or removes packages carrying goga
skills or pipelines: after the change succeeds, one call rebuilds the
central assets and the agents' symlink trees so they track the packages
that actually remain installed.

The routine is read-only towards the registry: it never writes
`connect.yml` (the connect command is the single writer), never runs pip,
and never installs packages.

## When to Call

| Caller situation | Call? | Rationale |
|---|---|---|
| A pip install/upgrade/uninstall succeeded | yes | the re-sync is what links (or unlinks) the changed packages into every connected agent |
| pip was not invoked (declined confirmation, empty set) | no | nothing changed on the interpreter — the exit code is the caller's own |
| pip exited non-zero | no | the failed outcome propagates; recovering a broken state is a separate scenario |

## Calling

```python
from pathlib import Path

from goga.connect import resync_registered_agents

# Re-sync the current user's installation
exit_code = resync_registered_agents(Path.home() / ".goga")

# Re-sync another user's installation (e.g. a --user flag resolved via pwd)
exit_code = resync_registered_agents(
    Path(pwd.getpwnam("alice").pw_dir) / ".goga",
)
```

- Pass the goga home directory (the one holding `connect.yml`), not the
  registry file.
- Never call it under sudo — it operates on the home that owns the passed
  directory; under `--sudo` flows, resolve the real user's home first and
  run the re-sync after the privileged part finishes.

## Exit Codes

| Exit code | Condition |
|---|---|
| 0 | every recorded agent re-synced |
| 0 | registry missing or empty — a normal no-op, not an error |
| 1 | registry malformed or unreadable (YAML parse failure, permission error, non-UTF-8) — reported to stderr; no agents are re-synced |
| first non-zero per-agent result | one or more agents failed; the loop continues and reports the first failure |

Treat the return value as the caller's final exit code only when the
preceding package operation succeeded.

## Side Effects

- Rebuilds central assets under the passed goga home: purges and recreates
  `skills/goga-*`, re-downloads the DSL specification, recreates
  `pipelines/` from the packages that remain installed — removed tools'
  skills and `<tool>:*.yml` pipelines disappear here.
- Rebuilds each connected agent's symlinks, removing stale ones.
- Emits a `Re-syncing <N> registered agent(s): <list>` banner to stderr
  followed by a `Connecting agent: <name>` line per agent; a missing or
  empty registry is silent.

## Preconditions

- The interpreter's installed package set is the one the re-sync should
  reflect — call it after the pip step, not before.
- The caller can write to the passed goga home and the agent directories.

## Anti-Patterns

- Do not read or parse `connect.yml` to iterate agents yourself — delegate
  to `resync_registered_agents`.
- Do not run the re-sync under sudo or against `/root/.goga` — resolve the
  owning user's home first.
- Do not call it after a failed pip step to "clean up" — a failed package
  operation propagates its own exit code.
