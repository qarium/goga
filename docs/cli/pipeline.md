# goga pipeline

Run a goga pipeline by name, or list available pipelines when no name is given (delegating execution to the external `flowmanager` binary).

## Synopsis

```bash
goga pipeline           # discovery mode: list available pipelines
goga pipeline <name>    # run mode: run a pipeline by name
```

## Description

The `pipeline` command is a single Click command (not a group) that collapses the former two-subcommand `goga flow ls` / `goga flow run <name>` surface into one. Its behavior depends on whether a name is given:

- **Without `name` (discovery mode):** prints the `Available pipelines:` header followed by one pipeline per line. Project pipelines are annotated with `(project)`; user pipelines are printed bare. Read-only — does not invoke `flowmanager`.
- **With `name` (run mode):** resolves the named pipeline to its absolute path and invokes `flowmanager run <absolute-path>`. The resulting exit code is propagated via `ctx.exit`.

Pipelines are flat `*.yml` files (one per pipeline) resolved from two directories, with the project source winning on name conflicts:

| Source   | Directory                | Origin                                                     |
|---------|--------------------------|------------------------------------------------------------|
| project | `<cwd>/.goga/pipelines/` | Checked into / authored for the current project            |
| user    | `~/.goga/pipelines/`     | Installed centrally by `goga connect` (see [connect](connect.md)) |

Only top-level `*.yml` is scanned — subdirectories are ignored, and `.yaml` files are excluded.

## Prerequisites

`goga pipeline <name>` shells out to the external **`flowmanager`** binary (a separate Go CLI, not part of goga). It must be installed and on your `PATH`:

```bash
which flowmanager
```

`goga pipeline` (discovery mode) does **not** require `flowmanager` — it only reads the local filesystem.

## Discovery Mode (`goga pipeline`)

List available pipeline names. The `Available pipelines:` header is always printed, even when the list is empty.

```bash
goga pipeline
```

Example output:

```
Available pipelines:
  deploy (project)
  build
  test
```

Project pipelines are annotated with `(project)`; user pipelines are printed bare.

## Run Mode (`goga pipeline <name>`)

Run a pipeline by name via `flowmanager`. Pass the bare name only (no `.yml` extension); the command resolves the absolute path internally and forwards it to `flowmanager run`.

```bash
goga pipeline deploy
```

If the name exists in both sources, the project source wins. The `flowmanager` exit code is propagated as the command's exit code.

## Exit Codes (run mode)

| Code | Meaning                                                                 |
|------|-------------------------------------------------------------------------|
| `0`  | `flowmanager` ran the pipeline successfully                             |
| `1`  | The named pipeline was not found in either source directory             |
| `126`| `flowmanager` is present but could not be invoked (e.g. not executable) |
| `127`| The `flowmanager` binary is missing from `PATH`                         |
| other| The `flowmanager` exit code, propagated unchanged                       |

## Exit Codes (discovery mode)

| Code | Meaning                                   |
|------|-------------------------------------------|
| `0`  | Always (even when the pipeline list is empty) |

## Notes

- Do not expect `ls` or `run` subcommands — `goga pipeline` is a single command.
- Do not expect auto-`--help` when no name is given — discovery mode prints the `Available pipelines:` header + list instead.
- Do not pass a file path or a name ending in `.yml` in run mode — pass the bare pipeline name only.
- `goga pipeline <name>` passes the pipeline's absolute path to `flowmanager` directly; there is no need to copy pipelines into `flowmanager`'s own directories.
