# Architecture plan: add-hooks-to-build

Open the build domain over a stable two-pass cycle with a verdict-collecting
gate. Normative inputs: `task.md` + `adr.md` (accepted) + `prd.md` in this
topic directory. Design provenance: the brainstorm pipeline reports (intake,
context, primary analysis, type map, type detail, cell distribution,
contracts, cell assembly) — all user-approved.

## Topic

- Short name: **add-hooks-to-build**
- Plan path: `.goga/history/2026/add-hooks-to-build/arch.md`

## Implementation Order

Leaves → root (a cell is assembled only after its providers):

1. **`goga/config/project`** (modify) — no Imports (leaf); the settings model
   everything else consumes.
2. **`goga/config`** (modify, mechanical) — depends on `goga/config/project`
   (embeddings); re-export list tracks the reshaped names.
3. **`goga/ralphex`** (modify) — no Imports (leaf); options table extension.
4. **`goga/hooks/catalog`** (modify, additive) — no Imports (leaf); five
   `build` records.
5. **`goga/build/hooks`** (create) — depends on `goga/hooks` (facade,
   unchanged); the new zone consumes only the platform facade.
6. **`goga/build`** (modify) — depends on `goga/config`, `goga/agents`,
   `goga/docker`, `goga/ralphex`, `goga/build/hooks`, `goga/history`; the
   core restructure + checkpoint integration.
7. **`goga/commands/build`** (modify) — depends on `goga/config`,
   `goga/build`, `goga/agents`, `goga/runtime`, `goga/docker`; the host CLI
   surface.
8. **`.goga/config.yml`** (dogfooding migration) — after the config cells:
   this repository's own build section migrates to the two-part form in the
   same change (the old block names become unknown keys and would silently
   disable the build section).

## Artifacts

Full DSL for created cells; add/change/delete diffs with the full new or
changed type blocks for modified cells. `unchanged` marks types kept as-is.

### 1. `goga/config/project/CODEMANIFEST` (modify)

**Delete types:** `TaskExecutorConfig`, `ReviewExecutorConfig`.

**Header (Usages/Annotations):** keep `convention` and the inline `yaml`
practice; extend the global Annotations with the two-part stance (see the
assembled DSL below).

```yaml
Usages:
  convention: .goga/usages/conventions.md
  yaml: |
    Use yaml.safe_load() to parse .goga/config.yml.
    Requires the PyYAML library.

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and testing in the project

  All data model classes in this cell are immutable dataclasses
  (frozen=True, kw_only=True), per `convention`. Use the standard library
  dataclasses module — NOT pydantic (pydantic is treated as tech debt in this
  project).

  Use the `yaml` practice for parsing .goga/config.yml via yaml.safe_load().

  The cell enforces structural validation only; semantic validation is
  deferred to the owning consumers.

  The build section is two-part: the `build` root carries the tasks-pass
  settings source (agent, env, max_iterations, session_timeout, idle_timeout,
  wait, prompts_dir, agents_dir, proxy, hosts); the `build.review` key carries
  the review-pass settings source (skip, agent, env, roles, base_ref,
  strategy, finalize, additional, and the session knobs). The loader extracts
  known fields only — unknown keys, including a stale `worktree`, are silently
  ignored; the retired keys `worktree`, `skip_finalize`, `codex_review` and
  the retired block names `task_executor` / `review_executor` are not
  extracted. Inheritance (review from root, additional.agent from
  review.agent) belongs to the consuming cell — values are exposed verbatim
  with no default merging.
```

**Body — full new/changed type blocks:**

```yaml
"load_project_config() -> config: ProjectConfig":
  location: loader.py
  annotations: |
    Parses .goga/config.yml from the project root and returns a ProjectConfig instance.

    Algorithm:
    1. Locate .goga/config.yml in the project root
    2. Parse the YAML via the `yaml` practice
    3. Validate the parsed document is a mapping; raise FileNotFoundError when
       the file is absent/empty, ValueError when it is not a mapping
    4. Extract and validate the top-level fields as today (lang, image,
       dockerfile)
    5. Extract the pipeline block as today (unchanged semantics)
    6. Extract the build block. Absent → build None; present but not a
       mapping → ValueError. From the mapping extract the tasks-pass root
       fields: agent (OPTIONAL — absent/YAML-null/empty/whitespace → None; a
       non-string value → ValueError), env (optional string mapping, default
       empty dict), max_iterations (OPTIONAL int — absent/YAML-null → None; a
       non-int value including a YAML boolean → ValueError), session_timeout,
       idle_timeout, wait (OPTIONAL strings — the agent emptiness pattern),
       prompts_dir and agents_dir (OPTIONAL strings), proxy (OPTIONAL string),
       hosts (optional string mapping, default empty dict). Unknown keys of
       the mapping are ignored — the loader extracts known fields only
    7. Extract the optional review sub-mapping of build: absent/YAML-null →
       review None; present but not a mapping → ValueError. Fields: skip
       (absent/null → None; non-bool → ValueError); agent (the agent
       pattern); env (the env pattern); roles (absent/null → None; non-list
       or a non-string element → ValueError; an empty list passes verbatim);
       base_ref (the agent pattern); strategy (absent/null/empty/whitespace →
       None; non-string → ValueError — structural typing only, the
       full|medium|short whitelist belongs to the consumer); finalize
       (absent/null/empty/whitespace → None; non-string → ValueError — the
       user-authored final review prompt, stored verbatim); additional
       (absent/null → None; present but not a mapping → ValueError; inside:
       agent — the agent pattern; patience — absent/null → None, non-int
       including a YAML boolean → ValueError; max_iterations — the patience
       pattern); the session knobs (the root pattern). Construct a
       `ReviewConfig` from the resolved fields and an `AdditionalReviewConfig`
       from the additional mapping, and pass them into `BuildConfig`
    8. Extract the codemanifest, lint, topics, commands, tools, and usages
       blocks exactly as today (unchanged)
    9. Construct and return the `ProjectConfig` from all assembled parts

    Requirements:
    - The two-part build model: root tasks-pass fields plus the optional
      review sub-mapping; values verbatim, no default merge — inheritance is
      the consumer's
    - The loader extracts known fields only: a stale worktree key or any
      unknown key is silently ignored — not an error, not stored
    - strategy and finalize are structural string checks — the whitelist and
      the prompt semantics belong to the consumer
    - All existing requirements of the unchanged sections stand as today

    Constraints:
    - Do not validate review semantics (roles whitelist, env-requires-agent,
      base_ref resolvability, strategy whitelist, patience range) — consumer
      territory
    - Do not default-merge root values into review — the consumer applies
      inheritance
    - Do not rename or alias the retired keys — they simply do not exist in
      the model

"ProjectConfig(lang: str, image: str | None, dockerfile: str | None, build: BuildConfig | None, pipeline: PipelineConfig | None, commands: dict, codemanifest: CodemanifestConfig | None, tools: dict[str, str] | None, usages: dict[str, dict[str, DepConfig]] | None = None, lint: LintConfig | None = None, topics: TopicsConfig | None = None)":
  location: config.py
  annotations: |
    Root project configuration object. Constructed by load_project_config.
    (Signature unchanged; the `build` field now holds the reshaped two-part
    `BuildConfig`.)
  properties:
    "build -> BuildConfig | None": |
      Build configuration from .goga/config.yml in the two-part form: the
      root tasks-pass settings and the optional `review` part. Instance of
      `BuildConfig`, or None when the build section is absent. Consumers that
      need it (goga/commands/build) guard the None case and raise
      ClickException before any field access.
    # all other properties unchanged from the current manifest

"BuildConfig(agent: str | None, env: dict[str, str], max_iterations: int | None, session_timeout: str | None, idle_timeout: str | None, wait: str | None, prompts_dir: str | None, agents_dir: str | None, proxy: str | None, hosts: dict[str, str], review: ReviewConfig | None)":
  location: config.py
  annotations: |
    Build execution configuration in the two-part form. Constructed by
    load_project_config from the build section of .goga/config.yml. The root
    fields are the tasks-pass settings source; the review part is the
    review-pass settings source. Inheritance from root into review belongs to
    the consumer.

    `agent`: tasks-pass executor agent name — None when unset
    `env`: tasks-pass environment layer — the review pass never receives it
    `max_iterations`: maximum task iterations
    `session_timeout`, `idle_timeout`, `wait`: session knobs (Go duration strings)
    `prompts_dir`, `agents_dir`: custom ralphex source directories
    `proxy`: optional HTTP/HTTPS proxy URL
    `hosts`: optional host→IP mapping for docker run --add-host
    `review`: the review-pass settings part, or None when absent

    Requirements:
    - All fields may be None; env and hosts default to empty dicts
    - Values stored verbatim, no inheritance applied here
  properties:
    "agent -> str | None": |
      Tasks-pass executor agent name matching the wrapper convention; None
      when unset. Resolution into a wrapper path belongs to the consumer.
    "env -> dict[str, str]": |
      Tasks-pass environment layer ({str: str}), verbatim. Applied as the
      env layer of the tasks pass only — the review pass never receives it.
      Empty dict when absent.
    "max_iterations -> int | None": |
      Maximum number of task iterations of the tasks pass. None when unset.
    "session_timeout -> str | None": |
      Session timeout duration, Go duration format. None when unset.
    "idle_timeout -> str | None": |
      Session idle timeout duration, Go duration format. None when unset.
    "wait -> str | None": |
      Rate-limit retry wait duration, Go duration format. None when unset.
    "prompts_dir -> str | None": |
      Custom ralphex prompt directory path. None when unset.
    "agents_dir -> str | None": |
      Custom ralphex agent directory path. None when unset.
    "proxy -> str | None": |
      Optional HTTP/HTTPS proxy URL for the build container.
    "hosts -> dict[str, str]": |
      Optional host→IP mapping for docker run --add-host flags. Empty dict
      when absent.
    "review -> ReviewConfig | None": |
      The review-pass settings part. Instance of `ReviewConfig`, or None when
      the build.review key is absent. Structural validity is owned by
      `load_project_config`; semantics and inheritance belong to the consumer.

"ReviewConfig(skip: bool | None, agent: str | None, env: dict[str, str], roles: list[str] | None, base_ref: str | None, strategy: str | None, finalize: str | None, additional: AdditionalReviewConfig | None, session_timeout: str | None, idle_timeout: str | None, wait: str | None)":
  location: config.py
  annotations: |
    The `build.review` settings source — the review-pass part of the two-part
    build model. Constructed by load_project_config. Every field is stored
    verbatim; an unset field is None (or an empty dict for env) and means
    "inherit from the root" to the consumer.

    Requirements:
    - Immutable frozen dataclass (frozen=True, kw_only=True), per `convention`
    - No normalization of emptiness, no whitelist; env resolves
      absent/YAML-null/{} to an empty dict

    Constraints:
    - Do not validate role names, agent names, strategy values, or env
      applicability at this level — structural typing only
  properties:
    "skip -> bool | None": |
      Tri-state source for skipping the review pass. None when the field is
      absent.
    "agent -> str | None": |
      Review-pass executor name matching the wrapper convention. None when
      unset — the consumer inherits the root agent.
    "env -> dict[str, str]": |
      Review-pass environment layer, verbatim. Empty dict when absent — the
      consumer inherits nothing for env (the root env is the tasks-pass
      layer and is never inherited).
    "roles -> list[str] | None": |
      Declared reviewer composition, verbatim. None when unset; an empty list
      stays an empty list (the full default set is the consumer-side meaning).
    "base_ref -> str | None": |
      Review diff base — a branch name or a commit hash, verbatim. None when
      unset (normalized by `load_project_config`).
    "strategy -> str | None": |
      Review strategy source — full, medium, or short; None when unset (the
      consumer applies the default medium). Structural typing only.
    "finalize -> str | None": |
      The user-authored final review prompt, verbatim. None when unset — the
      finalize step stays at the ralphex default (off).
    "additional -> AdditionalReviewConfig | None": |
      The external-review block source. Instance of `AdditionalReviewConfig`,
      or None when absent.
    "session_timeout -> str | None": |
      Review-pass session timeout; None inherits the root value.
    "idle_timeout -> str | None": |
      Review-pass idle timeout; None inherits the root value.
    "wait -> str | None": |
      Review-pass rate-limit wait; None inherits the root value.

"AdditionalReviewConfig(agent: str | None, patience: int | None, max_iterations: int | None)":
  location: config.py
  annotations: |
    The `build.review.additional` external-review block source.

    `agent`: external review agent name — None when unset (the consumer
             inherits review.agent)
    `patience`: external-review stop threshold (0 = disabled)
    `max_iterations`: external review iteration cap (0 = ralphex auto)

    Requirements:
    - Immutable frozen dataclass (frozen=True, kw_only=True), per `convention`
    - Values stored verbatim; 0 is a meaningful value, not an unset marker

    Constraints:
    - Do not validate agent names or ranges at this level — structural typing
      only
  properties:
    "agent -> str | None": |
      External review agent name matching the wrapper convention. None when
      unset — the consumer inherits review.agent.
    "patience -> int | None": |
      External-review stop threshold — stop after N consecutive unchanged
      rounds; 0 = disabled. None when unset.
    "max_iterations -> int | None": |
      External review iteration cap; 0 = ralphex auto (max(3,
      max_iterations/5)). None when unset.
```

