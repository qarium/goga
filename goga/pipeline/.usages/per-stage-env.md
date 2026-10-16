# Per-stage environment delivery

## Domain

How the `stages.<name>.env` workflow instruction reaches the executing
agent: authoring, the wrapper mechanism, and the layering rules.
Target audience: workflow authors declaring per-stage environments and
contributors combining them with profile data.

## Authoring

Inside the workflow stages block, a stage entry may carry `env` — a
map of environment variables for that stage, literal and/or rendered
from profile data:

```yaml
stages:
  worker:
    agent: '{{ worker.agent }}'
    env:
      ANTHROPIC_MODEL: '{{ worker.model }}'
  review:
    env:
      REVIEW_STRICTNESS: strict
```

`env` is valid ONLY under `stages.<name>` — never in an extend-entry.
An empty map equals absence. Keys must be legal environment variable
names (POSIX shape: a letter or underscore, then letters, digits, or
underscores) — anything else is a strict pre-run error naming the stage
and the key, raised before any wrapper is written.

## Delivery mechanism

afm stages carry a `command:` field following the absolute-executable-
path convention — so per-stage env travels through a generated sh
closure wrapper the field points at. After compilation goga patches
the `command:` field of exactly the env-declaring stages in the written
flow-file to point at their wrappers — a targeted patch; every other
byte of the flow-file stays untouched, and an env-free workflow is not
rewritten at all (byte-identical). The wrapper:

1. exports the stage's env values (above every global env layer),
2. execs the stage agent's wrapper — else the effective global wrapper
   (the same agent the run would use globally) — else the run fails
   strictly before launch, naming the stage.

Wrappers are generated per run in a container-local temp directory and
never touch the project directory. No contributor-side wrapper scripts
are ever required. Loop-expanded copies of an env-declaring stage all
carry the env — each copy receives its own wrapper with the same
values.

## What stays identical

Stages without `env` are compiled and serialized without wrappers —
the flow output of an env-free workflow stays byte-identical to the
compiler's direct composition. Skip, prompts, and depends_on handling
are unaffected.

## Combining with profiles

The env map is rendered together with the whole workflow-file: profile
data may drive both keys and values (iterate a profile mapping to
produce the whole block). When the profile may omit the data, guard the
whole `env:` key (not only the loop entries) with `{% if worker %}` —
the guarded block then vanishes cleanly when the profile omits it. An
un-guarded iteration over a missing key raises at render time (nested
access on a missing key), and a rendered-empty loop would leave `env:`
with a null value — a structural error.
