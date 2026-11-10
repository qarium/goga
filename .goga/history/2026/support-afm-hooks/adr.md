# Bridge afm lifecycle hooks onto the goga hooks platform as pipeline-domain run events

goga registers its own observer hook in the global layer of the `~/.afm/config.yaml`
whole-file write — `id: goga`, `events: all`, `command: python3 -m goga.pipeline hook`,
`inherit_env: true`, afm-default timeout/retries — and bridges afm's per-event
invocations (a fresh short-lived process per event: `sh -c`, CWD = the flow's
`root_dir`, JSON payload on stdin) onto the internal hooks platform as 15 soft actions
in the `pipeline` domain: the 13 `stage_*` transitions under their afm names plus
`run_resumed` (← `flow_resumed`) and `run_interrupted` (← `flow_interrupted`),
normalized to the platform's vocabulary — goga has no "flow" concept, and the run
boundaries stay with the unchanged `run_created` / `run_completed`. Every context
carries passthrough facts under goga-idiomatic names — `pipeline.name`;
`run.run_id` / `run_dir` / `root_dir` / `resumed`; `stage.id` / `name` /
`from_status` / `to_status` / `phase`; `event_id`, `occurred_at`, `reason` — with no
raw-payload exposure (`from_status` / `to_status` because `from` / `to` are Python
keywords and cannot be attribute names).

## Considered options

- **A dedicated `python -m goga.afmhook` module** — rejected: the events are pipeline
  events; the command lives as the `hook` subcommand of the in-container
  `python -m goga.pipeline` CLI (id `goga`, per-hook log
  `.afm/runs/<run-id>/hooks/goga.log`; the `ensure_in_docker` guard already covers the
  entrypoint).
- **An explicit curated `events:` list in the registration** — rejected: afm validates
  event names (an unknown name is a config error), so an explicit list would pin every
  launch to one exact afm catalog version; `events: all` keeps the bridge
  version-robust and the curated filter lives in one place — the bridge, which exits
  early on non-curated events (by `AFM_HOOK_EVENT`) before importing the platform.
- **Minimal hook environment (the original PRD C16)** — superseded by an explicit user
  decision: `inherit_env: true` (risk accepted, C16 amended). The bridge declares no
  `env`-map secrets of its own; the subscriber env visibility is documented instead of
  avoided.

## Consequences

- **Failure discipline.** Exit 0 on success, on ignored (non-curated) events, and on
  subscriber soft failures (the platform already warns naming the tool and the
  action); non-zero only on a bridge-internal failure (damaged stdin, emission
  crash) — afm writes it to the per-hook log and warns on the dashboard; the run is
  never affected either way (observer semantics end-to-end).
- **C16 amendment.** With `inherit_env: true` the hook process — and the subscriber
  hooks running inside it — inherits the afm process environment, including the launch
  env layers (env-file layers, the `pipeline.env` task layer, CLI `-e` entries). This
  carriage is deliberate and documented (`afm.md`,
  `docs/features/pipelines/hooks.md`).
- **Registry per event.** afm spawns the hook per event, so the platform's
  registry-built-once-per-command rule maps to once-per-event-process; the bridge
  keeps no cross-event state and must complete far inside afm's 30s default.
- **Scope guards.** The workflow layer is untouched; user-facing hooks authoring
  stays documentation-only in `afm.md` (the project layer `.afm/config.yaml` works
  for users today; the flow-file layers are the documented future authoring place,
  including context-formation considerations). The `hook` subcommand is afm-facing
  machinery, not user surface.
- **Left open for the design stage:** cell placement of the bridge code, the context
  record shapes, the catalog wiring, and the CODEMANIFEST changes.
