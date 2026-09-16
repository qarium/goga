# Tool onboarding: two hooks actions, a single "question → answer" mechanism, mediated config writes

**Status:** accepted

The `goga init` session opens to invited tools (`-t/--tool`) through two soft actions of the hooks platform — `onboarding/declare_session` (the declaration of questions and skips before the survey) and `onboarding/amend_config` (amendments and writes after all answers are collected, before `config.yml` is written) — and all of a tool's specialized participation reduces to a single mechanism: identifiable session questions and answers by id. The hooks platform is not reworked (C-4): an invitation is a marker in the per-tool context, not a delivery filter. Image hints (the pull image and the Dockerfile base image) receive the tag `N.M`, derived from the installed goga version via `host_goga_version()` — the same reading point as the host↔image compatibility check; an unreadable version is a clean session error without a traceback. This eliminates the drift of the hardcoded `:1.3` without manual tag maintenance in every minor release.

## Decisions

1. **Catalog actions.** The `onboarding` domain declares two addresses, both `error_class=soft`: `declare_session` — moment one (before the survey); `amend_config` — moment two (after the survey collects the answers, before the write). Each subscription is independent. The engine itself asks the tool question blocks — questions are declarative data; the platform never calls a hook to survey.
2. **Invitation.** The platform delivers the emission to every subscriber of the address; each tool context carries the invitation marker: an invited tool receives the active surface; a non-invited tool receives the "not invited" marker, and its hook must return immediately (a contract rule). An invited tool that subscribes to nothing participates silently.
3. **Question space.** The core defines 8 ids: `language`, `convention`, `codemanifest`, `build` (build_agent + build_env, i.e. `build.task_executor`), `docker_image`, `pipeline`, `tools`, `usages`. `review` is a future additive id (this task does not add the review survey). Tool questions are qualified by identity: `<tool>.<name>` (a duplicate within a tool rejects the declaration with a warning — the registrar pattern). Question kinds: `choice`, `input`, `confirm`, `pairs` (repeated key→value collection with proposed keys), `group` (one nesting level with simple children; a group's answer is a mapping).
4. **The core survey extends** (confirm-gated, within the existing patterns): `tools` — "Add goga tools to the project dependencies?" → repeated collection of name+version pairs; `usages` — repeated record collection per the schema: group → dependency name → git repository (optional ref/root per the config schema). Order: language → convention → codemanifest → build → docker_image → pipeline → tools → usages → tool question blocks.
5. **Skips.** A skip address is a dot-path into the question tree; core child names match the schema field names (`build.task_executor.env`); a tool's own question or group takes no prefix, another tool's takes `<tool>.`. Skipping a node skips the entire subtree; inside `pairs`, individual pairs are not addressable. The engine applies skips after the entire declaration, order-independently; an unknown path is a no-op with a warning. The survey never asks a skipped question; the tool tolerates the missing answer.
6. **Amendments — the single mechanism `answer(id, value)`.** A tool re-answers or updates an existing id; mappings merge recursively, scalars and lists are replaced. Substituting a user's answer is silent (a tool's lawful right). Tool conflicts resolve last-wins in delivery order (the alphabet of tool identities). No special registration members exist: `tools`/`usages` are ordinary ids; a tool's own entry lands under its identity (the platform assigns identities); version values follow the four-form grammar; a missing version reads as `latest`.
7. **Tool config writes go only through the API.** The engine serializes YAML and writes `.goga/tools/<tool>/<file>.yml`; writing the same file again rewrites it. Writes are buffered; the final created-files list combines the engine's files and the tools' files with attribution (automatically, with no "report file" member). A tool writing files directly, bypassing the API, acts outside the session contract.
8. **Failure resilience is staged per tool.** A tool's contribution (amendments + files) commits only after its moment-two hook completes successfully; a failure at any step discards the contribution entirely, emits a warning with the tool name and the reason, and the session continues with exit code 0. An existing `.goga/config.yml` (the `<tpl>` branch) is never rewritten; the related events are not emitted.
9. **Answer isolation.** `answers` holds nested mappings (groups are mappings; dotted keys never appear): a tool sees its own unprefixed questions and the core questions; other tools' answers are unreadable — tools coordinate through merges of shared sections, never through another tool's data.
10. **Documentation and the example.** The author contract lives in `docs/features/init/hooks.md` (modeled on the domain pages; it currently holds the "no hook actions" stub), with cross-references from `tools/hooks.md`; registrations appear in `goga hooks` automatically. The example tool is the test fixture package `goga_tool_*`, exercising the scenario exclusively through the public surface.

## Deviations from the PRD (deliberately accepted)

- **R4.1 "import is soft":** a broken package import is the hooks platform's single fatal case (the session fails with a clean error naming the package); every other participation failure is soft. The platform invariant outweighs the PRD wording.
- **R4.2 "the config is always created":** skipping any question is allowed (R2.3, literally); if a required schema field (`language`) is empty at write time and no amendment restores it, the session fails with a clean error naming the field.
- **R2.4 "registrations":** the design implements registrations as ordinary answers at the `tools`/`usages` ids rather than special surface members (one mechanism); the core survey thereby gains two new sections.

## Open Questions (design stage)

- The exact names and signatures of the context members (`invited`, `declare_*`, `skip`, `answers`, `answer`, `write_config` — working aliases of this ADR).
- The composition and wording of the core `tools`/`usages` prompts.
- Whether a tool may write another tool's keys into `tools` (merge mechanically allows it; the contract does not propose it — the design decides whether to validate).

## Considered Options

- **One action, the emission delivered twice with different contexts** — rejected: the hook would branch on the moment, blending two contracts (q1).
- **Filtered event delivery to invited tools only** — rejected: a platform rework that C-4 forbids (q3).
- **Addressing amendments by schema fields** — rejected in favor of addressing by question ids: one mechanism covering re-answers and updates (q10).
- **Special members `register_tool`/`register_dep`** — rejected: they duplicate `answer` with merge (q17–q18).
- **Dotted keys in `answers`** — rejected: nested mappings without path parsing; the dot-path survives only in skip addresses (q21–q22).
