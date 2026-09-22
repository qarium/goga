# Architecture plan: add-hooks-to-config

Open the config domain to tool hooks via an in-memory amendment checkpoint: one hard
action — `config / amend_config` — delivered over the existing hooks platform at the
project-configuration load moment, with the `lang` -> `language` model rename and the
uniform switch of the nine host-side config-consuming surfaces. Normative inputs:
`task.md` + `adr.md` (accepted — authoritative for every contract axis) + `prd.md` in
this topic directory. Design provenance: the brainstorm pipeline reports (intake,
context, primary analysis, type map, type detail, cell distribution, contracts, cell
assembly) — all user-approved; the contracts were approved cell-by-cell (gates A-D),
with one recorded adjustment: the facade `goga/config` does not embed the zone
(distribution D4, Option 2) — consumers wire to `goga/config/hooks` directly, following
the `goga/pipeline` <- `goga/pipeline/hooks` precedent.

## Topic

- Short name: **add-hooks-to-config**
- Plan path: `.goga/history/2026/add-hooks-to-config/arch.md`

## Implementation Order

Leaves -> root (a cell is assembled only after its providers):

1. **`goga/hooks/catalog`** (modify, additive) — no Imports (leaf); one catalog record.
2. **`goga/config/project`** (modify) — no Imports (leaf); the `lang` -> `language`
   rename the zone's path vocabulary depends on.
3. **`goga/config/hooks`** (create) — depends on `goga/hooks` (platform facade,
   unchanged) and `goga/config/project` (model types for the read view, the merge
   base, and the type-tree validation); the new zone — the core of the change.
4. **`goga/config`** (modify, docs-only) — after the zone: the CODEMANIFEST stays
   unchanged; the two usage files reference the zone's surface and the renamed
   accessor.
5. **`goga/usages/status`**, **`goga/usages/sync`** (modify) — depend on `goga/config`
   and `goga/config/hooks`; config-driven modules switch their load step and print
   the summary themselves.
6. **`goga/commands/{lint,contract,config,install,topics,build,pipeline}`** (modify) —
   depend on `goga/config` + `goga/config/hooks` (their domain dependencies are
   unchanged); the host CLI surfaces — switch + stderr summary; `contract` and
   `config` additionally carry the rename touch points.

## Artifacts

Full DSL for the created cell; add/change/delete diffs with the full new or changed
type blocks for modified cells. `unchanged` marks types kept as-is.

### 1. `goga/hooks/catalog/CODEMANIFEST` (modify, additive)

Header, body structure, and footer unchanged. `declared_actions` Requirements
**gain** (after the existing records; no existing record changes):

```yaml
    - The catalog carries the config amendment action — the record
      domain="config", name="amend_config", error_class="hard": the first
      failing tool of the action stops the command with a clean error
      naming the tool and the action; a structurally malformed
      contribution of the delivery is treated identically
```

### 2. `goga/config/project/CODEMANIFEST` (modify — rename)

Header (Usages: `convention`, inline `yaml`; global Annotations) unchanged.
Footer unchanged. Body — changed type blocks:

```yaml
"ProjectConfig(language: str, image: str | None, dockerfile: str | None, build: BuildConfig | None, pipeline: PipelineConfig | None, commands: dict, codemanifest: CodemanifestConfig | None, tools: dict[str, str] | None, usages: dict[str, dict[str, DepConfig]] | None = None, lint: LintConfig | None = None, topics: TopicsConfig | None = None)":
  location: config.py
  annotations: |
    Root project configuration object. Constructed by load_project_config.

    `language`: project language directive
    `image`: top-level Docker image shared by build and pipeline; None is a valid value
    `dockerfile`: top-level path to a project Dockerfile; None is a valid value
    `build`: build configuration in the two-part form as a `BuildConfig`
             instance, or None when the build section is absent in
             .goga/config.yml
    `pipeline`: pipeline configuration as a `PipelineConfig` instance, or None
                when the pipeline section is absent in .goga/config.yml
    `commands`: command hooks — reserved for future prompt customization
    `codemanifest`: CODEMANIFEST configuration as a `CodemanifestConfig` instance
    `tools`: optional raw mapping of goga-tool version declarations; values are
             strings in the four-form grammar (1.0.x, 1.x, 1.0.1, latest) but
             the loader performs NO semantic validation — invalid values pass
             through verbatim and surface as ValueError at the consumer's
             resolution step
    `usages`: optional usages-sync declarations from the `usages` section, as a
              dict[str, dict[str, DepConfig]] or None; defaults to None at the
              dataclass level (kw_only), matching commands/codemanifest/tools,
              so existing ProjectConfig(...) call sites that omit usages= remain
              valid
    `lint`: optional lint configuration; instance of `LintConfig` or None when
            the lint section is absent; defaults to None (kw_only); callers may
            omit lint=
    `topics`: optional fast-creation configuration; instance of
              `TopicsConfig` or None when the topics section is absent;
              defaults to None (kw_only), callers may omit topics=
  properties:
    "language -> str": |
      Project language. Sourced from the root language directive in .goga/config.yml.
```

