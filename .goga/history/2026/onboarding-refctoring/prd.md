# Extensible goga onboarding: tool embedding and compatible images

## Problem

**P-1. Onboarding is closed to tools.**
The user runs `goga init` in a project where goga tools (`goga_tool_*`) that need their own project configuration are installed. The onboarding session is closed: the core fixes the set of questions, and the answer-collection mechanics is a fixed set of fields; a tool can neither add its own questions to the session nor write its own configuration from the answers. Tool setup is divorced from initialization: the user configures the tool manually after init (editing files blind), and the tool author cannot offer a guided setup — a risk of incomplete or incorrect configuration.

**P-2. Image tag drift in the hints.**
Onboarding offers images with a hardcoded tag (`:1.3`) unrelated to the actual installed goga version (1.3.x). When goga moves to a new minor, the hints start offering images that fail the host↔image compatibility check on (major, minor) at the first container run — a broken first run, or manual tag maintenance in every release.

## Users

**U1. The user initializing a project** (primary). A developer running `goga init` — standalone or after scaffolding from a template. Context: first run in the project; goga tools may be installed in the environment. Goal: obtain a fully configured working project in one session — the standard config plus the invited tools' configs — and an image compatible with the installed goga. Expectations: one coherent session; sensible defaults; nothing breaks at the first container run after init; a tool failure does not take down the initialization.

**U2. The tool-package author (`goga_tool_*`)**. Publishes an extension that needs project configuration. Goal: embed the tool's questions into the `goga init` session and, from the answers, write its own config and specific registrations into the project config. Expectations: a documented, predictable extension contract (analogous to the existing hooks registration contract); no goga code changes required; predictable handling of the tool's failures.

**U3. The goga maintainer** (secondary, for P-2). Goal: keep the onboarding image hints correct across minor-version changes, without manually editing hardcoded tags in every release.

## Goals

**G-1. A single setup session.** The `goga init` user configures the standard goga config and the invited tools' configuration in one session — with no manual setup after initialization.

**G-2. An extension contract for tool authors.** The `goga_tool_*` author embeds the tool's questions into the `goga init` session and, from the answers, writes its own config plus specific registrations into the project config (itself into `tools`, dependencies into `usages`) — without extending the standard schema with arbitrary keys and without goga code changes, relying on a documented contract.

