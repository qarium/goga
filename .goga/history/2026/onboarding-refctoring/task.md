# Extensible `goga init` onboarding: tool participation via hooks actions and the dynamic image tag

## Current State

- **`goga/onboarding`** — the session is closed to tools: `Questionnaire` asks a fixed set of `ask_*` methods (click), and the answers are collected directly into `GogaConfigAnswers`; a tool can neither add questions to the session nor write its configuration. Image tags are hardcoded (`:1.3`) in the cell manifest's `image_defaults` practice and drift from the actual installed goga version.
- **`goga/hooks`** — the platform is ready for additive extension: `catalog` (`Action` records — data, not discovery), `registry` (the single registry build, isolated `ToolContext`s, the `by_tool` inspection), `dispatch` (`emit_hook_event` delivery, per-tool contexts via `context_for`, the error class per action), `tools` (the `goga_tool_*` enumeration, `HookRegistrar` with envelope validation). The catalog carries no `onboarding` domain actions.
- **`goga/commands/init`** — the CLI wrapper: routing of bare / `<tpl>`+onboarding / `--upgrade`, the "already initialized" guard on `.goga/`; no tool-invitation option exists.
- **`goga/version`** — `host_goga_version()` exists (the single host-version reading point, uses `importlib.metadata`); no `N.M` tag derivation for hints exists. The four-form version grammar is already implemented in `resolve_version` (N.x, N.M.x, N(.M)(.K), latest).
- **`goga/config/project`** — the `ProjectConfig` schema already contains `tools: dict[str, str]` (four-form version strings) and `usages: dict[str, dict[str, DepConfig(git, ref, root)]]`; the loader validates the structure. The schema is closed to tools' arbitrary keys.
- **Documentation** — `docs/features/init/hooks.md` — the "no hook actions" stub; the author contract for onboarding participation is undocumented.

## Description

Extend the `goga init` session with invited-tool participation and eliminate the image-tag drift. The ADR decisions (`adr.md`) are normative for the entire task — the "Decisions" sections 1–10, the "Deviations from the PRD" (R4.1, R4.2, R2.4), and the introductory decisions (the CLI `-t/--tool`, the `N.M` image tag):

