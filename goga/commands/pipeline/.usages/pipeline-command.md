# pipeline — host-side goga pipeline command

`goga pipeline` is a single Click command with five explicit forms. Every
form launches the goga Docker container and invokes python -m goga.pipeline
inside it. The host never reads pipeline files directly — the runtime
boundary to the in-container pipeline is docker.

## Forms

| Invocation | Behavior |
|---|---|
| `goga pipeline` (no name, no `--list`) | error: `Missing pipeline name. Use "goga pipeline --list" to list available pipelines, or provide a pipeline name.` — stderr, exit 1, no docker activity |
| `goga pipeline --list` / `-l` | flat list of pipeline names (project source entries suffixed with ` (project)`) |
| `goga pipeline --list --info` / `-l -i` | overview: every pipeline as a `* <name>` bullet block with indented `name:`/`description:` field lines |
| `goga pipeline NAME --info` / `-i` | card of one pipeline: `name:`/`description:` fields, a `---` separator, then `* <id>:` stage bullets with indented `title:` lines in execution order; nothing runs |
| `goga pipeline NAME` | run |

`--list` and a name together is an error (mutually exclusive, clean message,
exit 1). `--info` is a modifier, not a mode: without a name and without
`--list` it still yields the missing-name error.

## Options (selection)

| Option | Type | Effect |
|---|---|---|
| -l / --list | flag | select the listing forms |
| -i / --info | flag | show instead of act (overview with --list, card with NAME) |
| -t / --topic ID | str | bring the repository onto the requested work (branch name, topic slug, or prefix) before the run, creating it when nothing hosts it; run form only |
| --todo | flag | open the external editor with the topic's todo.md after the switch or the fast creation (run form only; a clean error without --topic and on a non-terminal before any git or docker activity; no short form — -t stays with --topic) |
| -w / --workflow NAME | str | apply an explicit workflow (run and card); the file must exist (early host validation) |
| --no-workflow | flag | disable workflow resolution (run and card) |
| -p / --parallel N | int | max concurrently executing stages; run only |
| -s / --skip NAME | repeatable | exclude a stage; run only |
| -c / --clean | flag | wipe persistent afm state before launch; run only |
| -u / --update | flag | refresh the image before the flat list and the run; no-op in the info forms |

## Continuing or starting work

    goga pipeline development --topic history-com
    goga pipeline development -t release-1-3-0
    goga pipeline refinement -t prune-history-and-new-status
    goga pipeline development --topic history-com --todo
    goga pipeline refinement -t prune-history-and-new-status --todo

Brings the repository onto the requested work — an exact branch name, an
exact topic slug, or their prefix — and then launches the usual run. When
nothing hosts the identifier, fresh work is created instead: the branch
named as entered and the topic directory of the year
(`Created branch <name> and topic <year>/<slug>`). The switch or creation
completes on the host before any docker activity; a repeated invocation
already on the host continues without switching. The flat list, overview,
and card forms silently ignore -t. Several candidates without a terminal, a
dirty working tree on a switch, or an unusable (empty-slug) or occupied
name without a terminal is a clean error before any launch.

With --todo the editor opens with the topic's todo.md after the
repository is on the work: the existing content when the topic has a
todo, an empty entry otherwise; a branch without a topic gets its
topic directory created first — the fast process is never interrupted.
Saving overwrites todo.md without a commit; an empty or unchanged file
leaves it untouched. Without a terminal --todo is a clean error before
any git or docker activity, and so is --todo without --topic — the entry
needs requested work; --list and --info forms ignore the flag
silently.

## Flag behavior in the list/info forms

- Ignored (no-op, no side effects): `-e/--env`, `--proxy`, `-c/--clean`,
  `-s/--skip`, `-p/--parallel`, `--add-host`, `-t/--topic`, `--todo`.
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
-p <port>:<port> is an internal translated docker token assembled by the
run launcher from the allocated port (run form
only). Different namespaces (Click CLI vs docker run argv) — no collision.
The user never authors the docker -p.

## Threading chains

    goga pipeline NAME            → run (full shape)
    goga pipeline NAME -t feat/x  → switch-or-create → run (full shape)
    goga pipeline --list          → minimal shape: list
    goga pipeline --list --info   → minimal shape: list --info
    goga pipeline NAME --info     → minimal shape: run NAME --info [-w WF | --no-workflow]

    goga pipeline NAME -p N
      → docker run … -m goga.pipeline run NAME --port PORT --parallel N
        → the in-container run launches afm bounded to N concurrent stages

Absent ⇒ parallel=None ⇒ no in-container --parallel ⇒ afm unbounded.
