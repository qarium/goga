# config — amending the project configuration

How the config-consuming operations use the hooks zone of the config
domain: delivering the amendment checkpoint at the project-configuration
load moment and consuming the effective configuration. For every
config-consuming surface — the host-side commands and the in-container
entrypoints alike.

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

config = load_project_config()  # authored load — the loader stays hooks-free
overlay = hooks.amend_config(config=config)
print_summary_to_stderr(overlay.summary_lines)
consume(overlay.config)  # every downstream consumer of the run
```

- The delivered context is built from the values you pass — the checkpoint
  reads no repository, no git, no files.
- Tools are mutually blind: every hook read the authored configuration,
  never another tool's contribution; each tool's contributions commit as a
  unit, in enumeration order.
- The amendment action is hard: the first failing tool — a crashed hook or
  a structurally malformed contribution — stops the command with a clean
  error naming the tool and the action.
- A tool package whose facade fails to import stops the command the same
  way — the error names the package (raised as ImportError at the
  registry build); convert it to the same clean error, never a raw
  traceback.
- An address without subscriptions returns the passthrough overlay — the
  configuration passed in, an empty applied list, empty summary lines.
  With no tool packages installed the load composes exactly what was
  passed.
- The authored .goga/config.yml is never modified — the effective
  configuration lives in memory for the current run; repeated runs with
  the same tools and file reproduce it deterministically.
- Values never appear in the summary — the lines carry the tool, the path,
  and set or forced only.

## One action, two moments

The checkpoint is not split by environment: the same action, the same path
vocabulary, and the same amendment semantics deliver at every load moment —
the host-side commands (goga/commands/pipeline, goga/commands/build) and the
in-container entrypoints (the pipeline run coordination, the build
entrypoint) alike.

Each side consumes only the fields it owns:

- the host consumes the docker-level launch fields — image, dockerfile,
  proxy, hosts — and runs the structural section guards on its effective
  configuration;
- the container consumes the run-parameter fields — the task env layers and
  the agent values — for everything downstream of its load.

A contribution into the other side's fields stays applied but unconsumed —
silently. No warning fires, no error is raised; the amendment summary lines
are the only visibility. Both delivery moments share the hard failure
semantics: the first failing tool stops the command with a clean error naming
the tool and the action, and the target binary (afm / ralphex) never
launches.
