# Opening the Config Domain to Tool Package Integrations

## Problem

Tool package authors can subscribe hooks to the checkpoints of the opened
domains — statuses, onboarding, topics, pipeline, and build — but the
project configuration that governs how the current command run behaves is
invisible and untouchable to those hooks. When a command loads
`.goga/config.yml`, no tool can read the loaded settings to make decisions
in its contributions, and no tool can adjust the effective configuration
of the current run — apply a prepared parameter set, mitigate a risky
setting, or simplify routine setup — without editing the user's authored
config file or changing goga itself.

Two demands are blocked today:

- **Read for decisions.** A hook receives only the facts of its own
  checkpoint — never the configuration the command actually runs with.
  Every config-dependent integration decision (adapt a contribution to
  the configured agent, environment, or build/pipeline/review settings)
  is blind.
- **In-memory tuning of a run.** A tool that could safely shape the
  effective settings of the current command — enable a review role, add
  an environment key, enforce a safer value — has no path that leaves the
  authored file alone.

Consequence: every integration scenario around configuration is
unanswerable for the ecosystem. The only options are manual edits of the
authored `.goga/config.yml` or changes inside goga; the project developer
loses the automation, risk mitigation, and simplification that installed
tools could provide, and a tool author facing a config-dependent
integration task has no defined path.

## Users

### Primary: tool package author (integration developer)

A developer extending goga by writing an installed `goga_tool_*` package.
Python author; reads the goga usage docs; subscribes through the
package's `register_hooks` facade callback; already familiar with the
hooks platform from the statuses, onboarding, topics, pipeline, and build
domains.

- **Trying to:** make their hooks configuration-aware — read the
  effective settings of the current command run to decide their
  contributions, and shape those settings for the run: apply prepared
  parameter sets, mitigate risky settings, simplify setup for the
  project.
- **When:** while designing and iterating on the tool package; the hook
  fires during a command run, at the moment the command loads the
  project configuration.
- **What matters:** a complete, predictable contract — what the config
  checkpoint delivers, what a hook may read, what it may amend and what
  it cannot, how amendments from several tools compose, how hook
  failures are treated. No goga code changes needed.
- **Constraints:** runs inside the goga container at the trust level of
  the installation; cannot assume goga code changes; tool identity is
  assigned by goga.

### Secondary: project developer (command runner, config owner)

Uses goga in a project; runs the config-consuming commands; installs
tool packages; authors and owns `.goga/config.yml`.

- **Trying to:** get commands executed as configured, with installed
  tools adding value — and still understand what the tools changed in
  the effective configuration of a run.
- **What matters:** the authored `.goga/config.yml` stays the single
  source of truth and is never rewritten; behavior stays predictable;
  tool participation is observable and diagnosable from the run output;
  a failing tool degrades the way the declared error class promises;
  the hooks layer adds nothing observable when no tools are subscribed.

## Goals

Priority order: G1 → G2 → G3. G1 is the primary outcome; G2 shapes how
G1 is delivered; G3 is the residual guarantee, not a veto.

- **G1 — Configuration-aware tool participation.** A tool package author
  can make their tools configuration-aware participants of any command
  run: at the config-load moment their hooks read the effective project
  configuration and contribute amendments that shape the current run —
  without changes inside goga, exactly as they already can in the opened
  domains.
- **G2 — The authored configuration is the source of truth.** The
  project developer's explicitly authored settings are never silently
  replaced. By default a tool's amendment applies only where the
  authored configuration is silent; overwriting an authored value
  requires the tool's explicit force intent. The effective
  configuration of a run is explainable from the run output, and the
  authored file is never modified.
- **G3 — Invisible when unused.** With no tool packages installed, or no
  subscriptions to the config action, every command behaves exactly as
  it does today — the hooks layer adds nothing observable.

## User Experience

### Entry points