All other `ProjectConfig` properties, and the types `BuildConfig`, `ReviewConfig`,
`AdditionalReviewConfig`, `PipelineConfig`, `CodemanifestConfig`, `LintConfig`,
`TopicsConfig`, `DepConfig` — **unchanged**.

`load_project_config` — signature and Requirements/Constraints unchanged except
Algorithm step 4:

```yaml
    4. Extract and validate the top-level fields (language, image, dockerfile);
       the language key is required — a missing key raises KeyError
```

**Delete:** the `lang` property (replaced by `language` above).

### 3. `goga/config/hooks/CODEMANIFEST` (create — full file)

**Cell facade note (python rules):** `__init__.py` of `goga/config/hooks` exposes the
full contract API through `__all__` (the 7 types:
`ConfigHooks`, `ConfigAmendment`, `PathAmendment`, `ToolAmendment`,
`merge_config_amendments`, `ConfigOverlay`, `AppliedAmendment`).

```yaml
Imports:
  - Types:
      - HookRegistry
      - wrap_context
      - build_hook_arguments
      - declared_actions
    Usages:
      - per-tool-delivery
      - registering-hooks
    From: goga/hooks
  - Types:
      - ProjectConfig
      - BuildConfig
      - ReviewConfig
      - AdditionalReviewConfig
      - PipelineConfig
      - CodemanifestConfig
      - DepConfig
      - LintConfig
      - TopicsConfig
    From: goga/config/project

Usages:
  convention: .goga/usages/conventions.md

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and
    testing in the project

  This cell owns the hooks zone of the config domain: the read-and-amend
  context of the project-configuration load moment, the deterministic
  in-memory amendment merge, and the checkpoint surface that delivers the
  amendment over the platform facade. One registry per run carries every
  checkpoint of a command — the checkpoints never multiply the package
  enumeration. Every context is built from the operation data the caller
  passes — no repository, git, or file reads happen here. The amendment
  action is hard: the first failing tool — a crashed hook or a
  structurally malformed contribution — stops the command with a clean
  error naming the tool and the action, and the tool's whole contribution
  is discarded. Tools are mutually blind — every amendment view reads the
  authored configuration, never another tool's staged or committed state;
  each tool's contributions commit as a unit, in enumeration order. The
  amendment lives in memory for the current run — the authored
  configuration file is never modified. The read view delivers the
  authored values — environment mappings included with their values;
  secrecy is enforced on the output side: no configuration value ever
  appears in the summary lines, warnings, or errors.
  Use the `per-tool-delivery` practice for the staged delivery loop of the
  amendment checkpoint — its loop skeleton, primitives, and tool-grouped
  commit apply as written.
  Use the `registering-hooks` practice for the hook signature and the
  failure handling behind the checkpoint.
  Use relative imports.

---

"ConfigAmendment(config: ProjectConfig)":
  location: amendments.py
  annotations: |
    The read-and-amend view of one tool — the delivered facts of the
    amendment checkpoint and the buffer of this tool's contributions.

    `config`: the authored loaded project configuration — values included,
               environment mappings included with their values

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
    Use the `registering-hooks` practice for the hook signature that
    receives this view.

    Requirements:
    - The reads deliver the authored configuration — read-only and
      identical for every tool; a tool never sees another tool's
      contribution
    - The buffered contributions belong to this tool alone
  properties:
    "config -> ProjectConfig": |
      The authored loaded project configuration — the settings sections
      and their values, environment mappings included with their values;
      read-only for the receiving hook.
  methods:
    "set(path: str, value: str | int | bool | list[str])": |
      Buffer one amendment that applies only where the authored
      configuration is silent at the path.

      `path`: the dotted leaf path in the authored vocabulary
      `value`: the amendment value

      Requirements:
      - The call buffers into the buffer of this tool alone and changes
        nothing until the delivery commits it
      - A later amendment of this tool on the same path replaces its
        earlier one
      - A set on a path where the authored configuration is not silent
        is dropped silently — not an error, no warning

      Constraints:
      - Do not cancel, redirect, or defer the operation — an amendment
        transforms the effective configuration layer only
    "force(path: str, value: str | int | bool | list[str])": |
      Buffer one amendment that overwrites the authored value at the
      path — the tool's explicit override intent.

      `path`: the dotted leaf path in the authored vocabulary
      `value`: the amendment value

      Requirements:
      - The call buffers into the buffer of this tool alone and changes
        nothing until the delivery commits it
      - A later amendment of this tool on the same path replaces its
        earlier one

      Constraints:
      - Do not cancel, redirect, or defer the operation — an amendment
        transforms the effective configuration layer only

"PathAmendment(path: str, intent: str, value: str | int | bool | list[str])":
  location: amendments.py
  annotations: |
    One buffered amendment — the addressed leaf path, the intent, and the
    value.

    `path`: the dotted leaf path in the authored vocabulary
    `intent`: exactly set or force
    `value`: the amendment value

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Pure data — constructed by the amendment buffer alone

"ToolAmendment(tool: str, amendments: list[PathAmendment])":
  location: overlay.py
  annotations: |
    The committed contribution of one tool — the pairing of the tool
    identity with its ordered path amendments.

    `tool`: the tool identity assigned by the platform
    `amendments`: the committed contributions of the tool, in buffer
                   order

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

"AppliedAmendment(tool: str, path: str, intent: str)":
  location: overlay.py
  annotations: |
    One applied amendment — the winning contribution of one path.

    `tool`: the tool identity whose amendment won the path
    `path`: the applied dotted leaf path
    `intent`: exactly set or forced

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Carries no value — no configuration value travels into any output

"ConfigOverlay(config: ProjectConfig, applied: list[AppliedAmendment])":
  location: overlay.py
  annotations: |
    The result of the amendment layer — the effective configuration and
    its applied amendments.

    `config`: the effective (in-memory, per-run) configuration
    `applied`: the applied amendments in enumeration order — one record
                per applied path, the winning amendment

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - The effective configuration is a `ProjectConfig` — every downstream
      consumer of the run observes it
  properties:
    "config -> ProjectConfig": |
      The effective configuration of the run — the authored configuration
      with the applied amendments merged in memory.
    "applied -> list[AppliedAmendment]": |
      The applied amendments in enumeration order — one record per
      applied path.
    "summary_lines -> list[str]": |
      The composed amendment summary — one header line plus one line per
      applied amendment (the tool, the path, set or forced), in
      enumeration order; empty when nothing applied. No configuration
      value ever appears in a line.

"merge_config_amendments(base: ProjectConfig, contributions: list[ToolAmendment]) -> overlay: ConfigOverlay":
  location: overlay.py
  annotations: |
    The deterministic amendment merge — compose the effective
    configuration from the authored base and the committed tool
    contributions.

    `base`: the authored loaded configuration
    `contributions`: the committed contributions in enumeration order
    `overlay`: the effective configuration with the applied amendments

    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. Validate every amendment of every contribution against the
       configuration model's type tree — the fields of `ProjectConfig`
       and of the section models `BuildConfig`, `ReviewConfig`,
       `AdditionalReviewConfig`, `PipelineConfig`, `CodemanifestConfig`,
       `DepConfig`, `LintConfig`, `TopicsConfig`, with arbitrary keys
       admitted under mapping-typed fields. A path is known iff it
       resolves to a leaf of the tree: a scalar leaf, a list-valued leaf,
       or an individual mapping entry. An unknown path, a non-leaf
       address, or a value of the wrong type at the node is a structural
       failure of the contributing tool — raise naming the tool and the
       malformedness; no amendment of the run applies
    2. Resolve each path deterministically: authored silence at a path
       means the loaded model carries an absence marker — None, an empty
       mapping, or an empty list; authored emptiness loses to set. A set
       on a non-silent authored path is dropped silently. On one path
       force beats any set regardless of enumeration order; among
       amendments of equal intent the later tool in enumeration order
       wins
    3. Compose the effective configuration: apply each winning amendment
       to the `base` in memory — materialize the missing intermediate
       nodes of a model-known path, replace list-valued leaves wholesale,
       set individual mapping entries, reconstruct the affected
       configuration instances
    4. Collect one `AppliedAmendment` per applied path — the winning
       tool, the path, set or forced — in enumeration order
    5. Return the `ConfigOverlay`

    Requirements:
    - Deterministic — the same base and the same contributions give the
      same overlay
    - Pure — the inputs stay unmutated; the result is a new
      configuration
    - The commands mapping is free-form — any key under it addresses a
      value without a node type check
    - The result is a structurally valid configuration — every applied
      value matches the node it landed on

    Constraints:
    - Do not read or write the filesystem — the authored file stays
      untouched
    - Do not validate the semantics of well-formed values — the consumers
      own semantic validation
    - Do not mutate `base`, the contributions, or their collections

"ConfigHooks()":
  location: events.py
  annotations: |
    The checkpoint surface of the config domain — the amendment delivery
    over the platform facade.

    Apply the `convention` practice for the code style and intra-package
    imports.
    Use the `per-tool-delivery` practice for the staged delivery loop of
    the amendment checkpoint.
    Use the `registering-hooks` practice for the registration contract
    behind the checkpoint.

    Requirements:
    - Cheap construction — no enumeration and no imports happen at
      construction
    - One `HookRegistry` per run carries every checkpoint of a command —
      the assembly runs once per run whatever the number of checkpoints
    - Every context is built from the values the caller passes — no
      repository, git, or file reads happen at the checkpoint
  methods:
    "amend_config(config: ProjectConfig) -> overlay: ConfigOverlay": |
      Deliver the config-amendment checkpoint and return the effective
      configuration with its applied amendments.

      `config`: the authored loaded project configuration — operation
                 data handed over by the calling command
      `overlay`: the effective configuration and the applied amendments

      Use the `per-tool-delivery` practice for the delivery loop.

      Algorithm:
      1. Resolve the address domain="config", action="amend_config"
         against `declared_actions`
      2. Walk the subscriptions of the address per tool in enumeration
         order: build the tool's `ConfigAmendment` view over the
         delivered facts — every tool reads the same authored `config` —
         wrap it via `wrap_context`, project the call arguments via
         `build_hook_arguments` with the tool's own context, and call
         each hook of the tool
      3. A tool whose every hook returned without raising commits as one
         `ToolAmendment` — a tool whose buffer carries no amendment
         commits nothing
      4. A tool with a raising hook is a hard failure: a clean error
         naming the tool and the action stops the command at the first
         failure; the tool's contribution is discarded
      5. Merge the committed contributions onto `config` via
         `merge_config_amendments`; a structural failure raised there is
         the same hard failure — the clean error names the tool and the
         action, nothing applies
      6. Return the overlay

      Requirements:
      - The commit granularity is the tool — a tool's whole contribution
        commits only after every hook of the tool succeeds
      - An address without subscriptions returns the passthrough overlay
        — the configuration passed in, an empty applied list, empty
        summary lines; the delivery is unobservable
      - With no tool packages installed the load composes exactly what
        was passed

      Constraints:
      - Do not apply any contribution outside the single merge after the
        walk
      - Do not skip a subscriber of the address
      - Do not read repositories, git, or the filesystem at the checkpoint
      - Do not print — the summary lines are data; the caller acts on
        them

---

Author: Goga
CreatedAt: 22/09/26
Description: |
  Owner of the config domain hooks zone — the read-and-amend context, the
  in-memory amendment merge, and the checkpoint surface over the hooks
  platform.
```

