# Host→container context transfer unified on cmd-proxying; credential mounts become user-owned

The host launchers used two different channels to carry run context into the goga Docker
container: build proxied its options through the post-image command line, while pipeline
smuggled three run options through container environment variables. We are unifying on
cmd-proxying — the build model — because it keeps the host CLI surface and the in-container
domain-package interface symmetric, and we are removing the automatic agent-credential
bind-mounts: credential provisioning becomes the user's responsibility. Decisions were
settled in a discovery interview on 25/09/26.

## Decisions

1. **Channel boundary rule (the fixed principle).** Everything the goga in-container CLI
   consumes (run options) travels as command arguments after the image; everything the afm
   binary, agents, and tools consume (environment) travels through the env-file. Build
   already follows this rule and does not change; pipeline moves onto it.
2. **Pipeline run-mode flag surface.** The run subcommand gains the flags the card form
   already has, plus skip: `-w/--workflow NAME`, `--no-workflow`, and a repeatable
   `-s/--skip NAME` join `--port` and `--parallel` in the in-container argv
   (`-m goga.pipeline run <name> --port <p> [-w <wf>] [--no-workflow] [-s <name>]...
   [--parallel <n>]`).
3. **The three env vars are removed entirely.** `GOGA_WORKFLOW_NAME`,
   `GOGA_WORKFLOW_DISABLED`, and `GOGA_SKIP_STAGES` stop being written and stop being
   read — cmd is the single channel; no fallback remains.
4. **The env-file keeps only environment layers:** home.env (base), project env, git
   identity, CLI `-e`, the proxy trio, and the launcher-owned afm constants `AFM_DIR` and
   `AFM_DOCKER_FILE_ROOTS` (afm's own env contract, not goga CLI options).
5. **Stale `GOGA_*` entries are inert.** A user passing them via `-e` or home.env gets no
   warning and no error — the names are simply no longer consumed; the launcher does not
   scan foreign env layers for names it no longer reads.
6. **Workflow log line stays host-side.** The host keeps its auto-match existence check
   solely to decide whether to print "Pipeline running with workflow NAME"; the flags
   themselves are forwarded unconditionally.
7. **Validation split unchanged.** The host validates `-w` file existence and the
   `-w`/`--no-workflow` exclusivity; the in-container CLI stays forwarding-only; unknown
   `--skip` names surface as the compiler's structural error.
8. **Card accepts `-s/--skip`.** The card (`run NAME --info`) reflects skip in its
   composition — the "card equals a run with the same flags" principle is carried through;
   skip was run-only only as an artifact of the env channel.
9. **Credential mounts are removed completely:** the `resolve_credential_mounts` calls in
   both launchers (build and the pipeline run form; the info forms never mounted), the
   `goga/agents/credentials` cell, its re-export from the `goga/agents` facade (which
   keeps only `resolve_wrapper_path`), and the `resolve-credential-mounts` practice.
10. **The user-owned replacement channel is `home.docker.run`** (~/.goga/config.yml raw
    docker tokens, e.g. `-v ~/.claude/.credentials.json:/home/goga/.claude/.credentials.json:ro`),
    with `-e KEY=VALUE` as the alternative. The `docker-auth-mounts` cook is rewritten as a
    short user guide for mounting one's own credentials — not deleted, because the host
    paths and the `/home/goga/...` container layout are still what a user needs to know.

## Considered Options

- **Keeping the `GOGA_*` env vars as a fallback** (for manual `docker run` invocations):
  rejected — two sources of truth drift apart and disagree with the card.
- **A single csv `--skip a,b` form**: rejected — the repeatable flag mirrors the host click
  surface and build's proxying model.
- **Warning or erroring on stale `GOGA_*` env values**: rejected — scanning shared env
  layers (a machine-wide home.env) for names the launcher no longer consumes invites false
  positives; silence is the honest contract for a removed channel.
- **Moving `AFM_DIR` / `AFM_DOCKER_FILE_ROOTS` to cmd args**: rejected — they are afm's own
  env contract written by the launcher as container constants, not goga CLI options.
- **Moving the workflow log in-container (or dropping it for auto-match)**: rejected — the
  host-side existence check preserves the log's accuracy without touching in-container
  logic.
- **Deleting the `docker-auth-mounts` cook outright**: rejected — rewritten as a user guide
  instead; the path table is exactly the knowledge a self-serving user needs.

## Consequences

- **Breaking change:** anything setting `GOGA_WORKFLOW_NAME`, `GOGA_WORKFLOW_DISABLED`, or
  `GOGA_SKIP_STAGES` (scripts, home.env, `-e`) silently loses effect.
- In-container run coordination stops reading the three env vars; its remaining env read is
  `AFM_DIR` (the afm pass-through environment stays).
- The card and run now share the full flag surface (`-w`, `--no-workflow`, `-s`), so the
  card's composition finally covers every run-time lever.
- Documents to re-align: `goga/pipeline/.usages/{run-pipeline.md, pipeline-cli.md,
  describe-pipeline.md}` (env channel → flags; card skip), `.goga/usages/cooks/
  docker-auth-mounts.md` (user-guide rewrite), the CODEMANIFESTs of `goga/commands/build`,
  `goga/commands/pipeline`, `goga/pipeline`, and `goga/agents`.
- Credential files mounted by the user through `home.docker.run` never become afm
  file-manager roots (`collect_file_roots` skips files — only directories root); the
  existing "credentials never become roots" wording simply loses its engine-mount member.
- The version-check probe, `DockerRunner`, and the build pass pipeline are untouched.

## Unresolved (later stages)

- Exact signatures and contracts of the touched routines (run coordination, the in-container
  CLI, the launcher argv assembly) — cell contract design is outside discovery scope.
- The final wording of the rewritten user guide (docker-auth-mounts cook).

---

Author: trifonovmixail
CreatedAt: 25/09/26
Description: |
  Decision record of the discovery interview for the pipeline-host-to-docker-values
  topic: unifying host→container context transfer on cmd-proxying (the build model),
  removing the GOGA_* env channel, and handing credential provisioning to the user
  via home.docker.run.