- **Tool author:** subscribes a hook to the config-domain action in the
  package's `register_hooks` callback — the same subscription model as
  the other domains. The hook fires during any goga command that loads
  the project configuration.
- **Project developer:** runs any config-consuming command (build,
  pipeline, lint, topics, config, …) with tool packages installed. No
  new command, flag, or file is introduced.

### Primary flow (tool author)

1. The author subscribes a hook to the config-domain action through the
   established facade callback.
2. A goga command loads the authored `.goga/config.yml` — the one
   checkpoint of the domain fires there, after the load and before any
   consumer reads the configuration.
3. If any installed tool subscribes to the action, goga assembles the
   run's registry and enumerates the tools (the platform's standard
   first-checkpoint behavior).
4. Each subscribed tool's hooks receive the delivered context of the
   action: a **read-only view of the authored loaded configuration** and
   an **amendment surface**.
5. The hook reads the settings it needs (for example: is a build agent
   configured, which review roles are enabled, which env keys are
   present) and decides its contribution.
6. The hook contributes amendments in two explicit forms:
   - **set** — the value applies only where the authored configuration
     is silent at that path;
   - **force** — the value overwrites even an authored setting; the
     tool's explicit override intent.
7. Delivery is per-tool and staged: tools are mutually blind — every
   hook reads the authored configuration, never another tool's staged
   or committed state; each tool's contributions commit as a unit, in
   enumeration order.
8. The contributions merge deterministically: authored-wins by default
   (a `set` on an authored path is dropped — not an error); among tools
   the later contributor in enumeration order wins on the same path;
   `force` overwrites both.
9. The command proceeds with the effective (merged, in-memory)
   configuration; every consumer of the configuration in that run
   observes the effective one. The authored file is untouched.

### Primary flow (project developer)

1. Runs a config-consuming command with tools installed.
2. When tools amend the configuration, the command prints a short
   summary of the applied amendments — which tool set or forced which
   configuration path. The effective configuration of the run is
   explainable from the run output alone.
3. After the run, `.goga/config.yml` on disk is unchanged; the next run
   starts again from the authored file and reproduces the same
   effective configuration deterministically (same tools, same file).

### Alternative flows

- **No tools installed or no subscriptions** — passthrough: no registry
  assembly for config, no summary, no other observable change; behavior
  is byte-identical to today.
- **A hook reads but amends nothing** — nothing is applied, no summary
  is printed, the command runs on the authored configuration.
- **Two tools amend the same not-authored path** — the later tool in
  enumeration order wins; each hook saw only the authored
  configuration.
- **A tool force-overwrites an authored value** — applied, and named in
  the summary like any other applied amendment.

### Failure flows

- **A hook fails (crashes or errors) during the config checkpoint** —
  the action is hard: the first failing tool stops the command with a
  clean error naming the tool and the action; the failing tool's whole
  contribution is discarded — nothing partial reaches the effective
  configuration, and the command does not run.
- **A `set` amendment targets an authored value** — not a failure: the
  amendment is dropped by the documented authored-wins rule, silently
  (no warning in the command output, no error). The tool author learns
  the rule from the contract documentation.
- **A contribution is structurally malformed** (an amendment that does
  not address the known configuration model — an unknown path or a
  value of the wrong shape) — the tool's delivery fails under the
  action's hard semantics: the command stops with a clean error naming
  the tool and the action. Semantic validity of well-formed values
  remains the consumers' concern, as today.
- **The configuration file is missing or structurally invalid** —
  existing loader behavior, unchanged; the checkpoint belongs to the
  successful load of the authored file.

### Feedback and consequences

- Applied amendments → the summary in the command output (tool, path,
  set/forced).
- Hard failure → a clean error naming the tool and the action; nothing
  applied from the failing tool.
- No amendments → no extra output.
- Amendments are per-run only: nothing persists, nothing is
  irreversible, re-running reproduces the same effective
  configuration. The authored file is never modified by hooks — an
  irreversible-change risk is excluded by design.