### Cell usage file: `goga/config/hooks/.usages/checkpoints.md` (create — full content)

```md
# config — amending the project configuration

How the config-consuming operations use the hooks zone of the config
domain: delivering the amendment checkpoint at the project-configuration
load moment and consuming the effective configuration. For every
host-side command and config-driven module that loads .goga/config.yml.

## The checkpoint surface

One `ConfigHooks` object serves the checkpoint of a run — the surface
shares one registry per run, so a command that reaches further checkpoints
enumerates the tool packages once.

```python
from goga.config.hooks import ConfigHooks

hooks = ConfigHooks()
```

## Amend at the load moment

Load the authored configuration, hand it to the zone entry, and consume
the effective configuration the delivery returns. Print the composed
summary lines to stderr; stdout stays data-clean.

```python
from goga.config import load_project_config

config = load_project_config()    # authored load — the loader stays hooks-free
overlay = hooks.amend_config(config=config)
print_summary_to_stderr(overlay.summary_lines)
consume(overlay.config)           # every downstream consumer of the run
```

- The delivered context is built from the values you pass — the checkpoint
  reads no repository, no git, no files.
- Tools are mutually blind: every hook read the authored configuration,
  never another tool's contribution; each tool's contributions commit as a
  unit, in enumeration order.
- The amendment action is hard: the first failing tool — a crashed hook or
  a structurally malformed contribution — stops the command with a clean
  error naming the tool and the action.
- An address without subscriptions returns the passthrough overlay — the
  configuration passed in, an empty applied list, empty summary lines.
  With no tool packages installed the load composes exactly what was
  passed.
- The authored .goga/config.yml is never modified — the effective
  configuration lives in memory for the current run; repeated runs with
  the same tools and file reproduce it deterministically.
- Values never appear in the summary — the lines carry the tool, the path,
  and set or forced only.

## In-container loads stay authored-only

The in-container entry points (`python -m goga.build` and any in-container
pipeline counterpart) load the authored configuration directly and
deliver no checkpoint — in-container loading is the correct behavior for
the build and pipeline domains.
```

