# config — amending the project configuration

How the config-consuming operations use the hooks zone of the config
domain: delivering the amendment checkpoint at the project-configuration
load moment and consuming the effective configuration. For every
host-side command and config-driven module that loads .goga/config.yml.

## The checkpoint surface

One `ConfigHooks` object serves the checkpoint of a run — the surface
shares one registry per run, so a command that reaches further checkpoints
enumerates the tool packages once.

```python
from goga.config.hooks import ConfigHooks

hooks = ConfigHooks()
```

## Amend at the load moment

Load the authored configuration, hand it to the zone entry, and consume
the effective configuration the delivery returns. Print the composed
summary lines to stderr; stdout stays data-clean.

```python
from goga.config import load_project_config

config = load_project_config()    # authored load — the loader stays hooks-free
overlay = hooks.amend_config(config=config)
print_summary_to_stderr(overlay.summary_lines)
consume(overlay.config)           # every downstream consumer of the run
```

- The delivered context is built from the values you pass — the checkpoint
  reads no repository, no git, no files.
- Tools are mutually blind: every hook read the authored configuration,
  never another tool's contribution; each tool's contributions commit as a
  unit, in enumeration order.
- The amendment action is hard: the first failing tool — a crashed hook or
  a structurally malformed contribution — stops the command with a clean
  error naming the tool and the action.
- An address without subscriptions returns the passthrough overlay — the
  configuration passed in, an empty applied list, empty summary lines.
  With no tool packages installed the load composes exactly what was
  passed.
- The authored .goga/config.yml is never modified — the effective
  configuration lives in memory for the current run; repeated runs with
  the same tools and file reproduce it deterministically.
- Values never appear in the summary — the lines carry the tool, the path,
  and set or forced only.

## In-container loads stay authored-only

The in-container entry points (`python -m goga.build` and any in-container
pipeline counterpart) load the authored configuration directly and
deliver no checkpoint — in-container loading is the correct behavior for
the build and pipeline domains.