**Unchanged types:** `PipelineConfig`, `CodemanifestConfig`, `LintConfig`,
`TopicsConfig`, `DepConfig`.

**Footer:** Author: Goga; CreatedAt: 24/07/26 (original); Description updated
to the two-part form.

### 2. `goga/config/CODEMANIFEST` (modify, mechanical)

Imports from `goga/config/project`: **remove** `TaskExecutorConfig`,
`ReviewExecutorConfig`; **add** `ReviewConfig`, `AdditionalReviewConfig`;
keep the rest. Embeddings updated symmetrically:

```yaml
->ProjectConfig: {}
->load_project_config: {}
->BuildConfig: {}
->ReviewConfig: {}
->AdditionalReviewConfig: {}
->PipelineConfig: {}
->CodemanifestConfig: {}
->DepConfig: {}
->LintConfig: {}
->HomeConfig: {}
->DockerArgsConfig: {}
->load_home_config: {}
->resolve_project_name: {}
->TopicsConfig: {}
```

Global Annotations: the re-export clause mentions the two-part build form.
Footer unchanged (Author: Goga, CreatedAt: 31/08/26).

### 3. `goga/ralphex/CODEMANIFEST` (modify)

Header and footer unchanged. `run_ralphex` — options table and requirements
updated (full block):

```yaml
"run_ralphex(plan: str, options: dict[str, str | int | bool], dry_run: bool, env: dict[str, str] | None = None) -> exit_code: int":
  location: run_ralphex.py
  annotations: |
    Launch the external `ralphex` binary to execute the given build plan with the resolved
    ralphex options. goga-side entry point to ralphex; performs no config generation,
    option resolution, or wrapper resolution — those live in goga/build.

    `plan`: path to the plan file (markdown), resolved by the caller (goga/build). Passed
           to ralphex as the positional argument.
    `options`: resolved ralphex options — the caller (goga/build) has already applied
              precedence and stage binding. Keys are ralphex option names; each key maps
              to exactly one ralphex CLI flag:
              - tasks_only (bool)             → --tasks-only          (bare flag)
              - review (bool)                 → --review              (bare flag)
              - external_only (bool)          → -e                    (bare flag)
              - session_timeout (str)         → --session-timeout     (value flag)
              - idle_timeout (str)            → --idle-timeout        (value flag)
              - wait (str)                    → --wait                (value flag)
              - max_iterations (int)          → --max-iterations      (value flag)
              - review_patience (int)         → --review-patience     (value flag)
              - max_external_iterations (int) → --max-external-iterations (value flag)
              - base_ref (str)                → --base-ref            (value flag)
    `dry_run`: when True, print the assembled ralphex command to sys.stderr and return 0
              without launching.
    `env`: optional environment layer applied on top of the inherited process
           environment for the ralphex subprocess only. Never logged, never printed.
    `exit_code`: 0 on success, 1 when ralphex is missing from PATH or the launch is
                rejected before the exec, otherwise ralphex's own exit code

    Algorithm:
    1. Receive `plan`, `options`, `dry_run`, and `env` from the caller
    2. Invoke ralphex via the `ralphex` practice with `plan` as the positional argument,
       --config-dir .ralphex/, and the flags mapped from `options`
    3. On `dry_run`: print the assembled command to sys.stderr and return 0 — never print
       the `env` layer values
    4. Verify `ralphex` is on PATH; when absent — return 1
    5. Execute ralphex via subprocess with the composed environment and propagate its
       exit code; a pre-exec rejection surfaces as a clean one-line message and exit
       code 1 — never a traceback, never the `env` contents

    Requirements:
    - Map `options` to ralphex CLI flags per the table: a bool key that is True emits a
      bare flag (False or absent → omit); a scalar key emits --<flag> <value> and is
      omitted when the value is None or an empty string — EXCEPT the zero-valued
      external flags: `review_patience` 0 and `max_external_iterations` 0 are meaningful
      (disabled / ralphex auto) and ARE passed as 0
    - The pass-mode bare flags (tasks_only, review, external_only) are mutually
      exclusive per invocation — the caller guarantees it; this launcher does not check
    - Apply the `ralphex` practice's exit-code rules verbatim

    Constraints:
    - Do not generate .ralphex/config, resolve options, or resolve wrappers — caller's
      responsibility
    - Do not check flag exclusivity — the caller owns pass composition
    - Do not log or otherwise expose the `env` layer contents
```

