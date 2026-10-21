# Architecture Plan — Contributor Profiles

Task: personal execution layer for shared processes (pipeline and build paths).
Source artifacts: `task.md` (scope), `prd.md` (requirements), `adr.md` (authoritative decisions).
Plan type: **modification of nine existing cells**; no new cells; one new third-party dependency.

## Topic

Contributor Profiles — personal execution layer for shared processes.
Plan path: `.goga/history/2026/contributor-profile/arch.md`.

## Acceptance Criteria (design gates)

- G1 personal execution, G4 working default, G2 single point of variance, G3 per-stage environment.
- Strict pre-run failures with actionable messages, identical for interactive and CI.
- Backward compatibility: pipeline path byte-identical flow output (wrappers generated only for stages declaring `env`); build path behaviour-identical with `.ralphex/config` command fields pointing at generated per-role wrappers.
- Environment propagation: `GOGA_PROFILE` reaches every launched container; `GOGA_WORKFLOW` carries workflow+profile inheritance for in-container builds.
- Launch feedback lines name workflow and profile; without an effective profile the output is unchanged.

## Stack

Python 3.10+; click>=8.0, pyyaml>=6.0 (existing); **jinja2>=3.1 (new — declare in `pyproject.toml`)**.
External boundaries unchanged: afm >= 0.4.15 per-stage `command:` (absolute executable path), ralphex `.ralphex/config` (`claude_command`, `custom_review_script`), Docker launcher env-file.

## Implementation Order

1. **`goga/pipeline/workflow`** — pure leaf (no Imports). Everything profile/rendering-related lands here first: both downstream paths consume it.
2. **`goga/config/project`** — no Imports; the `env` field of the additional review block is consumed by `goga/build` later.
3. **`goga/docker`** — home-profiles transport pair; consumed by `goga/pipeline`, `goga/build`, and both command cells.
4. **`goga/ralphex`** — annotation-only clarification (no contract change).
5. **`goga/agents`** — no changes (consumer `resolve_wrapper_path` already imported where needed).
6. **`goga/pipeline/hooks`** — overlay merge over the extended workflow model; depends on 1 (the grown `WorkflowDocument` / `WorkflowStage`); consumed by 8 (goga/pipeline).
7. **`goga/build`** — depends on 1 (new edge `load_workflow`), 2 (`AdditionalReviewConfig.env`), 3 (`decode_home_profiles`).
8. **`goga/pipeline`** — depends on 1 (existing edge grows), 3 (`decode_home_profiles`), 6 (hooks merge carries the new fields).
9. **`goga/commands/build`** — depends on 1 (new edge `load_home_profiles`), 3 (`encode_home_profiles`), 7.
10. **`goga/commands/pipeline`** — depends on 1 (new edge `load_home_profiles`), 3, 8.

## Artifacts

### Cell 1 — `goga/pipeline/workflow` (MODIFY)

#### CODEMANIFEST delta

**Header — Usages** (add):

```yaml
  jinja2: .goga/usages/cooks/jinja2.md
```

**Header — Annotations** (amend the retained opening paragraph, then append):

Retained-paragraph amendments (the rest of the existing global text stays verbatim):

```yaml
  This cell is a pure parser of project-level workflow-files. It loads a
  workflow-file (the reading step lives in `load_workflow`; `parse_workflow`
  accepts the rendered text), validates its structure (known top-level keys
  prompt / stages / extend / memory / profile / build, field types, loop
  counts, extend-entry positioning, and
  the inline agent/loop fields of an extend-entry), and returns a
  `WorkflowDocument` carrying declarative instructions for the compiler.
```

(append to the existing global text):

```yaml
  This cell additionally owns the contributor-profile zone of the workflow
  path: profile resolution (project-then-home lookup, project wins on the
  same name), strict profile-name validation, activation precedence
  resolution, and whole-file Jinja rendering of workflow-files before
  parsing. The zone stays pure: no environment reads, no subprocess, no
  network; file I/O is limited to the paths received as parameters.
  Rendering is a step before parsing — the rendered text passes the
  standard structural validation unchanged; rendering never bypasses
  validation. The template context is the entire content of the single
  active profile; with no activation the context is empty.

  Use `jinja2` for the rendering engine contract: the fixed environment
  flags, the missing-key semantics, and the strict syntax-error surfacing
  with location.
```

**Body — new types** (insert after the existing types):

