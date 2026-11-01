# collaboration-delivery — delivering assistants into the afm configuration

How authored collaboration reaches the engine on every launch: the
generated helper profiles, the env closures behind their commands, and
the whole-run task budget. Target audience: contributors reasoning about
the delivered artifacts and workflow authors checking why their authoring
survives every launch.

## The two artifacts

The engine consumes collaboration through two artifacts goga already
produces:

- the **compiled flow-file** — `collaboration: {mode: assistants}`,
  `max_depth` when a depth is authored, the `team` list, and the stage
  `assistants` entries;
- the **engine configuration** written before every launch — the generated
  `collaboration.profiles` and `collaboration.limits.max_tasks`.

The compiled flow is the single source of truth: a profile is
materialized exactly for the ids the flow references (`goga-<name>` of
every team member and every stage attachment). The two artifacts cannot
diverge, and no dead profile remains for an attachment removed by a stage
skip.

## Generated profiles

| Key | Value |
|-----|-------|
| `title` | the assistant's authored name |
| `command` | the resolved launch command (below) |
| `delegate` | the authored permission, false by default |

Nothing else is written into a generated profile. The profile id is
`goga-<name>`; the `goga-` prefix is the intended override channel — a
user-authored same-named profile in the project layer (`.afm/config.yaml`)
deliberately replaces goga's plumbing, and that file is user territory
goga never touches.

## Command resolution

The profile's command resolves exactly like a stage agent command:

1. the assistant's authored `agent` → its wrapper path;
2. else the effective global pipeline agent → its wrapper path;
3. else the launch fails strictly before the run with an error naming the
   assistant and its authoring site (the catalog or the stage whose
   attachment declares it).

An assistant carrying an `env` instruction is delivered through a
generated sh closure: the closure exports the assistant's env values and
execs the resolved wrapper, and the closure path becomes the profile's
command — a profile carries its own command and inherits none. Closures
are regenerated on every launch in a container-local temp directory, so
the authored configuration survives the per-launch configuration rewrite
by living in the workflow-file. Env keys must be legal environment
variable names — anything else is a strict pre-run error naming the
assistant and the key, raised before any closure is written.

## The task budget

`collaboration.limits.max_tasks` is written only when the workflow
carries a `delegation:` block — the authored `max_tasks`, materialized to
50 when the block omits it (the engine's own default is 20 and is never
relied upon). `delegation.depth` travels in the flow-file as
`collaboration.max_depth`.

## What goga never does

- goga neither reads nor writes the collaboration kill-switch — an
  environment that disables collaboration gets engine warnings and
  skipped helpers, and the run proceeds.
- goga writes no profile beyond the ids the flow references, and no key
  beyond `{title, command, delegate}`.
- goga never touches the project-layer `.afm/config.yaml`.
