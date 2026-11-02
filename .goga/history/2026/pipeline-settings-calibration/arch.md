# Architecture Plan — Pipeline Settings Calibration

## Topic

**Pipeline Settings Calibration** — five settled ADR decisions calibrating the
`goga pipeline` / `goga build` run path: direct in-container execution (D1),
assistant partial overrides (D2), the `!ENV` YAML constructor (D3), the static
`add_stage` field (D4), and the `--fail-on-error` flag (D5).

Plan path: `.goga/history/2026/pipeline-settings-calibration/arch.md`
(topic directory `.goga/history/2026/pipeline-settings-calibration/`).

Source of record: `adr.md` (five decisions), `prd.md` (R1–R5), `task.md`
(SC1–SC8, C1–C8). User decisions taken in the prototype interview: a new
sub-cell `goga/config/yaml` owns the `!ENV` loading (no code duplication);
the D2 content check covers every declaration of the effective document.

## Implementation Order

Leaves → root; each cell lists the reason for its position.

1. **`goga/config/yaml`** (CREATE) — no Imports; the leaf of the config
   family. Both config loaders depend on it.
2. **`goga/docker`** (MODIFY) — depends only on `goga/version`; its new
   predicate `is_in_docker` is imported by both command cells.
3. **`goga/config/project`** (MODIFY) — depends on `goga/config/yaml` (new
   edge); nothing in this topic depends on it besides consumers that already
   import it.
4. **`goga/config/tool`** (MODIFY) — depends on `goga/config/yaml` (new
   edge).
5. **`goga/pipeline/workflow`** (MODIFY) — no Imports; the model change
   (`WorkflowAssistant`) is consumed by the compiler, the hooks merge, and
   the afm-config write.
6. **`goga/pipeline/compiler`** (MODIFY) — imports `goga/pipeline/workflow`;
   receives the moved content check.
7. **`goga/pipeline/hooks`** (MODIFY) — imports `goga/pipeline/workflow` and
   `goga/hooks`; receives the field-level override merge.
8. **`goga/afm`** (MODIFY) — no Imports; the `--exit-on-fail` argv flag.
9. **`goga/pipeline`** (MODIFY) — imports afm, compiler, hooks, workflow,
   config, docker; threads the flag and writes the fifth static field.
10. **`goga/commands/pipeline`** (MODIFY) — the host launcher; imports
    `goga/docker` (now also `is_in_docker`); the direct-execution branch and
    the `--fail-on-error` source.
11. **`goga/commands/build`** (MODIFY) — the host build launcher; imports
    `goga/docker` (now also `is_in_docker`); the direct-execution branch.

## Artifacts

### 1. Cell `goga/config/yaml` — CREATE

#### CODEMANIFEST — `goga/config/yaml/CODEMANIFEST` (full new content)

```yaml
Usages:
  convention: .goga/usages/conventions.md
  yaml_env: .goga/usages/cooks/yaml_env_constructor.md

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and
    testing in the project

  This cell owns the environment-aware YAML loading of the configuration
  family: the `!ENV NAME` scalar tag resolved at load time through the
  yaml library's standard constructor mechanism. Use `yaml_env` for the
  constructor contract — the loader subclass scoping, the string-only
  resolution, and the library-native error channel. The home
  configuration loader is explicitly NOT a consumer of this cell: it
  stays on plain yaml.safe_load by product decision.

---

"parse_env_yaml(text: str) -> data: object":
  location: loader.py
  annotations: |
    Parse a configuration YAML text with environment references
    resolved: every `!ENV NAME` scalar resolves from the process
    environment at load time into a plain string.

    `text`: the raw YAML text of a configuration file
    `data`: the parsed value as-is — a mapping, a scalar, a list,
            whatever the YAML parses to; no content models, no validation

    Apply `yaml_env` for the constructor mechanism — the loader
    subclass, the constructor contract, and the error channel.

    Algorithm:
    1. Parse `text` through the env-aware loader subclass of the yaml
       safe loader with the `!ENV` scalar constructor registered on the
       subclass only (per `yaml_env`)
    2. Each tagged scalar resolves to a plain string — the referenced
       variable's value, "" when unset; no type coercion
    3. Return the parsed value unchanged

    Requirements:
    - The resolved value of a tagged scalar is always a string — no
      coercion; each field's own validation applies downstream
    - An unset variable resolves to ""
    - Malformed use (an empty argument, a non-scalar node) raises the
      yaml library's constructor error carrying the node position —
      no custom exception type
    - Registration happens on the loader subclass only — other
      yaml.safe_load call sites of the process stay unaffected

    Constraints:
    - Do not register the tag on the global yaml.SafeLoader or
      yaml.Loader classes
    - Do not validate, interpret, or normalize the parsed content —
      interpretation belongs to the consuming configuration loader
    - Do not log resolved values — they may carry secrets

---

Author: Goga
CreatedAt: 02/11/26
Description: |
  Owner of the environment-aware (!ENV) YAML loading for the goga
  configuration family — the project and tool configuration loaders
  parse through this cell; the home configuration stays on plain
  yaml.safe_load by product decision.
```

#### .usages file — `goga/config/yaml/.usages/env-variables.md` (full new content)

````md
# Environment references in configuration YAML (!ENV)

Domain: authoring environment-driven values in goga configuration files
and consuming the env-aware loader. Audience: authors of
.goga/config.yml and tool configuration files, and implementers of
configuration loaders that parse through `parse_env_yaml`.

## What the tag does

A scalar tagged `!ENV NAME` resolves, at load time, to the value of the
environment variable `NAME` — always as a plain string.

```yaml
# .goga/config.yml
pipeline:
  agent: !ENV PIPELINE_AGENT
```

- `PIPELINE_AGENT=claude` → `agent` parses to the string `"claude"`.
- `PIPELINE_AGENT` unset → `agent` parses to the empty string `""`;
  each field's own empty-value semantics then applies (the `agent`
  fields treat `""` as absence).
- No type coercion ever happens: `PORT: !ENV PORT` is the string
  value, and a field expecting an int rejects it per its own validation.

## Calling the loader

```python
from ..yaml import parse_env_yaml   # from a sibling sub-cell of goga/config

text = Path(".goga/config.yml").read_text()
raw = parse_env_yaml(text)   # plain Python value; tags already resolved
```