```yaml
"ProfileSource()":
  location: profile_source.py
  annotations: |
    str-backed Enum declaring the origin of a resolved profile. Modeled
    via the standard library enum module; str-mixin so values serialize
    as plain strings (per `convention`).
  properties:
    "PROJECT = \"project\"": |
      Origin = project-level <cwd>/.goga/profiles/ (committed).
    "HOME = \"home\"": |
      Origin = home-level ~/.goga/profiles/ (personal, carried in the
      decoded home bundle).

"ResolvedProfile(name: str, data: dict[str, Any], source: ProfileSource)":
  location: resolved_profile.py
  annotations: |
    The active profile as a single value: its name, its whole content
    mapping, and where it was found.

    `name`: the resolved profile name
    `data`: the entire profile content — every top-level key becomes a
            template variable at rendering
    `source`: where the profile was found — `ProfileSource` value

    Requirements:
    - Immutable frozen dataclass (frozen=True, kw_only=True), per
      `convention`

    Constraints:
    - Do not resolve wrappers, render templates, or apply the content
      anywhere here — consumers own both
  properties:
    "name -> str": |
      The resolved profile name.
    "data -> dict[str, Any]": |
      The entire profile content; the rendering context source.
    "source -> ProfileSource": |
      Origin of the profile: project or home.

"LoadedWorkflow(document: WorkflowDocument, profile: ResolvedProfile | None)":
  location: loaded_workflow.py
  annotations: |
    The result of loading a workflow-file under an activation context:
    the parsed document plus the profile that was active during the load
    (None when no profile resolved).

    `document`: the parsed `WorkflowDocument`
    `profile`: the `ResolvedProfile` active at rendering, or None

    Requirements:
    - Immutable frozen dataclass (frozen=True, kw_only=True), per
      `convention`

    Constraints:
    - Do not revalidate fields here — the parts were validated by their
      producers
  properties:
    "document -> WorkflowDocument": |
      The parsed workflow document.
    "profile -> ResolvedProfile | None": |
      The profile active during rendering, or None when the render ran
      with an empty context.

"WorkflowBuild(agent: str | None = None, env: dict[str, str] | None = None, review_agent: str | None = None, review_env: dict[str, str] | None = None, review_additional_agent: str | None = None, review_additional_env: dict[str, str] | None = None)":
  location: workflow_build.py
  annotations: |
    Data model of the top-level workflow `build:` block — the strict
    six-field set of build-pass settings the workflow may provide. All
    fields default to None (absent); an absent field never overrides the
    configuration.

    `agent`: tasks-pass agent override, or None
    `env`: tasks-pass env overlay (string map), or None
    `review_agent`: review-pass agent override, or None
    `review_env`: review-pass env overlay, or None
    `review_additional_agent`: external-review agent override, or None
    `review_additional_env`: external-review env overlay, or None

    Requirements:
    - Use @dataclass(kw_only=True) (per `convention`)
    - Field order is fixed: agent, env, review_agent, review_env,
      review_additional_agent, review_additional_env
    - Built only by `parse_workflow` from the validated block

    Constraints:
    - Do not merge with any configuration here — the build path owns the
      layering
    - No proxy, hosts, or any other field may appear — the parser
      rejects unknown keys of the block as structural errors
  properties:
    "agent -> str | None": |
      Tasks-pass agent override; None when absent.
    "env -> dict[str, str] | None": |
      Tasks-pass env overlay; None when absent.
    "review_agent -> str | None": |
      Review-pass agent override; None when absent.
    "review_env -> dict[str, str] | None": |
      Review-pass env overlay; None when absent.
    "review_additional_agent -> str | None": |
      External-review agent override; None when absent.
    "review_additional_env -> dict[str, str] | None": |
      External-review env overlay; None when absent.

"load_home_profiles(home_dir: Path) -> profiles: dict[str, dict[str, Any]]":
  location: load_home_profiles.py
  annotations: |
    Read and strictly parse the whole home profiles bundle: every flat
    *.yml file under `home_dir`, collected into one name → mapping.

    `home_dir`: the home profiles directory (typically
                ~/.goga/profiles/)
    `profiles`: mapping of profile name → profile content

    Algorithm:
    1. Scan flat *.yml files (non-recursive) under `home_dir`; a missing
       directory resolves to an empty mapping
    2. For each file: parse as YAML; invalid YAML or a non-mapping root
       raises one strict error naming the file path
    3. Return the collected mapping (file stem → content)

    Requirements:
    - A malformed home profile is a strict failure — the caller runs this
      on the host before any container launches
    - Deterministic — unchanged directory contents produce the identical
      mapping

    Constraints:
    - Do not read the environment — the directory arrives as a parameter
    - Do not validate profile-name grammar here — bundle keys that fail
      the grammar are inert; the lookup validates the REQUESTED name

"resolve_profile(name: str, project_dir: Path, home_profiles: dict[str, dict[str, Any]]) -> profile: ResolvedProfile":
  location: resolve_profile.py
  annotations: |
    Validate a profile name and resolve it to a `ResolvedProfile`:
    project lookup first, then the home bundle; on the same name the
    project profile wins.

    `name`: the requested profile name
    `project_dir`: the project profiles directory (typically
                   <cwd>/.goga/profiles/)
    `home_profiles`: the decoded home bundle mapping
    `profile`: the resolved `ResolvedProfile`

    Algorithm:
    1. Validate `name` against the profile-name grammar
       ([A-Za-z0-9][A-Za-z0-9._-]*; "." and ".." forbidden) — the name
       becomes a filesystem path component, so a violation raises one
       strict error naming the profile (path-traversal guard)
    2. When <project_dir>/<name>.yml exists: parse it; invalid YAML or a
       non-mapping root raises one strict error naming the profile and
       the path; return `ResolvedProfile` with source project
    3. Otherwise, when `name` is present in `home_profiles`: return
       `ResolvedProfile` with source home
    4. Otherwise raise one strict error naming the profile and BOTH
       lookup locations

    Requirements:
    - Project-wins on the same name
    - All failures are strict, pre-run, with actionable messages

    Constraints:
    - Do not read the environment — home data arrives as a parameter
    - Do not render anything here — the consumer renders

"render_workflow(text: str, profile_data: dict[str, Any], source_name: str = \"\") -> rendered: str":
  location: render_workflow.py
  annotations: |
    Render a whole workflow-file text as a Jinja template with the
    active profile content as the template context. Rendering is a step
    BEFORE parsing; the rendered text feeds the standard parser.

    `text`: the raw workflow-file text
    `profile_data`: the template context — the entire active profile
                    content, or an empty mapping for a context-less
                    render
    `source_name`: optional workflow file name carried into error
                   messages
    `rendered`: the rendered text

    Use `jinja2` for the environment configuration and the error
    surfacing.

    Algorithm:
    1. Build the rendering environment per `jinja2` — the fixed flag
       set, the standard Undefined, autoescape off
    2. Render the whole text with `profile_data` as the context
    3. A template syntax error raises one strict error carrying
       `source_name`, the line number, and the message

    Requirements:
    - A plain file without template syntax renders to itself
    - Missing context keys follow standard Jinja semantics — falsy in
      guards, empty when interpolated; nested access on a missing key
      fails at render time

    Constraints:
    - Do not parse YAML here — the consumer parses the rendered text
    - Do not read files or the environment — text and context arrive as
      parameters

"resolve_activation(cli_profile: str | None, env_profile: str | None, workflow_default: str | None) -> name: str | None":
  location: resolve_activation.py
  annotations: |
    Resolve the effective profile name from the three activation
    sources, strongest first: CLI option, environment variable,
    workflow default.

    `cli_profile`: the --profile flag value, or None
    `env_profile`: the GOGA_PROFILE value, or None
    `workflow_default`: the workflow's top-level profile: default, or
                        None
    `name`: the effective profile name, or None when every source is
            unset

    Algorithm:
    1. Return the first non-empty value among `cli_profile`,
       `env_profile`, `workflow_default` — in that order
    2. Empty and whitespace-only strings count as unset
    3. Return None when all sources are unset

    Requirements:
    - Pure — no environment reads; every source arrives as a parameter

    Constraints:
    - Do not load the profile here — only the name resolves

"load_workflow(workflow_path: Path, cli_profile: str | None = None, env_profile: str | None = None, home_profiles: dict[str, dict[str, Any]] | None = None) -> loaded: LoadedWorkflow":
  location: load_workflow.py
  annotations: |
    The single loading chain that turns a workflow-file path into a
    `LoadedWorkflow` under an activation context: read, peek the
    default, resolve activation, resolve the profile, render the whole
    file, parse the rendered text.

    `workflow_path`: absolute path to the workflow-file
    `cli_profile`: the CLI activation channel value, or None
    `env_profile`: the environment activation channel value, or None
    `home_profiles`: the decoded home bundle, or None (treated as empty)
    `loaded`: the `LoadedWorkflow` — document plus the active profile

    Use `jinja2` (through `render_workflow`) for the rendering step.

    Algorithm:
    1. Read the file text; OSError propagates unchanged
    2. Peek a literal top-level `profile:` value from the RAW text — a
       default that materializes only through template rendering does
       not participate in activation
    3. Resolve the effective profile name via `resolve_activation` from
       the two channel values and the peeked default
    4. When a name resolved: load it via `resolve_profile` against
       <cwd>/.goga/profiles/ and the home bundle; otherwise the profile
       is None
    5. Render the whole text via `render_workflow` with the profile
       content as the context — an empty context when no profile
       resolved
    6. Parse the rendered text via `parse_workflow`; structural errors
       propagate with their readable messages
    7. Return `LoadedWorkflow` of the document and the profile

    Requirements:
    - Rendering runs ALWAYS — a plain file renders to itself; templates
      without activation render with the empty context
    - Rendering never bypasses validation — the rendered text passes
      the standard structural validation unchanged
    - The activation channels arrive as parameters — the chain reads no
      environment

    Constraints:
    - Do not mutate the inputs; do not write anything
    - Do not resolve the workflow path or its existence here — the
      caller owns path composition and guards
```

**Body — extended types**:

- `WorkflowStage` — add field `env: dict[str, str] | None = None` as the SECOND field (canonical key order: agent, env, prompt, loop, skills, skip, approve, manual, notes, reflect, memory). Add property `"env -> dict[str, str] | None"`: per-stage environment instruction (string map, literal and/or rendered); declarative — extracted here, consumed by the pipeline run coordination's wrapper generation, NOT the compiler. Extend the type annotation with: `env` is validated by `parse_workflow` (dict of str→str; an empty map equals absence — None); constraint — env never reaches the serialized flow-file as a stage field and the compiler does not act on it.
- `WorkflowDocument` — add fields `profile: str | None = None`, `build: WorkflowBuild | None = None` (field order: prompt, stages, extend, memory, profile, build). Add properties `"profile -> str | None"` (the parsed counterpart of the peeked default; activation reads the raw text via the peek, not this field) and `"build -> WorkflowBuild | None"` (the six-field build block, consumed by the build path). Extend the empty-workflow rule: a workflow is empty only when prompt, stages, extend, memory, profile, AND build are all absent; a workflow consisting of the `build:` block alone is valid.
- `parse_workflow` — signature changes to `parse_workflow(text: str) -> workflow: WorkflowDocument` (rendered text in; no file I/O). Grammar extensions:
  - accepted top-level keys: prompt, stages, extend, memory, **profile**, **build** (unknown key error lists the new keys);
  - `profile`: optional str; non-str raises "non-str value in workflow.profile"; empty/whitespace normalizes to None;
  - `stages.<name>.env`: optional dict[str, str]; non-dict raises "non-mapping env in workflow.stages.NAME"; a non-str value raises "non-str value in workflow.stages.NAME.env.KEY"; an empty map equals absence (None); the unknown-key message of a stage entry now includes env;
  - `env` is forbidden in extend-entries: "env is forbidden in workflow.extend.NAME";
  - `build`: optional dict; non-dict raises "non-mapping build block in workflow"; strict key set — `agent`, `env`, `review` (with `agent`, `env`, `additional` with `agent`, `env`); an unknown key anywhere in the block raises "unknown key in workflow.build.KEY…: KEY; valid keys: agent, env, review.agent, review.env, review.additional.agent, review.additional.env" — proxy and hosts are unknown keys and therefore structural errors (the host launcher must not read workflow files); env values follow the string-map pattern; builds a `WorkflowBuild`.
  - Algorithm step 1 changes from "read the file" to "accept the rendered text"; YAML parse errors keep their existing messages.