1. **Two soft catalog actions** in the `onboarding` domain: `declare_session` — moment one (before the survey; declaring questions and skips), `amend_config` — moment two (after the survey collects every answer, before the config write; amendments and writes). Subscriptions are independent; the engine itself asks the tool question blocks — questions are declarative data, and the platform never calls a hook to survey.
2. **Invitation via a marker in the per-tool context**, not a delivery filter: the emission reaches every subscriber of the address; the invited tool's context carries the active surface, the non-invited tool's — the "not invited" marker (its hook must return immediately — a contract rule). An invited but unsubscribed tool participates silently.
3. **A single question space**: 8 core ids — `language`, `convention`, `codemanifest`, `build` (build_agent + build_env, i.e. `build.task_executor`), `docker_image`, `pipeline`, `tools`, `usages`; tool questions — `<tool>.<name>` (a duplicate id within a tool rejects the declaration with a warning — the registrar pattern). Question kinds: `choice`, `input`, `confirm`, `pairs` (repeated key→value collection with proposed keys), `group` (one nesting level; children are simple kinds; a group's answer is a mapping). `review` — a future additive id, not added in this task.
4. **The extended core survey** (confirm-gated, within the existing patterns): `tools` — a confirmation → repeated collection of name+version pairs; `usages` — repeated record collection per the schema group → dependency name → git repository (optional ref/root per the `DepConfig` schema). Order: language → convention → codemanifest → build → docker_image → pipeline → tools → usages → tool question blocks (deterministic enumeration order, with attribution of the tool name).
5. **Skips** — a dot-path into the question tree; core child names match the schema fields (e.g. `build.task_executor.env`); a tool's own question or group takes no prefix, another tool's takes `<tool>.`. Skipping a node skips the subtree; inside `pairs`, individual pairs are not addressable. The engine applies skips after the entire declaration, order-independently; an unknown path is a no-op with a warning. The survey never asks a skipped question; the tool tolerates the missing answer.
6. **Amendments — the single mechanism `answer(id, value)`**: re-answer or update an existing id; mappings merge recursively, scalars and lists are replaced. Substituting a user's answer is silent (a tool's lawful right). Tool conflicts resolve last-wins in delivery order (the alphabet of tool identities). The `tools`/`usages` registrations are ordinary answers at the ids (no special registration members exist); a tool's own entry lands under its identity; version values follow the four-form grammar; a missing version reads as `latest`.
7. **Tool config writes go only through the engine's API**: the engine serializes YAML and writes `.goga/tools/<tool>/<file>.yml`; writing the same file again rewrites it. Writes are buffered; the final created-files list combines the engine's files and the tools' files with attribution (automatically, with no "report file" member). A tool writing files directly, bypassing the API, acts outside the session contract.
8. **Failure resilience is staged per tool**: a tool's contribution (amendments + files) commits only after its moment-two hook completes successfully; a failure at any step discards the contribution entirely, emits a warning with the tool name and the reason, and the session continues with exit code 0. An existing `.goga/config.yml` (the `<tpl>` branch) is never rewritten; the related events are not emitted. A broken package import is the single fatal case: a clean session error naming the package, without a traceback.
9. **Answer isolation**: `answers` holds nested mappings (groups are mappings; dotted keys never appear); a tool sees its own unprefixed questions and the core questions; other tools' answers are unreadable — tools coordinate through merges of shared sections. An empty required schema field (`language`) at write time, unrestored by an amendment, is a clean session error naming the field.
10. **The `N.M` image tag** from `host_goga_version()` — the same reading point the host↔image compatibility check uses; the ready-image (pull) and Dockerfile base-image hints carry the current minor's tag; an unreadable version is a clean session error without a traceback.
11. **CLI**: the repeatable option `-t/--tool <name>` in both modes that run onboarding (bare and `<tpl>`); `-t` with `--upgrade` — a flag-combination validation error with a nonzero exit; deduplication of repeated names (the session asks the block once); a named but not installed tool — a warning naming it, the session continues without its block.
12. **Documentation and the example**: the author contract — `docs/features/init/hooks.md` (modeled on the existing domain hooks pages), cross-references from `docs/features/tools/hooks.md`; registrations appear in `goga hooks` automatically. The example tool is the test fixture package `goga_tool_*`, exercising the scenario exclusively through the public surface.

## Scope

**In scope:**

- Two additive `Action` records in the hooks catalog (`onboarding/declare_session`, `onboarding/amend_config`, both soft).
- The repeatable `-t/--tool` option of the init command: combination validation with `--upgrade`, deduplication, warnings about uninstalled tools.
- The "question → answer" mechanism in onboarding: the id space (8 core + `<tool>.<name>`), the kinds choice/input/confirm/pairs/group, the survey order, the attribution of tool blocks.
- Extending the core survey with the `tools` and `usages` sections (per the `ProjectConfig`/`DepConfig` schema).
- Skipping questions by dot-paths with subtree semantics and order-independent application.
- Amendments via `answer(id, value)`: mapping merge, replacement of scalars/lists, last-wins by delivery order; the tools' registrations in `tools`/`usages` as ordinary answers.
- Writing tool configs through the engine's API into `.goga/tools/<tool>/<file>.yml` with buffering and automatic attribution in the final file list.
- Staged failure resilience per tool; fatal only on a broken package import; the guarantee that the standard config is created from the core answers and the surviving tools' amendments.
- Answer isolation (nested mappings, no dotted keys); a clean session error on an empty required `language` field at write time.
- The `N.M` image-hints tag derived from `host_goga_version()`; a clean error on an unreadable version.
- Documentation of the author contract (`docs/features/init/hooks.md`, cross-references from `tools/hooks.md`).
- The example tool — the `goga_tool_*` test fixture package via the public surface; tests in the project's mirrored structure.

**Out of scope:**