Relative import from a sibling sub-cell of `goga/config` goes one level
up (`..yaml`); a module directly inside `goga/config` uses
`from .yaml import …`.

The result carries resolved strings only — no tag objects survive the
load. Downstream code never sees `!ENV`.

## Where the tag applies

- Project configuration (`.goga/config.yml`) — yes.
- Tool configuration files (`.goga/tools/<tool>/<file>`) — yes.
- Home configuration (`~/.goga/config.yml`) — NO: the home loader stays
  on plain `yaml.safe_load` by product decision.

## Malformed use

An empty argument (`!ENV` with nothing) or a non-scalar position raises
the yaml library's own constructor error naming the file position —
fix the YAML, not the loader.

## Testing note

Resolution is environment-dependent: tests control the environment
(monkeypatch the variable) and must not rely on ambient values.
````

### 2. Cell `goga/docker` — MODIFY

#### CODEMANIFEST — `goga/docker/CODEMANIFEST`

- **ADD** to the global `Annotations` block (after the seed-cell
  responsibility paragraph):

```yaml
  The in-image marker surface is two routines: the terminal guard
  `ensure_in_docker` for entrypoints that run ONLY inside the goga image
  (refusal exits the process), and the non-terminal predicate
  `is_in_docker` for dual-surface launchers that BRANCH between the
  docker substrate and direct in-container execution without refusing
  anything. Both read the same marker — `GOGA_DOCKER == "1"` — and
  nothing else; no further detection heuristics exist.
```

- **ADD** type declaration (after `ensure_in_docker`):

```yaml
"is_in_docker() -> flag: bool":
  location: env.py
  annotations: |
    Non-terminal in-image marker query: True only when the process runs
    inside the goga Docker image (the `GOGA_DOCKER` marker equals "1").
    The branching counterpart of the terminal guard `ensure_in_docker` —
    dual-surface launchers call this to choose the execution substrate
    (docker run on the host, direct child execution in the image)
    without refusing to run.

    `flag`: True when `GOGA_DOCKER` equals "1"; False for every other
       value including unset

    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. Read the `GOGA_DOCKER` environment variable
    2. Return True when the value is exactly "1"; False for every other
       value including unset

    Requirements:
    - Pure query — no output, no process termination, no filesystem or
      subprocess work
    - The marker rule is shared with `ensure_in_docker`: exactly
      `GOGA_DOCKER == "1"` means in-image; nothing else is consulted
    - Both branches (True/False) are covered by tests

    Constraints:
    - Do not terminate the process or print — refusal belongs to
      `ensure_in_docker`
    - Do not read any environment variable besides `GOGA_DOCKER`
    - Do not cache the value — callers may test the marker at any moment
```

Imports, Usages, Footer: unchanged.

#### .usages file — `goga/docker/.usages/ensure-in-docker.md`

- **EXTEND** "Public API" with:

```md
- `is_in_docker() -> bool` — non-terminal query over the same marker:
  True exactly when `GOGA_DOCKER == "1"`. For dual-surface launchers
  that run BOTH on the host and inside the goga image and must branch
  between substrates instead of refusing.
```

- **ADD** subsection under "Typical usage":

```md
### Branching on the marker (dual-surface launcher)

    from .docker import is_in_docker

    if is_in_docker():
        # direct in-container execution: spawn the composed
        # in-container command as a child process
        ...
    else:
        # host: docker run with the same composed command
        ...
```

- **AMEND** "Preconditions": `ensure_in_docker()` stays
  in-container-only; `is_in_docker()` is the marker surface
  dual-surface launchers use; it never refuses.
- **ADD** anti-pattern: "Do NOT use `is_in_docker()` to silently skip
  work — branch between two complete substrates; an option the chosen
  substrate cannot honor must fail with an error naming the option, not
  vanish."

### 3. Cell `goga/config/project` — MODIFY

#### CODEMANIFEST — `goga/config/project/CODEMANIFEST`

- **ADD** Imports block (top of header):

```yaml
Imports:
  - Types:
      - parse_env_yaml
    Usages:
      - env-variables
    From: goga/config/yaml
```

- **DELETE** the inline `yaml` usage key (now obsolete — parsing is
  delegated); `Usages` keeps `convention` only.
- **REPLACE** the global sentence `Use the \`yaml\` practice for parsing
  .goga/config.yml via yaml.safe_load().` with:

```yaml
  Load .goga/config.yml through `parse_env_yaml` — the environment-aware
  loader resolving `!ENV NAME` references at load time (per
  `env-variables`). Field validation applies verbatim: a resolved value
  is a plain string, and each field's established emptiness and type
  semantics hold.
```

- **CHANGE** `load_project_config`:
  - Algorithm step 2 → `Parse the YAML via \`parse_env_yaml\` — the
    environment-aware loader; \`!ENV NAME\` scalars resolve
    to plain strings at load time (unset resolves to ""); yaml errors,
    including constructor errors of malformed tag use, propagate
    unchanged through the library's error machinery`
  - **ADD** Requirement: `Environment references resolve at load time —
    a \`!ENV NAME\` scalar yields the referenced variable's value as a
    string; an unset variable yields "", which each field's own
    emptiness semantics treats exactly like an authored empty string
    (the \`agent\` fields resolve it to None; non-string fields reject it
    per their own validation)`
  - **ADD** Constraint: `Do not resolve \`!ENV\` references in this
    cell — loading goes through \`parse_env_yaml\`; no local tag
    handling exists`

All model types unchanged.

#### .usages file — `goga/config/.usages/project-configuration.md`

- **ADD** section (after "Loading Configuration"):

```md
## Environment references (!ENV)

Scalar values in `.goga/config.yml` may reference the environment: a
value written `!ENV NAME` resolves, at load time, to the string value of
the variable `NAME`.

```yaml
pipeline:
  agent: !ENV PIPELINE_AGENT