### 4. `goga/config` (modify — docs-only; CODEMANIFEST unchanged)

Imports, Usages, Annotations, embeddings, body, and footer of the facade
CODEMANIFEST are **unchanged** (the facade stays the behavior-free re-export of
project/home/git configuration types; the zone is wired directly by its consumers).
Two usage-file artifacts change:

**Create `goga/config/.usages/registering-hooks.md`** — full content:

```md
# config — registering hooks

How a `goga_tool_*` package subscribes its hooks to the config domain
action. For tool package authors; no goga code changes are needed.

The domain opens one action — the configuration amendment. It is a
read-and-amend view over the authored project configuration, delivered at
the load moment of `.goga/config.yml`, after the authored file is loaded
and before any consumer reads the configuration. It is a hard action.

## The events

| Address | Error class | Fires |
|---|---|---|
| `config / amend_config` | hard | At the project-configuration load moment of every host-side command that loads `.goga/config.yml` (pipeline, lint, contract, install, config, build, topics, usages status, usages sync). In-container loads stay authored-only and fire nothing. |

A failing moment fires nothing: a missing or structurally invalid
configuration file fails in the loader before the checkpoint.

## Subscribe

```python
def register_hooks(hooks):
    hooks.subscribe("config", "amend_config", "hardening", harden_config)
