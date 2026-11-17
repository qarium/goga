# Architecture Plan — Workflow-level global `agent` and `env`

## Topic

Short name: **workflow-global-agent-env**

Plan path: `.goga/history/2026/add-env-and-agent-to-workflow/arch.md`

Two top-level workflow-file keys — `agent` (str) and `env` (str→str map) — that
override the main configuration (`.goga/config.yml`) and act as the global
settings for both consumption surfaces: the pipeline run (`goga/pipeline`) and
the build (`goga/build`). Design decisions come from the accepted ADR
(`adr.md` in this topic directory); the task contract lives in `task.md`.

Scope: **4 modified cells, 9 changed types, 5 updated usage files. No new
cells, no new Imports, no new usage files.**

---

## Implementation Order

| # | Cell | Mark | Rationale |
|---|------|------|-----------|
| 1 | `goga/pipeline/workflow` | modified | Leaf: pure parser, no Imports. Owns the grammar and the `WorkflowDocument` model — every consumer resolves globals off the fields defined here, so the model must exist first. |
| 2 | `goga/pipeline/hooks` | modified | Depends on cell 1 (`WorkflowDocument` import). The overlay merge extends its verbatim-from-base set with the two new fields before any consumer reads an amended workflow. |
| 3 | `goga/pipeline` | modified | Depends on cells 1–2 (workflow types; hooks overlay). Resolves the effective global agent and the launch env base off the overlay workflow document. |
| 4 | `goga/build` | modified | Root of the feature surface; depends on cell 1 (workflow import) and `goga/config` (untouched). Layers the workflow globals as the middle layer of the build settings. |

Untouched and verified (contract drift forbidden): `goga/pipeline/compiler`
(consumes neither key — `WorkflowDocument` gains fields the compiler never
reads), `goga/agents/wrapper` (pure path resolution), `goga/config/project`
(models and verbatim exposure unchanged), `goga/commands/build` (workflow
carriage and `-w` forwarding already exist).

---

## Artifacts

### Cell 1: `goga/pipeline/workflow` — CODEMANIFEST [MODIFIED]

#### Header → `Annotations`

**REPLACE** in the opening paragraph: "known top-level keys prompt /
stages / extend / memory / profile / build / assistants / delegation /
repeat / gates" → "known top-level keys prompt / stages / extend /
memory / profile / build / assistants / delegation / repeat / gates /
agent / env".

**ADD** the following paragraph after the `gates` paragraph:

```text
agent and env are declarative workflow-global run settings — the two
top-level keys every consumer resolves as the global layer ahead of the
project configuration's own globals: agent (a single string naming the
run's global agent) and env (a str→str map of the run's global
environment layer). This cell validates both keys structurally and
extracts them into the document model; it resolves no wrappers, merges
no layers, and launches nothing — the consumers own every resolution
law. agent follows the empty-to-absence normalization of a scalar: a
non-str value is a structural error, an empty or whitespace-only value
normalizes to absence. env follows the string-map law: a non-mapping
value, a non-str key, or a non-str value is a structural error; an
empty map equals absence — the assistant explicit-clear discipline does
not apply to this key. Both keys count as content for the empty-workflow
rule: a workflow consisting of agent alone (or env alone) is valid;
profile never counts. Both keys ride the whole-file contributor-profile
rendering like the rest of the document, and the profile peek reads the
raw text — a value materializing only through rendering activates
nothing.
```

#### Body → `"WorkflowDocument(...)"`

**REPLACE** the signature line:

```yaml
"WorkflowDocument(prompt: str | None = None, stages: dict[str, WorkflowStage] | None = None, extend: dict[str, WorkflowExtendStage] | None = None, memory: WorkflowMemory | None = None, profile: str | None = None, build: WorkflowBuild | None = None, assistants: dict[str, WorkflowAssistant] | None = None, delegation: WorkflowDelegation | None = None, repeat: WorkflowRepeat | None = None, gates: WorkflowGates | None = None, agent: str | None = None, env: dict[str, str] | None = None)":
  location: workflow_document.py
```

**ADD** to the type-level `annotations` (after the `gates` parameter
description):

```text
    `agent`: the workflow-global agent name — the global run-settings
             layer every consumer resolves ahead of the configuration's
             pipeline agent, or None when the key is absent or empty
    `env`: the workflow-global environment layer (string map, literal
           and/or rendered), or None when the key is absent (an empty
           map equals absence)
```

**REPLACE** the field-order requirement bullet:

```text
    - memory defaults to None; profile defaults to None; build defaults to
      None; delegation defaults to None; repeat defaults to None; gates
      defaults to None; agent defaults to None; env defaults to None (an
      empty map equals absence — normalized by `parse_workflow`); field
      order is fixed: prompt, stages, extend, memory, profile, build,
      assistants, delegation, repeat, gates, agent, env — the two global
      run-settings fields close the canonical order
```

**REPLACE** the empty-workflow requirement bullet:

```text
    - The empty-workflow rule counts the new keys: a workflow is empty
      only when prompt is None AND stages is empty AND extend is empty
      AND memory is None AND build is None AND assistants is empty AND
      delegation is None AND repeat is None AND gates is None AND agent
      is None AND env is None — the global keys count as content;
      `profile` never counts (activation is not content: a profile-only
      workflow is still empty)
```

**REPLACE** the "A workflow-file with none of a top-level…" requirement
bullet (the version listing the two global keys):

```text
    - A workflow-file with none of a top-level `prompt`, any stage
      entries, any extend entries, the memory block, the build block,
      the assistants block, the delegation block, the repeat block, the
      gates block, the agent key, or the env block is rejected by
      `parse_workflow` with a structural error before this dataclass is
      built — at least one must be present
```

**ADD** properties:

```yaml
    "agent -> str | None": |
      The workflow-global agent name — the global run-settings layer
      consumers resolve ahead of the configuration's pipeline agent;
      None when the key is absent or empty.
    "env -> dict[str, str] | None": |
      The workflow-global environment layer (string map); None when
      the key is absent (an empty map equals absence).
```

#### Body → `"parse_workflow(text: str) -> workflow: WorkflowDocument"`

**ADD** to algorithm step 4 (after the `gates` extraction bullet):

```text
       - agent: if present, must be a str; otherwise raise a structural
         error "non-str value in workflow.agent". An empty or
         whitespace-only value normalizes to None
       - env: if present, must be a dict of str→str; a non-dict value
         raises a structural error "non-mapping env in workflow"; a
         non-str key raises "non-str key in workflow.env"; a non-str
         value raises "non-str value in workflow.env.KEY". An empty map
         equals absence — build with env=None
```

**REPLACE** algorithm step 5:

```text
    5. For every other top-level key — raise a structural error
       "unknown key in workflow: KEY; valid keys: prompt, stages,
       extend, memory, profile, build, assistants, delegation, repeat,
       gates, agent, env"
```

**REPLACE** algorithm step 7:

```text
    7. If prompt is None AND stages is empty (no entries) AND extend is
       empty (no entries) AND memory is None AND build is None AND
       assistants is empty AND delegation is None AND repeat is None
       AND gates is None AND agent is None AND env is None
       — raise a structural error "empty workflow — provide at least
       prompt, one stage, one extend entry, the memory block, the build
       block, the assistants block, the delegation block, the repeat
       block, the gates block, the agent key, or the env block"
       (profile never rescues a workflow from emptiness — activation
       is not content)
```

**REPLACE** algorithm step 8:

```text
    8. Return `WorkflowDocument` from the parsed prompt, stages, extend,
       memory, profile, build, assistants, delegation, repeat, gates,
       and the two global keys (the authored agent, or None; the
       authored env map, or None)
```

**REPLACE** the first requirements bullet:

```text
    - Top-level unknown keys are a structural error — only prompt,
      stages, extend, memory, profile, build, assistants, delegation,
      repeat, gates, agent, and env are accepted
```

**REPLACE** the "A workflow-file with none of a top-level…" requirement
bullet with the version listing the two global keys (see the
WorkflowDocument requirements above).

**ADD** requirements:

```text
    - agent (when present) must be a str; a non-str value raises
      "non-str value in workflow.agent"; an empty or whitespace-only
      value normalizes to None (absence)
    - env (when present) must be a dict of str→str; a non-dict value
      raises "non-mapping env in workflow"; a non-str key raises
      "non-str key in workflow.env"; a non-str value raises "non-str
      value in workflow.env.KEY"; an empty map equals absence
      (env=None)
    - A workflow consisting of the agent key alone or the env block
      alone is valid — both keys count as content
```

**ADD** constraint:

```text
    - Do not resolve agent to a wrapper path, merge env with any other
      layer, or apply either global anywhere here — the consumers own
      every resolution law
```

#### Footer

**REPLACE** the closing clause of `Description`: append "…and the two
global run settings (agent and env)" to the parser-zone enumeration.
`Author: Goga`; `CreatedAt` unchanged.

