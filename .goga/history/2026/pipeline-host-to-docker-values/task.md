# Unify host→container context transfer on cmd-proxying; make credential mounts user-owned

## Current State

The host launchers carry run context into the goga Docker container through two
different channels:

- `goga/commands/build` proxies its options through the post-image command line
  (the reference model).
- `goga/commands/pipeline` (`run_pipeline_container`) smuggles three run options
  through container environment variables — `GOGA_WORKFLOW_NAME`,
  `GOGA_WORKFLOW_DISABLED`, `GOGA_SKIP_STAGES` — written into the env-file.

In-container readers: `run_pipeline` (`goga/pipeline`) reads those env vars to
decide workflow resolution and skip. The in-container CLI `pipeline_cli` exposes
`-w/--workflow` and `--no-workflow` only in the card form (`run NAME --info` →
`describe_pipeline`); the run form picks its decision up from the env vars, so
skip is run-only — an artifact of the env channel, not a semantic choice.

Credential mounting: both launchers (`build` in `goga/commands/build`, the run
form in `goga/commands/pipeline`) call `resolve_credential_mounts` (owned by the
`goga/agents/credentials` cell, re-exported through the `goga/agents` facade)
to detect and bind-mount AI-agent credential files read-only automatically.

The full decision record, including rejected alternatives, lives in the ADR of
this topic (`.goga/history/2026/pipeline-host-to-docker-values/adr.md`).

## Description

Move the pipeline run form onto the build model of cmd-proxying and remove the
automatic credential mounts, per the ADR:

1. **Channel boundary rule (fixed principle).** Everything the goga in-container
   CLI consumes (run options) travels as command arguments after the image;
   everything the afm binary, agents, and tools consume travels through the
   env-file. Build already follows this rule and does not change its channel.
2. **Pipeline run-mode flag surface.** The host launcher forwards the run
   options through the in-container argv as flags joining `--port` and
   `--parallel`: `-w/--workflow NAME`, `--no-workflow`, and a repeatable
   `-s/--skip NAME`. The host Click surface itself is unchanged — only the
   delivery channel changes.
3. **The three env vars are removed entirely.** `GOGA_WORKFLOW_NAME`,
   `GOGA_WORKFLOW_DISABLED`, and `GOGA_SKIP_STAGES` stop being written and stop
   being read — cmd is the single channel; no fallback remains. Stale `GOGA_*`
   entries passed by a user via `-e` or home.env are inert: no warning, no
   error.
