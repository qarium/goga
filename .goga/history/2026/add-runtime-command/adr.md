# `goga runtime`: pure path queries plus a single-target `.tar.gz` archiver over the one runtime identity

Users reverse-engineer the internal runtime path formula and hand-roll archives to report, back up, or move run state. We add a `goga runtime` command group — `build`, `pipeline <name>`, `archive` — that exposes the existing location identity (no second path scheme) as pure one-line stdout queries, and packages exactly one target per invocation into a `.tar.gz`. The decisions below settle everything the PRD left open; requirement-level content (naming, collision, error contracts) lives in the PRD and is not repeated.

## Decisions

- **Archive target selection — mutually exclusive flags `-b/--build` and `-p/--pipeline <name>`.** No positional target token: `archive` carries no positional argument, the choice is self-documented in `--help`, and "none or both" is one check.
- **Archive layout — one wrapper root directory `goga-runtime-<target>-<branch>/`** holding the target's full recursive contents. A bare `tar xzf` into any directory cannot scatter files, and the root name matches the archive filename — the archive stays self-contained for a recipient without goga.
- **Packaging — Python stdlib `tarfile` + gzip, in-process.** No archive code exists in the project; stdlib adds no dependency and no PATH/binary/platform variance. Special files (symlinks etc.) are preserved as encountered — no dereference, no filters ("full recursive contents" taken literally).
- **In-image refusal.** Inside the goga image the state does not live by the runtime formula (build uses `<cwd>/.ralphex`, pipeline `/home/goga/pipeline`), so every `runtime` subcommand fails with a clean "host-side only" error there. The printed-path truthfulness contract (SC1/SC2) outweighs formula purity; a silent lie is worse than an explicit error. The detection mechanism is a design-stage concern, not fixed here.
- **Strict destination semantics.** A mid-packaging failure removes the partial archive file (nothing is kept); `-o` naming an existing directory is a clean error; a missing `-o` parent is a clean error (no implicit `mkdir`). Predictability over convenience.
- **An existing but empty target directory is packaged successfully** — the simple rule "directory exists → we package it". Only a missing directory is an error (R13).
- **Group option `-b/--branch <name>`** (before the subcommand, like `-y/--year` on `goga history`): the effective branch is the explicit value — slugified by the same `/`→`-` rule, so it addresses the directory the run on that branch actually created — or the git-derived one; the `default` fallback applies only when the option is absent and derivation fails. No git validation: the formula stays pure and git-free (state of a deleted branch is a legitimate archive target); typos are caught by `archive`'s missing-target error. An empty value means "not given", as with the history year.
- **The `-b` short alias deliberately has two meanings.** Group-level `-b` is `--branch`, `archive`'s `-b` is `--build` — click binds group options only before the subcommand name and subcommand options only after, so the parse positions are disjoint and can never collide. The residual cost is human-only ambiguity, accepted by the user for the shorter flag.
- **Path subcommands stay pure queries — no modifiers.** No `-a/--archive` shortcut (it saves nothing over `archive -b`/`-p` and would break the "path commands write nothing" guarantee), no tree/listing output (standard tools cover it: `tree "$(goga runtime build)"`). One command, one purpose; a listing capability would be a separate future PRD.
- **CLI conventions.** Bare `goga runtime` prints help and exits 0 (click group default, as `goga history`) — corrected at design review: on click 8.5.1 the group default exits 2, like a bare `goga history`; the manifest pins the non-zero default. A `<name>` starting with `-` is a clean error (the argv-parsability precedent of build/pipeline); `archive`'s success line is the absolute path of the created archive (consistent with `goga history path`).

## Terms

- **runtime directory** — `~/.goga/runtime/<purpose>/<normalized_project>/<branch>/<*suffix_parts>`, host-side persistent state of a container-launched tool.
- **location identity** — the (normalized project path, branch segment, sanitized pipeline suffix) triple addressing a runtime directory.
- **effective branch** — the branch segment actually used: the slugified `--branch` value, else the git-derived branch, else `default`.
- **artifacts** — the full recursive contents of a runtime directory, unfiltered.
- **target** — the single archive subject per invocation: `build` or one named pipeline.
- **sanitized pipeline name** — pipeline name with every `:` replaced by `-` (exactly the run-time host path segment rule).
- **archive stem** — `goga-runtime-<target>-<branch>`, the base of both the default archive filename and the wrapper root inside it.

## Consequences

- Archives are not byte-deterministic (file metadata is preserved as encountered); nothing requires reproducible bytes — determinism of the *name* and *layout* is what the contract fixes.
- Snapshot consistency while a run is actively writing state remains a documented limitation (PRD), not an enforced precondition.
- Code placement (cells, contracts, wiring) is deliberately undecided here — it belongs to the design/prototype stages; this record fixes behavior and constraints only.