#### `.usages` file — `goga/pipeline/workflow/.usages/parse-workflow.md` [UPDATED]

**REPLACE** the "Accepted structure" opening:

````markdown
Top-level keys: `prompt`, `stages`, `extend`, `memory`, `profile`, `build`,
`assistants`, `delegation`, `repeat`, `gates`, `agent`, `env`.

- `profile` — optional top-level string default naming the workflow's default
  contributor profile (`profile: default`); a non-str value is a structural
  error "non-str value in workflow.profile"; an empty/whitespace value
  normalizes to None. Activation reads this default from the RAW text via the
  load-time peek — a value that materializes only through template rendering
  does not participate in activation.
- `agent` — the workflow-global run agent (a single string; see below).
- `env` — the workflow-global environment layer (a str→str map; see below).
- `build` — the strict six-field build block (see below).
- `assistants` — the name-keyed catalog map of run-level helpers; the
  per-stage attachments (`stages.<name>.assistants`) are a name-keyed map
  too — each entry a reference (`gate`/`when`, `when` required) or a full
  inline declaration (the catalog field set plus `gate`/`when`).
- `delegation` — the delegation-bounds block (`depth`, `max_tasks`).
- `repeat` — the run-cycle tuning block (`max_cycles`, `keep_runs`; below).
````

**ADD** the following section after "Accepted structure", before "The build
block":

````markdown
## The global run settings (workflow.agent / workflow.env)

`agent` and `env` are the workflow-global run settings — the layer every
consumer resolves ahead of the project configuration's own globals:

```yaml
agent: claude
env:
  ANTHROPIC_MODEL: '{{ profile.model }}'
  GOGA_LOG_LEVEL: info
```

Structural validation (parse time):

- `agent`: a non-str value → structural error "non-str value in
  workflow.agent"; an empty or whitespace-only value normalizes to None
  (absence). The value names an agent — it is not validated against a
  known agent set; a missing wrapper surfaces at invocation time.
- `env`: a non-mapping value → structural error "non-mapping env in
  workflow"; a non-str key → "non-str key in workflow.env"; a non-str
  value → "non-str value in workflow.env.<key>". An empty map (`env: {}`)
  equals absence. Env key shapes are not validated here — illegal keys
  surface as strict pre-run errors at the delivery points.

Both keys count as content for the empty-workflow rule: a workflow
consisting of `agent:` alone (or `env:` alone) is valid. Both ride the
whole-file contributor-profile rendering — profile data may drive the
values like anywhere else in the file. This cell does NOT act on either
key: no wrapper resolution, no layer merging, no launch — the pipeline
run and the build own the layering laws of the globals.
````

**REPLACE** the "Empty-workflow rule" section:

````markdown
A workflow is empty only when `prompt`, `stages`, `extend`, `memory`,
`build`, `assistants`, `delegation`, `repeat`, `gates`, `agent`, AND `env`
are ALL absent — `profile` never counts (activation is not content). The
structural error "empty workflow" names the content options. A workflow
consisting of the `build:` block alone is valid; a workflow consisting of
the `repeat:` block alone is valid; a workflow consisting of `agent:`
alone is valid; a workflow carrying only `profile: name` is not.
````

---

### Cell 2: `goga/pipeline/hooks` — CODEMANIFEST [MODIFIED]

#### Header → `Annotations`

**ADD** at the end of the overlay-merge paragraph (after the gates
preservation sentences):

```text
The overlay merge preserves the global run settings of the workflow
model: the authored agent and env fields ride the rebuilt document
verbatim — in the verbatim-from-base set beside profile and build. The
merge reads the globals of the base only; a tool can neither supply
nor override them — global run settings belong to the workflow author
alone.
```

#### Body → `"merge_workflow_overlay(...)"` (signature unchanged)

**REPLACE** algorithm step 8:

```text
    8. Return the `WorkflowOverlay` — the workflow None only when the
       base is None and no contribution committed; the final document
       assembly carries the profile, build, agent, and env fields of
       `base` verbatim (exactly as memory survives the rebuild), the
       assistants field of the base together with the appended
       contributing entries, the effective repeat, and the effective
       gates settings block riding the rebuilt document verbatim —
       workflow-level instructions never vanish in the overlay
```

**ADD** requirement:

```text
    - The rebuilt `WorkflowDocument` preserves the global run settings:
      the agent and env fields of the base ride the rebuild verbatim —
      a rebuild that drops them would silently revert a tool-amended
      run to configuration-level globals; a tool-supplied global never
      reaches the final document (the merge reads the globals of the
      base only)
```

