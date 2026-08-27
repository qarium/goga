# pipeline — host-side goga pipeline command

`goga pipeline` is a single Click command with five explicit forms. Every
form launches the goga Docker container and invokes python -m goga.pipeline
inside it. The host never reads pipeline files directly — the runtime
boundary to goga/pipeline is docker.

## Forms

| Invocation | Behavior |
|---|---|
| `goga pipeline` (no name, no `--list`) | error: `Missing pipeline name. Use "goga pipeline --list" to list available pipelines, or provide a pipeline name.` — stderr, exit 1, no docker activity |
| `goga pipeline --list` / `-l` | flat list of pipeline names (project source entries suffixed with ` (project)`) |
| `goga pipeline --list --info` / `-l -i` | overview: every pipeline as a `* <name>` bullet block with indented `name:`/`description:` field lines |
| `goga pipeline NAME --info` / `-i` | card of one pipeline: `name:`/`description:` fields, a `---` separator, then `* <id>:` stage bullets with indented `title:` lines in execution order; nothing runs |
| `goga pipeline NAME` | run |
| `goga pipeline -b BRANCH NAME` | prepare the branch, then run on it |

`--list` and a name together is an error (mutually exclusive, clean message,
exit 1). `--info` is a modifier, not a mode: without a name and without
`--list` it still yields the missing-name error.

## Options (selection)

| Option | Type | Effect |
|---|---|---|
| -l / --list | flag | select the listing forms |
| -i / --info | flag | show instead of act (overview with --list, card with NAME) |
| -b / --branch NAME | str | prepare a fresh branch + history topic before the run; run form only |
| -w / --workflow NAME | str | apply an explicit workflow (run and card); the file must exist (early host validation) |
| --no-workflow | flag | disable workflow resolution (run and card) |
| -p / --parallel N | int | max concurrently executing stages; run only |
| -s / --skip NAME | repeatable | exclude a stage; run only |
| -c / --clean | flag | wipe persistent afm state before launch; run only |
| -u / --update | flag | refresh the image before the flat list and the run; no-op in the info forms |

## Branch preparation (-b/--branch)

Run form only. `-l`, `-l -i`, and `NAME -i` silently skip the whole
procedure — passing `-b` there is not an error and does nothing.

Order: the branch procedure runs after the argument-form validation and
before any docker activity (no image refresh, no first-run build, no
launch). An argument-form error (for example a missing pipeline name) wins:
no branch is created.

The entered name plays two roles:

- **branch name** — used exactly as entered when creating and switching
  (`git switch -c <name>`; git rejects invalid names itself);
- **history topic slug** — the normalized form that names the topic folder
  `.goga/history/<YYYY>/<slug>/`: lowercase, non-ASCII dropped, anything
  outside `[a-z0-9]` becomes `-`, repeat hyphens collapse, edge hyphens
  trim (`Feature/Foo_Bar` → `feature-foo-bar`, `release/1.3.0` →
  `release-1-3-0`).

Occupancy = a local branch with the entered name, OR a remote-tracking
branch with the entered name, OR an existing `.goga/history/<YYYY>/<slug>/`
folder for the current year.

- Interactive terminal: the reason is printed and a new name is prompted
  until the name is free (Ctrl-C aborts, nothing is created); a fully
  non-ASCII name (empty slug) is treated as invalid input and re-asked the
  same way.
- No terminal (CI/scripts): the reason plus the hint to pass another name
  via `-b` goes to stderr, exit code is non-zero, the pipeline does not
  start.
- Already on the target branch (slug of the entered name equals the slug of
  the current branch): nothing happens, the pipeline just runs.

When the procedure completes (a created-and-switched branch or the
already-on-branch case), goga prints `Pipeline running on branch <name>`
to stdout once, before the launch; the list/info forms print no branch
line.

After a successful `-b` run you stay on the new branch — goga does not
switch back.

## Flag behavior in the list/info forms

- Ignored (no-op, no side effects): `-e/--env`, `--proxy`, `-c/--clean`,
  `-s/--skip`, `-p/--parallel`, `--add-host`, `-b/--branch`.
- `-u/--update`: works in `--list` without `--info`; no-op in both `--info`
  forms.
- `-w/--workflow` and `--no-workflow`: validated as usual (exclusivity and,
  for -w, file existence) and honored by the card form.
- All errors go to stderr with a non-zero exit code; stdout stays clean for
  the listing, overview, and card output.

## Docker shapes

- Run form: full shape — allocated port, env-file, afm-config tmpfile,
  persistent afm state mount, credential mounts, caller-side signal
  handler.
- List/info forms: minimal read-only shape — none of the above. The
  decision travels in the subcommand argv: `-m goga.pipeline list [--info]`
  or `-m goga.pipeline run NAME --info [-w WORKFLOW | --no-workflow]`.

## -p vs docker -p

The user-facing -p/--parallel is a Click option. The Docker port-publish
-p <port>:<port> is an internal translated docker token assembled by
run_pipeline_container/DockerRunner from the allocated port (run form
only). Different namespaces (Click CLI vs docker run argv) — no collision.
The user never authors the docker -p.

## Threading chains

    goga pipeline NAME            → run (full shape)
    goga pipeline -b feat/x NAME  → ensure branch feat/x → run (full shape)
    goga pipeline --list          → minimal shape: list
    goga pipeline --list --info   → minimal shape: list --info
    goga pipeline NAME --info     → minimal shape: run NAME --info [-w WF | --no-workflow]

    goga pipeline NAME -p N
      → docker run … -m goga.pipeline run NAME --port PORT --parallel N
        → pipeline_cli → run_pipeline(parallel=N) → run_flow(max_parallel=N)
          → afm run --port PORT --max-parallel N <flow>

Absent ⇒ parallel=None ⇒ no in-container --parallel ⇒ afm unbounded.