```

- `domain` — always `"config"`; `action` — from the table; `name` — unique
  per tool per address; `hook` — the callable executed when the event
  fires.
- A hook receives values only for the parameters it declares by the fixed
  offered names: `context`, `self`.

## The amendment view

`amend_config` delivers a `ConfigAmendment` view per tool. The reads:
`config` — the authored loaded project configuration itself, read-only,
values and environment mappings included with their values (attribute
assignment is blocked). Compose new environment values from the existing
ones freely — secrecy is enforced on the output side: goga never prints
a configuration value.

```python
def harden_config(context):
    if context.config.build is None:
        context.set("build.agent", "claude")        # applies only where authored is silent
    context.set("pipeline.env.LOG_LEVEL", "DEBUG")  # materializes the absent branch
    context.force("topics.base_ref", "origin/main") # overwrites the authored value
```

- `set(path, value)` buffers an amendment that applies only where the
  authored configuration is silent at the path — the absence markers of
  the loaded model (`None`, `{}`, `[]`); authored emptiness loses to
  `set`.
- `force(path, value)` buffers an amendment that overwrites the authored
  value — the explicit override intent.
- Paths address model-known leaves in the authored vocabulary — the same
  keys the file uses: `language`, `image`, `build.agent`,
  `build.env.KEY`, `build.review.roles` (a list-valued leaf, replaced
  wholesale), `build.review.additional.patience`,
  `pipeline.env.KEY`, `tools.<name>`, `usages.<group>.<dep>.ref`,
  `lint.ignore`, `topics.base_ref`, and every other leaf of the
  configuration model. A model-known path stays addressable when its
  intermediate branch is absent — the amendment materializes the missing
  nodes.
- A later amendment of your tool on the same path replaces its earlier
  one.

## The merge rules

The contributions merge deterministically — the same tools and the same
authored file always produce the same effective configuration:

- Authored-wins by default: a `set` on a path where the authored
  configuration is not silent is dropped silently — no warning, no error.
- On one path `force` beats any `set` regardless of enumeration order.
- Among amendments of equal intent the later tool in enumeration order
  wins.
- Tools are mutually blind — every hook reads the authored configuration;
  each tool's contributions commit as a unit, in enumeration order.

## Failure treatment

The action is hard. The first failing tool stops the command with a clean
error naming the tool and the action; the failing tool's whole
contribution is discarded — nothing partial is applied, the command does
not run. A structurally malformed contribution — an unknown path, a
non-leaf address, or a value of the wrong type for the node — fails the
same way. Semantic validity of well-formed values stays with the
consumers, exactly as with the authored file.

## The run output

When amendments are applied, the command prints a short summary to
stderr: one header plus one line per applied amendment — the tool, the
path, set or forced — in enumeration order. Configuration values
(including environment values) never appear in the summary or any
informational output. `goga config` stdout stays data-clean and prints
effective (amended) values. With no applied amendments nothing is
printed. The authored file is never modified — after the run it is
byte-identical, and repeated runs reproduce the same effective
configuration.

## Integration scenarios

- **Config-aware decisions** — read `context.config` (is a build agent
  configured? which review roles? which env keys present?) and shape your
  contributions to the other domains accordingly.
- **Prepared parameter set on a minimal config** — `set` the knobs the
  author left unset; the absent branches materialize.
- **Risk mitigation** — `force` a safer value over a risky authored one;
  the override is visible in the summary.
- **Routine setup simplification** — `set` `pipeline.env.KEY` entries the
  author did not write, composed from the values you read.
```