```

- `PIPELINE_AGENT=claude` → `pipeline.agent` is the string `"claude"`.
- `PIPELINE_AGENT` unset → `pipeline.agent` is the empty string — the
  loader treats it exactly like an authored empty value (the `agent`
  fields resolve it to `None`), so the configuration still loads.
- Resolution is always a string — no coercion. A field expecting an int
  or bool rejects an `!ENV` value per its own validation.
- Malformed use (`!ENV` with an empty argument, a tag in an impossible
  position) fails the load with the yaml library's own error naming the
  file position.
- The resolved configuration depends on the environment: one committed
  file can serve multiple environments. Tests must control the
  variables explicitly.

The home configuration (`~/.goga/config.yml`) does NOT resolve `!ENV` —
the tag applies to the project configuration only.
```

### 4. Cell `goga/config/tool` — MODIFY

#### CODEMANIFEST — `goga/config/tool/CODEMANIFEST`

- **ADD** Imports block (the cell's first):

```yaml
Imports:
  - Types:
      - parse_env_yaml
    Usages:
      - env-variables
    From: goga/config/yaml
```

- **DELETE** the inline `yaml` usage key; `Usages` keeps `convention`.
- **REPLACE** the global fragment mentioning the `yaml` practice with:

```yaml
  Parse a present tool config file through `parse_env_yaml` — the
  environment-aware loader of the configuration family (per
  `env-variables`). The read side stays a raw passthrough:
  `!ENV NAME` scalars resolve to plain strings at load time, and the
  content belongs to the tool that owns it — no models, no structural
  expectations, no validation.
```

- **CHANGE** `load_tool_config`:
  - Type annotation line `Use the \`yaml\` practice for the raw parse.` →
    REPLACE with `Parse through \`parse_env_yaml\` from Imports (per
    \`env-variables\`) — no local tag handling` — no backtick reference
    to the deleted `yaml` practice may survive in the document
  - Algorithm step 4 → `A present file parses via \`parse_env_yaml\` —
    the environment-aware loader (\`!ENV NAME\` scalars
    resolve to plain strings at load time, unset resolves to ""); the
    raw value returns as-is — yaml errors, including constructor
    errors of malformed tag use, propagate unchanged through the
    library's error machinery`
  - **ADD** Requirement: `Environment references resolve at load time —
    a tool config file may carry \`!ENV NAME\` scalars under the same rule as the
    project configuration; the resolved strings flow into the raw value
    the consuming tool interprets`
  - **ADD** Constraint: `Do not resolve \`!ENV\` references in this
    cell — loading goes through \`parse_env_yaml\`; no local tag
    handling exists`

#### .usages file — `goga/config/.usages/tool-configuration.md`

- **ADD** section:

```md
## Environment references (!ENV)

Tool config files resolve `!ENV NAME` scalars the same way the project
configuration does — at load time, to the variable's string value.

    # .goga/tools/coverage/config.yml
    fail_under: !ENV COVERAGE_THRESHOLD

- Unset variable → the empty string `""`; the interpreting tool applies
  its own semantics to it.
- Resolution is a string, never a number or bool — a tool expecting an
  int must parse it itself.
- Malformed use fails the read with the yaml library's own error naming
  the file position.
```

### 5. Cell `goga/pipeline/workflow` — MODIFY

#### CODEMANIFEST — `goga/pipeline/workflow/CODEMANIFEST`

- **AMEND** the global "One entry model" paragraph — DELETE the clause
  `and requires at least one of prompt or skills` from the
  full-inline-declaration sentence, then append:

```yaml
  A full declaration — catalog or inline — MAY carry no prompt and no
  skills: an override-style entry that configures delivery fields
  (agent, env, delegate) and inherits its content from a tool-delivered
  entry of the same name at the overlay merge; the effective-content
  requirement (prompt or skills) is enforced at COMPILATION, not here.
```

- **REPLACE** in the cell-responsibility header sentence
  `materialized defaults (delegate false, gate false, max_tasks 50
  whenever the delegation block is authored)` the fragment
  `delegate false` → `delegate None` — an absent delegate is now the
  inheritable None, not a materialized false
- **ADD** global paragraph (after the assistants paragraph):

```yaml
  The model preserves field presence for the override fields: an
  explicitly authored empty skills list or env map is carried as an
  explicit empty value (an override that clears), never normalized to
  absence; delegate carries None when not authored and the authored
  boolean otherwise. Per-stage env of WorkflowStage keeps its own
  empty-equals-absence rule — the presence discipline applies to the
  assistant fields only.
```

- **CHANGE** `WorkflowAssistant`:
  - Signature → `"WorkflowAssistant(name: str, prompt: str | None =
    None, skills: list[str] | None = None, agent: str | None = None,
    delegate: bool | None = None, env: dict[str, str] | None = None,
    gate: bool = False, when: str = \"checkpoints\")"`
  - `delegate` parameter text → `whether the assistant may create child
    tasks — None when not authored (the value is inheritable: the
    overlay merge lets a delivered base supply it), False when
    explicitly authored off, True when authored on`
  - `skills` / `env` parameter texts → note that an authored empty
    value is carried as an explicit override, never normalized
  - Property `"env -> dict[str, str] | None"` → REPLACE its annotation
    with `The assistant's environment instruction (string map); None
    when not authored — an authored empty map is an explicit override
    that clears` (the old "empty map equals absence" wording dies with
    the presence discipline)
  - Property `"delegate -> bool | None"` → `Whether the assistant may
    create child tasks. None when not authored — an inheritable value
    the overlay merge resolves from a delivered base; the explicit
    False is an authored opt-out; True is the authored permission.
    Downstream consumers materialize False when the effective value
    stays None.`
  - **ADD** Requirements: `delegate defaults to None (NOT False) — an
    absent key and an explicit delegate: false are DIFFERENT
    instructions and must stay distinguishable to the overlay merge`;
    `An authored empty skills list and an authored empty env map are
    carried as explicit empty values — never normalized to None at
    parse time`

- **CHANGE** `parse_workflow`:
  - Step 6.5 → replace the prompt-or-skills and env sentences with:

```yaml
        prompt and agent (when present) are str; skills (when present)
        is a list[str] (an authored empty list is carried as an explicit
        empty value — an override that clears); delegate (when present)
        is a bool (absent builds None — not False); env (when present)
        is a str→str map (an authored empty map is carried as an
        explicit empty value — NOT normalized to absence). An entry may
        carry none of prompt/skills — an override-style entry; the
        effective-content requirement is enforced at compilation. Every
        entry key must match [A-Za-z0-9._-] and must not be "assistant"
        ("assistant name is reserved"); a key repeated across the
        catalog and any inline declaration raises "duplicate assistant
        name: NAME". Build a `WorkflowAssistant` per entry with the key
        as name
```

  - Step 6.7 → replace the full-inline-declaration sentence with:

```yaml
        A value whose keys are within {gate, when} is a reference; a
        value carrying any further key is a full inline declaration (the
        catalog field set plus gate and when) — it MAY carry no prompt
        and no skills (an override-style inline declaration); the
        effective-content requirement is enforced at compilation. The
        empty-preservation and delegate rules of 6.5 apply verbatim to
        the inline field values. Build a `WorkflowAssistant` per entry
        with the key as name
```

  - Requirements → delete every "at least one of prompt or skills"
    rule (catalog and inline); REPLACE the catalog-grammar phrase
    `env is a str→str map (an empty map equals absence)` with `env is
    a str→str map (an authored empty map is an explicit override)`;
    **ADD**: `An assistant entry (catalog or
    full inline) without prompt and without skills parses successfully
    — override-style authoring; the requirement that the EFFECTIVE entry
    resolve content is the compiler's structural check, not a parse
    rule`; `For assistant fields, presence is preserved: skills [] and
    env {} are explicit empty overrides; delegate absent is None`

#### .usages file — `goga/pipeline/workflow/.usages/assistants.md`

- Catalog table `delegate` row → Default `not authored`, note:
  `explicit false is an authored opt-out; omitted is inheritable`.
- **REPLACE** "At least one of `prompt` or `skills` is required per
  entry." with:

```md
An entry MAY carry neither `prompt` nor `skills` — an override-style
entry that configures delivery fields (`agent`, `delegate`, `env`) and
takes its content from a tool-delivered entry of the same name. The
EFFECTIVE entry must resolve `prompt` or `skills` — enforced at
compilation with an error naming the assistant and its authoring site;
an override naming an assistant no tool delivers stops compilation.
```

- **ADD** section:

```md
## Explicit empty values (overrides)

`skills: []` and `env: {}` are authored overrides that CLEAR the field —
they are not absence. `delegate:` omitted is absence (the value may
flow from a tool-delivered entry); `delegate: false` is an explicit
opt-out. Absence vs empty decides what a tool delivery may still
supply.
```

- Structural-errors table → delete the `no prompt and no skills` row;
  in the compilation-time list **ADD**: `an effective entry resolving
  no prompt and no skills (including an override naming an assistant no
  tool delivers)`.
- **REPLACE** the inline-declaration sentence of the stage-attachments
  section (`it accepts the catalog field set plus gate/when and
  requires at least one of prompt or skills`) with `it accepts the
  catalog field set plus gate/when and may carry neither prompt nor
  skills — an override-style inline declaration (the effective-content
  requirement is enforced at compilation)`.
- **REPLACE** the anti-pattern `Do not rely on engine defaults: gate,
  delegate, and max_tasks are materialized by the parser, not silently
  inherited; when is authored on every attachment and the compiled
  engagement value is always written explicitly.` with `Do not rely on
  engine defaults: gate and max_tasks are materialized by the parser;
  delegate omitted is None — inheritable from a delivered base at the
  overlay merge, explicit false is an authored opt-out; when is
  authored on every attachment and the compiled engagement value is
  always written explicitly.`

#### .usages file — `goga/pipeline/workflow/.usages/parse-workflow.md`

- **AMEND** the `assistants` row (line ~93): append to the note:
  `(override-style entries — no prompt/skills — are valid declarations;
  content resolves at compilation)`.

Note on dependent cells: the parser relaxation flows to every importer
of `load_workflow` — `goga/build` included: an override-style entry
parses there too (strictly more permissive, no behavioral break; the
build path consumes no assistants). No manifest change in
`goga/build`; the ripple is acknowledged here.

### 6. Cell `goga/pipeline/compiler` — MODIFY

#### CODEMANIFEST — `goga/pipeline/compiler/CODEMANIFEST`

- **CHANGE** `compile_flow`:
  - Step 4.10 → **ADD** sub-item after the namespace assembly, before
    the per-stage resolution:

```yaml
           - the content check: EVERY declaration of the effective
             assistant namespace (the catalog plus every full inline
             declaration, override-style entries included) must resolve
             content — its effective prompt is not None OR its effective
             skills is not None; a declaration resolving neither (an
             override-style entry no tool delivery supplied content for)
             raises a structural error naming the assistant and its
             authoring site (the catalog
             workflow.assistants.<name> or the stage
             workflow.stages.<stage>.assistants.<name> whose entry
             declares it). The check addresses declarations only — a
             reference (gate/when only) carries no content of its own
             and resolves against a declaration
```

  - **ADD** Requirements:

```yaml
    - Every assistant declaration of the effective document resolves
      prompt or skills — the content requirement moved here from the
      parser; override-style entries are legal authoring that must be
      covered by a delivered base
    - A workflow without same-name assistant collisions compiles exactly
      as the same workflow carrying no override entries — the content
      check is the only additional compilation rule
    - The content-check error names the assistant AND its authoring
      site through the existing structural-error channel
```

  - **ADD** Constraint: `Do not enforce content presence at parse time
    or on references — the check runs here, over declarations of the
    effective document`

#### .usages file — `goga/pipeline/compiler/.usages/compile-flow.md`

- **REPLACE** the "Compilation checks" paragraph with:

```md
Compilation checks (structural errors naming the workflow location): an
attachment naming no member of the assistant namespace (the catalog plus
every full inline declaration); a DECLARATION of the namespace resolving
no prompt and no skills — every declaration must resolve content, so an
override-style entry (authored without prompt/skills) is legal only when
a tool-delivered entry of the same name supplies the content; the same
assistant name twice in one stage's list; an attachment on a stage whose
translated body carries `script`; an attachment on a stage whose
translated agents value is exactly `["planning"]`. The checks run over
the working body after skip removal and loop expansion. An authored
`assistants` key in a stage body is likewise a structural error — the
single authoring source is the workflow stages block.
```

### 7. Cell `goga/pipeline/hooks` — MODIFY

#### CODEMANIFEST — `goga/pipeline/hooks/CODEMANIFEST`

- **REPLACE** the global catalog-merge sentence ("The assistant catalog
  merges by name: an authored entry wins under its name; a contributing
  entry adds a fresh name; among contributing tools the later entry wins
  per name; a contribution entry whose name appears anywhere in the
  evolving merged assistant namespace … is dropped silently, so the
  merged document never carries a duplicate assistant name") with:

```yaml
  The assistant catalog merges by name with field-level overrides: among
  contributing tools the later entry wins per name, and that winning
  delivered entry is the BASE; an authored entry under the same
  name overrides field by field — every field the authored entry
  specifies (agent, env, delegate, prompt, skills — presence decides,
  an explicit empty skills/env is an override) replaces the base value
  while omitted fields keep flowing from the base. A delivered name with
  no authored entry adds as a fresh name verbatim. Tool INLINE
  declarations under an authored name stay silently dropped; every other
  duplicate-suppression rule of the evolving merged namespace holds —
  the merged document never carries a duplicate assistant name.
```

- **CHANGE** `merge_workflow_overlay`:
  - Step 4a → **REPLACE** with:

```yaml
    4a. assistants (catalog): resolve the winning delivered entry per
        name among the contributions in enumeration order (the
        later-tool-wins rule among contributions). For a name carrying an authored entry
        (the authored catalog or an authored inline declaration — one
        authoring surface owns the name): the winning delivered entry of
        that name is the BASE, and the authored entry overrides field by
        field — every field it specifies (agent, env, delegate, prompt,
        skills; presence decides — None is not authored, an explicit
        empty skills list or env map IS) replaces the base value, every
        omitted field flows from the base; no delivered entry under the
        name leaves the authored entry standing alone. A delivered name
        with no authored entry adds as a fresh name with the winning
        entry verbatim. Tool inline declarations under an authored name
        are dropped silently; the namespace carries each
        name exactly once
```

  - **ADD** Requirements:

```yaml
    - The override is field-presence based: an authored None means
      "not authored" (the base value flows), an authored empty
      skills/env means "clear" (the base value is replaced with the
      empty value), an authored delegate False is an opt-out while an
      absent delegate inherits the base value
    - A name authored inline and delivered in a tool CATALOG follows the
      same rule — the authored inline declaration overrides the
      delivered catalog entry field by field
    - Workflows whose assistant names collide with no tool delivery
      merge to their authored workflow verbatim
```

  - **ADD** Constraint: `Do not merge content fields partially — prompt
    and skills replace whole (no text concatenation, no list union); the
    field unit is the merge unit`

#### .usages file — `goga/pipeline/hooks/.usages/checkpoints.md`

- **REPLACE** the first bullet of "Amend before compilation" (the
  authored-intent-wins marker) with:

```md
- A tool contributes one declarative `WorkflowDocument`; authored intent
  wins per slot — the prompt appends, the memory block is whole, the repeat
  block is whole, stage fields fill only what the author left unset, extend
  entries add; the assistant catalog merges with field-level overrides —
  the winning tool-delivered entry of a name is the base and the authored
  entry replaces exactly the fields it specifies (agent, env, delegate,
  prompt, skills; an explicit empty skills/env clears), omitted fields
  flow from the tool, a delivered name with no authored entry adds fresh
  (tool inline declarations under an authored name stay dropped); the
  delegation block is whole, and stage assistant maps append with name
  deduplication.
```

### 8. Cell `goga/afm` — MODIFY

#### CODEMANIFEST — `goga/afm/CODEMANIFEST`

- **CHANGE** `run_flow`:
  - Signature → `"run_flow(flow_path: Path, port: int, max_parallel:
    int | None = None, exit_on_fail: bool = False, env: dict[str, str]
    | None = None) -> exit_code: int"`
  - **ADD** parameter text after `max_parallel`:

```yaml
    `exit_on_fail`: when True, the launch argv carries the engine's
                    explicit --exit-on-fail flag — a failed stage stops
                    the run and the engine exits with code 1 (the
                    engine's native capability, per the `afm` practice).
                    When False (default), the flag is OMITTED and the
                    engine's own failure semantics apply as without the
                    flag. The
                    flag is an argv flag — visible in the process
                    listing — never the AFM_EXIT_ON_FAIL environment
                    variable
```

  - Algorithm step 3 → append after the max_parallel clause: `, — when
    \`exit_on_fail\` is True — the --exit-on-fail flag,`
  - **ADD** Requirements: `Forward exit_on_fail via the explicit
    --exit-on-fail argv flag ONLY when True — False omits the flag, and
    the launch argv then carries no fail-fast flag`; `Exit-code
    propagation stays verbatim: with the flag set, a failed stage
    surfaces as the engine's exit code 1 returned verbatim`
  - **ADD** Constraints: `Do not set the AFM_EXIT_ON_FAIL environment
    variable — the argv flag is the single channel (visible in the
    process listing, per the \`afm\` practice)`; `Do not introduce new
    exit machinery — the engine's exit code propagates verbatim`

#### .usages file — `goga/afm/.usages/run-flow.md`

- **REPLACE** the signature line; **ADD** the `exit_on_fail` parameter
  bullet; **ADD** section and anti-pattern:

```md
## Fail-fast contract

The `--exit-on-fail` flag is emitted **only** when `exit_on_fail` is
True — the same omission discipline as `--max-parallel`. The flag rides
the argv (visible in the process listing); the `AFM_EXIT_ON_FAIL`
environment variable is never set by goga. The engine's exit code —
including the failure exit under the flag — propagates verbatim.
```

```md
- Do not set `AFM_EXIT_ON_FAIL` in the env layer or the process
  environment — the argv flag is the single channel.
```

### 9. Cell `goga/pipeline` — MODIFY

#### CODEMANIFEST — `goga/pipeline/CODEMANIFEST`

- **AMEND** the inline `argparse` usage — the run subcommand
  description now reads: `run (a required name, an optional --info
  flag, the workflow flags -w/--workflow NAME and --no-workflow, the
  profile flag -p/--profile NAME, a repeatable -s/--skip NAME, and a
  --fail-on-error flag — all five available with and without --info
  (fail-on-error takes effect in run mode only), --port required only
  without --info, and an optional --parallel N (run mode only)`.
- **CHANGE** `pipeline_cli`:
  - Algorithm step 1, run branch → append `and a --fail-on-error
    store-true flag`
  - Algorithm step 4, `run without --info` → `call \`run_pipeline\`
    with name, port, the parsed workflow flags, the parsed profile
    value, the parsed skip names, parallel, and the parsed fail_on_error
    value; return its exit code`
  - **ADD** Requirement: `The run subcommand accepts --fail-on-error;
    it binds in both info and run modes (ignored in info mode) — the
    same surface pattern as the workflow, profile, and skip flags`
- **CHANGE** `run_pipeline`:
  - Signature → `"run_pipeline(name: str, project_dir: Path, user_dir:
    Path, port: int, workflow: str | None = None, no_workflow: bool =
    False, profile: str | None = None, skip: list[str] | None = None,
    parallel: int | None = None, fail_on_error: bool = False) ->
    exit_code: int"`
  - **ADD** parameter text: `\`fail_on_error\`: the CLI fail-fast
    decision from the --fail-on-error flag of the in-container run
    subcommand; forwarded to \`run_flow\` as its exit_on_fail argument —
    a failed stage ends the run with the engine's failure exit code.
    False (default) changes nothing`
  - Algorithm step 21 → `Launch afm via \`run_flow\` with the compiled
    flow-file path, \`port\`, max_parallel=\`parallel\`,
    exit_on_fail=\`fail_on_error\`, and the composed layer as its env
    parameter — the process environment of the container stays
    untouched`
  - **ADD** Requirement: `Always forward fail_on_error to run_flow
    (exit_on_fail); False propagates — no flag, no env variable`
- **CHANGE** `write_afm_config`:
  - Step 2 → replace "the four static fields" phrasing with: `the FIVE
    static fields — the dashboard theme, the disabled browser launch,
    the disabled internal proxy provider, the in-container prompts
    directory, and the disabled dashboard stage-addition
    (add_stage.enabled false — the stage set presented to the engine
    stays exactly the compiled pipeline)`
  - Step 3.3 → `when the declaration carries a NON-EMPTY effective env
    map (not None and not empty — an explicitly cleared env is no env)`
    … and append `the effective delegate materializes False when None`
  - Requirements → replace "The four static fields" with "The five
    static fields and the hook entry are constants — never
    configurable through the project configuration or the CLI"; **ADD**:
    `add_stage.enabled false is written unconditionally on every launch
    — the dashboard of a goga-managed run accepts no out-of-model stage
    addition`; `Assistant env delivery keys on a non-empty effective map
    only — None and {} both mean "no closure"; delegate materializes
    False when the effective value is None`

#### .usages file — `goga/pipeline/.usages/pipeline-cli.md`

- Run form line → append `[--fail-on-error]`; **ADD** option bullet:
  `- --fail-on-error (flag) — fail-fast: a failed stage ends the run
  with a non-zero engine exit; binds in both modes, effective in run
  mode only (ignored with --info)`.

#### .usages file — `goga/pipeline/.usages/run-pipeline.md`

- Signature → `... skip=None, parallel=None, fail_on_error=False) ->
  exit_code`; **ADD** parameter bullet `\`fail_on_error: bool\` —
  fail-fast decision of the run; forwarded to \`run_flow\` as
  \`exit_on_fail\``; "four static fields" → "five static fields (theme,
  open_browser, proxy.enabled, prompts_dir, add_stage.enabled=false —
  the dashboard stage-addition is off for goga-managed runs)"; **ADD**
  chain example:

```md
    goga pipeline NAME --fail-on-error
      → docker run|direct … -m goga.pipeline run NAME --port PORT --fail-on-error
        → pipeline_cli: fail_on_error = True
          → run_pipeline(…, fail_on_error=True)
            → run_flow(…, exit_on_fail=True)
              → afm run --port PORT --exit-on-fail <flow>
```

### 10. Cell `goga/commands/pipeline` — MODIFY

#### CODEMANIFEST — `goga/commands/pipeline/CODEMANIFEST`

- **ADD** `is_in_docker` to the `Types` list of the `From:
  goga/docker` Imports block.
- **ADD** global annotation block (end of the header annotations):

```yaml
  Dual execution substrate: inside the goga image (the `is_in_docker`
  marker True) every form executes the SAME
  composed in-container command line and env contract directly as a
  child process of the current environment, instead of through
  `docker run`. The composition code the host path uses is the code the
  direct path reuses — one substrate, identical behavior and output on
  both surfaces; divergence between them is a defect. On the direct
  path the docker-CLI check is not performed, image acquisition never
  runs, and the port is still allocated and passed identically on both
  substrates. The
  host-only options (-t/--topic, --todo, --update, -e/--env,
  --add-host, --proxy) fail on the direct path with an explicit error
  naming the option — nothing is silently ignored; --clean keeps its
  meaning and wipes the in-container AFM_DIR before launch; --dry-run
  on the direct path prints the command it would run. The host path
  (marker absent) keeps the docker launch flow as its only path.
```

- **CHANGE** `pipeline`:
  - Signature → append `, fail_on_error: bool = False`
  - **ADD** parameter text: `\`fail_on_error\`: flag from the
    --fail-on-error option — the run-form fail-fast decision; forwarded
    into the in-container argv as --fail-on-error ONLY when set, and
    through the in-container CLI onto the engine's --exit-on-fail. Run
    form only; the listing and info forms accept it without effect`
  - **ADD** algorithm step 1a (after step 1):

```yaml
    1a. Resolve the execution substrate once via `is_in_docker`. On
        the direct path, reject every host-only option BEFORE any other
        work — each of `topic`, `todo`, `update`,
        `extra_env`, `add_host`, `proxy` that was passed is one clean
        error naming the option (stderr, exit 1; nothing to stdout, no
        topic procedure, no port allocation, no launch). The host path
        (marker absent) skips this step entirely
```

  - Step 5 run branch → append `and fail_on_error` to the
    `run_pipeline_container` argument set
  - **ADD** Requirements: `Expose --fail-on-error as a click flag;
    forward it into the in-container run argv only when set (absent ⇒
    no flag ⇒ the run launches with no fail-fast flag)`;
    `On the direct path, every host-only option is a named clean error
    before any activity — no option is silently ignored`
- **CHANGE** `run_pipeline_container`:
  - Signature → append `, fail_on_error: bool = False` (after
    `home_profiles`)
  - Step 9 args → append `and, only when fail_on_error is True,
    --fail-on-error — appended ONLY when set`
  - **ADD** step 12a (after step 12 composition, alternative to the
    DockerRunner branch):

```yaml
    12a. Direct path (`is_in_docker` True): skip the docker-CLI check
        (step 1), the env-file creation and docker-run input assembly
        (steps 8-9 — the composed env layers below apply to the child
        process environment directly; no env-file is written, nothing
        to unlink), the image acquisition (steps 10-11), and
        `DockerRunner`. Apply
        the SAME composed env contract to the child process environment
        (the env-file layers — home.env base, git identity, raw CLI
        entries, AFM_DIR=/home/goga/pipeline, AFM_DOCKER_FILE_ROOTS,
        the proxy triple, GOGA_EXTRA_ENV, GOGA_PROFILE,
        GOGA_HOME_PROFILES, GOGA_WORKFLOW — same encoders, same
        engine-skip rules) — no env-file is written; spawn the composed
        argv (python3 -m goga.pipeline run <name> --port <port> ...) as
        a child process with that environment, streaming output; when
        clean is True, wipe the in-container AFM_DIR directory first;
        install the SIGTERM/SIGINT handler (exit 128 + signum) and
        forward signals to the child; return the child's exit code
        verbatim. `update` never reaches this branch (the caller
        rejected it); on --dry-run print the direct command
        shell-quoted and exit 0
```

  - **ADD** Requirements: `The direct path and the container path
    compose the argv and env from the same code — the only difference
    is the execution substrate (child process vs docker run)`;
    `The direct path writes no env-file — the composed layers apply to
    the child environment directly; nothing to unlink`; `Signals on the
    direct path terminate the child and exit 128 + signum`; `--clean on
    the direct path wipes the in-container AFM_DIR before launch`
  - **ADD** Constraint: `Do not perform the docker-CLI check, image
    acquisition, or DockerRunner launch on the direct path — the branch
    ends at the child process`
- **CHANGE** `run_pipeline_info_container`:
  - **ADD** step 7a:

```yaml
    7a. Direct path (`is_in_docker` True): skip the docker-CLI check and
        the image steps; apply the same minimal env composition (the
        profile cargo variables only, when cargo exists) to the child
        process environment; spawn the composed argv (python3 -m
        goga.pipeline list[ --info] / run NAME --info ...) as a child
        process; return the child's exit code verbatim. No port, no
        persistent state, no env-file — the minimal read-only shape
        holds on both substrates
```

#### .usages file — `goga/commands/pipeline/.usages/pipeline-command.md`

- **ADD** section:

```md
## Direct in-container execution (GOGA_DOCKER=1)

Inside the goga image the same command runs without docker: the
composed in-container argv and env contract execute as a child process.

    # in-container
    goga pipeline deploy                     # direct run
    goga pipeline --list                     # direct listing
    goga pipeline deploy --fail-on-error     # direct run, fail-fast

- Host-only options are errors on this path: -t/--topic, --todo,
  --update, -e/--env, --add-host, --proxy — each fails naming the
  option.
- --clean wipes the in-container AFM_DIR (/home/goga/pipeline) before
  the run; --dry-run prints the direct command.
- The port is still allocated and passed; the env contract (engine
  variables, carriage payloads) is identical to the docker launch.
- On the host (no marker) nothing changes — docker run as always.
```

### 11. Cell `goga/commands/build` — MODIFY

#### CODEMANIFEST — `goga/commands/build/CODEMANIFEST`

- **ADD** `is_in_docker` to the `Types` list of the `From:
  goga/docker` Imports block.
- **ADD** global annotation block (end of the header annotations):

```yaml
  Dual execution substrate: inside the goga image (the `is_in_docker`
  marker True) the command executes the
  SAME composed in-container command line (python3 -m goga.build PLAN
  + cli_flags) and env contract directly as a child process of the
  current environment, instead of through `docker run`. The
  composition code the host path uses is the code the direct path
  reuses; divergence between the two surfaces is a defect. On the
  direct path the docker-CLI check is not performed and image
  acquisition never runs; the host-only options (-e/--env, --add-host,
  --proxy, --update) fail with an explicit error naming the option —
  nothing is silently ignored. --clean on the direct path wipes the
  directory ralphex actually uses without the nested bind-mount — the
  cwd-relative .ralphex of the project — and the no-.ralphex-in-project
  invariant holds on every exit path; ralphex state does not persist
  across direct runs (no host runtime mount exists on that path) — an
  accepted property of the direct surface, documented as such.
  --dry-run on the direct path prints the direct command shell-quoted
  and exits 0. The exit semantics of the command stay those of the
  build itself — this command carries no --fail-on-error flag.
```

- **CHANGE** `build` (signature UNCHANGED — no --fail-on-error):
  - **AMEND** algorithm step 1 (the docker-CLI availability check) —
    HOST PATH ONLY: the direct path of 1a skips it entirely (no
    docker-CLI check inside the image)
  - **ADD** algorithm step 1a (runs BEFORE the docker-CLI check of
    step 1):

```yaml
    1a. Resolve the execution substrate once via `is_in_docker` —
        BEFORE the docker-CLI check of step 1; on the direct path
        step 1 is skipped entirely. On the direct path, reject every
        host-only option BEFORE any other work — each of `extra_env`,
        `add_host`,
        `proxy`, `update` that was passed is one clean error naming the
        option (stderr, exit 1; nothing to stdout; no env assembly, no
        launch). The host path skips this rejection and runs step 1 as
        today
```

  - **ADD** step 14a (after the env composition, alternative to the
    docker steps 15–17):

```yaml
    14a. Direct path (`is_in_docker` True): skip the env-file write
        (step 9), the docker-run input assembly (steps 12-13), the
        docker-CLI check, `docker_build_if_not_exist`, `docker_update`,
        and `DockerRunner` (the docker steps 15-17); the composed env
        contract applies to the child process environment directly —
        no env-file is written, nothing to unlink.
        Apply the SAME composed env contract (home.env base, git
        identity, the proxy triple when a proxy resolved from config,
        GOGA_EXTRA_ENV, GOGA_PROFILE, GOGA_HOME_PROFILES) to the child
        process environment — no env-file is written; when `clean` is
        True, wipe <cwd>/.ralphex before the run; spawn the composed
        argv (python3 -m goga.build <plan> + cli_flags) as a child
        process with that environment, streaming output; install the
        SIGTERM/SIGINT handler (exit 128 + signum) and forward signals
        to the child; return the child's exit code verbatim. On dry_run
        print the direct command shell-quoted and exit 0. In finally:
        remove .ralphex/ from the project directory via
        `_cleanup_ralphex_in_project` as on the host path
```

  - **ADD** Requirements: `The direct path and the container path
    compose the argv and env from the same code — the only difference
    is the execution substrate`; `On the direct path, every host-only
    option is a named clean error before any activity; --update never
    reaches the direct branch`; `--clean on the direct path wipes
    <cwd>/.ralphex (the location ralphex uses without the nested
    bind-mount); the host runtime directory steps are docker-only`;
    `The no-.ralphex-in-project invariant holds under every exit path
    on both substrates`; `Signals on the direct path terminate the
    child and exit 128 + signum`
  - **ADD** Constraints: `Do not perform the docker-CLI check, image
    acquisition, or DockerRunner launch on the direct path — the branch
    ends at the child process`; `Do not add --fail-on-error to this
    command — build keeps its own exit semantics`

#### .usages file — `goga/commands/build/.usages/build.md`

- **ADD** section:

```md
## Direct in-container execution (GOGA_DOCKER=1)

Inside the goga image the same command runs without docker: the
composed in-container argv and env contract execute as a child process.

    # in-container
    goga build plan.md              # direct build
    goga build plan.md --clean      # wipes <cwd>/.ralphex first
    goga build plan.md --dry-run    # prints the direct command, exits 0

- Host-only options are errors on this path: -e/--env, --add-host,
  --proxy, --update — each fails naming the option.
- ralphex state does not persist across direct runs (the host runtime
  bind-mount exists only under docker); the project directory stays
  clean in every case.
- On the host (no marker) nothing changes — docker run as always.
```

## Dependency Map

```
goga/version
    ↑
goga/docker ──(is_in_docker, DockerRunner, codecs, builder)──→ goga/commands/pipeline
    │                        └──(is_in_docker, DockerRunner, builder, translate_params)──→ goga/commands/build
    │
goga/config/yaml (NEW) ──(parse_env_yaml)──→ goga/config/project ──┐
    └──────────────(parse_env_yaml)────────→ goga/config/tool ─────┤ (both re-exported by the goga/config facade)
                                                                   │
goga/pipeline/workflow ←──(Types)──── goga/pipeline/compiler ──┐   │
    ↑                              ←── goga/pipeline/hooks ←── goga/hooks
    │                                   │
goga/afm (run_flow) ←───────────────────┤
    ↑                                   │
goga/pipeline ──(compile_flow, hooks, workflow, config, docker, afm)──┘
    ↑ usages only (pipeline-cli, run-pipeline, …)
goga/commands/pipeline
goga/commands/build ──(build type)──→ goga/build
```

New edges: `goga/config/project → goga/config/yaml`,
`goga/config/tool → goga/config/yaml`. Extended existing edges: the
`goga/docker → goga/commands/{pipeline,build}` imports gain
`is_in_docker`. No edge changes direction; no cycles (the new cell has
no Imports).

## Verification Checklist

After implementing each artifact, verify:

- **`goga/config/yaml`**: `python -c "from goga.config.yaml import
  parse_env_yaml"`; `!ENV NAME` resolves (set → value, unset → `""`);
  malformed `!ENV` raises `yaml.constructor.ConstructorError` with a
  mark; the tag does NOT leak into other `yaml.safe_load` sites of the
  process; no resolved values logged.
- **`goga/docker`**: `is_in_docker()` returns True iff `GOGA_DOCKER`
  is exactly `"1"`; both branches tested; `ensure_in_docker` behavior
  unchanged.
- **`goga/config/project`**: `pipeline.agent: !ENV X` uses the variable
  when set (SC6); unset → loads, `agent` resolves `None` (SC6);
  non-string fields reject `""` per their own validation; home loader untouched.
- **`goga/config/tool`**: tool config resolves `!ENV` identically;
  raw passthrough preserved.
- **`goga/pipeline/workflow`**: an assistant entry without prompt and
  skills parses (override-style); `env: {}` / `skills: []` preserved
  (not None); `delegate` absent → `None`, `false` → `False`; stage env
  empty-map normalization unchanged; duplicate-name errors unchanged.
- **`goga/pipeline/compiler`**: an effective declaration with neither
  prompt nor skills → `StructuralError` naming the assistant and its
  site (SC5); an override covered by a tool compiles; non-colliding
  workflows compile byte-identically (SC5).
- **`goga/pipeline/hooks`**: authored `agent`/`env` override the tool
  base while content flows from the tool (SC4); authored `prompt`
  replaces; unspecified fields inherit (SC4); tool inline declarations
  under authored names still dropped; no-collision merges unchanged.
- **`goga/afm`**: `exit_on_fail=True` adds `--exit-on-fail` to the afm
  argv; False omits it; `AFM_EXIT_ON_FAIL` never set; exit code
  propagation unchanged (SC8).
- **`goga/pipeline`**: `--fail-on-error` binds in run and info modes of
  the argparse surface; `run_pipeline` forwards to `run_flow`; the
  afm config carries `add_stage: {enabled: false}` unconditionally
  (SC7); assistant env closure only for a non-empty effective map;
  delegate materializes False when None.
- **`goga/commands/pipeline`**: with `GOGA_DOCKER=1` and no docker CLI,
  run/list/overview/card execute directly (SC1); each host-only option
  fails naming itself (SC2); without the marker the docker flow is
  byte-identical (SC3); `--fail-on-error` reaches the in-container argv
  only when set; `--clean` wipes the in-container AFM_DIR; `--dry-run`
  prints the direct command.
- **`goga/commands/build`**: direct build inside the image (SC1);
  host-only rejections (SC2); host unchanged (SC3); `--clean` wipes
  `<cwd>/.ralphex`; no `.ralphex/` remains in the project under any
  exit path.
- **Whole project**: `pytest tests/ -x` green; `ruff check goga/`
  clean; `goga lint` passes on the changed manifests; `goga schema`
  resolves the new cell and the two new import edges without cycles.
