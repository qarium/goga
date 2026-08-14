# Template-based project scaffolding with copier

## Library

**copier** — a template-driven project generation engine with migration support (a migration updates a previously generated project to a newer version of the same template).

Installation: `pip install copier`

**IMPORTANT** — the library must be declared in the project's main dependencies (never in extras).

copier transitively pulls `pydantic`, `questionary`, `prompt-toolkit`. goga drives copier programmatically through two operations: `run_copy` (project creation) and `run_update` (migrating a previously created project). During primary generation, the copier interactive survey (`questionary`) asks every template question not covered by programmatic answers; goga passes only `project_name` programmatically.

## Two operations

goga distinguishes two domains — **onboarding** (collecting answers for `.goga/config.yml`) and **scaffold** (generating the project boilerplate from a template). Scaffold wraps copier and provides exactly two operations:

| copier operation | goga CLI | Purpose |
|-----------------|----------|---------|
| `run_copy` | `goga init <tpl>` | Create a project from a template (primary generation) |
| `run_update` | `goga init --upgrade` | Update a previously created project to a newer version of the same template |

`run_update` reads the previously recorded template + answers from the state file (see below) — this is the template's "migration history", the reason copier was chosen over cookiecutter.

## run_copy — primary generation

```python
from copier import run_copy

run_copy(
    template,            # template git URL (optionally with a ref fragment: url.git#v1.0) or a local path
    ".",                 # dst_path — target directory (the current one for goga init)
    data={"project_name": project_name},   # programmatically assembled answers
    answers_file=".goga/scaffold.yml",     # goga dictates the state file location
    vcs_ref=ref,         # optional: overrides the ref parsed from the URL fragment
    defaults=False,      # MANDATORY False: the survey asks questions not covered by data
)
```

- `dst_path="."` — the project is generated into the current directory (where `goga init` runs).
- `data` — a dictionary of prefilled template answers; merged with the defaults from the template's `copier.yml`. `project_name` is resolved from the git project name with a fallback to an interactive prompt when the name cannot be resolved.
- `vcs_ref` — the template's branch/tag/commit. When the ref is given both in the URL fragment and explicitly via the CLI `--ref`, the explicit `--ref` takes precedence.
- `defaults=False` is **mandatory** on primary generation — questions not covered by `data` are asked interactively (questionary, a TTY is required). A required question without a programmatic answer and without a default does not fail the generation — it is asked of the user. In a non-interactive environment (pipe/CI) questionary receives EOF, copier raises `InteractiveSessionError` — the cause is echoed to stderr.

## run_update — template migration

```python
from copier import run_update

run_update(
    ".",                               # dst_path — target directory of the previously created project
    answers_file=".goga/scaffold.yml", # the same state file run_copy wrote
    vcs_ref=ref,                       # optional: overrides the migration target ref (--ref)
    overwrite=True,                    # MANDATORY — without it copier raises UserMessageError
    defaults=True,                     # do not invoke the interactive survey for new template questions
)
```

- `run_update` takes no explicit `template` and `data`: it reads the template and answers recorded by `run_copy` in `answers_file` and re-applies a newer version of the template.
- Therefore the `answers_file` for `run_copy` and `run_update` must be the same — it is one shared state.
- `overwrite=True` is **mandatory**: copier's `Worker.run_update` without it raises `UserMessageError("Enable overwrite to update a subproject.")` — the user reviews the migration diff via git in the destination project.
- `vcs_ref`, when given, overrides the migration target ref (by default the migration goes to the latest commit of the template branch recorded in the state file).
- `defaults=True` — the migration is non-interactive; a new required question of a newer template version without a default fails the migration with a nonzero exit and the cause echoed to stderr.
- copier verifies preconditions and raises `UserMessageError` (→ nonzero) on violation: the target directory must be a git repository, clean (no uncommitted changes), and the template must be git-trackable (a git URL, not a local path) with a non-decreasing version.

## answers_file — programmatic override (the key goga convention)

`answers_file=".goga/scaffold.yml"` is passed **programmatically** to both operations. copier gives the programmatic argument priority over any `answers_file` declared in the template's `copier.yml`. Thus goga dictates the state file location regardless of what the template author wrote.

```python
# goga always passes answers_file programmatically — a hard convention enforced by the engine
answers_file = ".goga/scaffold.yml"
```

- `.goga/scaffold.yml` is the goga state file: which template and which answers were applied. `--upgrade` reads it.
- The state file must **not** end up in the user project's `.gitignore` — `goga init --upgrade` depends on it.

## The state file .goga/scaffold.yml

copier renders `answers_file` from the template: YAML with the template source (URL + `_commit`) and the dictionary of applied answers. **The key template convention**: the state file is created only if the template itself contains an answers-file entry — `{{ _copier_conf.answers_file }}.jinja` rendering `_copier_answers` (for non-jinja files see the copier documentation). Without such an entry `.goga/scaffold.yml` never appears, and `goga init --upgrade` fails with "missing scaffold state file". goga does not manage the contents directly — copier writes and reads it itself; goga only fixes the path via the programmatic `answers_file`.

## Composition with the caller

The caller decides what happens after `run_copy` returns: primary generation does not invoke any other tooling.

## Anti-patterns

- Do not delegate the `answers_file` location to the template via `copier.yml` — goga passes it programmatically as a hard convention; otherwise the state file location would depend on the template author's discipline.
- Do not pass `defaults=True` to `run_copy` — a required template question without a default, not covered by `data`, fails the generation with `ValueError` instead of being asked interactively.
- Do not ship a template without an answers-file entry (`{{ _copier_conf.answers_file }}.jinja`) — the state file will not be created and `--upgrade` will not work.
- Do not pass different `answers_file` values to `run_copy` and `run_update` — it is one shared state; `--upgrade` reads what the primary `run_copy` wrote.
- Do not git-ignore `.goga/scaffold.yml` in user projects — `goga init --upgrade` will stop working.
- Do not invoke `run_copy` non-interactively (pipe/CI) for a template with uncovered questions — the questionary survey requires a TTY and will fail with `InteractiveSessionError`.
- Do not implement your own Jinja2 + `git clone` on top of copier — the engine already handles recursive clone, ref resolution, `.git/` cleanup, binary files, symlinks, and conditional file inclusion correctly.