**Update `goga/config/.usages/project-configuration.md`** — deltas:

- The `lang` accessor example (`config.lang  # str — project language`) becomes `config.language  # str — project language`; the immutability example (`replace(config, lang="go")`) becomes `replace(config, language="go")`.
- The "Loading Configuration" chapter gains the zone-entry note (load stays authored-only; the amendment checkpoint belongs to the consumer; the note is self-contained — no reference to other practices):
  ```md
  `load_project_config` performs the authored load only — no hooks fire
  inside it. A host-side command that offers the config amendment
  checkpoint hands the loaded configuration to the zone entry
  (`goga.config.hooks`) and consumes the effective configuration the
  delivery returns.
  ```

### 5. `goga/usages/status` and `goga/usages/sync` (modify)

### 6. `goga/commands/{pipeline,lint,contract,install,config,build,topics}` (modify)

Common wiring for all nine consumer CODEMANIFESTs plus the per-cell annotation deltas:



**Common import block added to every consumer CODEMANIFEST** (alongside the existing `From: goga/config` block, which stays):

```yaml
  - Types:
      - ConfigHooks
      - ConfigOverlay
    Usages:
      - checkpoints
    From: goga/config/hooks
```

**Common global-annotation clause added** (commands):

```yaml
  Use the `checkpoints` practice for the config amendment checkpoint at
  the project-configuration load moment — the command loads the authored
  configuration, delivers the checkpoint, consumes the effective
  configuration of the returned `ConfigOverlay`, and prints the amendment
  summary lines to stderr.
```