4. **The env-file keeps only environment layers:** home.env (base), project
   env, git identity, CLI `-e`, the proxy trio, and the launcher-owned afm
   constants `AFM_DIR` and `AFM_DOCKER_FILE_ROOTS` (afm's own env contract).
5. **In-container contract.** `pipeline_cli` parses the new flags; run
   coordination (`run_pipeline`) receives the workflow decision and skip names
   as explicit parameters instead of reading the environment.
6. **Card accepts skip.** The card form (`describe_pipeline`) reflects skip in
   its composition — the "card equals a run with the same flags" principle is
   carried through. The skip names join `-w`/`--no-workflow` in the host card
   launcher too: `run_pipeline_info_container` appends the repeatable
   `-s NAME` to the card argv, so `-s` stops being run-form-only on the host;
   the Click option itself (name, short alias, repeatability) is unchanged.
7. **Validation split unchanged.** The host validates `-w` file existence and
   the `-w`/`--no-workflow` exclusivity; the in-container CLI stays
   forwarding-only; unknown `--skip` names surface as the compiler's structural
   error.
8. **Workflow log line stays host-side.** The host keeps its auto-match
   existence check solely to decide whether to print the "running with workflow
   NAME" line; the flags themselves are forwarded unconditionally.
9. **Credential mounts are removed completely:** the `resolve_credential_mounts`
   calls in both launchers, the `goga/agents/credentials` cell, its re-export
   from the `goga/agents` facade (which keeps only `resolve_wrapper_path`), and
   the `resolve-credential-mounts` practice.
10. **User-owned replacement channel:** `home.docker.run` (~/.goga/config.yml
    raw docker tokens) with `-e KEY=VALUE` as the alternative; the
    `docker-auth-mounts` cook is rewritten as a short user guide for mounting
    one's own credentials (path table preserved), per the approved rewrite
    plan.

## Scope

**In scope:**

- `goga/commands/pipeline`: run-form launcher argv assembly gains the
  workflow/skip flags; the card launcher (`run_pipeline_info_container`)
  forwards the skip names alongside the workflow flags; the three `GOGA_*`
  env-file entries are no longer written; the `resolve_credential_mounts`
  call is removed from the run form.
- `goga/pipeline`: `pipeline_cli` parses `-w`, `--no-workflow`, repeatable
  `-s`; `run_pipeline` takes the workflow decision and skip names as explicit
  parameters (env reading removed); `describe_pipeline` accepts skip.
- `goga/commands/build`: removal of the `resolve_credential_mounts` call only.
- `goga/agents`: facade re-export removed (keeps `resolve_wrapper_path`); the
  `goga/agents/credentials` cell is deleted.
- Documentation realignment: `goga/pipeline/.usages/run-pipeline.md`
  (env channel → explicit parameters), `goga/pipeline/.usages/pipeline-cli.md`
  (new flags), `goga/pipeline/.usages/describe-pipeline.md` (card skip);
  `.goga/usages/cooks/docker-auth-mounts.md` rewritten as a user guide
  (domain → self-served provisioning; `home.docker.run` as the primary channel
  referencing `home-configuration`; preserved host→container path table; `-e`
  alternative; macOS Keychain caveat; user-facing recommendations; automatic
  detection rule and launcher semantics removed); the
  `resolve-credential-mounts` practice file is deleted.
- CODEMANIFEST updates: `goga/commands/build`, `goga/commands/pipeline`,
  `goga/pipeline`, `goga/agents` (contracts and annotations re-aligned to the
  new channel; credential-mount references removed), and
  `goga/pipeline/compiler` (annotation-only: the `GOGA_SKIP_STAGES`-channel
  mention in the `compile_flow` memory-participation rule becomes the
  flag-driven skip wording; contract and behavior unchanged).

**Out of scope:**

- The version-check probe, `DockerRunner`, and the build pass pipeline.
- `AFM_DIR` / `AFM_DOCKER_FILE_ROOTS` — they stay in the env-file (afm's own
  env contract, not goga CLI options).
- The `home.docker.run` raw-token mechanics and the `home-configuration`
  usage (already document the replacement channel).
- Any warning/error for stale `GOGA_*` env values — silence is the contract.
- The host Click flag surface (`-w`, `--no-workflow`, `-s`, `-p`) — the
  options themselves (names, aliases, repeatability) are unchanged; the only
  behavioral shift is `-s` joining the card-form forwarding (Description
  item 6).

## Acceptance Criteria

- A pipeline run launched from the host produces an in-container argv that
  carries the workflow decision and skip names as flags; the launcher writes
  no `GOGA_*` entries into the env-file (user-supplied `-e` / home.env
  entries still pass through verbatim and are inert).
- Setting `GOGA_WORKFLOW_NAME` / `GOGA_WORKFLOW_DISABLED` / `GOGA_SKIP_STAGES`
  via `-e` or home.env has no effect on a run (inert names).
- The card (`run NAME --info`) reflects `-s/--skip` in its composition: the
  in-container card subcommand accepts the repeatable flag, and the host card
  form (`goga pipeline NAME --info`) forwards the skip names into the card
  argv — the same flags produce the same composition in card and run forms.
- The host rejects a missing `-w` workflow file and the combined
  `-w` + `--no-workflow` usage, as before; unknown skip names fail in-container
  as the compiler's structural error.
- The host prints the "running with workflow NAME" line exactly when the
  auto-match workflow file exists.
- No credential bind-mounts are added by any launcher; the
  `goga/agents/credentials` cell, its facade re-export, and the
  `resolve-credential-mounts` practice no longer exist; `resolve_wrapper_path`
  remains available from `goga/agents`.
- `goga lint` passes over the updated manifests; the realigned usages describe
  the flag channel (no `GOGA_*` mentions remain in them).
- `docker-auth-mounts` reads as a user guide: self-served mounting via
  `home.docker.run` with the host→container path table, `-e` alternative, and
  the macOS caveat — with no automatic-mount rule.

## Stack

- **Frameworks:** none beyond the existing ones — Click (host CLI), argparse
  (in-container CLI).
- **Libraries:** existing goga package modules only; no new libraries.
- **Infrastructure:** Docker (`docker run` post-image argv + env-file
  mechanism), unchanged.

## External Dependencies

| Component | Usage file | Status |
|-----------|------------|--------|
| Docker credential self-mounting (user guide) | `.goga/usages/cooks/docker-auth-mounts.md` | updated (rewritten as user guide during implementation, per approved plan) |

No new external dependencies are introduced; every tool in use is already
covered by existing usages.

## Risks and Constraints

- **Breaking change:** anything setting `GOGA_WORKFLOW_NAME`,
  `GOGA_WORKFLOW_DISABLED`, or `GOGA_SKIP_STAGES` (scripts, home.env, `-e`)
  silently loses effect — accepted by the ADR; release notes should call it
  out.
- Two workstreams meet in `run_pipeline_container` (argv assembly + credential
  removal) — the change must land as one coherent shift, not two passes.
- In-container run coordination keeps exactly one env read (`AFM_DIR`); the afm
  pass-through environment must remain untouched.
- Credential files mounted by users through `home.docker.run` never become afm
  file-manager roots (`collect_file_roots` skips files — only directories
  root); the existing "credentials never become roots" wording only loses its
  engine-mount member.
- The card and run must keep sharing one workflow/skip rule set — the same
  flags compose the same result in both forms.

## Scope Estimate

Single task. The two directions (channel unification and credential-mount
removal) follow one organizing principle — the ADR boundary rule — and
intersect in the same launcher routine (`run_pipeline_container`), so
decomposition would double-edit one contract for no independent value. Confirmed
with the user during formulation.

## Existing Architecture

Affected cells and their roles:

- `goga/commands/pipeline` — host-side CLI wrapper; every form launches the
  goga Docker container; the run form assembles the env-file and the
  in-container argv. Imports `goga/agents` (credential mounts + wrapper path —
  the credential member is removed), `goga/config` (home/project configuration,
  config hooks), `goga/docker` (runner, image acquisition), `goga/pipeline`
  (usages only — the runtime boundary is docker, no Python type imports),
  `goga/runtime`, `goga/topics`.
- `goga/pipeline` — in-container domain package: discovery, card composition,
  run coordination, the CLI entrypoint. Imports `goga/afm` (`run_flow`),
  `goga/docker` (`ensure_in_docker`), `goga/history`, `goga/config`,
  `goga/pipeline/compiler`, `goga/pipeline/hooks`, `goga/pipeline/workflow`.
- `goga/commands/build` — host-side build launcher (the cmd-proxying model to
  copy); only its credential-mount usage changes. Imports `goga/agents`
  (credential mounts — removed), `goga/build`, `goga/config`, `goga/docker`,
  `goga/runtime`.
- `goga/agents` — facade over `goga/agents/wrapper` (`resolve_wrapper_path`,
  kept) and `goga/agents/credentials` (`resolve_credential_mounts`, removed).
- `goga/pipeline/compiler` — annotation-touch only: the `compile_flow`
  annotation mentions the removed `GOGA_SKIP_STAGES` channel; behavior is
  unchanged (skip directives keep arriving through `WorkflowDocument`).
- `goga/docker`, `goga/build` — untouched (version-check probe, `DockerRunner`,
  build pass pipeline).

## Notes

- Task formulated from the topic ADR (discovery interview, 25/09/26); every
  decision above traces to a numbered ADR decision.
- Exact routine signatures and contract wording are deliberately left to the
  contract-design stages (brainstorm/design), per the ADR's "Unresolved"
  section; this document fixes scope and boundaries only.
- The `docker-auth-mounts` rewrite plan was approved during formulation: user
  guide with domain → self-served provisioning, `home.docker.run` primary
  channel (referencing `home-configuration`, no duplicated mechanics),
  preserved path table, `-e` alternative, macOS Keychain caveat, user-facing
  recommendations; the automatic-detection rule and launcher semantics are
  removed.
