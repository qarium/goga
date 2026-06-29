# goga flow

List and run goga flows (delegating execution to the external `flowmanager` binary).

## Synopsis

```bash
goga flow ls
goga flow run <name>
```

## Description

The `flow` command group is a thin Click wrapper over the `goga.afm` cell. `ls` discovers flow files across two source directories; `run` resolves a named flow to its absolute path and invokes `flowmanager run <absolute-path>`.

Flows are flat `*.yml` files (one per flow) resolved from two directories, with the project source winning on name conflicts:

| Source   | Directory             | Origin                                                     |
|----------|-----------------------|------------------------------------------------------------|
| project  | `<cwd>/.goga/flows/`  | Checked into / authored for the current project            |
| user     | `~/.goga/flows/`      | Installed centrally by `goga connect` (see [connect](connect.md)) |

Only top-level `*.yml` is scanned — subdirectories are ignored, and `.yaml` files are excluded.

## Prerequisites

`goga flow run` shells out to the external **`flowmanager`** binary (a separate Go CLI, not part of goga). It must be installed and on your `PATH`:

```bash
which flowmanager
```

`goga flow ls` does **not** require `flowmanager` — it only reads the local filesystem.

## Subcommands

### `goga flow ls`

List available flow names. Project flows are annotated with `(project)`; user flows are printed bare.

```bash
goga flow ls
```

Example output:

```
deploy (project)
build
test
```

Read-only — no filesystem writes and no `flowmanager` invocation.

### `goga flow run <name>`

Run a flow by name via `flowmanager`. Pass the bare name only (no `.yml` extension); the command resolves the absolute path internally and forwards it to `flowmanager run`.

```bash
goga flow run deploy
```

If the name exists in both sources, the project source wins. The `flowmanager` exit code is propagated as `goga flow run`'s exit code.

## Exit Codes (`run`)

| Code | Meaning                                                                 |
|------|-------------------------------------------------------------------------|
| `0`  | `flowmanager` ran the flow successfully                                 |
| `1`  | The named flow was not found in either source directory                 |
| `126`| `flowmanager` is present but could not be invoked (e.g. not executable) |
| `127`| The `flowmanager` binary is missing from `PATH`                         |
| other| The `flowmanager` exit code, propagated unchanged                       |

## Notes

- Do not pass a file path or a name ending in `.yml` — pass the bare flow name.
- `goga flow run` passes the flow's absolute path to `flowmanager` directly; there is no need to copy flows into `flowmanager`'s own directories.