## Requirements

### Checkpoint and subscription

- **R1.** Every goga command that loads the project configuration
  (`.goga/config.yml`) offers exactly one hooks checkpoint at the load
  moment — after the authored file is loaded, before any consumer reads
  the configuration. The checkpoint is addressed as a config-domain
  action in the platform's action catalog, with the hard error class.
  The checkpoint is reached uniformly by all commands that load the
  project configuration today.
- **R2.** Tool packages subscribe through the established
  `register_hooks` facade callback — the same subscription model,
  envelope, and per-tool isolation as the other domains. No new
  registration mechanics.

### Read surface

- **R3.** Each subscribed hook receives a read-only view of the authored
  loaded project configuration — the settings sections and their values
  as loaded, environment mappings included with their values —
  sufficient for config-dependent decisions and for composing amendments
  that extend existing values.
- **R4.** The view is read-only: a hook cannot mutate the configuration
  through it (the platform's delivery rule — attribute assignment is
  blocked).

### Amendment surface

- **R5.** The delivered context offers an amendment surface with two
  explicit forms: **set(path, value)** — applies only where the authored
  configuration is silent at the path; **force(path, value)** —
  overwrites an authored value, the tool's explicit override intent.
- **R6.** Amendments address leaf paths of the project configuration
  known to the configuration model — scalar leaves, list-valued leaves
  replaced wholesale, and individual mapping entries; whole-section
  replacement is not part of the surface. The home configuration
  (`~/.goga/config.yml`) is not part of the surface.
- **R7.** Amendments live in memory for the current command run only.
  Hooks never modify `.goga/config.yml` or any other file; the authored
  file is the only authoring surface.

### Delivery and merge

- **R8.** Delivery is per-tool and staged: every hook reads the authored
  configuration (mutual blindness); each tool's contributions commit as
  a unit, in enumeration order, over the run's single registry.
- **R9.** The merge is deterministic and rule-fixed: authored-wins by
  default — a `set` on a non-silent authored path is dropped; on the
  same path `force` beats any `set` regardless of enumeration order;
  among amendments of equal intent the later contributor in enumeration
  order wins. The same set of installed tools and the same authored
  file always produce the same effective configuration.
- **R10.** The command run consumes the effective (merged)
  configuration; every downstream consumer of the configuration in that
  run observes the effective one.

### Failure treatment

- **R11.** The action's error class is hard: the first failing tool — a
  crashed hook or a structurally malformed contribution — stops the
  command with a clean error naming the tool and the action; the failing
  tool's whole contribution is discarded; nothing partial is applied.
- **R12.** A `set` amendment dropped by the authored-wins rule is not a
  failure and produces no warning in the command output.
- **R13.** Semantic validation of well-formed amended values remains
  with the configuration's consumers, as today; the loader's
  structural-only validation boundary is not relocated.

### Feedback

- **R14.** When amendments are applied, the command prints a short
  summary of the applied amendments — the tool, the configuration path,
  and whether the value was set or forced. Environment values never
  appear in the summary or any informational output. With no applied
  amendments there is no summary. With no subscribed tools, behavior is
  byte-identical to today: no registry assembly for config, no summary,
  no other observable change.

### Documentation

- **R15.** The tool-author contract of the checkpoint — what the view
  delivers (including the output-side env secrecy rule), the two amendment forms,
  the merge rules, the failure treatment, and the summary — is published
  in the project's usage docs, in the same form as the other opened
  domains, so a tool author can build against it without reading goga
  source.

## Constraints

- The checkpoint is delivered over the existing hooks platform — the
  action catalog, run registry, dispatch, and tool enumeration are used
  as they exist; the platform's own semantics are not changed. The
  catalog is extended additively: the new config-domain record is added;
  published records of other domains are never rewritten.
- The `goga/config` facade stays behavior-free: the hooks behavior of
  the domain belongs to a hooks zone of the config domain, following the
  structure of the opened domains.