- The `review` survey (a future additive core id).
- A non-interactive/CI onboarding mode with answers from a file.
- A rework of the hooks platform (delivery, registration, isolation models) — only additive catalog records.
- An open `.goga/config.yml` schema with tools' arbitrary keys; merging or rewriting an existing `config.yml`.
- Runtime updates of the image tag in existing projects (the change concerns only the onboarding hints).
- The `goga install` post-install hooks and the home config `~/.goga/config.yml`.
- Separate tool onboarding sessions outside `goga init`.
- Special registration members (`register_tool`/`register_dep`) — rejected by the ADR in favor of `answer`.

## Acceptance Criteria

- **S1.** `goga init -t <name>` (the tool installed, the project without `.goga/`): the tool's question block appears in the same session after the core questions with attribution; on completion, a valid `.goga/config.yml` (core schema, including the tool's registrations in `tools`/`usages`) and the tool's own config in `.goga/tools/<tool>/` exist — with no manual setup after init.
- **S2.** Without `-t`, the session contains no tool questions; the result matches today's behavior.
- **S3.** The extension-contract documentation exists (`docs/features/init/hooks.md` + cross-references); the example tool works exclusively through the public surface, without goga code changes.
- **S4.** A failing tool (an exception in the declaration, the amendments, or writing its config): init completes successfully (exit code 0), the standard config is created, the output carries a warning with the tool name and the reason, and the tool's contribution is discarded entirely (staged); the other invited tools are configured.
- **S5.** `-t` with an uninstalled tool: a warning naming it; the session continues; exit code 0.
- **S6.** An existing `.goga/config.yml` (the `<tpl>` branch): the file is unchanged, no config questions are asked, the related tool events are never emitted.
- **S7.** With goga version `N.M.*` installed, the image hints (pull and the Dockerfile base image) carry the tag `:N.M`; after a minor goga upgrade, the hints show the new minor without code changes.
- **S8.** The image offered by default passes the host↔image compatibility check on (major, minor) at the first container run.
- **S9.** An unreadable goga version and a broken tool-package import — clean session errors with an actionable message (the field/package name), without a traceback; an empty required `language` field — a clean error naming the field.
- **S10.** A duplicate question id within a tool — declaration rejection with a warning (partial declarations survive); an unknown skip path — a no-op with a warning; the onboarding-action registrations are visible in the `goga hooks` inspection.
- **S11.** `-t` with `--upgrade` — a nonzero exit with an actionable message about the incompatible flags; a repeated `-t` name deduplicates (the block is asked once).
- **S12.** A skip declared by a tool suppresses the questions of the subtree (the core's, its own, and other tools'): the survey never shows the skipped question and never requests its answer; order-independent application of skips does not change the result.
- **S13.** Isolation and amendment conflicts: a participating tool never sees another tool's questions and answers (only the core's and its own); when two tools amend the same id, the last in delivery order wins (last-wins), mappings merge recursively, scalars and lists are replaced.
- **S14.** On session completion, the final created-files list is printed: the engine's files plus the tools' files with attribution of the tool name.

## Stack

- **Frameworks:** click — the interactive CLI survey of all question kinds (core and tools).
- **Libraries:** PyYAML — serialization of `.goga/config.yml` and the tools' configs; `importlib.metadata` (stdlib) — only through `host_goga_version()` from `goga/version`.
- **Models and logging:** dataclasses (`frozen=True`, `kw_only=True`), `logging` — per the project's conventions.
- **Infrastructure:** none — the entire session is interactive on the host, before building and running containers.
- **Testing:** pytest, pytest-cov, ruff (in `[project.optional-dependencies] test`); the example tool — a `goga_tool_*` pytest fixture package installed into the test environment.

## External Dependencies

| Component | Usage file | Status |
|-----------|------------|--------|
| click | `.goga/usages/cooks/click.md` | existing |
| PyYAML | the inline `yaml` practice in the `goga/onboarding` manifest | existing |

No new external dependencies; the practice files in `.goga/usages/cooks/` are neither created nor updated.

## Risks and Constraints