**Footer** — extend Description with the profile-resolution and rendering zone.

#### Usage files

**NEW `goga/pipeline/workflow/.usages/profiles.md`**:

```md
# Profile resolution and activation

## Domain

Resolution and activation of contributor profiles for workflow rendering:
how a profile name becomes the template context, how the two lookup
locations interact, and how the activation channels compose. Target
audience: consumers of the workflow cell that resolve profiles — the
pipeline run coordination and card (goga/pipeline), the build path
(goga/build), and the host launchers that collect the home bundle
(goga/commands/pipeline, goga/commands/build).

## Profile files

- Project profiles: `<project>/.goga/profiles/<name>.yml` — committed,
  shared.
- Home profiles: `~/.goga/profiles/<name>.yml` — personal, never
  committed.
- The same name in both locations: the project file wins.
- A profile is a free-form YAML mapping; its entire content becomes the
  template context — every top-level key is a template variable. The
  data model of a profile is defined solely by what the workflow's
  templates read.
- Management is files-only: no CLI subcommands exist for creating,
  listing, or inspecting profiles.

## Name grammar

A profile name must match `[A-Za-z0-9][A-Za-z0-9._-]*`; the names `.`
and `..` are forbidden. The name becomes a filesystem path component,
so the grammar is a path-traversal guard — a violation is a strict
pre-run failure naming the profile.

## Activation precedence

From strongest to weakest:

1. the `--profile` CLI option (arrives as the cli channel),
2. the `GOGA_PROFILE` environment variable (arrives as the env channel),
3. the workflow's top-level `profile:` default.

Empty strings count as unset. With no workflow in effect, activation is
ignored entirely — nothing loads, no line prints.

```python
from goga.pipeline.workflow import resolve_activation

name = resolve_activation(cli_profile, env_profile, workflow_default)
# name is the effective profile name, or None when every source is unset
```

## Resolving a name

`resolve_profile(name, project_dir, home_profiles)` validates the name
grammar, looks up `<project_dir>/<name>.yml` first (strict failure
naming the profile and path when the file is malformed), then the home
bundle mapping, and otherwise fails strictly naming the profile and BOTH
lookup locations. The result carries the name, the content mapping, and
the source (`project` or `home`).

## Collecting the home bundle (host side)

`load_home_profiles(home_dir)` reads every flat `*.yml` file under the
directory (a missing directory is an empty bundle). Every file must be
valid YAML with a mapping root — a malformed home profile is a strict
failure on the host BEFORE any container launches. The returned mapping
feeds the docker-cell encoder for the `GOGA_HOME_PROFILES` carriage and
arrives in-container through the docker-cell decoder.

## Failure strictness

All profile failures are pre-run: nothing partial executes, humans and
CI see identical behaviour, and every message is actionable (profile
name, path, or both lookup locations).
```

**NEW `goga/pipeline/workflow/.usages/load-workflow.md`**:

```md
# Loading a workflow-file with rendering

## Domain

The single loading chain that turns a workflow-file path into a parsed
`WorkflowDocument` under an active profile: read, default-peek,
activation, profile resolution, whole-file rendering, parsing. Target
audience: consumers that load workflow-files — the pipeline run
coordination and card (goga/pipeline, through `resolve_workflow`) and
the build path (goga/build, through `resolve_build_workflow`).

## The chain

```python
from goga.pipeline.workflow import load_workflow

loaded = load_workflow(
    workflow_path,
    cli_profile=profile_flag,      # --profile value, or None
    env_profile=goga_profile,      # GOGA_PROFILE value, or None
    home_profiles=decoded_bundle,  # decode_home_profiles(...) result
)
document = loaded.document         # WorkflowDocument
profile = loaded.profile           # ResolvedProfile | None
```

Steps performed by the chain:

1. Reads the file text (a missing file raises OSError — callers guard
   existence).
2. Peeks a literal top-level `profile:` value from the RAW text. The
   default must be authorable as a plain line: `profile: default`. A
   value that materializes only through template rendering does not
   participate in activation.
3. Resolves the effective profile name (CLI > environment > workflow
   default).
4. Loads the profile when a name resolved — project lookup first
   (`<cwd>/.goga/profiles/`), then the home bundle mapping. Missing or
   malformed → strict pre-run failure.
5. Renders the WHOLE file as a Jinja template with the profile content
   as the context. No activation → empty context; a file without
   template syntax renders to itself.
6. Parses the rendered text through the standard grammar and structural
   validation — unchanged rules; rendering never bypasses validation.
7. Returns the document and the profile that was active during the
   render.

## What the consumer owns

- The channel values: the CLI flag value and the `GOGA_PROFILE` value
  arrive as parameters — the chain reads no environment.
- The home bundle: decode `GOGA_HOME_PROFILES` (goga/docker) before the
  call and pass the mapping.
- The workflow path: composition, containment guards, and existence
  checks belong to the caller.

## Failure modes (all pre-run, all strict)

- Missing profile (name resolved, file absent in both locations) —
  names the profile and both lookup locations.
- Malformed profile file (invalid YAML, non-mapping) — names the
  profile and path.
- Jinja syntax error — names the workflow file and the line.
- Rendered workflow failing structural validation — the standard
  structural errors, unchanged.

## Interplay with skip merges

A skip merge (goga/pipeline) rebuilds the document in memory; the
`profile` and `build` fields survive the rebuild verbatim, exactly as
the memory configuration does.
```

**UPDATE `goga/pipeline/workflow/.usages/parse-workflow.md`** — grammar section additions: the three new keys (`profile:` top-level string default; `stages.<name>.env` string map valid ONLY in the stages block and forbidden in extend-entries; the `build:` block with the strict six-field set where anything else — including `proxy` and `hosts` — is a structural error, because the host launcher must not read workflow files); the updated empty-workflow rule (a build-only workflow is valid).

### Cell 2 — `goga/config/project` (MODIFY)

#### CODEMANIFEST delta

**Header** — unchanged.

**Body**:

- `AdditionalReviewConfig` — signature becomes
  `AdditionalReviewConfig(agent: str | None, patience: int | None, max_iterations: int | None, env: dict[str, str])`
  (new field last). Add property:

```yaml
    "env -> dict[str, str]": |
      Independent env layer for the external reviewer. Empty mapping by
      default; values verbatim. Never inherited from review env — the
      layer is independent by design.
```

- `load_project_config` — Algorithm step 7 (the additional sub-mapping): add extraction of `env` by the env pattern (optional string mapping, default empty dict; a non-string value raises ValueError). No signature change.

**Footer** — extend Description: build.review.additional carries an independent env layer for the external reviewer.

#### Usage files

None (cell has no `.usages/`; the field follows the existing env-field patterns).

### Cell 3 — `goga/docker` (MODIFY)

#### CODEMANIFEST delta

**Header — Annotations** (append):