Removed from the table: `worktree`, `skip_finalize` (retired surface).

### 4. `goga/hooks/catalog/CODEMANIFEST` (modify, additive)

Header and footer unchanged. `declared_actions` Requirements **gain** (after
the existing records; no existing record changes):

```yaml
    - The catalog carries the build validation-gate action — the record
      domain="build", name="validate_build", error_class="hard": a veto
      stops the build before any pass with one merged error; the domain's
      delivery walk runs every subscribed tool's hooks to completion — a
      deliberate domain-local deviation from the stop-at-first-failure hard
      semantics, recorded by the build domain's zone
    - The catalog carries the build start-notification action — the record
      domain="build", name="build_started", error_class="soft": a failing
      hook of the action is skipped with a warning and the run continues
    - The catalog carries the build pass-start notification action — the
      record domain="build", name="pass_started", error_class="soft": a
      failing hook of the action is skipped with a warning and the pass
      launches
    - The catalog carries the build pass-completion notification action —
      the record domain="build", name="pass_completed", error_class="soft":
      a failing hook of the action is skipped with a warning; the completion
      fact is already delivered
    - The catalog carries the build completion notification action — the
      record domain="build", name="build_completed", error_class="soft": a
      failing hook of the action is skipped with a warning; the run's exit
      code is unaffected
```

### 5. `goga/build/hooks/CODEMANIFEST` (create — full file)