**ADD** constraint:

```text
    - Do not read the agent or env fields of any contribution document
      — the globals are author-territory; only the base carries them
      into the overlay
```

#### Footer

**REPLACE** in `Description`: "the workflow-level `profile` and `build`
fields" → "the workflow-level `profile` and `build` fields, the global
`agent` and `env` run settings". `Author: Goga`; `CreatedAt` unchanged.

#### `.usages` file — `goga/pipeline/hooks/.usages/checkpoints.md` [UPDATED]

**REPLACE** the first bullet of "Amend before compilation" (insert the
globals sentence after "extend entries add;"):

````markdown
- A tool contributes one declarative `WorkflowDocument`; authored intent
  wins per slot — the prompt appends, the memory block is whole, the repeat
  block is whole, the gates settings block is whole, stage fields fill only
  what the author left unset (an authored per-stage check-step list is
  never overwritten), extend entries add; the workflow-global run settings
  (`agent`, `env`) ride the authored workflow verbatim — a tool can
  neither supply nor override them; the assistant catalog merges
  with field-level overrides —
  the winning tool-delivered entry of a name is the base and the authored
  entry replaces exactly the fields it specifies (agent, env, delegate,
  prompt, skills; an explicit empty skills/env clears), omitted fields
  flow from the tool, a delivered name with no authored entry adds fresh
  (tool inline declarations under an authored name stay dropped); the
  delegation block is whole, and stage assistant maps append with name
  deduplication.
````

---

### Cell 3: `goga/pipeline` — CODEMANIFEST [MODIFIED]

#### Header → `Annotations`

**ADD** the following paragraph after the "Per-stage environment delivery"
paragraph:

```text
The run coordination resolves the effective global agent and the
effective launch env base from the effective workflow document and
the effective project configuration. The workflow's global agent,
when the effective workflow carries one, is the global agent of the
run — the single value feeding the afm client command, the per-stage
wrapper exec fallback, and the assistant fallback; with no workflow
global the effective pipeline agent holds the role. The effective
launch env base is the key-wise merge of the effective pipeline.env
with the workflow's global env — a workflow key overrides the
same-named configuration key, untouched configuration keys survive;
the CLI entries layer above the base and the engine-variable keys drop
from it silently. The globals activate only through the run's
workflow: with the layer off or no workflow resolved, the
configuration values feed the same consumption points. Gate AI-review
steps keep their own strict agent requirement — the global agent is
never their fallback. The card form performs no global resolution —
wrapper generation and launch layers are run-only surfaces.
```

#### Body → `"run_pipeline(...)"` (signature unchanged)

**INSERT** new algorithm step 14 (former steps 14–23 shift to 15–24):

```text
    14. Resolve the effective global agent: the agent field of the
        overlay workflow document when it carries one, otherwise the
        effective configuration's pipeline.agent. The resolved value
        feeds the per-stage wrapper generation (its exec fallback), the
        afm configuration write (the client command and the assistant
        fallback), and nothing else
```

**REPLACE** in step 15 (former 14): "the effective pipeline agent" →
"the effective global agent (resolved at step 14)".

**REPLACE** in step 17 (former 16): "write the afm configuration file
via `write_afm_config` with the effective pipeline agent" → "…with the
effective global agent (resolved at step 14)".

**REPLACE** step 20 (former 19):

```text
    20. Compose the afm launch environment layer per `extra-env-carriage`:
        decode the CLI entries payload via `decode_extra_env` from the
        dedicated engine variable; apply the decoded entries above the
        effective launch env base — the key-wise merge of the effective
        pipeline.env task env layer with the overlay workflow's global
        env (a workflow key overrides the same-named configuration key,
        untouched configuration keys survive); add
        GOGA_PROFILE=<effective profile name> when a profile resolved
        — the afm subprocess and its stages inherit it, so a build
        invoked inside the pipeline runtime picks the same profile up
        through its env channel with no additional options (the
        workflow travels via GOGA_WORKFLOW of the launch environment;
        the launcher env-file line stays ambient-only); drop the keys
        of the composed base and the CLI entries colliding with the
        engine set — GOGA_PROFILE, GOGA_WORKFLOW, GOGA_HOME_PROFILES,
        GOGA_EXTRA_ENV, AFM_DIR, AFM_DOCKER_FILE_ROOTS, HTTP_PROXY,
        HTTPS_PROXY, NO_PROXY — silently, the inherited launch values
        stand. A damaged payload is one clean error here — no events
        fire, afm never launches
```