```yaml
  The zone also owns the home-profiles bundle carriage across the docker
  boundary: one routine encodes the whole home bundle into the
  single-line payload of the dedicated engine variable GOGA_HOME_PROFILES,
  the other returns the mapping a consuming domain resolves profiles
  against. Both routines are pure — the bundle source belongs to the
  calling host launcher, the application belongs to the consuming domain.
  The consumer wiring of both halves — the env-file placement, the
  engine-skip rule, when the line is written — lives in the
  home-profiles-carriage practice of this cell's usages directory.
```

**Body — new types**:

```yaml
"encode_home_profiles(profiles: dict[str, dict[str, Any]]) -> value: str":
  location: home_profiles.py
  annotations: |
    Encode the home profiles bundle into the engine payload value
    carried across the docker boundary in the container env-file.

    `profiles`: the whole home bundle — profile name → content mapping
    `value`: the single-line payload string for the GOGA_HOME_PROFILES
             engine variable; an empty string when the bundle is empty

    Algorithm:
    1. An empty mapping resolves to an empty string — nothing to carry
    2. Serialize the mapping as compact JSON without whitespace
    3. Encode as standard base64 with padding into a single line and
       return it

    Requirements:
    - Deterministic — identical bundles produce the identical value
    - The value decodes back into exactly the input mapping
    - Pure — no filesystem access, no environment reads, no side
      effects

    Constraints:
    - Do not validate profile contents — a malformed home profile fails
      strictly on the host BEFORE encoding (the loader owns that check)
    - Do not read the environment — the caller owns the bundle source
    - Do not print or log the payload

"decode_home_profiles(value: str) -> profiles: dict[str, dict[str, Any]]":
  location: home_profiles.py
  annotations: |
    Decode the GOGA_HOME_PROFILES engine payload back into the home
    profiles bundle a consuming domain resolves profiles against.

    `value`: the payload string of the engine variable; an absent or
             empty variable arrives as an empty string
    `profiles`: the decoded bundle mapping; empty when the payload
                carried nothing

    Algorithm:
    1. An empty `value` resolves to an empty mapping — nothing to
       resolve against
    2. Decode the base64 payload and parse the JSON mapping inside
    3. A payload that fails decoding or parsing, carries a non-mapping
       root, or carries non-string mapping values raises one clean
       error naming the GOGA_HOME_PROFILES engine variable — no payload
       content appears in the error

    Requirements:
    - Pure — the mapping is returned, nothing is applied anywhere
    - The result equals the mapping `encode_home_profiles` produced
      from the same bundle

    Constraints:
    - Do not read the environment — the caller owns the variable read
    - Do not print or log the payload or any decoded value
    - Do not apply the mapping to any environment — application belongs
      to the consuming domain
```

**Footer** — extend Description with the home-profiles carriage.

#### Usage files

**NEW `goga/docker/.usages/home-profiles-carriage.md`**:

```md
# The home-profiles carriage across the docker boundary

How a domain threads the personal home profiles (~/.goga/profiles/)
across the docker launch boundary. For the host-side launchers that
write the container env-file (goga/commands/pipeline,
goga/commands/build) and the in-container domains that resolve profiles
against the bundle (goga/pipeline, goga/build).

## The carriage contract

Host home directories are never mounted. The whole home bundle travels
as ONE derived value, the engine variable `GOGA_HOME_PROFILES`:

- the host launcher reads and strictly parses the bundle
  (`load_home_profiles` from goga/pipeline/workflow — a malformed home
  profile fails on the host before any container launches);
- the same launcher encodes the mapping (`encode_home_profiles`) and
  writes the single payload line into the container env-file;
- the in-container domain reads the variable once, decodes it
  (`decode_home_profiles`), and passes the mapping into its profile
  resolution.

The whole bundle — not just one profile — crosses the boundary because
the effective profile name may only become known in-container (the
workflow `profile:` default).

## Host half — write the payload line

```python
from goga.pipeline.workflow import load_home_profiles
from goga.docker import encode_home_profiles

home_profiles = load_home_profiles(home_dir)      # strict on malformed
if home_profiles:
    lines.append(f"GOGA_HOME_PROFILES={encode_home_profiles(home_profiles)}")
```

- Write the line only when the bundle is non-empty — an empty bundle
  writes nothing.
- The line follows the CLI entries in the env-file and respects the
  engine-skip rule: an explicit user `-e GOGA_HOME_PROFILES=...` entry
  keeps winning over the launcher-produced value.

## Container half — decode once, resolve against

```python
import os
from goga.docker import decode_home_profiles

bundle = decode_home_profiles(os.environ.get("GOGA_HOME_PROFILES", ""))
loaded = load_workflow(path, cli_profile, env_profile, home_profiles=bundle)
```

- The variable is read once per launch; a damaged payload fails as one
  clean error naming the variable — nothing partially applied, no stage
  or pass launches.
- The decoded mapping is passed as a parameter into profile resolution;
  the container's process environment is never mutated.

## Ladder position and secrecy

`GOGA_HOME_PROFILES` is an engine variable — launch mechanics: nothing
overrides it, and task-layer or CLI keys colliding with it are dropped
silently (the inherited launch value stands). Payload and decoded
values are never printed or logged.
```

### Cell 4 — `goga/ralphex` (MODIFY — annotations only)

#### CODEMANIFEST delta

**Global Annotations** (append): the optional env layer of the `env` parameter is no longer the carriage for the build passes' task env layers — per-role closure wrappers generated by the caller (goga/build) own each executor's environment; the ralphex subprocess inherits the container environment. The launcher contract (signature, option-to-flag mapping, exit-code propagation, secret handling) is unchanged.

**`run_ralphex` annotation** (Requirements addition): build-path callers deliver task env layers through generated per-role wrappers, not through the `env` parameter; the parameter remains the general layer mechanism, never logged, never printed.

**Footer** — unchanged.

#### Usage files

None.

### Cell 5 — `goga/agents` (NO CHANGES)

`resolve_wrapper_path` is consumed by the two new wrapper generators (`apply_stage_env_wrappers` in goga/pipeline, `write_role_env_wrappers` in goga/build); both cells already import the type and the `resolve-wrapper-path` practice. Verify no drift; no plan artifacts.

### Cell 6 — `goga/pipeline/hooks` (MODIFY — overlay merge)

#### CODEMANIFEST delta

**Header** — unchanged.

**Body — extended type**:

- `merge_workflow_overlay` — the per-stage field merge (Algorithm step 4) covers the FULL declared field set of `WorkflowStage`, including `env`: an authored env is unbeatable exactly like every other authored stage field; an unset env takes the value of the later contributing tool that sets it (the merge is field-set-complete, never a named-subset copy — a new stage field flows through without touching this cell again). The final document assembly carries the `profile` and `build` fields of `base` verbatim (exactly as `memory` survives the rebuild) — workflow-level instructions never vanish in the overlay. Add Requirement: the rebuilt `WorkflowDocument` preserves every workflow-level field of the base (`profile`, `build` verbatim; `memory` as today) and the stage merge is over the complete `WorkflowStage` field set.

**Footer** — extend Description: the overlay merge preserves the full workflow model — per-stage `env` instructions and the workflow-level `profile` and `build` fields.

#### Usage files

None.

### Cell 7 — `goga/build` (MODIFY)

#### CODEMANIFEST delta

**Header — Imports** (add):

```yaml
  - Types:
      - load_workflow
      - LoadedWorkflow
      - WorkflowBuild
    Usages:
      - load-workflow
      - profiles
    From: goga/pipeline/workflow
  - Types:
      - decode_home_profiles
    Usages:
      - home-profiles-carriage
    From: goga/docker
```

(the second entry extends the existing `From: goga/docker` import — Types beside `ensure_in_docker` / `decode_extra_env`, the usage beside `ensure-in-docker` / `extra-env-carriage`)

**Header — Annotations** (append):