```yaml
Imports:
  - Types:
      - HookRegistry
      - wrap_context
      - build_hook_arguments
      - emit_hook_event
      - declared_actions
    Usages:
      - declaring-actions
      - per-tool-delivery
      - registering-hooks
    From: goga/hooks

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

  This cell owns the hooks zone of the build domain: the fact vocabulary of
  the run events, the read-only contexts of the five moments, the
  verdict-collecting gate view, and the checkpoint surface that delivers the
  gate and emits the four notifications over the platform facade. One
  registry per run carries every checkpoint of a command — the checkpoints
  never multiply the package enumeration. Every context is built from the
  operation data the caller passes — no repository reads and no git access
  happen here, at any checkpoint moment. Env values are never present in any
  fact: presence is delivered as names only. The gate is the domain's hard
  action with a deliberate domain-local deviation: the staged per-tool walk
  runs to completion — every subscribed tool's validation hooks run, no
  early stop between tools — and collects the vetoes, following the
  `per-tool-delivery` precedent instead of the platform's
  stop-at-first-failure hard semantics; verdict collection requires every
  tool's outcome. The four notifications are soft — a failing hook warns
  naming the tool, the action, and the reason, and the run's outcome is
  unaffected.
  Use the `per-tool-delivery` practice for the staged walk of the gate — its
  loop skeleton, primitives, and per-tool grouping apply as written with one
  refinement: the walk never stops early and collects vetoes instead of
  committing contributions; a tool with no veto and no crash approves
  silently.
  Use the `declaring-actions` practice for the emission contract of the
  notification checkpoints.
  Use the `registering-hooks` practice for the hook signature and the failure
  handling behind every checkpoint.
  Use relative imports.

---

"WorkIdentity(branch: str, slug: str | None = None, year: str | None = None)":
  location: facts.py
  annotations: |
    The identity of the current work — the branch, with the topic slug and
    year when the branch hosts a topic.

    `branch`: the current branch name as resolved by the operation ("unknown"
              when resolution failed)
    `slug`: the normalized topic slug — present when the branch hosts a topic
    `year`: the resolved year as four digits — present when the branch hosts
             a topic

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - The hosting decision and every resolution happen in the constructing
      operation — nothing is read here
    - The branch-only form — `slug` and `year` None — serves a branch hosting
      no topic
  properties:
    "branch -> str": |
      The current branch name as resolved by the operation; "unknown" when
      the operation could not resolve it.
    "slug -> str | None": |
      The normalized topic slug, or None in the branch-only form.
    "year -> str | None": |
      The resolved year as four digits, or None in the branch-only form.

"BuildMoment(plan: str, work: WorkIdentity, dry_run: bool)":
  location: facts.py
  annotations: |
    The uniform envelope of every build context — the plan under execution,
    the work identity, and the rehearsal fact.

    `plan`: the plan file path of the run
    `work`: the current work identity
    `dry_run`: True when the run rehearses without launching anything

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
  properties:
    "plan -> str": |
      The plan file path of the run.
    "work -> WorkIdentity": |
      The current work identity.
    "dry_run -> bool": |
      True when the run rehearses the cycle without launching passes.

"StageFacts(stage: str, agent: str | None, env: list[str], max_iterations: int | None, session_timeout: str | None, idle_timeout: str | None, wait: str | None, roles: list[str] | None, base_ref: str | None, strategy: str | None, finalize: str | None, additional: AdditionalFacts | None)":
  location: facts.py
  annotations: |
    The resolved facts of one stage part of the run — the delivered
    projection of the operation's resolved settings for that stage.

    `stage`: exactly tasks or review
    `agent`: the executor agent name of the stage
    `env`: the env presence of the stage layer as NAMES — values never
            appear anywhere
    `max_iterations`, `session_timeout`, `idle_timeout`, `wait`: the resolved
            pass knobs of the stage
    `roles`: the declared reviewer composition — review stage only
    `base_ref`: the review diff base — review stage only
    `strategy`: the resolved review strategy — review stage only
    `finalize`: the full finalize prompt text when configured — review stage
            only, None otherwise
    `additional`: the external-review facts — review stage only

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Pure facts — the constructing operation passes resolved values with
      inheritance already applied; nothing is read or derived here
    - The review members are None on the tasks part
    - `env` carries names only — an empty list means no env layer
  properties:
    "stage -> str": |
      The stage identity — exactly tasks or review.
    "agent -> str | None": |
      The executor agent name of the stage.
    "env -> list[str]": |
      The env presence of the stage layer as names; never values.
    "max_iterations -> int | None": |
      The resolved iteration cap of the stage.
    "session_timeout -> str | None": |
      The resolved session timeout of the stage.
    "idle_timeout -> str | None": |
      The resolved idle timeout of the stage.
    "wait -> str | None": |
      The resolved rate-limit wait of the stage.
    "roles -> list[str] | None": |
      The declared reviewer composition of the review stage; None on the
      tasks part.
    "base_ref -> str | None": |
      The review diff base of the review stage; None on the tasks part.
    "strategy -> str | None": |
      The resolved review strategy (full, medium, short); None on the tasks
      part.
    "finalize -> str | None": |
      The full finalize prompt text when configured; None when unset or on
      the tasks part.
    "additional -> AdditionalFacts | None": |
      The external-review facts of the review stage; None on the tasks part.

"AdditionalFacts(agent: str | None, patience: int | None, max_iterations: int | None)":
  location: facts.py
  annotations: |
    The delivered mirror of the external-review block — the documented facts
    of `build.review.additional` for tool authors.

    `agent`: the external review agent name (after inheritance)
    `patience`: the external-review stop threshold (0 = disabled)
    `max_iterations`: the external review iteration cap (0 = ralphex auto)

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
  properties:
    "agent -> str | None": |
      The external review agent name, or None when unset.
    "patience -> int | None": |
      The external-review stop threshold; 0 = disabled; None when unset.
    "max_iterations -> int | None": |
      The external review iteration cap; 0 = ralphex auto; None when unset.

"RelocationOutcome(moved: bool, destination: str | None)":
  location: facts.py
  annotations: |
    The outcome of the plan relocation attempt.

    `moved`: True when the plan file was relocated
    `destination`: the relocation destination path when moved, None otherwise

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
  properties:
    "moved -> bool": |
      True when the plan was relocated into the completed directory.
    "destination -> str | None": |
      The relocation destination when moved, None when not moved.

"Violation(tool: str, hook: str, reason: str)":
  location: facts.py
  annotations: |
    One collected veto of the gate walk.

    `tool`: the tool identity assigned by the platform
    `hook`: the hook name that vetoed (or crashed)
    `reason`: the veto reason — a hook-authored message or the crash reason;
              never a raw traceback

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
  properties:
    "tool -> str": |
      The tool identity of the vetoing tool.
    "hook -> str": |
      The hook name that vetoed or crashed.
    "reason -> str": |
      The veto reason — authored or crash-derived; never a raw traceback.

"GateVerdict(violations: list[Violation])":
  location: facts.py
  annotations: |
    The collected verdict of the gate walk — every veto of every subscribed
    tool, in enumeration order.

    `violations`: the collected violations; an empty list means approved

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - The verdict is data only — acting on it (the merged error, the exit
      code) belongs to the operation
  properties:
    "violations -> list[Violation]": |
      The collected violations in enumeration order.
    "approved -> bool": |
      True when no violation was collected — the run may proceed.

"BuildValidation(moment: BuildMoment, tasks: StageFacts, review: StageFacts, skip: bool)":
  location: contexts.py
  annotations: |
    The gate's delivered view of one tool — the read-only facts of the run
    about to start, plus the veto buffer of this tool alone.

    `moment`: the uniform envelope
    `tasks`: the resolved facts of the tasks stage
    `review`: the resolved facts of the review stage (always present,
              including a skipped review — the facts describe the resolved
              settings, not the execution)
    `skip`: the resolved review skip state

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
    Use the `registering-hooks` practice for the hook signature that
    receives this view.

    Requirements:
    - The reads deliver the resolved facts — read-only; a hook observes and
      cannot alter anything
    - The veto buffer belongs to this tool alone
  properties:
    "moment -> BuildMoment": |
      The uniform envelope of the run.
    "tasks -> StageFacts": |
      The resolved facts of the tasks stage.
    "review -> StageFacts": |
      The resolved facts of the review stage.
    "skip -> bool": |
      The resolved review skip state of the run.
  methods:
    "veto(reason: str)": |
      Buffer this tool's veto of the run.

      `reason`: the human-readable violation reason

      Requirements:
      - The call buffers into the buffer of this tool alone and changes
        nothing until the walk collects it
      - The replacement is whole — a later call replaces the earlier reason
      - The view records no hook identity — the walk attributes the veto
        to a hook by observing the buffer change around each call
      - An empty or whitespace-only reason is stored as given — the merged
        error renders it verbatim

      Constraints:
      - Do not cancel, redirect, or defer the operation — a veto stops the
        run through the collected verdict only

"BuildStarted(moment: BuildMoment, tasks: StageFacts, review: StageFacts, skip: bool)":
  location: contexts.py
  annotations: |
    The read-only context of the start notification — the same resolved
    facts the gate saw, delivered immediately before the first pass launch.

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Read-only facts of the starting run — a hook observes and cannot alter
  properties:
    "moment -> BuildMoment": |
      The uniform envelope of the run.
    "tasks -> StageFacts": |
      The resolved facts of the tasks stage.
    "review -> StageFacts": |
      The resolved facts of the review stage.
    "skip -> bool": |
      The resolved review skip state of the run.

"PassStarted(moment: BuildMoment, facts: StageFacts)":
  location: contexts.py
  annotations: |
    The read-only context of the pass-start notification — the facts of the
    pass about to launch.

    `facts`: the stage facts of the launching pass

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Read-only facts of the launching pass
  properties:
    "moment -> BuildMoment": |
      The uniform envelope of the run.
    "facts -> StageFacts": |
      The stage facts of the pass about to launch.

"PassCompleted(moment: BuildMoment, facts: StageFacts, exit_code: int)":
  location: contexts.py
  annotations: |
    The read-only context of the pass-completion notification — the facts of
    the finished pass plus its actual exit code. Completion is a fact, not a
    success claim.

    `facts`: the stage facts of the finished pass
    `exit_code`: the actual exit code of the pass — zero, non-zero, or a
                  spawn-failure code

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
  properties:
    "moment -> BuildMoment": |
      The uniform envelope of the run.
    "facts -> StageFacts": |
      The stage facts of the finished pass.
    "exit_code -> int": |
      The actual exit code of the pass return.

"BuildCompleted(moment: BuildMoment, exit_code: int, stages: list[str], relocation: RelocationOutcome, statuses: list[str])":
  location: contexts.py
  annotations: |
    The read-only context of the completion notification — the outcome of
    the started run at the completion moment.

    `exit_code`: the final exit code of the run — the last executed pass's
                  code
    `stages`: the executed stage sequence in execution order (a skipped
               review is absent)
    `relocation`: the outcome of the plan relocation attempt
    `statuses`: the work's current history statuses at the completion moment,
                 recomputed after the relocation attempt; an empty list in
                 the branch-only form

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Read-only facts of the completed run — the artifact → history-status
      integration builds from these facts alone
  properties:
    "moment -> BuildMoment": |
      The uniform envelope of the run.
    "exit_code -> int": |
      The final exit code of the run.
    "stages -> list[str]": |
      The executed stage sequence in execution order.
    "relocation -> RelocationOutcome": |
      The outcome of the plan relocation attempt.
    "statuses -> list[str]": |
      The work's current history statuses at the completion moment; empty in
      the branch-only form.

"BuildHooks()":
  location: events.py
  annotations: |
    The checkpoint surface of the build domain — the verdict-collecting gate
    delivery and the four notification emissions over the platform facade.

    Apply the `convention` practice for the code style and intra-package
    imports.
    Use the `per-tool-delivery` practice for the staged walk of the gate —
    with the recorded refinement: the walk runs to completion and collects
    vetoes; no early stop, no contribution commit.
    Use the `declaring-actions` practice for the emission contract of the
    notification checkpoints.
    Use the `registering-hooks` practice for the registration contract behind
    every checkpoint.

    Requirements:
    - Cheap construction — no enumeration and no imports happen at
      construction
    - One `HookRegistry` per run carries every checkpoint of a command —
      the assembly runs once per run whatever the number of checkpoints
    - Every context is built from the values the caller passes — no
      repository reads happen at a checkpoint
  methods:
    "validate_build(moment: BuildMoment, tasks: StageFacts, review: StageFacts, skip: bool) -> verdict: GateVerdict": |
      Deliver the validation gate and return the collected verdict.

      `moment`: the uniform envelope
      `tasks`: the resolved facts of the tasks stage
      `review`: the resolved facts of the review stage
      `skip`: the resolved review skip state
      `verdict`: the collected verdict — `approved` when no tool vetoed

      Use the `per-tool-delivery` practice for the walk (with the recorded
      refinement).

      Algorithm:
      1. Resolve the address domain="build", action="validate_build"
         against `declared_actions`
      2. Walk the subscriptions of the address per tool in enumeration
         order: build the tool's `BuildValidation` view over the delivered
         facts, wrap it via `wrap_context`, project the call arguments via
         `build_hook_arguments` with the tool's own self context, and call
         each hook of the tool; snapshot the view's veto buffer before
         each hook call — a buffer change during a call attributes the
         veto to that hook's subscription name (a later veto replaces the
         earlier attribution, mirroring the whole-replacement rule)
      3. A tool whose every hook returned without raising and whose view
         carries no buffered veto approves silently — no record
      4. A tool whose view carries a buffered veto contributes exactly one
         `Violation` (the tool, the attributed vetoing hook, the reason)
      5. A tool with a raising hook contributes exactly one `Violation`
         with the crash reason as the reason — never a raw traceback — and
         the walk continues; a crash overrides the tool's buffered veto
         (the crash reason replaces it); the walk NEVER stops between
         tools, whatever a tool returned or raised
      6. Return the `GateVerdict` with the violations in enumeration order

      Requirements:
      - Every subscribed tool's hooks run — no early stop; a non-vetoing
        subscriber is invoked even when another tool already vetoed
      - Exactly one `Violation` per tool: the buffered veto with its
        attributed hook, or the crash reason when a hook raised (the
        crash overrides the buffer)
      - An address without subscriptions returns an empty verdict — approved;
        with no tool packages installed the gate is inert
      - The gate modifies nothing — no contribution, no mutation of any
        delivered fact

      Constraints:
      - Do not stop the walk at the first veto or crash — verdict collection
        requires every tool's outcome
      - Do not skip a subscriber of the address
      - Do not read repositories or the filesystem at the checkpoint
      - Do not deliver env values — the facts carry names only
    "emit_build_started(moment: BuildMoment, tasks: StageFacts, review: StageFacts, skip: bool)": |
      Emit the start notification — the resolved facts the gate saw,
      immediately before the first pass launch.

      Use the `declaring-actions` practice for the emission contract.

      Algorithm:
      1. Build the `BuildStarted` context from the values
      2. Emit the address domain="build", action="build_started" via
         `emit_hook_event`

      Requirements:
      - Fire-and-forget — nothing is collected and no value returns
      - A failing hook is skipped with a warning under the soft error class
        of the action — the run proceeds
    "emit_pass_started(moment: BuildMoment, facts: StageFacts)": |
      Emit the pass-start notification — the facts of the pass about to
      launch.

      `facts`: the stage facts of the launching pass

      Use the `declaring-actions` practice for the emission contract.

      Algorithm:
      1. Build the `PassStarted` context from the values
      2. Emit the address domain="build", action="pass_started" via
         `emit_hook_event`

      Requirements:
      - Fire-and-forget — nothing is collected and no value returns
    "emit_pass_completed(moment: BuildMoment, facts: StageFacts, exit_code: int)": |
      Emit the pass-completion notification — the facts of the finished
      pass with its actual exit code.

      `facts`: the stage facts of the finished pass
      `exit_code`: the actual exit code of the pass return

      Use the `declaring-actions` practice for the emission contract.

      Algorithm:
      1. Build the `PassCompleted` context from the values
      2. Emit the address domain="build", action="pass_completed" via
         `emit_hook_event`

      Requirements:
      - Fire-and-forget — nothing is collected and no value returns
      - The emission happens on every pass return path — zero, non-zero,
        and spawn failures alike; completion is a fact
    "emit_build_completed(moment: BuildMoment, exit_code: int, stages: list[str], relocation: RelocationOutcome, statuses: list[str])": |
      Emit the completion notification — the outcome of the started run.

      `exit_code`: the final exit code of the run
      `stages`: the executed stage sequence
      `relocation`: the relocation outcome
      `statuses`: the work's history statuses recomputed at the completion
                   moment

      Use the `declaring-actions` practice for the emission contract.

      Algorithm:
      1. Build the `BuildCompleted` context from the values
      2. Emit the address domain="build", action="build_completed" via
         `emit_hook_event`

      Requirements:
      - Fire-and-forget — nothing is collected and no value returns
      - The emission happens on every return path of a started run — zero,
        non-zero, and spawn failures alike

---

Author: Goga
CreatedAt: 21/09/26
Description: |
  Owner of the build domain hooks zone — the run-event facts, the
  verdict-collecting validation gate, and the checkpoint surface over the
  hooks platform.
```

