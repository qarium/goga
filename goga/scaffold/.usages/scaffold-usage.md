# Project Scaffolding — goga/scaffold

## Overview

The `goga.scaffold` package wraps the copier template engine for goga project
scaffolding. It exposes two operations: primary generation from a template and
migration of a previously scaffolded project.

## Facade

Import the engine directly from `goga.scaffold`:

```python
from goga.scaffold import Scaffold
```

## Usage

### Scaffold — generate a project from a template

`Scaffold.generate(template_input, ref_override)` creates a project from a
copier template in the engine target directory. The raw template source may
carry a ref fragment; an explicit `ref_override` (`--ref`) takes precedence
over the fragment.

```python
from goga.scaffold import Scaffold

scaffold = Scaffold()  # defaults: current directory, .goga/scaffold.yml
exit_code = scaffold.generate(
    "https://github.com/example/goga-py-template.git#v1.0",
    ref_override="main",  # overrides the v1.0 fragment
)
```

- The engine passes the copier state-file path (`.goga/scaffold.yml` by default) to copier;
  the state file is persisted when the template renders it (the template must contain an
  answers-file entry — the copier `{{ _copier_conf.answers_file }}.jinja` convention).
- Questions not covered by the programmatic answers are asked interactively by copier
  (questionary TUI; a TTY is required). The project name is resolved from the git remote,
  falling back to an interactive prompt, and supplied programmatically.
- Returns `0` on success, nonzero on error (the error cause is echoed to stderr).

### Scaffold — migrate a scaffolded project

`Scaffold.upgrade(ref_override)` re-applies the recorded template at a newer version. It
reads the template source and answers from the state file persisted by `generate`;
`ref_override` (the CLI `--ref`) optionally overrides the migration target ref.

```python
from goga.scaffold import Scaffold

scaffold = Scaffold()
exit_code = scaffold.upgrade(ref_override="v2.0")  # migrate to v2.0; omit for the recorded/default ref
```

- Use the same state-file path that `generate` used (the default).
- The state file must exist; a missing state file yields a nonzero exit (not a
  silent success).
- copier's `run_update` requires `overwrite=True` (passed internally) and enforces preconditions
  surfaced as a nonzero exit: the destination must be a git repository, clean (no uncommitted
  changes), and the template must be git-trackable (a git URL) with a non-decreasing version.
- Returns `0` on success, nonzero on error.

## Construction

`Scaffold(dst_path, answers_file)` accepts the target directory and the copier
state-file path. Both default to the goga hard convention (the current
directory and `.goga/scaffold.yml`). Tests override them to point at a
temporary directory.

## Side effects

- `generate` writes files into `dst_path`; the state file at `answers_file` is
  persisted by the template's answers-file entry (without such an entry no
  state file is created and `upgrade` reports it missing).
- `upgrade` rewrites files in `dst_path` according to the newer template
  version.
- The state file must NOT be git-ignored in a scaffolded project — `upgrade`
  depends on it.

## Anti-patterns

- Do not run `upgrade` without a prior `generate` in the same target (no state
  file to read).
- Do not pass a different `answers_file` to `generate` and `upgrade` — they
  share one state file.
- Do not ship a template without an answers-file entry — the state file is the
  migration history `upgrade` depends on.
- Do not run `generate` non-interactively (CI/pipe) with template questions
  lacking programmatic answers or defaults — the copier survey requires a TTY
  and fails with the cause echoed to stderr.