**REPLACE** in the GOGA_PROFILE requirement bullet ("When a profile
resolved, the afm launch layer carries GOGA_PROFILE…"): "keys of
pipeline.env and the CLI entries colliding with the engine set" →
"keys of the composed base and the CLI entries colliding with the
engine set".

**ADD** requirements:

```text
    - The effective global agent resolves once per run from the overlay
      workflow document's agent field, falling back to the effective
      pipeline.agent; it feeds exactly the three consumption points
      and nothing else; with the workflow layer off or no workflow
      resolved the effective pipeline.agent holds the role
    - The launch env base is the key-wise merge of pipeline.env with
      the workflow global env (workflow wins per key, config keys
      survive); CLI entries stay above; engine-variable keys still
      drop silently
    - A gate AI-review step carries its own agent requirement — the
      global agent never backs a gate step
```

#### Body → `"write_afm_config(...)"` (signature unchanged)

**REPLACE** in the type annotation opening: "the agent client command
resolved from the effective pipeline agent" → "the agent client command
resolved from the effective global agent".

**REPLACE** the `agent` parameter annotation:

```text
    `agent`: the effective global agent — the workflow global agent of
             the effective workflow when it carries one, otherwise the
             authored pipeline.agent as amended by the config
             delivery; None when neither resolves
```

**ADD** requirement:

```text
    - The assistant fallback resolves to the `agent` parameter — the
      effective global agent including the workflow global layer; an
      assistant declaration without its own agent launches under the
      workflow's global agent when the workflow carries one
```

#### Body → `"apply_stage_env_wrappers(...)"` (signature unchanged)

**REPLACE** the `global_agent` parameter annotation:

```text
    `global_agent`: the effective global agent — the workflow global
                    agent of the effective workflow when it carries
                    one, otherwise the effective pipeline agent; None
                    when no global agent resolved (a script claim
                    needs no agent at all)
```

#### Body → `"apply_skip_stages(...)"` (signature unchanged)

**REPLACE** the tail of algorithm step 4 (after the gates sentence):

```text
       … gates = the gates field of `workflow` when it is not None
       else None — carried verbatim; agent = the agent field of
       `workflow` when it is not None else None; env = the env field
       of `workflow` when it is not None else None — carried verbatim.
       The input `workflow` and its maps are NOT mutated
```

**ADD** requirements:

```text
    - The global run settings (agent, env) of the input workflow
      survive the rebuild verbatim — a rebuild that drops them would
      silently revert a skip-driven run to configuration-level globals
    - When `workflow` is None and `skip_stages` is non-empty — the
      constructed `WorkflowDocument` carries agent None and env None
```

#### Footer

**REPLACE** in `Description`: add "the workflow-global run-settings
resolution (the effective global agent and the launch env base)" to the
run-coordination enumeration. `Author: Goga`; `CreatedAt` unchanged.

#### `.usages` file — `goga/pipeline/.usages/run-pipeline.md` [UPDATED]

**REPLACE** the sentence in "Configuration: load-and-amend":

````markdown
Everything downstream consumes the effective configuration — the afm
configuration write reads the effective `pipeline.agent`, the launch layer
reads the effective `pipeline.env` — each overridable by the workflow's
global `agent`/`env` keys (see Workflow-global run settings). The first
failing tool stops the run with a clean error naming the tool and the
action: afm never launches and no run events fire.
````

**REPLACE** the opening of "afm configuration":

````markdown
Before the launch the coordination writes the whole afm configuration file
via `write_afm_config`: the client command resolved from the effective
global agent (the workflow's global `agent` when the effective workflow
carries one, else the effective `pipeline.agent`) — written only when an
agent resolves, so per-stage workflow agents or afm's own defaults cover
the absent global default — plus the five static fields …
````

**ADD** the following section after "Workflow amendment":

````markdown
## Workflow-global run settings

A workflow-file may carry two global run settings — `agent` (a string) and
`env` (a str→str map). When a workflow is in effect, its globals override
the configuration's own pipeline globals:

- The **effective global agent** is the workflow's `agent` when it carries
  one, else the effective `pipeline.agent`. One resolved value feeds the
  three global consumers: the afm client command of the configuration
  write, the exec fallback of the per-stage env wrappers, and the
  assistant fallback (an assistant declaration without its own agent
  launches under the workflow's global agent).
- The **effective launch env base** is `pipeline.env` key-wise merged with
  the workflow's `env` — a workflow key overrides the same-named config
  key, untouched config keys survive. CLI entries (`-e` /
  `GOGA_EXTRA_ENV`) stay above the base; engine-variable keys drop
  silently, as ever.

The globals are ambient: stages, gate steps, and assistants inherit the
global env through the afm launch layer exactly as they inherit
`pipeline.env`. Activation is workflow-scoped — with `--no-workflow`, a
silent auto-match miss, or no workflow-file, the configuration values
feed the same points and nothing changes. Gate AI-review steps still
require their own `agent` — the global agent is not their fallback.
````

**REPLACE** in "Environment":

````markdown
… the composed layer — the effective launch env base (`pipeline.env`
key-wise merged with the workflow's global `env`) with the decoded CLI
entries applied above it, plus `GOGA_PROFILE=<effective profile name>`
when a profile resolved — passes to `run_flow` as its `env` parameter …
Keys of the composed base and the CLI entries colliding with the engine
set — `GOGA_PROFILE`, `GOGA_WORKFLOW`, `GOGA_HOME_PROFILES`,
`GOGA_EXTRA_ENV`, `AFM_DIR`, `AFM_DOCKER_FILE_ROOTS`, `HTTP_PROXY`,
`HTTPS_PROXY`, `NO_PROXY` — are dropped silently from the layer; the
inherited launch values stand.
````

#### `.usages` file — `goga/pipeline/.usages/per-stage-env.md` [UPDATED]

**ADD** at the end of the "Delivery mechanism" section:

````markdown
The global env layers — `pipeline.env` and the workflow's global `env` —
reach every stage ambiently through the afm launch layer; a stage wrapper
exports only the stage's own values above them. Nothing about the
per-stage delivery changes with a workflow global env in effect.
````

---

### Cell 4: `goga/build` — CODEMANIFEST [MODIFIED]

#### Header → `Annotations`

**REPLACE** the "Workflow layering" paragraph:

```text
Workflow layering: build settings compose config < workflow global <
workflow build: < CLI at the resolution point. The workflow's two
global run settings ride the same layering: the global agent fills
every pass-agent field that neither the build block nor the
configuration fills, and the global env merges key-wise under every
pass env (a workflow key overrides the same-named configuration key,
untouched configuration keys survive; the build-block env wins per key
above the global). The layering applies whenever a workflow is in
effect — a document without a build: block still carries its globals.
Use `load-workflow` for the loading chain and `profiles` for the
activation rules.
```

#### Body → `"build(plan: str, config: ProjectConfig, cli_options: dict) -> exit_code:int"` (signature unchanged)

**REPLACE** algorithm step 4:

```text
    4. Layer the build settings when a workflow is in effect:
       `merge_workflow_build` of the effective config.build with the
       document's build block (None when the document carries no
       block) and the document's global agent and env — the layered
       BuildConfig feeds every downstream step; the layering runs
       whenever the loaded document is present (the globals apply with
       no build block too). A build invocation whose configuration has
       no build section is one clean logged error naming the
       requirement (exit 1, no events, nothing written) before any
       layering — with or without a workflow in effect, reachable only
       via a direct in-container invocation (the host launcher guards
       the section host-side)
```

**REPLACE** the workflow-layering requirement bullet:

```text
    - Workflow layering composes config < workflow global < workflow
      build: < CLI at the resolution point; an absent value at every
      layer never overrides; env maps merge key-wise
```

#### Body → `"merge_workflow_build(...)"` — full replacement (NEW signature)

```yaml
"merge_workflow_build(config: BuildConfig, build_block: WorkflowBuild | None, global_agent: str | None = None, global_env: dict[str, str] | None = None) -> config: BuildConfig":
  location: workflow_build.py
  annotations: |
    Overlay the workflow layers onto the effective build configuration:
    the two global run settings as the middle layer and the six-field
    build block above them — producing a NEW BuildConfig where each pass
    agent resolves build-block > global > configuration, each pass env
    merges key-wise configuration < global < block, and absent values at
    every layer never override.

    `config`: the effective build configuration (the base layer)
    `build_block`: the workflow build block model, or None when the
                   workflow carries no block (the globals still layer)
    `global_agent`: the workflow's global agent, or None
    `global_env`: the workflow's global env map, or None
    `config`: the layered build configuration (a new value; inputs
              unmutated)

    Algorithm:
    1. Agent fields, per pass (root, review, additional): the
       build-block field when set, else `global_agent` when set, else
       the configuration field; None only when all three sources are
       unset
    2. Env maps, key-wise with the later layer winning per key: each
       pass env (tasks, review, additional) = the configuration pass
       env overlaid with `global_env`, then with the block pass env —
       the rest of each underlying env survives. The global env is a
       base under the review and additional env layers alike; the
       configuration's own fields still never inherit into each other
       (the configuration root env stays the tasks-pass layer only)
    3. Every other field of BuildConfig and its nested models passes
       through verbatim (session knobs, iteration caps, skip, roles,
       base_ref, strategy, finalize, patience, prompts_dir,
       agents_dir, proxy, hosts)
    4. The agent-inheritance cascade of the settings resolution runs
       over the layered values — an unset layered review agent
       inherits the layered root (block agent, else global, else
       configuration agent); an unset layered additional agent
       inherits the layered review agent

    Requirements:
    - Pure — new BuildConfig and new nested models; inputs unmutated
    - An absent value at any layer (None block field, None global,
      None config field) never overrides
    - `config` is always a non-None `BuildConfig` — the workflow
      layers overlay ONLY onto an existing build section; a build
      invocation with no build section in .goga/config.yml raises one
      strict error naming the requirement (reachable only via a direct
      in-container invocation — the host launcher guards the section
      host-side) instead of the raw attribute failure
    - When config.review is None and any review-sourced value would be
      set (a block review field, or a global reaching the review
      pass): construct a NEW `ReviewConfig` (the layered set fields,
      every other field None / empty; a NEW
      `AdditionalReviewConfig` when additional-sourced values are set)
      so `resolve_run_settings` receives a well-formed layered
      configuration
    - With `global_agent` and `global_env` both None the layering
      matches the block-only overlay exactly

    Constraints:
    - Do not apply CLI values here — CLI applies at the settings
      resolution, preserving config < workflow global < workflow
      build: < CLI
    - Do not resolve wrappers or validate agents here
    - Do not inherit configuration env between passes here — the
      global env is the only cross-pass base; the pass env layers stay
      otherwise independent
```

#### Body → `"resolve_run_settings(...)"` (signature unchanged)

**REPLACE** in the type annotation opening: "when a workflow is in
effect, the caller has already overlaid its build block via
`merge_workflow_build`" → "when a workflow is in effect, the caller has
already overlaid its global run settings and build block via
`merge_workflow_build`".

#### Footer

**REPLACE** in `Description`: "Workflow-driven build-settings layering
(config < workflow build: < CLI)" → "Workflow-driven build-settings
layering (config < workflow global < workflow build: < CLI)". `Author:
Goga`; `CreatedAt` unchanged.

#### `.usages` file — `goga/build/.usages/workflow-layering.md` [UPDATED]

**REPLACE** the Domain sentence: "the six-field `build:` block, the
key-wise env merge, and the config < workflow < CLI order" → "the two
global run settings (`agent`, `env`), the six-field `build:` block, the
key-wise env merge, and the config < workflow global < workflow build: <
CLI order".

**REPLACE** the "Layering order" section:

````markdown
## Layering order

    .goga/config.yml  <  workflow global (agent/env)  <  workflow build:  <  CLI flags

The workflow-file may carry two global run settings — top-level
`agent` (a string) and top-level `env` (a str→str map) — that apply
whenever a workflow is in effect, with or without a `build:` block:

- Agent: each pass (root, review, additional) resolves the
  `build:`-block field, else the global `agent`, else the config
  field. The config's inheritance cascade (review inherits root,
  additional inherits review) then fills the still-unset fields from
  the effective, post-override root.
- Env: each pass env merges key-wise — config < workflow global <
  `build:` block < CLI. The global env is a base under the review and
  external-review env layers too; the config's own fields still never
  inherit into each other (config root env stays tasks-only).
- Absent values at any layer never override; an empty global env map
  equals absence.

Example: the workflow sets one global model variable — every pass
(task, review, external review) receives it above its own config env,
and a `build.env` key can still win per key.
````

---

## Dependency Map

```
goga/config (models, UNTOUCHED) ─────────────────────────────────┐
                                                                 │
goga/pipeline/workflow  [MODIFIED: grammar + WorkflowDocument]    │
   │  WorkflowDocument / WorkflowBuild / LoadedWorkflow /        │
   │  load_workflow / WorkflowSyntaxError                        │
   ├──> goga/pipeline/hooks  [MODIFIED: merge_workflow_overlay]  │
   │        │  WorkflowOverlay / PipelineHooks / contexts         │
   │        ▼                                                    ▼
   ├──> goga/pipeline  [MODIFIED: run_pipeline / write_afm_config /
   │        apply_stage_env_wrappers / apply_skip_stages]
   │
   └──> goga/build  [MODIFIED: build / merge_workflow_build]

goga/pipeline/compiler — UNTOUCHED (consumes neither key)
goga/agents/wrapper   — UNTOUCHED (pure path resolution)
goga/commands/build   — UNTOUCHED (workflow carriage exists)
```

No new import edges: the global values are primitives (`str`,
`dict[str, str]`) riding the existing `WorkflowDocument` / `WorkflowBuild`
carriage.

---

## Verification Checklist

### After each CODEMANIFEST change

- [ ] `goga lint` passes for all four cells (DSL syntax: quoted signatures,
      `location` unchanged, properties with types, Header/Body/Footer order)
- [ ] Annotations reference only resolvable names (usages keys, types,
      signature variables); no "from Imports" phrasing in new text
- [ ] No annotation duplicates another level; no implementation details
- [ ] Footers updated only where stated; `Author: Goga` and `CreatedAt`
      preserved

### After implementing the parser (cell 1)

- [ ] A workflow-file with top-level `agent` and/or `env` parses; both
      fields present on `WorkflowDocument`
- [ ] Non-str `agent` (map, list, number) → structural error; empty /
      whitespace-only → None
- [ ] Non-string-map `env` (scalar, list, non-str key/value) → structural
      error; empty map → None
- [ ] `agent:`-only and `env:`-only workflows are valid; `profile:`-only
      workflow still raises the empty-workflow error with the new message
- [ ] Unknown-key error lists the twelve valid keys
- [ ] Contributor-profile rendering carries both keys; the profile peek
      is unaffected

### After implementing the overlay (cell 2)

- [ ] Authored `agent`/`env` survive `merge_workflow_overlay` verbatim
- [ ] A tool contribution carrying `agent`/`env` never lands either field
      in the merged document
- [ ] `apply_skip_stages` rebuild carries both fields; skip-driven
      workflow-less construction carries None/None

### After implementing the run (cell 3)

- [ ] Workflow global `agent` feeds the afm client command, the stage
      env-wrapper exec fallback, and the assistant fallback; without it,
      `pipeline.agent` applies exactly as before
- [ ] Launch env = key-wise `pipeline.env` ⊕ workflow `env` (workflow key
      wins, untouched config keys survive); CLI entries above;
      engine-variable keys still dropped
- [ ] Assistant without `agent` resolves to the workflow global agent,
      then the existing fallback chain
- [ ] Gate AI-review step without its own `agent` still fails strictly
- [ ] With `--no-workflow` / silent miss / no file: behavior identical to
      the pre-feature run (regression)
- [ ] The card output is unchanged

### After implementing the build (cell 4)

- [ ] Each pass agent resolves build-block > workflow global > config;
      the inheritance cascade runs from the effective post-override root
- [ ] Pass env merges key-wise config < workflow global < build-block <
      CLI for all three passes; the global env reaches review and
      external-review env as a base under their own layers
- [ ] Globals apply with no `build:` block (layering runs whenever a
      workflow is in effect)
- [ ] With no workflow active: build behavior identical to before
      (regression)
- [ ] `goga/commands/build`, compiler, wrapper resolution, config models
      show zero diff (contract drift check)

### Tests (mirror structure per `convention`)

- [ ] `tests/pipeline/workflow/test_parse_workflow_globals.py` (new, the
      block-family convention of test_parse_workflow_{assistants,gates,
      memory,repeat}.py) — grammar, normalization, empty-workflow
      message, unknown-key message; extend
      `test_workflow_document_contract.py` / `test_workflow_document_logic.py`
      for the field order and the empty-workflow rule
- [ ] `tests/pipeline/hooks/test_overlay.py` (+ a focused
      `test_overlay_globals.py` if the family split is preferred) —
      verbatim carriage, tool-global suppression
- [ ] `tests/pipeline/` — the three consumption points and the launch env
      merge boundaries (CLI wins, engine keys drop) in the run surfaces
      (`test_integration_materialization.py`, `test_pipeline_cli.py`);
      the assistant fallback in `test_afm_config_collaboration.py`; the
      rebuild carriage in `test_apply_skip_stages.py`
- [ ] `tests/build/test_workflow_build_merge_logic.py` and
      `test_workflow_build_merge_contract.py` — the 4-layer matrix for
      all three passes, cascade composition, no-block-with-globals case,
      globals-None regression
