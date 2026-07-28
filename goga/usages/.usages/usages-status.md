# Usages status — goga/usages

## Domain

Programmatic, config-driven status check of already-synchronized cell-level usages against
the current state of the remote git repository declared for each dep. Target audience: the
`goga usages status` command and any caller checking usages drift programmatically.

## Facade

```python
from goga.usages import status

report = status(group=None, dep=None)
```

`status` returns a `UsageStatusReport`. It loads `.goga/config.yml` itself, iterates the
declared deps, and never prints — rendering is the caller's responsibility.

## Configuration contract

`status` reads the same `usages` section of `.goga/config.yml` as synchronization:

```yaml
usages:
  libs:
    click:
      git: https://github.com/pallets/click.git
      ref: main
      root: docs           # optional — subpath inside the repo to walk from
```

Each `<group>/<dep>` declares a required `git` URL, an optional `ref`, and an optional
`root`. When the `usages` section is absent or empty → the report is empty and the exit
code is `0`.

## Status determination

For each declared dep (after applying the group/dep filters):

- target directory `.goga/usages/<group>/<dep>/` absent → **new** (declared, never synchronized)
- present → the remote is cloned at `git`/`ref`, the expected tree is rebuilt with the same
  `root`, and the local tree is compared by content hashes:
  - trees match → **up to date**
  - trees differ → **out of date**
- a clone/checkout/deploy failure → **error** for that dep (best-effort: other deps are still checked)

Without a stored manifest, "out of date" only reports that the local tree differs from the
remote-rebuilt tree; it cannot distinguish "upstream moved ahead" from "locally edited".

## Result shape

`UsageStatusReport` exposes:

- `deps` — per-dep records (`DepStatus`), in declaration order
- `exit_code` — `0` iff every dep is `up to date`; `1` otherwise (covers `new`, `out of date`,
  `error`). An empty report yields `0`.

Each `DepStatus` exposes `group`, `dep`, `state` (`UsageState`), `folders`
(`list[FolderStatus]`), and `error` (a credential-free message, set only for `error`).
`folders` is empty for `new`/`error` and populated for `up to date`/`out of date`.

Each `FolderStatus` exposes `path` (relative path within the dep) and `state`
(`up to date` / `out of date`).

## Exit codes

- `0` — every checked dep is `up to date` (including the empty-report case).
- `1` — at least one dep is `new`, `out of date`, or `error`.

## Filters

`group` limits the check to one group; `dep` limits it to one dep name across all groups
when `group` is not set. A non-matching value yields an empty result, never an error.

## Constraints for consumers

- Call `status` only from a directory containing `.goga/config.yml`.
- The check clones each dep (network cost per dep); use the filters to check narrowly.
- The check is read-only: `.goga/usages/`, `cooks/`, and root `*.md` are never modified.
- Sources are git only (no local-path mode).