**Cell facade note (python rules):** `__init__.py` of `goga/build/hooks`
exposes the full contract API through `__all__` (the 13 types).

### 6. `goga/build/CODEMANIFEST` (modify)

**Delete types:** `resolve_review_options`, `ReviewOptions` (file
`review_options.py` superseded by `run_settings.py`).

**Header — Imports/Usages/Annotations (full new header):**

```yaml
Imports:
  - Types:
      - ProjectConfig
      - BuildConfig
      - ReviewConfig
      - AdditionalReviewConfig
      - load_project_config
    From: goga/config
  - Types:
      - resolve_wrapper_path
    Usages:
      - resolve-wrapper-path
    From: goga/agents
  - Types:
      - ensure_in_docker
    Usages:
      - ensure-in-docker
    From: goga/docker
  - Types:
      - run_ralphex
    Usages:
      - run-ralphex
    From: goga/ralphex
  - Types:
      - BuildHooks
      - BuildMoment
      - StageFacts
      - WorkIdentity
      - RelocationOutcome
      - GateVerdict
    Usages:
      - checkpoints
    From: goga/build/hooks
  - Types:
      - resolve_current_branch_name
      - collect_topic_statuses
    Usages:
      - topic-paths
      - topic-statuses
    From: goga/history

Usages:
  conventions: .goga/usages/conventions.md
  ralphex: .goga/usages/cooks/ralphex.md
  agent-wrappers: .goga/usages/cooks/agent-as-claude-wrappers.md

Annotations: |
  The `conventions` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and testing in the project

  This cell owns the build domain: manifest-commit verification, two-part
  settings resolution with root inheritance, the stable two-pass cycle with
  the five checkpoints, ralphex config generation with the external-review
  surface, vendored defaults sync with finalize materialization, and plan
  relocation. Every non-skipped run is exactly two ralphex invocations — a
  tasks pass then a review pass; the combined full pass does not exist. It
  delegates the ralphex launch to `run_ralphex` from goga/ralphex (per the
  `run-ralphex` practice) — ralphex is launched through `run_ralphex`, never
  directly from this cell.

  The checkpoint facts resolve in this operation before delivery (per the
  `checkpoints` practice): the work identity via `resolve_current_branch_name`
  with the "unknown" fallback and the completion statuses via
  `collect_topic_statuses` — both before the checkpoint moments, never at
  them. Env values are never delivered to any context and never printed —
  presence travels as names only.

  Use the `conventions` practice for development and testing.
  Use the `ralphex` practice for the ralphex config-generation contract (the
  .ralphex/config key layout, the external-review surface, the finalize step
  files) written before launch.
  Use the `agent-wrappers` practice for the in-container wrapper naming
  convention referenced when writing claude_command into .ralphex/config.
  Use the `resolve-wrapper-path` practice when calling `resolve_wrapper_path`.
  Use the `run-ralphex` practice to delegate the launch.
  Use the `checkpoints` practice for the checkpoint integration order and the
  fact resolution.
  Use the `topic-paths` practice for the work identity resolution behind the
  branch hosting and the `topic-statuses` practice for the completion status
  facts.
  Write all output to sys.stderr (click is not used).
  Run git external commands via subprocess (the manifest pre-check and the
  branch resolution) — never at a checkpoint moment.
```

**Body — full new/changed type blocks** (locations: `build.py`,
`__main__.py`, `run_settings.py` (new file), `pass_options.py` (new file),
`review_config.py`, `ralphex_runtime.py`, `ralphex_config.py`,
`build_pass.py`, `plan_relocation.py`):