**G-3. Always compatible image suggestions.** Onboarding offers only images compatible with the installed goga version (the current minor's tag), without manual tag maintenance in every minor release.

## User Experience

### Entry point

`goga init` (in a project without `.goga/`), `goga init <tpl>` (scaffold, then onboarding), `goga init --upgrade` (template migration, no onboarding — unchanged). A new repeatable tool-invitation flag: `-t/--tool <name>`.

### Main scenario (fresh project, the session creates the config)

1. **The session header** and the wizard description — as today.
2. **Tool invitation (before the survey starts).** Every tool explicitly named via `-t` and installed participates through its share of the event context: it declares its questions (declarative data) and/or the skipping of any session questions. Only explicitly named tools receive invitations; unnamed tools receive none and stay silent. The session never re-confirms an explicitly named tool — the flag is itself the explicit invitation.
3. **The core survey** (minus the questions declared for skipping): language → base convention (when the file is absent) → codemanifest usages/annotations → build-agent → Dockerfile → image → env → pipeline-agent → pipeline-env. The image hints carry the installed goga's current minor tag; the user may enter any image name.
4. **Tool question blocks.** The session engine asks each participating tool's declared questions — after the core questions, in the deterministic tool-enumeration order, with explicit attribution ("questions from tool X").
5. **Amendments before the write.** After the survey collects the answers and before the write, each participating tool may modify the configuration object under assembly: values within the standard config schema plus registrations of itself into `tools` and of dependencies into `usages`; the tool writes its own config by its own rules.
6. **The write and the summary.** The session creates `.goga/config.yml` (the core structure plus the tools' registrations), the Dockerfile (when chosen), and the tools' configs. The user sees the list of created files and warnings about skipped tools. Exit code — success.

### Alternative scenarios

- **Without `-t`** (or none of the named tools is installed): no tool question blocks — the session matches today's behavior.
- **`-t X`, tool X not installed:** an actionable warning naming the tool; the session continues without X's block.
- **`goga init <tpl>`, the template brought `.goga/config.yml`:** behavior as today — the session skips config creation and the related questions entirely; it also skips the config-related tool events (tools do not participate in this branch); the existing file is never rewritten.
- **A repeated bare `goga init` in an initialized project:** the refusal "Project already initialized" (as today).
- **`-t` together with `--upgrade`:** a flag-combination validation error with a nonzero exit (this mode has no onboarding).

### Failures (soft)

An invited tool failing at any participation moment (a broken import, an exception in the declarations, in the amendments, or while writing its config): the session skips the tool's block with a warning (tool name + reason), continues, and the remaining tools and the core complete as intended. The standard `.goga/config.yml` is created from the core answers and the surviving tools' amendments. Initialization completes successfully.

### Feedback, interruption, retry

The session's progress is transparent: section headers, attribution of tool blocks, warnings about failures and uninstalled invited tools, and the final list of created files. User interruption behaves as today. After a successful write, a repeated bare init is impossible (the guard). The created artifacts are ordinary project files; no special rollback mechanics is introduced.

## Requirements

### Tool invitation

- **R1.1.** `goga init` accepts a repeatable option `-t/--tool <name>`; the invitation acts in both modes that run onboarding (bare and `<tpl>`).
- **R1.2.** Without `-t`, no tool question blocks exist — the session matches today's.
- **R1.3.** Only explicitly named tools receive invitations; unnamed installed tools receive none and ask no questions.
- **R1.4.** A named but not installed tool — a warning naming it; the session continues without its block; a repeated name deduplicates (the session asks the block once).
- **R1.5.** `-t` with `--upgrade` — a flag-combination validation error with a nonzero exit and an actionable message.

### Tool participation in the session (the two-moment model)

- **R2.1.** The core questions come first (minus those declared for skipping), then the participating tools' question blocks — in the deterministic tool-enumeration order, with attribution of the tool name.
- **R2.2.** A tool declares its questions as declarative data at invitation (before the survey starts); the session engine asks them in its block; the answers are available to the tool for building its configuration.
- **R2.3.** At invitation, a tool may declare the skipping of any session questions (the core's and other tools'); the survey never shows a question declared for skipping and never requests its answer.
- **R2.4.** After the survey collects the answers and before the write, a participating tool may modify the configuration object under assembly: values within the standard config schema plus registrations of itself into `tools` and of dependencies into `usages`; arbitrary new keys never enter the standard schema.
- **R2.5.** A tool writes its own config from its answers and by its own rules.
- **R2.6.** A documented extension contract provides the tool's capabilities without goga code changes; the onboarding-action registrations are visible in the `goga hooks` inspection.

### The configuration object

- **R3.1.** The session collects the configuration as a fillable "question → value" mapping (core and tool questions) and serializes it into `.goga/config.yml` per the core structure (including the tools' registrations).
- **R3.2.** An existing `.goga/config.yml`: the session skips the config's creation and its related questions; it skips the config-related tool events; it never rewrites the file.

### Failure resilience

- **R4.1.** The session handles a failure of an invited tool (import, declarations, amendments, writing its config) as soft: it skips the tool's block, prints a warning with the name and the reason, and continues.
- **R4.2.** The standard `.goga/config.yml` is created from the core answers and the surviving tools' amendments regardless of the failed tools.
- **R4.3.** The final exit code is success whenever the core completes successfully, regardless of tool failures.

### Images

- **R5.1.** The image hints (the ready image for pull and the Dockerfile base image) carry the tag equal to the installed goga's current minor version (e.g., 1.3.x → `:1.3`).
- **R5.2.** The minor comes from the installed goga distribution's version-reading point — the same one the host↔image compatibility check uses.
- **R5.3.** The user may enter an arbitrary image name — the hints never restrict the input.
- **R5.4.** An unreadable goga version — a clean session error with an actionable message (no traceback).

### Feedback

- **R6.1.** The session shows the attribution of tool blocks, warnings about failures and about uninstalled invited tools; it reports the created files.

## Constraints

- **C-1. The init modes are immutable.** The routing of bare / `<tpl>`+onboarding / `--upgrade`, and the "already initialized" guard (`.goga/` exists → bare refusal), stay as is.
- **C-2. The existing config.yml is untouchable.** The "whoever created it first wins" rule holds: an existing `.goga/config.yml` is never rewritten; this branch skips the config-related tool events.
- **C-3. The standard config keeps a typed schema.** `.goga/config.yml` stays on the core schema (including the `tools`/`usages` sections); tools add no arbitrary keys.
- **C-4. Extension goes only through the hooks platform.** Tool embedding uses the existing platform model (additive catalog extension, records never rewritten; registration; delivery with an error class; the `goga hooks` inspection); tools run at the installation trust level — without isolation or sandboxing; existing subscriptions and the CLI keep working.
- **C-5. The interactive CLI channel.** The entire session is an interactive CLI on the host, before building and running containers; no tool participation exists outside this channel.
- **C-6. Image version compatibility.** The host↔image check on (major, minor) exists and does not change; the image suggestions must satisfy it.
- **C-7. Extension without goga patches.** A tool author implements the embedding solely in their package per a documented contract (modeled on the existing author-contract documentation).

## Scope

### In Scope

- The config-collection mechanics as a fillable "question → value" mapping in the `goga init` session (an internal questionnaire rework; the output structure of `.goga/config.yml` — the core schema — is preserved).
- The onboarding action in the hooks catalog and the individual tool contexts: invitation, declaring one's own questions, declaring question skips, amending the object before the write, registrations in `tools`/`usages`, writing the tool's own config.
- The repeatable option `-t/--tool <name>` (including validation of the combination with `--upgrade`, warnings about uninstalled tools, deduplication).
- The image-hints tag (the ready image and the Dockerfile base image) derived from the installed goga's current minor version.
- Soft handling of tool failures with warnings; the guarantee that the standard config is created.
- Documentation of the extension contract for tool authors and an update of the init/hooks documentation; visibility of the new registrations in `goga hooks`.

### Out of Scope

- Separate tool onboarding sessions outside `goga init` (explicitly rejected).
- An open `.goga/config.yml` schema with arbitrary keys; merging or rewriting an existing config.yml.
- Runtime updates of the image tag in existing projects (the change concerns only the onboarding hints).
- A rework of the hooks platform (delivery, registration, isolation models) — only additive catalog records are allowed.
- A non-interactive/CI onboarding mode with answers from a file.
- The `goga install` post-install hooks and the home config `~/.goga/config.yml`.

## Success Criteria

- **S1.** With `goga init -t <name>` (the tool installed, the project without `.goga/`), the tool's question block appears in the same session after the core questions with attribution; on completion, a valid `.goga/config.yml` (core schema, including the tool's registrations in `tools`/`usages`) and the tool's own config exist — with no manual setup after init.
- **S2.** Without `-t`, the session contains no tool questions; the result matches today's behavior.
- **S3.** A tool author implements the embedding without goga code changes, solely per the documented contract (the contract documentation exists; the example tool works exclusively through the public surface).
- **S4.** A failing tool: init completes successfully (exit code 0), the standard config is created, the output carries a warning with the tool name and the reason; the other invited tools are configured.
- **S5.** `-t` with an uninstalled tool: a warning; the session continues; exit code 0.
- **S6.** An existing `.goga/config.yml` (the `<tpl>` branch): the file is unchanged, no config questions are asked, the related tool events never fire.
- **S7.** With goga version N.M.* installed, the image hints carry the tag `:N.M`; after a minor goga upgrade, the hints automatically show the new minor without code changes.
- **S8.** The image offered by default passes the host↔image compatibility check on (major, minor) at the first container run.