**Common algorithm-step replacement at the load moment** (worded per cell below): load via `load_project_config` → deliver `ConfigHooks().amend_config(config=…)` → consume `overlay.config` downstream → print `overlay.summary_lines` to stderr per the `click` practice (nothing when empty).

---

**`goga/commands/pipeline`** — Algorithm step 1 becomes: load the configuration via `load_project_config` (fail fast on schema errors), deliver the config amendment checkpoint per the `checkpoints` practice, and treat the effective configuration of the `ConfigOverlay` as the run's configuration — the missing-pipeline-section guard and every downstream read address the effective configuration; the home configuration load stays authored-only (closed surface). Requirements add: the amendment summary prints to stderr; stdout unchanged.

**`goga/commands/lint`** — the ignore-derivation step: a successful load delivers the checkpoint and derives `ignore` from the effective configuration of the `ConfigOverlay`; a failed/absent load runs lint unfiltered and offers no checkpoint — nothing was loaded. Requirements add: the summary prints to stderr.

**`goga/commands/contract`** — Algorithm step 1 delivers the checkpoint after the load; step 2 (language resolution) reads the effective configuration: CLI `lang` argument when given, otherwise the `language` field of `ProjectConfig` (renamed field; the CLI option surface is unchanged). Requirements add: the summary prints to stderr.

**`goga/commands/install`** — every configuration load of the command flows (the bulk-mode resolution path) delivers the checkpoint and resolves the tools mapping from the effective configuration of the `ConfigOverlay`; the local path loads no configuration and offers no checkpoint. Requirements add: the summary prints to stderr.

**`goga/commands/config`** — Algorithm step 1 delivers the checkpoint; the traversal runs over the effective configuration of the `ConfigOverlay` — the printed values are the effective (amended) ones; dot-notation resolves the `language` field directly (no alias map between the authored key and the model field). Requirements add: the amendment summary prints to stderr while stdout stays the data-clean value surface (headers + values only); exit codes unchanged.

**`goga/commands/build`** — Algorithm step 2 delivers the checkpoint right after the authored load; the `config.build is None` guard and every downstream field access address the effective configuration of the `ConfigOverlay`; the home configuration load stays authored-only. Requirements add: the summary prints to stderr.

**`goga/commands/topics`** — the configuration load delivers the checkpoint; the base-ref and template resolution read the effective configuration of the `ConfigOverlay`. Requirements add: the summary prints to stderr.

**`goga/usages/status`** — Algorithm step 1 becomes: load the configuration via `load_project_config`, deliver the config amendment checkpoint per the `checkpoints` practice, print the amendment summary lines of the `ConfigOverlay` to stderr (nothing when empty), and iterate the declared deps of the effective configuration. Usages of the cell gain the `click` practice (stderr output). Constraints change: the constraint `Do not print — rendering belongs to the command` becomes `Do not print the report — report rendering belongs to the command; the amendment summary lines of the 'ConfigOverlay' print to stderr per the 'click' practice`.

**`goga/usages/sync`** — Algorithm step 1 becomes: load the configuration via `load_project_config`, deliver the config amendment checkpoint per the `checkpoints` practice, print the amendment summary lines of the `ConfigOverlay` to stderr (nothing when empty), and read the usages declarations of the effective configuration. Usages of the cell gain the `click` practice (stderr output).

**Deliberately unchanged:** `goga/build` (the in-container `main` keeps the pure authored loader), `goga/commands/usages` (owns no configuration load; the summary printing belongs to `status`/`sync`).

## Dependency Map