- No repository, git, or file reads happen at checkpoint time — every
  delivered context is built from the operation data the caller passes
  (the config load's call sites own the file read).
- One registry per run: the checkpoint never multiplies the package
  enumeration.
- Environment values never appear in the informational output of a run
  (summary, warnings, errors). The read view itself delivers the
  authored values — the build domain's names-only rule concerns the
  assembled runtime environment and does not transfer to the authored
  project configuration.
- The project configuration loader keeps structural-only validation;
  semantic validation stays with the consumers.
- Package enumeration and the merge are deterministic.
- Existing command contracts and CLI behavior are unchanged — the
  checkpoint extends the load moment, it does not redefine it.
- The address of the config action must remain unambiguous against the
  existing `onboarding`/`amend_config` action (distinct domains keep the
  addresses distinct).

## Scope

### In Scope

- The config-domain hooks checkpoint at the project-configuration load
  moment: the catalog action with the hard error class, delivered over
  the existing platform.
- The read surface: the read-only view of the authored loaded project
  configuration for subscribed hooks, environment mappings included.
- The amendment surface: `set` and `force`, per-tool staged delivery,
  the authored-wins / later-tool-wins / force merge — deterministic.
- The in-memory effective configuration consumed by the command run.
- The run-output summary of applied amendments.
- The byte-identical passthrough guarantee when nothing is subscribed.
- The tool-author contract documentation (usage docs).
- Uniform reach: every command that loads the project configuration
  today offers the checkpoint.

### Out of Scope

- Persistent configuration changes — tools writing to
  `.goga/config.yml` or any store; any new config authoring surface.
- Exposing the home configuration (`~/.goga/config.yml`) — stays closed.
- New or changed config CLI commands — `goga config` remains the
  read-only value printer it is today.
- Changes to the hooks platform semantics (catalog rules, registry,
  dispatch, registration envelope) beyond the additive catalog record.
- Re-opening or amending the actions of other domains.
- Veto or gate powers over runs based on configuration (policy blocking
  remains the build domain's gate concern).
- Redesign of the configuration model — new sections, fields, or
  defaults.
- Changes to tool package discovery, installation, or the trust model.
- Amendments to git-derived project identity (the config domain's git
  introspection stays read-only and outside the surface).

## Success Criteria

- **SC1.** A tool package subscribed to the config action receives,
  during a real command run, the read-only view of the authored loaded
  project configuration, environment mappings included with their
  values.
- **SC2.** A subscribed tool shapes the current run: a `set` on a path
  where the authored configuration is silent changes what the command
  consumes; a `force` overwrites an authored value — verified by the
  command behaving per the amended effective configuration.
- **SC3.** The checkpoint is reached uniformly: each command that loads
  the project configuration today offers it (verified across the
  config-consuming commands).
- **SC4.** After a run with amendments applied, the authored
  `.goga/config.yml` on disk is byte-identical to before the run.
- **SC5.** A `set` targeting an authored value changes nothing and fails
  nothing (no warning, no error); the same path amended with `force`
  takes effect.
- **SC6.** The run output names each applied amendment — tool, path,
  set/forced — so the effective configuration is explainable from the
  run output alone.
- **SC7.** Two tools amending the same not-authored path: the later
  tool in enumeration order wins; each hook saw only the authored
  configuration; repeated runs with the same tools and file produce the
  same effective configuration.
- **SC8.** With no tool packages installed — and with installed but
  unsubscribed tools — every config-loading command behaves exactly as
  before the change: identical output and exit codes, no summary, no
  registry assembly for config.
- **SC9.** A failing hook (or structurally malformed contribution)
  during the config checkpoint stops the command with a clean error
  naming the tool and the action; none of that tool's amendments reach
  the effective configuration; the command does not run.
- **SC10.** The tool-author contract is published in the project's usage
  docs in the established form — a tool author can build against the
  checkpoint without reading goga source.