```yaml
"build(plan: str, config: ProjectConfig, cli_options: dict) -> exit_code:int":
  location: build.py
  annotations: |
    Orchestrates the stable two-pass build cycle with the five hooks
    checkpoints.

    `plan`: path to the plan file (markdown)
    `config`: loaded project configuration object
    `cli_options`: dictionary of CLI options (dry_run, skip_manifest_check,
                   skip_review, base_ref, review_patience, session_timeout,
                   idle_timeout, wait, max_iterations)
    `exit_code`: process exit code (0 = success, 1 = failure)

    Algorithm:
    0. (pre-check) When skip_manifest_check is not set: verify all project
       CODEMANIFEST files are committed to git; reject with exit code 1 when
       any are uncommitted. A pre-check failure fires no events
    1. Resolve the run settings via `resolve_run_settings` — the two parts
       with root inheritance, the tri-state skip, the strategy default medium
    2. Validate the review configuration via `validate_review_config` when
       the review pass will run; a validation failure fires no events
    3. Rewrite .ralphex/prompts/ and .ralphex/agents/ from the vendored
       defaults via `sync_ralphex_defaults` — roles filtering, finalize
       materialization when the prompt is set
    4. Resolve the checkpoint facts from this operation's own data: the
       `WorkIdentity` (branch via `resolve_current_branch_name` with the
       "unknown" fallback, slug/year when the branch hosts a topic), the
       `BuildMoment` (plan, work, dry_run), and both `StageFacts` (env as
       names)
    5. Run the validation gate via `BuildHooks.validate_build`; when the
       returned `GateVerdict` is not approved: print one merged error listing
       every violation (tool, hook, reason) to sys.stderr and return exit
       code 1 — no pass launches, the plan is not relocated, no further
       events fire
    6. Emit `build_started` with the same facts the gate saw
    7. Tasks pass: compose the options via `compose_pass_options` (stage
       tasks), resolve the root agent wrapper per the `resolve-wrapper-path`
       practice, emit `pass_started`, launch via `run_build_pass` with the
       root env as the env layer, emit `pass_completed` with the actual exit
       code
    8. When the tasks pass succeeded and review is not skipped: review pass
       under the review agent's wrapper (the additional agent's wrapper under
       the short strategy), the review env as the env layer, the
       strategy-bound options; `pass_started` / launch / `pass_completed`
       around it. A failed tasks pass never launches the review pass
    9. Relocate the plan via `move_completed_plan` with outcome = success of
       the final pass (dry-run and failure leave the plan in place); take the
       returned `RelocationOutcome`
    10. Recompute the work's history statuses via `collect_topic_statuses`
        AFTER the relocation attempt (moved or not; branch-only form — an
        empty list)
    11. Emit `build_completed` with the final exit code, the executed stage
        sequence, the relocation outcome, and the recomputed statuses
    12. Return the exit code of the last executed pass

    Apply `conventions` for docstring style and intra-package imports.
    Apply `ralphex` for the config-generation contract.
    Apply `agent-wrappers` for the wrapper path semantics.
    Apply `resolve-wrapper-path` when calling `resolve_wrapper_path`.
    Apply `run-ralphex` when delegating the launch.
    Apply `checkpoints` for the checkpoint order and fact resolution.
    Apply `topic-paths` and `topic-statuses` for the work identity and the
    completion statuses.

    Requirements:
    - `ralphex` is launched only through `run_ralphex` — never via a direct
      subprocess call
    - Every non-skipped run is exactly two passes; a skipped review yields
      exactly one tasks pass
    - The run's exit code is the last executed pass's; plan relocation
      happens only on success of the final pass
    - The task env never reaches the review pass (secret-safe, never printed)
    - On dry-run: fire the identical event structure with the dry_run fact,
      print the commands of both passes without env layers, relocate nothing
    - Pre-launch failures (steps 0-3) fire no events — the moment never
      happened
    - A blocked run (step 5) fires nothing after the gate
    - Warnings and errors of the checkpoints name the tool, the action, and
      the reason (delivered by the zone per its practices)

    Constraints:
    - Do not assemble the ralphex command or invoke ralphex directly —
      delegate to `run_ralphex`
    - Do not read git at a checkpoint moment — the facts resolve before
      delivery
    - Do not deliver or print env values — names only, in every fact
    - The .ralphex/ directory lifecycle is owned by the host launcher
      (goga/commands/build)

"main() -> exit_code:int":
  location: __main__.py
  annotations: |
    Entry point for python -m goga.build execution inside a Docker container.

    `exit_code`: process exit code (0 = success, 1 = failure)

    Algorithm:
    0. Call `ensure_in_docker` as the very first statement (per the
       `ensure-in-docker` practice)
    1. Parse CLI arguments via argparse (plan + options); the argparse
       surface carries the --skip-review / --no-skip-review pair resolving
       to skip_review: bool | None, --base-ref, --dry-run,
       --skip-manifest-check, --session-timeout, --idle-timeout, --wait,
       --max-iterations, and --review-patience (addressing
       build.review.additional.patience); --worktree and --skip-finalize do
       not exist
    2. Load project configuration via `load_project_config`
    3. Build cli_options from the parsed argparse results
    4. Invoke `build`(plan, `ProjectConfig`, cli_options)
    5. Return the resulting `exit_code`

    Requirements:
    - The guard at step 0 MUST be covered by tests for both branches

    Apply the `ensure-in-docker` practice at step 0.

"resolve_run_settings(config: BuildConfig, cli_options: dict) -> settings: RunSettings":
  location: run_settings.py
  annotations: |
    Resolve the run settings of one build from the two-part configuration
    and the CLI options — root inheritance applied, tri-state skip resolved,
    strategy defaulted.

    `config`: build configuration (`BuildConfig`) in the two-part form;
    `review` may be None — step 0 covers it
    `cli_options`: CLI options dictionary; the keys read here are skip_review
    (bool | None), base_ref (str | None — empty/whitespace counts as unset),
    review_patience, session_timeout, idle_timeout, wait, max_iterations
    (each None when the flag was not given)
    `settings`: the resolved run plan (`RunSettings`)

    Algorithm:
    0. When `config.review` is None (the build.review key is absent),
       treat every review field as unset: skip resolves False, the agent
       and session knobs inherit the root values per step 4,
       base_ref/roles/finalize stay None, and the additional part resolves
       with agent = the resolved review agent and patience/max_iterations
       None
    1. Resolve skip: cli_options skip_review when not None, otherwise the
       skip field of `ReviewConfig`, otherwise False
    2. Resolve strategy: the strategy field of `ReviewConfig` when set,
       otherwise medium
    3. Tasks part: the root agent, env, max_iterations, and session knobs
       verbatim
    4. Review part: each field from `ReviewConfig` when set, otherwise the
       root value (agent, session knobs; max_iterations is root-only; env
       never inherits — the root env is the tasks-pass layer only, the
       review env is exactly build.review.env)
    5. Additional: agent from `AdditionalReviewConfig` when set, otherwise
       the resolved review agent; patience and max_iterations from
       `AdditionalReviewConfig` verbatim (None when the block is absent)
    6. base_ref: cli_options base_ref when not None (empty/whitespace →
       unset; padded → stripped), otherwise `ReviewConfig` base_ref

    Requirements:
    - Precedence CLI > config > default > omit for every resolved knob
    - Unset at both levels resolves to None — the key stays absent from the
      ralphex options
    - env dicts pass verbatim; the review env never inherits the root env
      (secret-safe — the root env is the tasks-pass layer); an empty
      review env means no review layer

    Constraints:
    - Pure — no side effects, no validation of values (separate routine)
    - Do not resolve wrappers — wrapper resolution belongs to the
      orchestrator and the validation routine
    - Do not validate the strategy value — the whitelist check belongs to
      `validate_review_config`

"RunSettings(skip: bool, tasks: PassSettings, review: ReviewPassSettings)":
  location: run_settings.py
  annotations: |
    The resolved run plan of a single build.

    `skip`: the final skip decision (False when neither source is set)
    `tasks`: the resolved tasks-pass part
    `review`: the resolved review-pass part (inheritance applied; always
              present — a skipped run still carries the resolved review
              facts)

    Requirements:
    - Immutable frozen dataclass (frozen=True, kw_only=True), per
      `conventions`
    - Computed by `resolve_run_settings` — never loaded from YAML directly
  properties:
    "skip -> bool": |
      The final skip decision of the tri-state resolution.
    "tasks -> PassSettings": |
      The resolved tasks-pass part.
    "review -> ReviewPassSettings": |
      The resolved review-pass part with root inheritance applied.

"PassSettings(agent: str | None, env: dict[str, str], max_iterations: int | None, session_timeout: str | None, idle_timeout: str | None, wait: str | None)":
  location: run_settings.py
  annotations: |
    The resolved tasks-pass part of the run plan.

    Apply the `conventions` practice for the data-model rules and
    intra-package imports.
  properties:
    "agent -> str | None": |
      The tasks-pass executor agent name, None when unset.
    "env -> dict[str, str]": |
      The tasks-pass env layer, verbatim; the review pass never receives it.
    "max_iterations -> int | None": |
      The tasks-pass iteration cap; None when unset.
    "session_timeout -> str | None": |
      The tasks-pass session timeout; None when unset.
    "idle_timeout -> str | None": |
      The tasks-pass idle timeout; None when unset.
    "wait -> str | None": |
      The tasks-pass rate-limit wait; None when unset.

"PassSettings::ReviewPassSettings(roles: list[str] | None, base_ref: str | None, strategy: str, finalize: str | None, additional: AdditionalReviewConfig)":
  location: run_settings.py
  annotations: |
    The resolved review-pass part — a concretization of the base pass part:
    the inherited agent and session-knob fields, the verbatim review env
    layer (never inherited from the root), plus the review-only members.

    `roles`: the declared reviewer composition, verbatim
    `base_ref`: the resolved review diff base, None when unset
    `strategy`: the resolved strategy — exactly full, medium, or short
    `finalize`: the user-authored finalize prompt, None when unset
    `additional`: the resolved external-review block (agent inherited from
                   the review agent when unset)

    Requirements:
    - Immutable frozen dataclass (frozen=True, kw_only=True), per
      `conventions`
  properties:
    "roles -> list[str] | None": |
      The declared reviewer composition; None or empty list mean the full
      default set to the consumer.
    "base_ref -> str | None": |
      The resolved review diff base; None when unset.
    "strategy -> str": |
      The resolved review strategy — full, medium, or short.
    "finalize -> str | None": |
      The finalize prompt; None leaves the step at the ralphex default (off).
    "additional -> AdditionalReviewConfig": |
      The resolved external-review block; its agent field carries the
      inherited review agent when unset in config.

"compose_pass_options(settings: RunSettings, stage: str) -> options: dict[str, str | int | bool]":
  location: pass_options.py
  annotations: |
    Compose the ralphex options of one pass from the resolved run settings.

    `settings`: the resolved run plan
    `stage`: exactly tasks or review
    `options`: the ralphex options of the pass, consumed by `run_build_pass`

    Algorithm:
    1. tasks: the tasks_only mode flag plus the resolved tasks knobs
    2. review: the mode flag by strategy — review, or external_only under
       short — plus the resolved review knobs, base_ref, review_patience
       from additional.patience, and max_external_iterations from
       additional.max_iterations (0 = ralphex auto, passed verbatim)

    Requirements:
    - Unset knobs stay absent from the dict — the assembled ralphex command
      carries no flag for them
    - Review-only options never appear on the tasks pass
    - Exactly one pass-mode flag per composition — the modes are mutually
      exclusive

    Constraints:
    - Pure — no side effects, no config reads beyond `settings`

"validate_review_config(settings: RunSettings) -> none: None":
  location: review_config.py
  annotations: |
    Semantically validate the review configuration of a run whose review
    pass will execute; raise ValueError naming the invalid value.

    `settings`: the resolved run plan (`RunSettings`) — carries every
                review fact the checks read (roles, env, agent,
                additional, strategy)

    Algorithm:
    1. Return without checks when `settings` says skip — a skipped run does
       not validate review fields
    2. Check every role of the review part against the ralphex whitelist
       (quality, implementation, testing, simplification, documentation); a
       role outside the whitelist raises ValueError naming the role
    3. When the review part carries a non-empty env and no review agent —
       raise ValueError naming the problem (env requires agent)
    4. Resolve the review-agent wrapper via `resolve_wrapper_path` and
       require the wrapper file to exist; absence raises ValueError naming
       the agent
    5. When the strategy engages the external review (short always; full
       when additional.agent is set): resolve the additional-agent wrapper
       the same way and require its existence
    6. Check the resolved strategy of the review part against the
       whitelist full | medium | short; a value outside the whitelist
       raises ValueError naming the value

    Requirements:
    - Runs before any side effect — before writing .ralphex/ and before the
      first checkpoint
    - The error message names the invalid value

    Constraints:
    - Do not validate the tasks agent wrapper here — its absence surfaces at
      ralphex time
    - Do not check review fields of a skipped run

"sync_ralphex_defaults(config: BuildConfig, settings: RunSettings) -> none: None":
  location: ralphex_runtime.py
  annotations: |
    Fully rewrite .ralphex/prompts/ and .ralphex/agents/ from the vendored
    ralphex defaults (or the configured custom directories), apply the
    declared reviewer composition to the review prompts, and materialize the
    ralphex files of the finalize step when the finalize prompt is set.

    `config`: build configuration (`BuildConfig`) with optional prompts_dir /
    agents_dir
    `settings`: the resolved run plan (`RunSettings`)

    Algorithm:
    1. Choose the prompts source: the prompts_dir field of `BuildConfig`
       when set, otherwise the vendored package defaults; choose the agents
       source the same way
    2. Fully rewrite both target directories (clear, then copy)
    3. When the roles of the review part are a non-empty list: filter both
       review prompts — keep only the {{agent:X}} lines of the selected
       roles; adapt the accompanying text to the actual number of remaining
       roles
    4. Copy the definition files of all review agents regardless of the
       selection
    5. When the finalize prompt is set: materialize the ralphex files of the
       finalize step from the prompt string per the `ralphex` practice (the
       finalize prompt file of the review step)

    Requirements:
    - The full rewrite happens once per build run, regardless of roles
    - With the full default set (or no roles) the prompts are byte-identical
      to the vendored defaults
    - An empty intersection of roles with a phase's default set is a regular
      phase without subagents — no error, no fallback
    - Custom prompts_dir / agents_dir sources are copied as-is, without
      filtering
    - The finalize materialization happens only when the prompt is set;
      unset leaves the vendored tree untouched

    Constraints:
    - Do not touch .ralphex/config — it is written by the config routine

"write_ralphex_config(settings: RunSettings, wrapper_path: str) -> none: None":
  location: ralphex_config.py
  annotations: |
    Generate .ralphex/config for one ralphex pass.

    `settings`: the resolved run plan (`RunSettings`) — the external surface
    and the finalize fact of the review pass
    `wrapper_path`: executor wrapper path of the current pass (the
    claude_command value)

    Algorithm:
    1. Set claude_command to `wrapper_path`
    2. Apply claude_args defaults when missing
    3. Set preserve_anthropic_api_key to true
    4. Set move_plan_on_completion to false — always, for every pass
    5. External surface (the review pass): under the medium strategy set
       codex_enabled to false — the external review is explicitly disabled
       (internal agents only); under full or short leave the ralphex
       default (enabled), and when the resolved additional agent is set,
       set external_review_tool to custom and custom_review_script to the
       additional agent's wrapper path; when unset, leave the ralphex
       default (codex)
    6. When the finalize prompt is set: set finalize_enabled to true; unset
       leaves the ralphex default (false)

    Requirements:
    - In a two-pass run this routine is called twice — each pass passes its
      own executor wrapper (task wrapper; review wrapper — the additional
      wrapper under the short strategy)
    - Under the medium strategy the external review is explicitly disabled
      (codex_enabled false); full and short leave it enabled

    Constraints:
    - Do not write prompts or agents here
    - Do not derive the external surface from anything but the resolved
      settings

"run_build_pass(plan: str, settings: RunSettings, options: dict[str, str | int | bool], wrapper_path: str, dry_run: bool, env: dict[str, str] | None = None) -> exit_code: int":
  location: build_pass.py
  annotations: |
    Execute one ralphex pass: write the pass config, delegate the launch.

    `plan`: path to the plan file (markdown)
    `settings`: the resolved run plan (`RunSettings`) — carried to the
                config routine
    `options`: the resolved ralphex options of the pass (composed by
               `compose_pass_options`; carries exactly one pass-mode flag)
    `wrapper_path`: executor wrapper of the current pass
    `dry_run`: when True, print instead of launching
    `env`: optional environment layer forwarded verbatim to `run_ralphex` —
           the tasks pass receives the root env, the review pass the review
           env; values are never printed
    `exit_code`: the exit code returned by ralphex

    Algorithm:
    1. Write .ralphex/config via the config routine with `wrapper_path` and
       the pass settings
    2. Delegate the launch to `run_ralphex` with `plan`, `options`, `dry_run`,
       and `env`
    3. Return the exit code of `run_ralphex`

    Constraints:
    - Do not assemble or invoke the ralphex command directly — only through
      `run_ralphex`

"move_completed_plan(plan: str, outcome: bool, dry_run: bool) -> relocation: RelocationOutcome":
  location: plan_relocation.py
  annotations: |
    Relocate a completed plan file into the completed/ subdirectory of the
    directory holding the plan, and report the outcome.

    `plan`: path to the plan file
    `outcome`: True when the run succeeded
    `dry_run`: when True, nothing was launched — leave the plan in place
    `relocation`: the outcome facts — moved with the destination, or not
                  moved

    Algorithm:
    1. When `outcome` is False or `dry_run` is True: return the not-moved
       outcome
    2. Move the plan file to <plan_dir>/completed/<plan_name>, creating the
       completed/ subdirectory when missing
    3. Return the moved outcome with the destination

    Requirements:
    - Called after any started run — after the success of the last pass

    Constraints:
    - Do not hard-code docs/plans/ — the directory follows the plan file
      location
```