```
goga/hooks/catalog (+1 record) --> goga/hooks (unchanged facade) --\
                                                                    \ 4 types + per-tool-delivery /
                                                                     \ registering-hooks
goga/config/project (rename) ----------------------------------------\> goga/config/hooks  (NEW)
                                                                         | 7 types + checkpoints.md
             config types + project-configuration (existing edge)         | ConfigHooks, ConfigOverlay
              ------------------------------------------------------------         + checkpoints
              |                                                            |
  goga/config (facade, CODEMANIFEST unchanged;                             |
  docs: registering-hooks.md NEW, project-configuration.md UPDATED)       |
              ^ config types (existing imports)                            |
              |                                                            |
  +-----------+-------------------------+        +-------------------------+---------+
  | goga/commands/{pipeline,lint,       |        | goga/usages/{status,sync}         |
  | contract,install,config,build,      |        | (print the summary themselves)    |
  | topics} (switch + stderr summary)   |        | (switch + stderr summary)         |
  +-------------------------------------+        +-----------------------------------+

Unchanged by design: goga/build `main` (in-container authored-only load),
goga/commands/usages (owns no configuration load), the whole hooks platform
beyond the additive catalog record.
```

No circular imports: `goga/config/hooks` imports only `goga/hooks` and
`goga/config/project`; the facade `goga/config` is imported by consumers only; no
consumer is imported by any provider.

## Verification Checklist

After each artifact lands:

- **`goga lint`** passes over every modified/created CODEMANIFEST (DSL syntax:
  casing, signature rules, `location` restrictions, section order, import/usage
  link rules).
- **Facade checks** — `python -c "from goga.config.hooks import ConfigHooks,
  ConfigAmendment, PathAmendment, ToolAmendment, merge_config_amendments,
  ConfigOverlay, AppliedAmendment"`.
- **Absence checks** (breaking removals): no reference to the model field `lang`
  anywhere in goga sources, tests, or usage docs — the model field, the loader
  construction, the `goga config` alias bridge, and the `goga contract` resolution
  all use `language`; the CLI `--lang` option of `goga contract` is unchanged.
- **Catalog check**: `declared_actions()` carries the `config / amend_config`
  record; the existing records are byte-identical.
- **Schema check**: `goga schema` shows `goga/config/hooks` with 7 types and its
  dependencies on `goga/hooks` and `goga/config/project` only.
- **Tests**: `pytest tests/ -x` (new unit tests mirror the source structure —
  `tests/config/hooks/test_{amendments,overlay,events}.py`; consumer switch and
  rename covered in the per-command test modules; integration scenarios in
  `tests/integration/`); `ruff check` over the touched packages.
- **Passthrough check**: with no tool packages installed, every config-loading
  command produces byte-identical output and exit codes; the authored
  `.goga/config.yml` is byte-identical after runs with amendments applied.
- **Merge-algebra checks** (unit, per the ADR): `set` on a silent path applies;
  `set` on an authored value is a silent no-op; `force` overwrites authored
  values; on one path `force` beats `set` regardless of enumeration order; among
  equal intent the later tool wins; within one tool the later same-path amendment
  replaces the earlier; absent intermediate branches materialize; list leaves
  replace wholesale; unknown path / non-leaf address / wrong-typed value stop the
  command with a clean error naming the tool and the action and discard the whole
  tool contribution; repeated runs reproduce the same effective configuration.
- **Summary checks**: one header plus one line per applied amendment in
  enumeration order, printed to stderr by every switched command; `status`/
  `sync` print it themselves; nothing printed when nothing applied; no
  configuration value (env values included) ever appears in summary, warnings,
  or errors; `goga config` stdout stays data-clean (headers + effective values).
- **Uniform-reach check**: each of the nine host-side surfaces delivers the
  checkpoint (pipeline, lint, contract, install, config, build, topics, usages
  status, usages sync); the in-container `goga/build` `__main__` entry keeps the
  pure authored loader.
- **Docs**: `registering-hooks.md` answers every tool-author scenario (read for
  decisions, prepared parameter set, risk mitigation, routine setup) from the
  events table, the view members, and the failure semantics alone;
  `project-configuration.md` shows the `config.language` accessor and the
  zone-entry note.
- **Acceptance criteria** of `task.md` re-checked against the implemented
  behavior (all ten mapped in the cell-assembly report).