```yaml
  Workflow layering: build settings compose config < workflow build: <
  CLI at the resolution point — the six-field workflow block overlays
  the effective build configuration before the settings resolution;
  env maps merge key-wise (a workflow key overrides the same-named
  config key, the rest of the config env survives). Use `load-workflow`
  for the loading chain and `profiles` for the activation rules.

  Per-role closure wrappers: every build pass executor (tasks, review,
  additional) runs through a generated closure wrapper — one uniform,
  predictable mechanism; per-role, not per-agent (the same agent may
  carry different env per role). Wrappers live in a container-local
  temp directory, regenerated at each pass config write; task env
  layers leave the ralphex launch env — the subprocess inherits the
  container environment. Layers stay independent: the additional layer
  never inherits review env, mirroring the review-never-inherits-root
  rule.

  GOGA_WORKFLOW is interpreted only by this cell (in-container builds):
  written solely by the pipeline-run launcher, beaten by the -w CLI
  flag. It is a deliberate, documented, narrow relaxation of the
  "run options never travel through the environment" rule.

  Launch feedback: one stderr line — Build running with workflow "<w>"
  and profile "<p>" — printed only when a workflow is in effect AND an
  effective profile resolved; every other run prints no line.
```

**Body — new types**:

```yaml
"resolve_build_workflow(workflow_cli: str | None, workflow_env: str | None, cli_profile: str | None = None, env_profile: str | None = None, home_profiles: dict[str, dict[str, Any]] | None = None) -> loaded: LoadedWorkflow | None":
  location: resolve_build_workflow.py
  annotations: |
    Select and load the workflow that drives a build: the CLI flag
    beats the environment value; no selection means no workflow — and
    activation is ignored entirely.

    `workflow_cli`: the -w/--workflow flag value, or None
    `workflow_env`: the GOGA_WORKFLOW value, or None
    `cli_profile`: the --profile flag value, or None
    `env_profile`: the GOGA_PROFILE value, or None
    `home_profiles`: the decoded home bundle, or None
    `loaded`: the `LoadedWorkflow`, or None when no workflow is in
              effect

    Use `load-workflow` for the chain semantics and `profiles` for the
    activation rules.

    Algorithm:
    1. `workflow_cli` beats `workflow_env`; empty strings count as
       unset
    2. When neither is set — return None (no workflow in effect;
       activation is ignored entirely — nothing loads)
    3. Compose <cwd>/.goga/workflows/<name>.yml; a name whose resolved
       path escapes the workflows directory raises one strict
       "invalid workflow name" error; a missing file raises one strict
       error naming the workflow and the directory (an explicit
       selection, not a silent miss)
    4. Load via `load_workflow` with the activation channels and the
       home bundle; return the result

    Requirements:
    - The CLI flag beats the environment value on both axes (workflow
      and profile)

    Constraints:
    - Do not read the environment — both channel values arrive as
      parameters
    - Do not render or parse here — the loading chain owns both

"merge_workflow_build(config: BuildConfig, build_block: WorkflowBuild) -> config: BuildConfig":
  location: workflow_build.py
  annotations: |
    Overlay the six-field workflow build block onto the effective build
    configuration: a NEW BuildConfig where absent block fields never
    override, agent fields override when set, and env maps merge
    key-wise.

    `config`: the effective build configuration (the base layer)
    `build_block`: the workflow `build:` block model
    `config`: the layered build configuration (a new value; inputs
              unmutated)

    Algorithm:
    1. Agent fields: root agent = build_block.agent when set, otherwise
       the config value; review agent and additional agent the same way
    2. Env maps, key-wise with the block winning per key: tasks env =
       config env overlaid with block env; review env = config review
       env overlaid with block review env; additional env = config
       additional env overlaid with block additional env (the rest of
       each config env survives — the override-one-variable use case)
    3. Every other field of BuildConfig and its nested models passes
       through verbatim (session knobs, iteration caps, skip, roles,
       base_ref, strategy, finalize, patience, prompts_dir, agents_dir,
       proxy, hosts)

    Requirements:
    - Pure — new BuildConfig and new nested models; inputs unmutated
    - An absent block field (None) never overrides the configuration
    - `config` is always a non-None `BuildConfig` — the workflow block
      layers ONLY onto an existing build section; a build invocation
      with no build section in .goga/config.yml raises one strict
      error naming the requirement (reachable only via a direct
      in-container invocation — the host launcher guards the section
      host-side) instead of the raw attribute failure
    - When `config.review` is None and the block sets any review field:
      construct a NEW `ReviewConfig` (the set fields, every other
      field None / empty; a NEW `AdditionalReviewConfig` when
      additional fields are set) so `resolve_run_settings` receives a
      well-formed layered configuration

    Constraints:
    - Do not apply CLI values here — CLI applies at the settings
      resolution, preserving config < workflow build: < CLI
    - Do not resolve wrappers or validate agents here

"write_role_env_wrappers(settings: RunSettings, cli_entries: dict[str, str]) -> wrapper_paths: dict[str, Path]":
  location: role_env_wrappers.py
  annotations: |
    Generate the per-role closure wrappers every build pass executor
    runs through: export the role's env layer with the decoded CLI
    entries applied on top, then exec the role agent's resolved
    wrapper.

    `settings`: the resolved run plan — agents and env layers of the
                three roles
    `cli_entries`: the decoded CLI entries payload (decode_extra_env
                   result)
    `wrapper_paths`: role name → absolute wrapper path; the keys are
                     tasks, review, additional

    Apply `resolve-wrapper-path` when resolving each role agent.

    Algorithm:
    1. Create the base directory /tmp/goga-build-env/ when missing
       (container-local temp; never under /workspace)
    2. Per role (tasks, review, additional): resolve the role agent —
       tasks agent, review agent, additional agent (the inherited
       review agent when unset); a role agent that resolves to no
       wrapper raises one strict error naming the role BEFORE any pass
       launches
    3. Compose the closure content: export the role's env layer
       (tasks env, review env, additional env) with `cli_entries`
       applied ON TOP — CLI wins per key, engine-variable keys dropped
       silently — then exec the resolved wrapper path
    4. Write the executable script file per role
    5. Return the role → path mapping

    Requirements:
    - Per-role, NOT per-agent: the same underlying agent can carry
      different env per role
    - Regenerated at each pass's .ralphex/config write — the caller
      invokes this per pass; the writes are idempotent overwrites
    - Layers stay independent — the additional wrapper never exports
      review env and vice versa

    Constraints:
    - Do not write anything under /workspace — container-local temp
      only
    - Do not print or log env values or wrapper contents (dry-run
      prints command lines only, as today)
    - Do not launch anything — the pass executor owns the launch
```

**Body — extended types**:

- `build` — signature unchanged (`cli_options` gains keys `workflow`, `profile`). Algorithm amendments:
  - the single-decode step widens: decode the CLI entries payload AND the home bundle (`decode_home_profiles`), and read `GOGA_WORKFLOW` / `GOGA_PROFILE` once each — a damaged bundle is one clean error, nothing partially applied, no events;
  - resolve the workflow via `resolve_build_workflow(cli_options.workflow, GOGA_WORKFLOW value, cli_options.profile, GOGA_PROFILE value, decoded bundle)`;
  - print the stderr feedback line when a workflow is in effect AND the loaded profile is not None (`Build running with workflow "<w>" and profile "<p>"`);
  - layer the build settings: `merge_workflow_build(effective config.build, loaded.document.build)` when the block is present; `resolve_run_settings` consumes the layered config;
  - per pass: `write_role_env_wrappers(settings, decoded cli_entries)` → `write_ralphex_config(settings, <pass role wrapper>, additional wrapper path)` → `run_build_pass(plan, settings, options, <pass role wrapper>, dry_run)` — no env layer argument; under the `medium` strategy the additional layer stays inert (external review disabled), under `short` the additional wrapper is the pass executor.
  - Requirements additions: GOGA_WORKFLOW is never written by the build path; the agent guard keeps running before the first state write on the layered effective configuration.