**Footer:** Author: Goga; CreatedAt: 18/08/26 (original); Description
updated to the stable two-pass cycle with checkpoints.

### 7. `goga/commands/build/CODEMANIFEST` (modify)

Imports/Usages keys unchanged (provider practice contents update in place:
`project-configuration`, `build-usage`).

**Global Annotations — delete** the clause "The command surfaces the
review-phase tri-state flags to the user and rejects the two-pass × worktree
combination...". **Add:**

```yaml
  The command surfaces the review-phase tri-state pair to the user and
  forwards it verbatim — the tri-state resolves in-container. The flag
  surface carries no --worktree and no --skip-finalize (removed with no
  replacement); --review-patience addresses build.review.additional.patience
  and --base-ref addresses build.review.base_ref (forwarding only —
  precedence resolves in-container); skip_manifest_check stays a CLI-only
  pre-check toggle. The task env (build.env) is not written into the
  container env-file — it is forwarded for the tasks-pass env layer
  in-container; the env-file carries the base layers (home.env, git
  identity, CLI -e, proxy).
```

**`build(...)` annotation deltas:** CLI options list without `--worktree`
and `--skip-finalize`; Algorithm step 2.2 guard repointed to the two-part
model — `config.build.agent is None` → ClickException ("build.agent is
required in .goga/config.yml to run 'goga build'"), replacing the retired
`config.build.task_executor.agent` path; Algorithm step 2.3 (the
review-worktree guard) deleted; step 3 cli_flags without the removed flags
(`--review-patience` forwarded as a value flag); step 7 env layering
without the task env; every Requirements/Constraints bullet naming
`task_executor` (the agent-guard wording, the env-file layering bullets)
rewritten to the two-part form — the env-file carries the base layers
(home.env, git identity, CLI -e, proxy) only, and `build.env` reaches the
container solely as the in-container tasks-pass env layer; Requirements
add "no worktree handling anywhere on the surface"; all other steps,
Requirements, and Constraints unchanged. Unchanged types:
`resolve_build_runtime_dir`, `clean_build_runtime_dir`,
`_cleanup_ralphex_in_project`. Footer unchanged.

### Usage-file artifacts

**Create `goga/build/hooks/.usages/checkpoints.md`** — full content:

```md
# build — delivering the build checkpoints

How the build operation consumes the hooks zone of the build domain: running the
validation gate before the first pass and emitting the four notifications around
the passes. For the in-container build orchestration.

## The checkpoint surface

One `BuildHooks` object serves every checkpoint of a run — the surface shares one
registry per run, so a run that reaches several checkpoints enumerates the tool
packages once.

    from goga.build.hooks import BuildHooks

    hooks = BuildHooks()

## Resolve the facts in the operation

Every context is built from the values the caller passes — the checkpoint reads
no repository. Resolve before the delivery:

- `WorkIdentity` — the current branch with the topic slug and year when the
  branch hosts a topic (`resolve_current_branch_name` with the `"unknown"`
  fallback — resolved before the checkpoint).
- `BuildMoment` — the plan, the work identity, `dry_run`.
- `StageFacts` (tasks and review) — the executor agent, env presence as NAMES
  (never values), the resolved option facts; the review facts carry roles,
  base_ref, strategy, the additional facts, and the finalize prompt text when
  configured.

## Gate before the first pass

After goga's own pre-checks (manifest check, settings resolution, review-config
validation, ralphex defaults sync) and before the first pass launch:

    verdict = hooks.validate_build(moment=moment, tasks=tasks_facts,
                                   review=review_facts, skip=skip)
    if not verdict.approved:
        # one merged error listing every violation (tool, hook, reason); exit 1;
        # no pass launches; the plan stays; no further events

- The gate walk runs to completion: every subscribed tool's validation hooks run
  — no early stop between tools; a non-vetoing subscriber is still invoked.
- A hook vetoes via the delivered view: `context.veto(reason)`. A crashing hook
  counts as its tool's veto with the crash reason.
- The gate modifies nothing — observe-and-veto only.

## Emit around the cycle

    hooks.emit_build_started(moment, tasks, review, skip)
    hooks.emit_pass_started(moment, tasks_facts)
    exit_code = run_build_pass(...)            # tasks pass
    hooks.emit_pass_completed(moment, tasks_facts, exit_code)
    if exit_code == 0 and not skip:
        hooks.emit_pass_started(moment, review_facts)
        exit_code = run_build_pass(...)        # review pass
        hooks.emit_pass_completed(moment, review_facts, exit_code)
    relocation = move_completed_plan(...)
    statuses = collect_topic_statuses(...)     # recompute after the relocation attempt
    hooks.emit_build_completed(moment, exit_code, stages, relocation, statuses)

- The four notifications are fire-and-forget: a failing hook warns naming the
  tool, the action, and the reason; the run's outcome is unaffected.
- `pass_completed` and `build_completed` fire on zero, non-zero, and
  spawn-failure codes alike — completion is a fact, not a success claim.
- Dry-run fires the identical structure with the `dry_run` fact; the gate runs;
  nothing executes.
- With no tool packages installed the whole surface is inert — an unsubscribed
  gate returns an approved verdict, emissions are unobservable.
```

**Create `goga/build/.usages/registering-hooks.md`** — full content:

```md
# build — registering hooks

How a `goga_tool_*` package subscribes its hooks to the build domain actions.
For tool package authors; no goga code changes are needed.

The domain opens five actions. One is the validation gate — a read-and-veto
view over the resolved run facts, delivered before the first pass; it is a hard
action with verdict collection: every subscribed tool's hooks run and all
vetoes merge into one error. Four are notifications — the read-only facts of
the run: at the start, around each pass, and at the completion.

## The events

| Address | Error class | Fires |
|---|---|---|
| `build / validate_build` | hard | After goga's own pre-checks (manifest check, settings resolution, review-config validation, ralphex defaults sync) and before the first pass launch — including dry-run runs. |
| `build / build_started` | soft | Immediately after the gate passes, before the first pass launch. |
| `build / pass_started` | soft | Before each pass launch — tasks and review. |
| `build / pass_completed` | soft | On every pass return — zero, non-zero, and spawn-failure codes alike, carrying the actual exit code. |
| `build / build_completed` | soft | On every return of a started build — after the relocation attempt and the status recompute. |

A failing moment fires nothing: goga pre-launch failures (uncommitted
manifests, invalid review config, unavailable defaults, missing build section
or agent) return before any checkpoint. A blocked (vetoed) run fires nothing
after the gate.

## Subscribe

    def register_hooks(hooks):
        hooks.subscribe("build", "validate_build", "policy", enforce_policy)
        hooks.subscribe("build", "build_completed", "reporter", report_build)

- `domain` — always `"build"`; `action` — from the table; `name` — unique per
  tool per address; `hook` — the callable executed when the event fires.
- A hook receives values only for the parameters it declares by the fixed
  offered names: `context`, `self`.

## The gate view

`validate_build` delivers a `BuildValidation` view per tool: `moment` (plan,
work, dry_run), `tasks` and `review` — the resolved stage facts (the executor
agent, env presence as names, the option facts; review adds roles, base_ref,
strategy, the additional facts, and the finalize prompt text), `skip`.

    def enforce_policy(context):
        if violates(context):
            context.veto("reason")

- `veto(reason)` buffers your tool's single veto; a repeat call replaces the
  reason whole.
- Your tool's hooks all run even when another tool already vetoed — verdict
  collection requires every tool's outcome.
- A crashing hook counts as your tool's veto with the crash reason — never a
  raw traceback.
- All vetoes merge into one clean error (tool, hook, reason); the run stops
  before any pass: exit code 1, the plan stays in place, no
  started/pass/completed events fire.

## The notifications

All four deliver read-only facts; a failing hook warns naming your tool, the
action, and the reason — the run's outcome is never affected.

- `build_started` — `BuildStarted`: the same facts as the gate.
- `pass_started` — `PassStarted`: the stage facts of the pass about to launch.
- `pass_completed` — `PassCompleted`: the stage facts plus the actual
  `exit_code`. Completion is a fact, not a success claim.
- `build_completed` — `BuildCompleted`: the final `exit_code`, `stages` (the
  executed sequence), `relocation` (moved + destination), `statuses` (the
  work's current history statuses recomputed after the relocation attempt —
  empty in the branch-only form), `dry_run`.

Env values are never delivered — presence as names only, in every context.

## Integration scenarios

- **Build reporting, automation, external notifications** — subscribe to the
  four notifications; read the stage facts, the exit codes, the relocation
  outcome, `dry_run`; keep state in your `self` context.
- **Artifact → history-status on completion** — subscribe to
  `build_completed`; read `relocation` and `work`; register your status on the
  statuses domain keyed by your artifact.
- **Policy enforcement** — subscribe to `validate_build`; inspect the resolved
  facts; `context.veto(reason)` when policy is violated — or stay silent to use
  the gate as a pre-start notification.
```

**Rewrite `goga/build/.usages/build-usage.md`** — the in-container invocation
contract for the host launcher: remove worktree/skip_finalize and the
executor-induced two-pass wording; document the always-two-pass cycle, the
two-part settings with inheritance, strategies, `additional`, `finalize`, the
five checkpoints (gate + four notifications, dry-run rehearsal), the updated
cli_options key list (`dry_run`, `skip_manifest_check`, `skip_review`,
`base_ref`, `review_patience`, `session_timeout`, `idle_timeout`, `wait`,
`max_iterations`), and the `build(...)` invocation example.

**Update `goga/config/.usages/project-configuration.md`** — the build chapter
rewritten to the two-part form (root keys; `build.review` keys with the
strategy triple and the additional block; inheritance rules applied by the
consumer; retired keys silently ignored; a YAML example; the migration note
that old block names become unknown keys and silently disable the build
section).

**Update `goga/commands/build/.usages/build.md`** — the command doc to the
new flag surface (two flags removed, env layering note).

### Config migration (dogfooding)

`.goga/config.yml` — the build section migrates to the two-part form in the
same change: the current `task_executor`/`review_executor` blocks become the
`build` root (agent, env from `task_executor`) and `build.review` (agent, env
from `review_executor`, plus the existing `base_ref`), preserving this
repository's effective settings.

## Dependency Map

```
goga/config/project ──► goga/config (embeddings)
goga/hooks/catalog ──► goga/hooks (facade, unchanged) ◄── goga/history (unchanged)
                             ▲ facade primitives + declaring-actions /
                             │ per-tool-delivery / registering-hooks
                    goga/build/hooks  (NEW: 13 types + checkpoints.md)
                             ▲ BuildHooks, BuildMoment, StageFacts, WorkIdentity,
                             │ RelocationOutcome, GateVerdict + checkpoints practice
 goga/config ───────────────┐│
 goga/agents ───────────────┼┤
 goga/docker ───────────────┼┼► goga/build ──► goga/commands/build
 goga/ralphex ──────────────┼┤       ▲    (build AS run_build + build-usage)
 goga/history ──────────────┘└───────┘
```

No circular imports (verified in the cell-distribution phase).

## Verification Checklist

After each artifact lands:

- **`goga lint`** passes over every modified/created CODEMANIFEST (DSL
  syntax: casing, signature rules, `location` restrictions, section order).
- **Facade checks** — `python -c "from goga.build.hooks import BuildHooks,
  BuildMoment, StageFacts, WorkIdentity, AdditionalFacts, RelocationOutcome,
  Violation, GateVerdict, BuildValidation, BuildStarted, PassStarted,
  PassCompleted, BuildCompleted"` and the re-export facade `from goga.config
  import BuildConfig, ReviewConfig, AdditionalReviewConfig`.
- **Absence checks** (breaking removals): no `--worktree`, no
  `--skip-finalize`, no `worktree`/`skip_finalize`/`codex_review` config
  keys, no `task_executor`/`review_executor` block names — across the CLI,
  the loader, and the manifests.
- **Catalog check**: `declared_actions()` carries the five `build` records;
  the existing records are byte-identical.
- **Schema check**: `goga schema` shows `goga/build/hooks` with 13 types and
  its dependency on `goga/hooks` only.
- **Tests**: `pytest tests/ -x`; `ruff check` over the touched packages.
- **Dogfooding**: `.goga/config.yml` build section in the two-part form; a
  build run executes the two passes.
- **Docs**: `registering-hooks.md` answers every integration scenario
  (reporting/automation/notifications; artifact → status; policy
  enforcement) from moments, context members, and failure semantics alone.
- **Acceptance criteria SC1–SC10** re-checked against the implemented
  behavior (per the task file's validation commands).
