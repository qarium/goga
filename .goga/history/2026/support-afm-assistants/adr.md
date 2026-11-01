# Assistants and run agents: delivery through flow-file parts plus engine-config plumbing

goga authors collaboration (an `assistants:` catalog, a `delegation:` block, per-stage
`assistants:` attachments) in the workflow-file only, and delivers it along two
channels the engine offers: everything expressible in the flow-file
(`collaboration.mode`/`max_depth`, the `team` list, stage `assistants` entries) is
compiled into the flow, and everything the flow-file cannot express (helper profiles
with their commands, the whole-run task budget) is delivered through the global
`~/.afm/config.yaml` that goga fully rewrites on every launch. The compiled flow-file
is the single source of truth: the config write materializes profiles exactly for the
ids the compiled flow references, so the two artifacts can never diverge.

Why two channels: afm (v2.x) lets a flow override only `collaboration.max_depth` and
`collaboration.mode` — profiles and `limits.max_tasks` exist in config layers only.
Why the compiled flow is the source of truth: it makes divergence structurally
impossible and leaves no dead profile entries for attachments removed by stage skips.

## Decision map

1. **Catalog → team member + generated profile.** Each top-level `assistants:` entry
   compiles to an afm `team` member (`id: <name>`, `title: <name>` — so the dashboard
   handle is `@<name>` — `profile: goga-<name>`, plus materialized `instruction` and
   `skills`) and to a profile in the global config. Stable ids derived from authored
   names are what make afm's resume reuse members instead of duplicating them.

2. **Generated profile ids are namespaced: `goga-<name>`.** Authored names are
   validated against `[A-Za-z0-9._-]` (the engine's member-id charset; one authored
   `name` feeds member `id`, member `title`, and the profile id suffix). The prefix
   prevents accidental collisions with user-authored project-layer profiles; a user
   defining `goga-<name>` in `.afm/config.yaml` deliberately overrides goga's plumbing
   — that is the intended override channel, not a bug.

3. **Assistant names are globally unique across the workflow-file** — the catalog and
   all inline declarations form one namespace; a repeated name is a validation error.
   Consequence: name = assistant identity, "attached twice to one stage" is a special
   case, and profile derivation needs no stage component.

4. **Profiles carry only what the flow-file cannot express.** A generated profile is
   exactly `{title, command, delegate}` — nothing else. `instruction`, `title`,
   `mode`, `trigger`, and `skills` ride in the flow entries (team member and every
   stage attachment), each materialized always, defaults included
   (`gate`→`mode: required|advisory`, `when: start|checkpoints|finish`→
   `trigger: one_shot|checkpoints|on_completion`; goga's `checkpoints` default must be
   written explicitly because the engine's default is `one_shot`). Rejected:
   duplicating the prompt into `profile.instructions` — it would rely on an
   undocumented engine fallback and split one instruction across two artifacts.

5. **`skills` is emitted into every attachment entry even though afm does not
   interpret it yet** (unknown keys pass through silently). Rejected: forbidding
   `skills` on inline declarations — the engine will support assistant-level skills
   soon, and the forward-compatible emission starts working the day it lands. Team
   members carry `skills` too (supported today, serves the run-agent role).

6. **`env` on assistants follows the stage precedent.** Catalog and inline entries
   accept `env: {KEY: value}` (references cannot override it); delivery is the
   established sh-closure pattern — the closure path becomes the profile's `command`
   (a profile must carry its own command and does not inherit `client.command`).
   Closures are recreated every launch, so authored configuration survives goga's
   per-launch config rewrite by living in the workflow-file, not in artifacts.

7. **Delegation bounds split by channel.** `delegation.depth` → flow
   `collaboration.max_depth`; `delegation.max_tasks` → global config
   `collaboration.limits.max_tasks` (materialized as 50 when the block is authored
   without the value — the engine default is 20). Authored only when the
   `delegation:` block is present.

8. **`collaboration: {mode: assistants}` is emitted into every compiled flow** — the
   one deliberate byte-level change to collaboration-free workflows; the dashboard
   mode precedence (flow > project > global > team) makes the flow the only layer
   goga authors. Top-level key order: `prompt, root_dir, name, description, memory,
   collaboration, team, stages`.

9. **The collaboration kill-switch is not goga's business.** goga neither reads nor
   writes `collaboration.enabled` or `AFM_COLLABORATION`; an environment that disables
   collaboration gets warnings and skipped helpers from the engine, and the run
   proceeds (a flow cannot influence the switch at all).

10. **Validation follows the project's two-layer pattern.** Structural checks
    (entry forms, types, `when` values, unknown keys, name charset, duplicate names,
    `assistants` inside extend-entries) live in the workflow parser; cross-reference
    checks (unknown reference, attachment on a script-only stage — translated body
    carries `script` — or a planning-only stage — `agents == ["planning"]` — the same
    assistant twice on one stage) live in the compiler, like stage-name validation.
    `skip: true` plus attachments is not an error: the stage is removed and nothing
    attaches. Agent names resolve exactly like stage agents (non-empty string →
    wrapper path); no extra existence check.

11. **Tool-contributor overlay: append, not just fill.** For stage `assistants`
    lists, tools may extend even an authored list — merge appends with
    deduplication by name (authored entries first; a tool entry whose name is
    already present is dropped silently, so tools cannot break the author's
    validation). The catalog merges like `extend` (authored names win, tools add
    fresh names); `delegation` merges like `memory` (whole-block authored-unbeatable).

## Engine assumptions to verify during implementation

- Profile ids tolerate `goga-<name>` where `<name>` matches `[A-Za-z0-9._-]`.
- `limits.max_tasks` follows the project > global precedence (the user's
  project-layer value overrides goga's global write).
- `max_depth: 0` suppresses helper creation but not team members.

## Out of scope (recorded, not silently assumed)

- Cell/CODEMANIFEST architecture — the next stage's work, not part of this decision.
- User-facing docs (`docs/features/pipelines/workflows.md`) get updated as part of
  the task; the afm fact base moves into `.goga/usages/cooks/afm.md` alongside this
  ADR (collaboration contract section added).