- `main` — argparse surface adds `-p/--profile NAME` and `-w/--workflow NAME` (forwarded into cli_options; `-p` is free here — build has no parallel option).
- `resolve_run_settings` — annotations only: consumes the layered BuildConfig; signature and inheritance rules unchanged.
- `write_ralphex_config` — signature gains `additional_wrapper_path: str | None = None`; `claude_command` carries the pass's role wrapper path; the external-review surface sets `custom_review_script` to the additional wrapper path when engaged.
- `run_build_pass` — the `env` parameter is REMOVED: the ralphex subprocess inherits the container environment; task env layers ride the role wrapper.

**Footer** — extend Description with workflow layering and per-role wrappers.

#### Usage files

**NEW `goga/build/.usages/workflow-layering.md`**:

```md
# Workflow-driven build settings layering

## Domain

How a workflow-file drives build settings on top of .goga/config.yml:
the six-field `build:` block, the key-wise env merge, and the
config < workflow < CLI order. Target audience: configuration authors
(deciding what lives in config vs workflow) and contributors inheriting
a workflow inside a pipeline runtime.

## The block

A workflow-file may carry a top-level `build:` block with exactly six
fields — `agent`, `env`, `review.agent`, `review.env`,
`review.additional.agent`, `review.additional.env`. Anything else in
the block (including `proxy` and `hosts`) is a structural error: those
are consumed on the host before the container starts, and the host
launcher never reads workflow files.

## Layering order

    .goga/config.yml  <  workflow build:  <  CLI flags

- Absent block fields never override the configuration.
- Agent fields override when set (root, review, additional — each
  independently).
- Env maps merge KEY-WISE: a workflow key overrides the same-named
  config key; every other config env entry survives. Example: the
  workflow sets one model variable, the config keeps the rest.

## Workflow selection

- Host builds: `-w/--workflow NAME` selects the workflow (existence
  validated host-side).
- Builds inside a pipeline runtime: the pipeline-run launcher writes
  `GOGA_WORKFLOW` naming the effective workflow; the in-container build
  picks it up with no extra options. The CLI flag beats the
  environment value.
- No workflow selected → no layering, and profile activation is
  ignored entirely.

## Profile activation

The build honors the same activation channels and precedence as
pipelines (`--profile` > `GOGA_PROFILE` > workflow `profile:` default);
the workflow-file is rendered with the active profile before its
`build:` block is read. A successful launch with an effective profile
prints one stderr line: `Build running with workflow "<w>" and profile
"<p>"`.

## What does NOT change

Ralphex invocation shape, the two-pass cycle, hooks checkpoints, and
plan relocation are unchanged. Env delivery to executors moves to
generated per-role wrappers — agents receive the same effective
environment through the wrappers; only the command fields in `.ralphex/config`
now point at the generated wrappers.
```

**UPDATE `goga/build/.usages/build-usage.md`** — add: the `-w/--workflow` and `-p/--profile` in-container flags; the workflow inheritance via GOGA_WORKFLOW; the per-role wrapper mechanism (same effective env, new command fields); the feedback line; task env layers leaving the launch env.

### Cell 8 — `goga/pipeline` (MODIFY)

#### CODEMANIFEST delta

**Header — Imports**: the `From: goga/pipeline/workflow` entry adds Type `LoadedWorkflow` and Usages `load-workflow`, `profiles` (beside the existing `parse-workflow`, `memory`); the `From: goga/docker` entry adds Type `decode_home_profiles` and Usage `home-profiles-carriage` (beside the existing `ensure-in-docker`, `extra-env-carriage`).

**Header — Usages (inline `argparse`)** (amend the run-subcommand surface): the enumeration gains the profile flag — "the workflow flags -w/--workflow NAME and --no-workflow, the profile flag -p/--profile NAME, a repeatable -s/--skip NAME — all four available with and without --info" (the rest of the inline text stays verbatim).

**Header — Annotations** (append):

```yaml
  Per-stage environment delivery: the stages.<name>.env instruction is
  delivered by a generated per-stage closure wrapper the afm stage
  command points at (the absolute-executable-path convention; Use `afm`
  for the command-field contract). The wrapper exports the stage env,
  then execs the stage agent's wrapper, else the effective global
  agent's wrapper (resolved the same way for both consumers), else
  fails strictly before the run. Wrappers live in a container-local
  temp directory — never under /workspace; per-stage values layer
  above all global env layers.

  The stage command rewrite runs AFTER compilation as a targeted patch
  of the flow-file `compile_flow` already wrote: the compiler's direct
  serialization for env-free stages is untouched, keeping the flow
  output byte-identical for runs that declare no stage env (wrappers
  are generated and the file is patched only for stages that declare
  env; with none, the file is neither read nor rewritten).

  Activation: the run coordination and the card apply the profile
  through one channel set — the CLI --profile flag value, the
  GOGA_PROFILE value, and the decoded GOGA_HOME_PROFILES bundle; the
  card keeps reflecting what a run with the same flags would apply.
  When a profile resolves, the run coordination exports its name into
  the afm launch layer as GOGA_PROFILE — pipeline stages (and builds
  invoked inside the runtime) inherit the effective profile with no
  additional options. Use `load-workflow` and `profiles` for the
  loading chain and the activation rules.

  Launch feedback: the run coordination prints one stdout line —
  Pipeline running with workflow "<w>" and profile "<p>" — when a
  workflow resolved; without an effective profile the line names the
  workflow only; without a workflow no line prints.
```

**Body — new type**:

```yaml
"apply_stage_env_wrappers(stages: list[FlowStage], workflow: WorkflowDocument | None, global_agent: str | None, flow_path: Path) -> stages: list[FlowStage]":
  location: stage_env_wrappers.py
  annotations: |
    Deliver the per-stage env instructions of a compiled flow: generate
    one sh closure wrapper per env-declaring stage, patch the command
    fields of exactly those stages in the ALREADY WRITTEN flow-file,
    and return a new stage list where those stages' command fields
    point at their wrappers. Stages without an env instruction pass
    through as the SAME objects, untouched.

    `stages`: the compiled flow stages
    `workflow`: the effective workflow document (its stages map carries
                the env instructions), or None (no stage is wrapped)
    `global_agent`: the effective global pipeline agent — the fallback
                    exec target; None when no global agent resolved
    `flow_path`: the path of the flow-file written by `compile_flow` —
                 the target of the post-compile command patch
    `stages`: the new stage list — wrapped stages carry command fields
              pointing at their generated wrappers

    Apply `resolve-wrapper-path` when resolving each exec target.

    Algorithm:
    1. Select the stages whose workflow entry carries a non-None env
       (matched by stage name); with none — return the input list
       unchanged WITHOUT reading or writing `flow_path` (the env-free
       invariant). Loop expansion multiplies the match: EVERY compiled
       copy descended from an env-declaring loop stage (its id carries
       the expansion suffix of the workflow stage name) is selected and
       receives its own wrapper carrying the same env values
    2. Per selected stage, resolve the exec target: the stage agent's
       wrapper, else the global agent's wrapper, else raise one strict
       pre-run error naming the stage
    3. Generate one sh closure per selected stage in a container-local
       temp directory: export the stage's env values, then exec the
       resolved wrapper path
    4. Patch `flow_path`: rewrite ONLY the command fields of the
       selected stages in the serialized flow-file to the absolute
       wrapper paths — every other byte of the file stays untouched
    5. Return the new list: selected stages carry command = the
       absolute wrapper path; every other stage is the SAME input
       object

    Requirements:
    - The input list and its stage objects are never mutated
    - Wrappers are generated ONLY for env-declaring stages — env-free
      runs keep byte-identical flow output (the flow-file is neither
      read nor rewritten when no stage declares env)
    - The file patch touches only the command fields of the selected
      stages; the rest of the serialized flow-file is byte-identical
    - Per-stage values layer above all global env layers (the wrapper
      exports them last)

    Constraints:
    - Do not compile, reorder, or restructure stages — this runs after
      compilation
    - Do not write anything under the project directory or /workspace
      — container-local temp only
    - Do not print or log env values
```

**Body — extended types**:

- `resolve_workflow` — signature gains `cli_profile: str | None = None`, `env_profile: str | None = None`, `home_profiles: dict[str, dict[str, Any]] | None = None`; return type becomes `LoadedWorkflow | None`. The rule set (disabled → None; explicit name; basename auto-match; containment guard → silent None; missing file → silent None) is unchanged; the existing-file branch delegates to `load_workflow` with the activation channels. Consumers read `.document` (amendment machinery, compilation) and `.profile` (feedback line).
- `run_pipeline` — signature gains `profile: str | None = None`. The environment reads widen to four: AFM_DIR, the CLI entries payload, `GOGA_PROFILE`, and `GOGA_HOME_PROFILES` (decoded via `decode_home_profiles`; a damaged bundle is one clean error before events). Algorithm insertions: (a) pass the activation channels into `resolve_workflow`; (b) print the feedback line to stdout when a workflow resolved — with the profile name when one resolved, without it otherwise; (c) after `compile_flow`, run `apply_stage_env_wrappers(stages, workflow, effective pipeline agent, flow_path)` — a post-compile command rewrite over the flow-file `compile_flow` already wrote (env-declaring stages only; a no-op that touches no file when none declare env); (d) the afm launch layer gains `GOGA_PROFILE=<effective profile name>` when a profile resolved — the afm subprocess and its stages inherit it, so a build invoked inside the pipeline runtime picks the same profile up through its env channel with no additional options (the workflow travels via `GOGA_WORKFLOW` of the launch environment; the launcher env-file line stays ambient-only); keys of `pipeline.env` and the CLI entries colliding with the engine set — `GOGA_PROFILE`, `GOGA_WORKFLOW`, `GOGA_HOME_PROFILES`, `GOGA_EXTRA_ENV` — are dropped silently from the layer, the inherited launch values stand; the launch path is otherwise unchanged.
- `describe_pipeline` — signature gains `profile: str | None = None`; the card applies the profile through the same channels (the same environment reads); the composition reflects the env wrappers; no line prints; the card writes nothing.
- `pipeline_cli` — the run subcommand adds `-p/--profile NAME` (binds in info and run modes, like the workflow flags); the signature is unchanged.
- `apply_skip_stages` — the rebuild carries the `profile` and `build` fields verbatim.

**Footer** — extend Description with the per-stage env delivery.

#### Usage files

**NEW `goga/pipeline/.usages/per-stage-env.md`**:

```md
# Per-stage environment delivery

## Domain

How the `stages.<name>.env` workflow instruction reaches the executing
agent: authoring, the wrapper mechanism, and the layering rules.
Target audience: workflow authors declaring per-stage environments and
contributors combining them with profile data.

## Authoring

Inside the workflow stages block, a stage entry may carry `env` — a
map of environment variables for that stage, literal and/or rendered
from profile data:

```yaml
stages:
  worker:
    agent: '{{ worker.agent }}'
    env:
      ANTHROPIC_MODEL: '{{ worker.model }}'
  review:
    env:
      REVIEW_STRICTNESS: strict
```

`env` is valid ONLY under `stages.<name>` — never in an extend-entry.
An empty map equals absence.

## Delivery mechanism

afm stages carry a `command:` field following the absolute-executable-
path convention — so per-stage env travels through a generated sh
closure wrapper the field points at. After compilation goga patches
the `command:` field of exactly the env-declaring stages in the written
flow-file to point at their wrappers — a targeted patch; every other
byte of the flow-file stays untouched, and an env-free workflow is not
rewritten at all (byte-identical). The wrapper:

1. exports the stage's env values (above every global env layer),
2. execs the stage agent's wrapper — else the effective global wrapper
   (the same agent the run would use globally) — else the run fails
   strictly before launch, naming the stage.

Wrappers are generated per run in a container-local temp directory and
never touch the project directory. No contributor-side wrapper scripts
are ever required. Loop-expanded copies of an env-declaring stage all
carry the env — each copy receives its own wrapper with the same
values.

## What stays identical

Stages without `env` are compiled and serialized without wrappers —
the flow output of an env-free workflow stays byte-identical to the
compiler's direct composition. Skip, prompts, and depends_on handling
are unaffected.

## Combining with profiles

The env map is rendered together with the whole workflow-file: profile
data may drive both keys and values (iterate a profile mapping to
produce the whole block). A stage whose env comes only from profile
data vanishes cleanly when the profile omits it.
```

**UPDATE `goga/pipeline/.usages/run-pipeline.md`** — activation wiring, the four environment reads, the post-compile wrapper application, the feedback line (now printed in-container), the GOGA_PROFILE export into the afm launch layer (nested-build inheritance), the widened engine-key drop set, the byte-identical invariant.
**UPDATE `goga/pipeline/.usages/describe-pipeline.md`** — the card applies the profile through the same channels; no new reporting surfaces.
**UPDATE `goga/pipeline/.usages/pipeline-cli.md`** — the new `-p/--profile` flag of the run subcommand.

### Cell 9 — `goga/commands/build` (MODIFY)

#### CODEMANIFEST delta

**Header — Imports** (add):

```yaml
  - Types:
      - load_home_profiles
    Usages:
      - profiles
    From: goga/pipeline/workflow
  - Types:
      - encode_home_profiles
    Usages:
      - home-profiles-carriage
    From: goga/docker
```

(the second entry extends the existing `From: goga/docker` import — Types beside `DockerRunner` / `docker_update` / `docker_build_if_not_exist` / `encode_extra_env`, the usage beside `extra-env-carriage`)

**Header — Annotations** (append):

```yaml
  The launcher gains -p/--profile NAME and -w/--workflow NAME: both
  forward into the in-container argv as their long flags, value
  appended only when set. The -w name is validated host-side for path
  containment and file existence under <cwd>/.goga/workflows/ (a
  light early diagnostic; the file itself is never read on the host).

  Home bundle: the command loads ~/.goga/profiles/ once via
  `load_home_profiles` (Apply `profiles`) — a malformed home
  profile is one clean error BEFORE any docker activity. The env-file
  gains two engine lines written after the CLI entries under the
  engine-skip rule (an explicit -e entry keeps winning): GOGA_PROFILE —
  the ambient host value, written only when non-empty — and
  GOGA_HOME_PROFILES — the encoded bundle, written only when the bundle
  is non-empty. GOGA_WORKFLOW is never written by this launcher (the
  pipeline-run launcher owns it). The build feedback line prints
  in-container; this launcher prints none.
```

**Body — extended types**:

- `build` (the command) — signature gains `profile: str | None` and `workflow: str | None`; CLI options add `-p/--profile NAME` and `-w/--workflow NAME`; validation adds the leading-dash check for both values (argv parsability, mirroring the workflow name rule); the algorithm adds: load the home bundle once before docker activity; append `--profile <v>` / `--workflow <v>` to the in-container argv when set; extend the env-file composition with the two engine lines per the engine-skip rule. All other steps unchanged.

**Footer** — extend Description with the profile and workflow flags.

#### Usage files

**UPDATE `goga/commands/build/.usages/build.md`** — the new flags, the ambient/engine-skip carriage lines, the host-side bundle load with the strict malformed-profile failure, and the note that the feedback line prints in-container.

### Cell 10 — `goga/commands/pipeline` (MODIFY)

#### CODEMANIFEST delta

**Header — Imports** (add):

```yaml
  - Types:
      - load_home_profiles
    Usages:
      - profiles
    From: goga/pipeline/workflow
  - Types:
      - encode_home_profiles
    Usages:
      - home-profiles-carriage
    From: goga/docker
```

(the second entry extends the existing `From: goga/docker` import — Types beside `DockerRunner` / `docker_update` / `docker_build_if_not_exist` / `encode_extra_env`, the usage beside `extra-env-carriage`)

**Header — Annotations** (append):