- **C-1.** The init modes are immutable: bare / `<tpl>`+onboarding / `--upgrade`, the "already initialized" guard.
- **C-2.** The existing `config.yml` is untouchable: "whoever created it first wins"; this branch skips the related tool events.
- **C-3.** The `config.yml` schema stays the core's typed schema; tools add no arbitrary keys.
- **C-4.** Extension goes only through the hooks platform (additive catalog records; the installation trust level, no sandbox); existing subscriptions and the CLI keep working.
- **C-5.** The interactive CLI channel on the host, before containers.
- **C-6.** The host↔image compatibility check on (major, minor) does not change; the image suggestions must satisfy it.
- **C-7.** Extension without goga patches — only the tool's package per a documented contract.
- **Deliberate deviations from the PRD (fixed by the ADR):** a broken import is fatal, not soft (R4.1); an empty required field at write time is a clean session error, not "the config always" (R4.2); the registrations are implemented as answers at the ids, not as special members (R2.4).
- **Determinism:** the tool-block order is the package-enumeration order; last-wins of amendments is the delivery order (the alphabet of identities).
- **Open questions of the design stage (from the ADR):** the exact names and signatures of the context members (`invited`, `declare_*`, `skip`, `answers`, `answer`, `write_config` — working aliases); the composition and wording of the core `tools`/`usages` prompts; whether writing other tools' keys into `tools` is admissible (whether to validate — the design decides).

## Scope Estimate

**A single task** (large). Work zones: the hooks catalog (small, additive), the onboarding session engine — the core of the work (questions/skips/amendments/staged/writes), CLI + the image tag (small), documentation + the example tool (medium). The parts are rigidly coupled by a single contract; decomposition into cells is performed by the brainstorm stage per the DSL (bottom-up). ~15–20 types/entities, high interaction complexity (merge/last-wins, staged rollback, answer isolation, hooks-platform invariants).

## Existing Architecture

The affected cells and connections:

- **`goga/hooks/catalog`** — additively two `Action(domain="onboarding", …, error_class="soft")` records; catalog records are never rewritten; the catalog stays data.
- **`goga/onboarding`** — the main rework: the session engine consumes the hooks platform through the `goga/hooks` facade (the registry, delivery, per-tool contexts); the `Questionnaire`/`FileGenerator`/`InitAnswers`/`GogaConfigAnswers`/`InitLogic` contracts change to the "question → answer" mechanism; the `image_defaults` practice loses the hardcoded tag — the hints take the `N.M` tag from the version.
- **`goga/commands/init`** — the new `-t/--tool` option, combination validation, passing the invitation into the onboarding logic; the command remains the integration point of the onboarding and scaffold domains and delegates execution.
- **`goga/version`** — `host_goga_version()` — the single version-reading point (reuse it; do not duplicate the metadata reading); the four-form version grammar for the registrations — reuse `resolve_version`; the design decides where to place the `N.M` tag derivation.
- **`goga/config/project`** — the schema's consumer, unchanged: the final YAML must pass `load_project_config` (`tools: dict[str, str]`, `usages: dict[str, dict[str, DepConfig(git, ref, root)]]`).
- **`docs/features/init/`, `docs/features/tools/`** — the author-contract documentation and cross-references.
- **`tests/`** — mirrors the structure; the `goga_tool_*` fixture package for the example tool (the package enumeration reads the installed distributions).
- Dependency direction: `goga/onboarding` → `goga/hooks` (one-way, no cycles); `goga/commands/init` → `goga/onboarding`, `goga/scaffold` (the existing integration point).

## Notes

- The normative source of the decisions is the ADR `.goga/history/2026/onboarding-refctoring/adr.md`; the PRD `prd.md` remains in force in the part not changed by the ADR's deviations.
- Code examples are not included in the task (a stage limitation); the context members' signatures are an open question of the design.
- The contract rule for non-invited tools: the hook must return immediately on the "not invited" marker.
- A skip inside `pairs` is addressable only by the node as a whole — individual pairs are not addressable.
