# Profile resolution and activation

## Domain

Resolution and activation of contributor profiles for workflow rendering:
how a profile name becomes the template context, how the two lookup
locations interact, and how the activation channels compose. Target
audience: consumers of the workflow cell that resolve profiles — the
pipeline run coordination and card (goga/pipeline), the build path
(goga/build), and the host launchers that collect the home bundle
(goga/commands/pipeline, goga/commands/build).

## Profile files

- Project profiles: `<project>/.goga/profiles/<name>.yml` — committed,
  shared.
- Home profiles: `~/.goga/profiles/<name>.yml` — personal, never
  committed.
- The same name in both locations: the project file wins.
- A profile is a free-form YAML mapping; its entire content becomes the
  template context — every top-level key is a template variable. The
  data model of a profile is defined solely by what the workflow's
  templates read.
- Management is files-only: no CLI subcommands exist for creating,
  listing, or inspecting profiles.

## Name grammar

A profile name must match `[A-Za-z0-9][A-Za-z0-9._-]*`; the names `.`
and `..` are forbidden. The name becomes a filesystem path component,
so the grammar is a path-traversal guard — a violation is a strict
pre-run failure naming the profile.

## Activation precedence

From strongest to weakest:

1. the `--profile` CLI option (arrives as the cli channel),
2. the `GOGA_PROFILE` environment variable (arrives as the env channel),
3. the workflow's top-level `profile:` default.

Empty strings count as unset. With no workflow in effect, activation is
ignored entirely — nothing loads, no line prints.

```python
from goga.pipeline.workflow import resolve_activation

name = resolve_activation(cli_profile, env_profile, workflow_default)
# name is the effective profile name, or None when every source is unset
```

## Resolving a name

`resolve_profile(name, project_dir, home_profiles)` validates the name
grammar, looks up `<project_dir>/<name>.yml` first (strict failure
naming the profile and path when the file is malformed), then the home
bundle mapping, and otherwise fails strictly naming the profile and BOTH
lookup locations. The result carries the name, the content mapping, and
the source (`project` or `home`).

## Collecting the home bundle (host side)

`load_home_profiles(home_dir)` reads every flat `*.yml` file under the
directory (a missing directory is an empty bundle). Every file must be
valid YAML with a mapping root — a malformed home profile is a strict
failure on the host BEFORE any container launches. The returned mapping
feeds the docker-cell encoder for the `GOGA_HOME_PROFILES` carriage and
arrives in-container through the docker-cell decoder.

## Failure strictness

All profile failures are pre-run: nothing partial executes, humans and
CI see identical behaviour, and every message is actionable (profile
name, path, or both lookup locations).