```yaml
  The command gains -p/--profile NAME: the short alias -p moves from
  --parallel to --profile, and --parallel becomes long-only. The value
  forwards into the in-container argv of the run and card forms as the
  long flag, appended only when set, and passes the same leading-dash
  argv-parsability check as the workflow name.

  Home bundle: the command loads ~/.goga/profiles/ once via
  `load_home_profiles` (Apply `profiles`) — a malformed home
  profile is one clean error BEFORE any docker activity; the bundle is
  handed to both launchers.

  Run launcher env-file: three new engine lines after the CLI entries
  under the engine-skip rule (an explicit -e entry keeps winning) —
  GOGA_PROFILE (the ambient host value, written only when non-empty),
  GOGA_HOME_PROFILES (the encoded bundle, written only when non-empty),
  and GOGA_WORKFLOW (the effective workflow name of the run decision;
  written only by the run launcher, only when a workflow will be
  applied). Info launcher: the env-file is added ONLY when there is
  something to carry — a non-empty ambient GOGA_PROFILE or a non-empty
  home bundle; without cargo the info launch keeps the minimal
  read-only shape (no port, no env-file, no persistent state mount).

  The workflow log line lives in-container: the run coordination prints
  the launch feedback line (it knows the effective profile, including
  the workflow default, and its source); the host launcher prints no
  workflow line. A profile-free run still shows the single
  workflow-naming line, streamed from the container.
```

**Body — extended types**:

- `pipeline` (the command) — signature gains `profile: str | None`; the `-p/--profile` click option (with the `--parallel` long-only change); validation adds the leading-dash check for the profile value; the algorithm adds the home-bundle load (after the argument-form checks, before the dispatch) and passes the bundle plus the profile into both launchers.
- `run_pipeline_container` — signature gains `profile: str | None` and `home_profiles: dict[str, dict[str, Any]] | None = None`; the in-container argv appends `--profile <v>` when set; the env-file gains the three engine lines per the engine-skip rule; the workflow log print step is REMOVED (the line prints in-container); every other step unchanged.
- `run_pipeline_info_container` — signature gains `profile: str | None` and `home_profiles: dict[str, dict[str, Any]] | None = None`; the card argv appends `--profile <v>` when set; an env-file is added only when the ambient GOGA_PROFILE is non-empty or the bundle is non-empty (carrying those two lines; never GOGA_WORKFLOW); with nothing to carry the launch keeps the minimal read-only shape.

**Footer** — extend Description with the profile activation carriage.

#### Usage files

**UPDATE `goga/commands/pipeline/.usages/pipeline-command.md`** — the flag matrix change (`-p/--profile`; `--parallel` long-only), the three engine-variable carriage lines and their write conditions, the conditional info-form env-file, the in-container move of the workflow log line, and the strict host-side failure on a malformed home profile.

### Dependency — `pyproject.toml` (MODIFY)

Add `jinja2>=3.1` to the runtime dependencies (project convention: every third-party library declared with a minimum version).

## Dependency Map

```
LEAVES:  goga/pipeline/workflow (no Imports; + jinja2 cook)
         goga/config/project (no Imports)    goga/ralphex (no Imports)
         goga/version (existing leaf)

  goga/version ───────────────> goga/docker
  goga/docker ─────────────┐
  goga/config (/project) ──┤
  goga/ralphex ────────────┼────> goga/build ───────────> goga/commands/build
  goga/agents ─────────────┤        ▲    ▲
  goga/build/hooks ────────┘        │    │
  goga/config/hooks ───────────────┤    │
  goga/history ────────────────────┘    │
                                        │
  goga/pipeline/workflow ──────────────┘   [NEW EDGE: load_workflow,
                                            LoadedWorkflow, WorkflowBuild;
                                            Usages: load-workflow, profiles]

  goga/pipeline/compiler, goga/afm, goga/docker, goga/config, goga/agents,
  goga/pipeline/hooks (MODIFIED: merge keeps the full stage field set
  incl. env; profile/build survive the overlay rebuild), goga/history,
  goga/pipeline/workflow (existing edge, grows: + LoadedWorkflow,
  + Usages load-workflow, profiles) ─────> goga/pipeline

  goga/topics, goga/config, goga/config/hooks, goga/runtime, goga/docker,
  goga/pipeline (Usages only),
  goga/pipeline/workflow [NEW EDGE: load_home_profiles] ──> goga/commands/pipeline

  goga/build, goga/config, goga/config/hooks, goga/runtime, goga/docker,
  goga/pipeline/workflow [NEW EDGE: load_home_profiles] ──> goga/commands/build
```

No import cycles: `goga/pipeline/workflow` is a leaf, so every new edge points into it; the command cells are terminal.

## Verification Checklist

After implementing each artifact, verify:

- [ ] **workflow cell**: `parse_workflow` accepts rendered text; the six top-level keys validate (unknown-key errors list `profile`, `build`); `env` rejected in extend-entries; `build:` rejects `proxy`/`hosts` and any seventh key; empty-map env → None; `load_workflow` renders ALWAYS (plain file → identity); peek finds only literal `profile:` lines; all profile failures name the profile (+ path/locations); TemplateSyntaxError surfaces file + line.
- [ ] **config cell**: `build.review.additional.env` loads (optional string map, default empty; non-string → ValueError); existing configs parse identically.
- [ ] **docker cell**: `encode`/`decode_home_profiles` round-trip; empty bundle ↔ empty string; damaged payload → one clean error naming `GOGA_HOME_PROFILES`, no content leaked; nothing printed.
- [ ] **build cell**: layering `config < workflow build: < CLI` holds end-to-end (write a config knob, override in workflow, override on CLI — assert the winner at each step); env merge is key-wise (config survivors retained); review fields set by the block with `config.review` None construct a well-formed `ReviewConfig` (defaults for the unset); a workflow build block with no config build section → one strict error naming the requirement; per-role wrappers exported with CLI entries on top, engine keys dropped; `.ralphex/config` command fields point at wrappers; no env layer argument on the pass launch; `GOGA_WORKFLOW` beats nothing when `-w` set; no workflow → no line, activation ignored; feedback line only with effective profile; profile-free run behaviour-identical (same effective env, same results).
- [ ] **pipeline cell**: env-free workflow → flow-file byte-identical to before (no wrappers generated); env-declaring stage → `command:` points at an executable wrapper that exports then execs (stage agent → global agent → strict failure); per-stage values beat global layers; card equals run composition under the same flags; four env reads exactly; feedback line text with/without profile; damaged bundle → clean pre-run error, no events; effective profile (any activation channel, incl. `--profile` and the workflow default) exported as `GOGA_PROFILE` into the afm launch layer — a nested in-container build inherits workflow AND profile with no additional options; engine-key collisions (`GOGA_PROFILE` / `GOGA_WORKFLOW` / `GOGA_HOME_PROFILES` / `GOGA_EXTRA_ENV`) dropped silently from the layer.
- [ ] **commands cells**: `-p/--profile` on all four surfaces (host pipeline — with `--parallel` long-only — host build, in-container CLI, in-container build argv); leading-dash rejection; env-file engine lines written only when non-empty and skipped when user-supplied via `-e`; info env-file only when something to carry; `GOGA_WORKFLOW` written only by the run launcher; malformed home profile fails before any docker activity; no host workflow line anymore.
- [ ] **hooks cell**: an env-declaring workflow plus a committed tool contribution — the per-stage `env` instruction and the workflow-level `profile` / `build` fields survive the `merge_workflow_overlay` rebuild (the merged stages carry `env`; the merged document carries `profile` / `build` verbatim).
- [ ] **project-level**: `pyproject.toml` declares `jinja2>=3.1`; `goga lint` passes on all nine modified CODEMANIFESTs; facade imports (`from goga.pipeline.workflow import load_workflow`, `from goga.docker import decode_home_profiles`) resolve; full test suite green.
- [ ] **Acceptance criteria**: each of the eight gates from the Acceptance Criteria section demonstrated end-to-end (G1/G4/G2/G3 scenarios, strict failures, byte-identical pipeline path, behaviour-identical build path, propagation, feedback lines).
