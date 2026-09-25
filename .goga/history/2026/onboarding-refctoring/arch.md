# Architecture plan — Extensible `goga init` onboarding: tool participation via hooks actions and the dynamic image tag

## Topic

**Extensible `goga init` onboarding** — tool participation via hooks actions and the
 dynamic image tag.
Plan path: `.goga/history/2026/onboarding-refctoring/arch.md` (the output of `goga history path -f arch.md`).
Normative inputs: `task.md` (decisions 1–12, S1–S14) and `adr.md`; stage decisions: q1=q2=q3=q6=A,
the `minor_version` rename, and map/distribution corrections (q7–q9, q16, q18, q20).

## Implementation Order

| # | Cell | Status | Order rationale |
|---|---|---|---|
| 1 | `goga/version` | modify | leaf without Imports; the onboarding facade depends on it |
| 2 | `goga/hooks/catalog` | modify | leaf without Imports; the hooks facade and delivery depend on it |
| 3 | `goga/hooks` (facade) | modify | depends on the existing leaves catalog/registry/dispatch/tools (unchanged) |
| 4 | `goga/onboarding/questions` | create | leaf without Imports — the session data model |
| 5 | `goga/onboarding/participation` | create | depends on questions (No. 4) and goga/hooks (No. 3) |
| 6 | `goga/onboarding/survey` | create | depends on questions (No. 4) and participation (No. 5, F1: `ToolDeclaration`) |
| 7 | `goga/onboarding/generator` | create | depends on questions (No. 4) and participation (No. 5) |
| 8 | `goga/onboarding` (facade) | modify | depends on the four leaves (No. 4–7), goga/version (No. 1), and goga/config (exists) |
| 9 | `goga/commands/init` | modify | depends on the onboarding facade (No. 8) and goga/scaffold (exists) |

The graph has no cycles; the order runs leaves → root.

## Artifacts

### 1. `goga/version` — CODEMANIFEST *(modify)*

**Diff — add** (to the existing Body, after the `host_goga_version` block):

```yaml
"minor_version(version: str) -> minor: str":
  location: version.py
  annotations: |
    Derive the minor line of a version string — the N.M form consumers use
    to present values that must match the installed minor (image tag hints).

    `version`: version string (release segments, possibly with
      dev/pre/post/local tails)
    `minor`: the minor line N.M

    Apply the `convention` practice for docstring style and the
    pure-function discipline.

    Algorithm:
    1. Reduce `version` to its leading release segments: the first numeric
       segment is the major, the optional second numeric segment is the minor
    2. Treat a missing minor segment as 0
    3. Return the two segments joined by a dot — the minor line
    4. An argument with no leading numeric major segment raises ValueError

    Requirements:
    - Pure function — deterministic, no I/O, no logging
    - Richer tails reduce silently: 1.2.1.dev3, 1.2.0rc1, 1.2.0.post1,
      1.2.0+local all reduce to the 1.2 line

    Constraints:
    - Do not read the installed version here — the caller owns the metadata
      boundary; this routine receives it as `version`
    - Do not validate that segments form a real released version — shape
      recognition only, mirroring `resolve_version`
```

Nothing changes and nothing is deleted: `Usages`/`Annotations` (global), `resolve_version`,
`resolve_relative_spec`, `compare_versions`, `host_goga_version`, `version_check_enabled`,
`ensure_version_match`, the footer — verbatim.

**Usage file — create:** `goga/version/.usages/minor-line.md`

```md
# Minor line of a version — goga/version

## Domain

Deriving the minor line (N.M) of a version string. Target audience: features
that present values matching the installed minor — image tag hints,
compatibility labels — and need the same minor the host↔image comparison
uses.

## Public API

    from goga.version import minor_version, host_goga_version

- `minor_version(version: str) -> str` — the N.M line of `version`. A missing
  minor segment reads as 0; dev/pre/post/local tails are discarded; an
  undeterminable major segment raises ValueError.
- `host_goga_version() -> str` — the installed goga version; the single
  reading point. Propagates the metadata exception when undeterminable.

## Ready-to-use pattern

### Offer a hint matching the installed minor

Read once, derive, format at the consumer:

```python
from goga.version import host_goga_version, minor_version

version = host_goga_version()   # may raise when metadata is unreadable — handle at the caller
tag = minor_version(version)    # "1.3.2" -> "1.3"
image_hint = f"qarium/goga-python-3.12:{tag}"
```

- `minor_version` is pure — the caller owns the metadata boundary and passes
  the string; the routine never reads, prints, or exits.
- A hint built from the returned line agrees with the (major, minor)
  host↔image check by construction.

## Notes for the consumer

- Do not parse the version string at the call site — this routine owns the
  reduction.
- An unreadable installed version is the caller's error to translate into a
  clean message.
```

### 2. `goga/hooks/catalog` — CODEMANIFEST *(modify)*

**Diff — add** to the `declared_actions` → `Requirements` block (after the existing item about `statuses`,
which stays verbatim):

```yaml
    - The catalog carries the onboarding session-declaration action — the
      record domain="onboarding", name="declare_session", error_class="soft":
      a failing hook of the action is skipped with a warning and the sequence
      continues
    - The catalog carries the onboarding config-amendment action — the record
      domain="onboarding", name="amend_config", error_class="soft": a failing
      hook of the action is skipped with a warning and the sequence continues
```

Nothing changes and nothing is deleted. The cell has no usage files (and gains none).

### 3. `goga/hooks` — CODEMANIFEST *(facade, modify)*

**Diff — Imports:** add `wrap_context` and `build_hook_arguments` to the existing import record from
`goga/hooks/dispatch` (which already carries `emit_hook_event`); add a new import record from
`goga/hooks/tools` with the type `enumerate_tool_packages`:

```yaml
Imports:
  - Types:
      - declared_actions
    From: goga/hooks/catalog
  - Types:
      - HookRegistry
      - ToolHooks
    From: goga/hooks/registry
  - Types:
      - emit_hook_event
      - wrap_context
      - build_hook_arguments
    From: goga/hooks/dispatch
  - Types:
      - enumerate_tool_packages
    From: goga/hooks/tools
```

**Diff — Annotations (global block):** append one sentence to the end of the existing facade
characterization (the existing wording stays verbatim):

```yaml
    It additionally re-exports the delivery primitives and the
    installed-package enumeration — for domains that orchestrate per-tool
    delivery themselves and need each hook's outcome or the installed
    identities.
```

**Diff — Body:** add after the existing embeddings:

```yaml
->wrap_context: {}
->build_hook_arguments: {}
->enumerate_tool_packages: {}
```

**Usage file — create:** `goga/hooks/.usages/per-tool-delivery.md`

```md
# hooks — delivering per tool with staged control

How a goga domain delivers an action to its subscribed hooks per tool, when
the plain emission is not enough — the domain must know each tool's outcome
(staged contributions, compensating rollback). For domain maintainers inside
goga.

## When to use

Use `emit_hook_event` when the domain only hands the context over — the
emission is fire-and-forget and collects nothing after the event. Use this
pattern when a tool's contribution is committed only after its hooks succeed;
per-hook outcomes are out of reach through the emission, so the domain drives
the delivery loop itself over the public primitives.

## The public primitives

    from goga.hooks import HookRegistry, wrap_context, build_hook_arguments

- `HookRegistry()` — the run registry; `build_once()` assembles it once per
  run.
- `registry.subscriptions_for(domain, action)` — the address's
  subscriptions, in enumeration order.
- `registry.self_context(tool)` — the isolated context of one tool.
- `wrap_context(view)` — the delivery view of your context: reads and calls
  pass through, attribute assignment is blocked.
- `build_hook_arguments(hook, proxy, self_context)` — the keyword arguments
  for the call; only names the hook declared receive values.

## The pattern

```python
registry = HookRegistry()
registry.build_once()

groups: dict[str, list] = {}
for sub in registry.subscriptions_for("<domain>", "<action>"):
    groups.setdefault(sub.tool, []).append(sub)

for tool, subs in groups.items():
    proxy = wrap_context(build_the_context_for(tool))   # your per-tool view
    try:
        for sub in subs:
            sub.hook(**build_hook_arguments(sub.hook, proxy, registry.self_context(tool)))
    except Exception as reason:
        logger.warning("tool skipped", extra={"tool": tool, "action": "<action>", "reason": reason})
        discard(tool)          # the tool's whole contribution
        continue
    commit(tool)               # only after every hook of the tool succeeded
```

## Rules the pattern keeps

- Deliver to every subscriber of the address — never filter delivery by
  invitation or any other criterion; a tool's eligibility lives in its
  context (a marker the hook checks), not in delivery.
- Treat a failure per the action's error class recorded in the catalog —
  soft: warn naming the tool, the action, and the reason, then continue with
  the next tool. The single fatal case (a broken package import) surfaces at
  `build_once`.
- One registry per run — build it once and share it across your checkpoints.
- Do not deliver a hook any value it did not declare —
  `build_hook_arguments` is the single projection.
```

### 4. `goga/onboarding/questions` — CODEMANIFEST *(create)*

```yaml
Usages:
  convention: .goga/usages/conventions.md

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and testing in the project

  This cell owns the declarative question-and-answer model of the
  onboarding session: the question records of every kind, the nesting
  groups, and the session answer space. Data and pure answer operations
  only — no interactivity, no filesystem, no tool delivery. The question
  records are immutable; the answer space is the single mutable
  accumulator of one run. Use relative imports.

---

"Question(id: str, kind: str, prompt: str, choices: list[str] | None = None, default: str | bool | None = None, keys: list[str] | None = None)":
  location: questions.py
  annotations: |
    One declarative question record — the survey unit of the session.

    `id`: the local name of the question within its parent — unique among
      the siblings of its tree position
    `kind`: the question kind — one of choice, input, confirm, pairs
    `prompt`: the user-facing prompt text
    `choices`: the offered values; set for the choice kind
    `default`: the preselected value or the input default; a bool for the
      confirm kind
    `keys`: the proposed keys of the repeated key-value collection; set for
      the pairs kind

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - The record carries data only — rendering the question and validating
      the answer value belong to the survey engine
    - The kind fixes the parameterization: `choices` for choice, `default`
      for input and confirm, `keys` for pairs
    - The answer value of each kind: choice and input — a string, confirm —
      a boolean, pairs — a mapping of strings
  properties:
    "id -> str": |
      The local name of the question within its parent.
    "kind -> str": |
      The question kind — choice, input, confirm, or pairs.
    "prompt -> str": |
      The user-facing prompt text.
    "choices -> list[str] | None": |
      The offered values of the choice kind.
    "default -> str | bool | None": |
      The preselected value or the input default; a bool for confirm.
    "keys -> list[str] | None": |
      The proposed keys of the pairs kind.

"QuestionGroup(id: str, prompt: str | None = None, children: list[Question | QuestionGroup] | None = None)":
  location: questions.py
  annotations: |
    One nesting node of the question tree — a section whose answer is the
    mapping of its children's answers.

    `id`: the local name of the group within its parent — unique among the
      siblings of its tree position
    `prompt`: the optional section heading; a purely structural node carries
      none
    `children`: the nested questions and groups, in survey order

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - The tree path of a node — the ids from the root to the node joined by
      dots — addresses the node in skip requests and answer paths
    - The answer value of a group is a nested mapping keyed by child ids —
      never a flat dotted key
    - A group declared by a tool is limited to one nesting level with
      simple children; deeper nesting belongs to the core survey structure
  properties:
    "id -> str": |
      The local name of the group within its parent.
    "prompt -> str | None": |
      The optional section heading of the group.
    "children -> list[Question | QuestionGroup] | None": |
      The nested questions and groups, in survey order.

"SessionAnswers()":
  location: answers.py
  annotations: |
    The answer space of one session — the question-to-value mapping shared
    by the survey, the tool participation, and the file generation.

    Apply the `convention` practice for the code style and intra-package
    imports.

    Requirements:
    - Created empty; the structure is nested mappings keyed by question
      ids — groups hold mappings, no dotted keys are ever stored
    - The single mutable accumulator of the run — every answer, core and
      tool, lands here exactly once
  methods:
    "record(id: str, value: str | bool | dict) -> _: None": |
      Record the user's answer collected by the survey.

      `id`: the dot-path of the answered question in the plan tree
      `value`: the answer value of the question kind

      Algorithm:
      1. Resolve `id` segment by segment, creating the intermediate
         mappings of the traversed groups
      2. Set the value at the leaf name

      Requirements:
      - Recording replaces — a later record at the same path overwrites the
        earlier value; merging belongs to amendments
    "amend(id: str, value: str | bool | dict) -> _: None": |
      Apply one amendment of a tool contribution at the addressed location.

      `id`: the dot-path of the addressed entry
      `value`: the amendment value

      Algorithm:
      1. Resolve `id` segment by segment, creating the intermediate
         mappings of the traversed groups
      2. An existing mapping at the leaf merges recursively with `value`;
         a scalar or a list replaces; an absent leaf is created

      Requirements:
      - Mappings merge recursively; scalars and lists replace
      - Amendments apply in delivery order — a later amendment wins at
        every conflicting leaf
      - Substituting a user's answer is a tool's lawful right — the
        amendment applies silently
    "view_for(tool: str) -> view: dict": |
      The isolated answer view of one tool.

      `tool`: the tool identity
      `view`: the core answers plus the tool's own answers under their
              local names

      Algorithm:
      1. Take the core section of the space
      2. Add the tool's own section re-keyed by local names, without the
         tool prefix

      Requirements:
      - The answers of other tools are never present — coordination goes
        through amendments of shared sections, not through reading foreign
        data
      - The view is a snapshot — amendments applied after the call do not
        appear in it
    "snapshot() -> view: dict": |
      The full answer space for generation.

      `view`: the complete nested structure — the core and every committed
              tool section

      Requirements:
      - Reflects the committed state at the call moment — generation runs
        after the tool contributions are committed

---

Author: Goga
CreatedAt: 14/09/26
Description: |
  Declarative question-and-answer model of the onboarding session —
  question records, nesting groups, and the session answer space.
```

**Usage file — create:** `goga/onboarding/questions/.usages/question-records.md`

```md
# Question records — goga/onboarding/questions

## Domain

The declarative question-and-answer model of the onboarding session:
question records of every kind, nesting groups, and the session answer
space. Target audience: cells that build or survey a question tree, and
tool package authors whose session questions are declared as these
records.

## Public API

    from goga.onboarding import Question, QuestionGroup, SessionAnswers

- `Question(id, kind, prompt, choices=None, default=None, keys=None)` — one
  simple question. Kinds: `choice` (answer — a string from `choices`),
  `input` (answer — a free-form string), `confirm` (answer — a bool),
  `pairs` (answer — a mapping of strings; `keys` proposes the keys).
- `QuestionGroup(id, prompt=None, children=None)` — one nesting level; the
  group's answer is the mapping of its children's answers.
- `SessionAnswers` — the answer space of one run: `record`, `amend`,
  `view_for`, `snapshot`.

## Ready-to-use patterns

### Declare a question of each kind

```python
from goga.onboarding import Question, QuestionGroup

language = Question(id="language", kind="choice", prompt="Project language",
                    choices=["python", "golang"], default="python")
image = Question(id="image", kind="input", prompt="Image name")
setup = Question(id="setup", kind="confirm", prompt="Configure the tool?", default=False)
env = Question(id="env", kind="pairs", prompt="Environment variables",
               keys=["API_URL", "TOKEN"])
```

### Declare a group

```python
block = QuestionGroup(id="reporting", prompt="Reporting settings",
                      children=[setup, env])
```

A group carries one nesting level with simple children; its answer is a
mapping keyed by child ids.

### Address answers

Paths join ids with dots (`reporting.env`); stored answers are nested
mappings — groups hold mappings, no dotted keys. `record` replaces at the
path; `amend` merges mappings recursively and replaces scalars and lists
(last applied wins); `view_for(tool)` returns the core plus the tool's own
answers under local names — other tools' answers are never visible;
`snapshot` returns the committed whole for generation.

## Notes for the consumer

- Question records are immutable value objects — build them fresh, never
  mutate.
- The `id` is local to its parent; uniqueness matters among siblings of the
  same tree position.
```

### 5. `goga/onboarding/participation` — CODEMANIFEST *(create)*

```yaml
Imports:
  - Types:
      - Question
      - QuestionGroup
      - SessionAnswers
    Usages:
      - question-records
    From: goga/onboarding/questions
  - Types:
      - HookRegistry
      - wrap_context
      - build_hook_arguments
      - enumerate_tool_packages
    Usages:
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
  - Understanding the general principles and rules of development and testing in the project

  This cell owns the tool participation in the onboarding session: the
  invitation, the two onboarding action moments delivered per tool with
  staged control, the tool declaration and contribution surfaces, and the
  isolated answer views. The per-tool delivery composes `wrap_context`
  and `build_hook_arguments` per the `per-tool-delivery` practice. A
  failure of one tool never cancels another tool or the session; the
  single fatal case is a broken package import. Every warning names the
  tool, the action, and the reason. Use relative imports.

---

"ToolDeclaration(tool: str, invited: bool)":
  location: declaration.py
  annotations: |
    The moment-one surface delivered to one tool — the session declaration
    context and its buffer.

    `tool`: the tool identity assigned by the platform
    `invited`: the invitation marker — False marks a subscribed tool the
      session did not invite

    Apply the `convention` practice for the code style and intra-package
    imports.
    Use the `question-records` practice for the declaration records.
    Use the `registering-hooks` practice for the hook signature and the
    failure handling behind the action.

    Requirements:
    - A hook of a non-invited tool returns immediately — the False marker
      is the contract rule; no member is called
    - The declared questions and skips are buffered; the engine reads them
      after the delivery of the moment completes
    - A hook is never called to survey — the engine asks the declared
      questions itself
  properties:
    "tool -> str": |
      The tool identity of the owning tool.
    "invited -> bool": |
      The invitation marker of the session.
    "questions -> list[Question | QuestionGroup]": |
      The declared questions and groups, in declaration order.
    "skips -> list[str]": |
      The declared skip paths, in declaration order.
  methods:
    "declare(item: Question | QuestionGroup) -> _: None": |
      Declare one question or one group of the tool's block.

      `item`: the question record or the one-level group

      Requirements:
      - A group of a tool is limited to one nesting level with simple
        children
      - The local names are the tool's own — the engine qualifies them
        with the tool identity
    "skip(path: str) -> _: None": |
      Declare one skip request.

      `path`: the raw path — unprefixed for the core tree or the tool's
        own block, prefixed with a tool identity for another tool's block

      Requirements:
      - The engine resolves and applies every declared skip as one set
        after the whole declaration; individual pairs inside a pairs
        question are not addressable

"ToolContribution(tool: str, invited: bool, answers: dict)":
  location: contribution.py
  annotations: |
    The moment-two surface delivered to one tool and the staged buffer of
    its contribution — the amendments and the config files.

    `tool`: the tool identity assigned by the platform
    `invited`: the invitation marker of the session
    `answers`: the isolated answer view of the tool — the core answers plus
      its own under local names

    Apply the `convention` practice for the code style and intra-package
    imports.
    Use the `registering-hooks` practice for the hook signature and the
    failure handling behind the action.

    Requirements:
    - A hook of a non-invited tool returns immediately
    - The contribution is staged — the engine applies the buffered
      amendments and writes the buffered files only after every hook of
      the tool of this moment completed without failure
    - The view carries nothing of the other tools — coordination goes
      through amendments of shared sections
  properties:
    "tool -> str": |
      The tool identity of the owning tool.
    "invited -> bool": |
      The invitation marker of the session.
    "answers -> dict": |
      The isolated answer view — the core and the tool's own answers.
    "amendments -> list[tuple[str, str | bool | dict]]": |
      The buffered amendments — the path and the value, in call order.
    "files -> list[tuple[str, dict]]": |
      The buffered config files — the file name and the data, in call
      order.
  methods:
    "answer(id: str, value: str | bool | dict) -> _: None": |
      Buffer one amendment of the collected configuration.

      `id`: the dot-path of the addressed entry
      `value`: the amendment value

      Requirements:
      - Merge semantics apply at the addressed location — mappings merge
        recursively, scalars and lists replace
      - Substituting a user's answer is silent — a lawful right of the
        tool
      - The registrations in the tools and usages sections are ordinary
        amendments at their ids
    "write_config(file: str, data: dict) -> _: None": |
      Buffer one config file of the tool.

      `file`: the file name inside the tool's config directory
      `data`: the serializable mapping of the file

      Requirements:
      - The engine serializes and writes the file into the tool's config
        directory; writing the same file again replaces it
      - A tool never writes its config files itself — the engine API is
        the single write path

"ToolParticipation(invited: list[str])":
  location: participation.py
  annotations: |
    The mediator of the tool participation — both onboarding action moments
    delivered per tool with staged control.

    `invited`: the invited tool identities, deduplicated, in flag order

    Apply the `convention` practice for the code style and intra-package
    imports.
    Use the `per-tool-delivery` practice for the delivery loop.
    Use the `registering-hooks` practice for the registration contract
    behind the actions.
  properties:
    "invited -> list[str]": |
      The invited tool identities, deduplicated, in flag order.
  methods:
    "collect_declarations() -> declarations: list[ToolDeclaration]": |
      Deliver the moment one — the session declaration action.

      `declarations`: the declarations of the surviving tools, in
                      enumeration order

      Algorithm:
      1. Build the run registry — `HookRegistry` — once for the whole
         session; a broken package import is a clean error naming the
         package — the single fatal case
      2. Warn for every invited identity that is not among the installed
         tool packages — resolved via `enumerate_tool_packages` — naming
         it; the session continues without its block
      3. Deliver the declaration action to every subscriber per tool, in
         enumeration order: an invited tool receives an active surface, a
         subscribed tool without an invitation receives the not-invited
         marker
      4. A failing hook of a tool drops that tool's whole declaration — a
         warning, the session continues; the other tools stand
      5. Return the declarations of the surviving tools

      Requirements:
      - An invited tool without a subscription to the action participates
        silently — no block, no warning
    "collect_contributions(answers: SessionAnswers) -> contributions: list[ToolContribution]": |
      Deliver the moment two — the config amendment action — and commit the
      surviving contributions.

      `answers`: the session answer space after the survey
      `contributions`: the committed contributions, in enumeration order

      Algorithm:
      1. Deliver the amendment action to every subscriber per tool, in
         enumeration order, each tool with its isolated answer view
      2. A failing hook of a tool discards its whole contribution — the
         amendments and the files together — with a warning; the session
         continues; the other tools stand
      3. Commit every surviving contribution: apply its buffered
         amendments to `answers` in delivery order; collect its buffered
         files
      4. Return the committed contributions

      Requirements:
      - The committed amendments apply in delivery order — the enumeration
        order of the tool identities; a conflicting leaf is won by the
        last applied amendment
      - The file buffer of a failed tool is discarded together with its
        amendments

---

Author: Goga
CreatedAt: 14/09/26
Description: |
  Tool participation in the onboarding session — the invitation, the two
  onboarding action moments delivered per tool, the staged contributions,
  and the isolated answer views.
```

**Usage files — create:**

`goga/onboarding/participation/.usages/session-participation.md`

```md
# Session participation — goga/onboarding/participation

## Domain

Mediating the tool participation in one onboarding session: the invitation
set, the declaration moment before the survey, the amendment moment after
it, and the staged commit of the surviving contributions. Target
audience: the session orchestrator.

## Public API

    from goga.onboarding import ToolParticipation

- `ToolParticipation(invited)` — the mediator of one session; `invited` is
  the deduplicated list of tool names from the command line, in flag
  order.
- `collect_declarations() -> list[ToolDeclaration]` — deliver
  `onboarding/declare_session` per tool. Warns for every invited name not
  among the installed tool packages; a failing hook of a tool drops that
  tool's whole declaration; an invited tool without a subscription
  participates silently.
- `collect_contributions(answers) -> list[ToolContribution]` — deliver
  `onboarding/amend_config` per tool after the survey. A failing hook
  discards the tool's whole contribution (amendments and files); the
  surviving contributions are committed: amendments apply to `answers` in
  delivery order, files are collected for generation.

## Ready-to-use pattern

### Run both moments around the survey

```python
from goga.onboarding import SessionAnswers, ToolParticipation

participation = ToolParticipation(invited=["my-tool", "viewer"])
declarations = participation.collect_declarations()   # moment one — before the survey
# ... assemble the plan, run the survey into answers ...
contributions = participation.collect_contributions(answers)  # moment two — after
```

## Notes for the consumer

- One registry per session — build and both deliveries share it; a broken
  package import is the single fatal case (a clean error naming the
  package).
- Tool failures are soft — every warning names the tool, the action, and
  the reason; the session and the other tools continue.
- The returned contributions carry the committed file buffers — hand them
  to the artifact generation.
```

`goga/onboarding/participation/.usages/tool-contexts.md`

```md
# Onboarding contexts — goga/onboarding/participation

## Domain

What a tool package receives inside a `goga init` session and the member
contract of the two onboarding actions. Target audience: authors of
`goga_tool_*` packages that need project configuration.

## Subscribing

Register hooks for the two actions in the package facade — the tool
identity is assigned by goga from the package name:

```python
def register_hooks(hooks):
    hooks.subscribe("onboarding", "declare_session", "declare", declare_session)
    hooks.subscribe("onboarding", "amend_config", "amend", amend_config)
```

A hook declares `context` (and optionally `self`) by name; values land by
name. Subscribing to one action only is fine — the moments are
independent.

## Moment one — declare_session(context)

Declare the tool's questions and skips as data; the engine asks them
itself after the core questions, under a heading with the tool's name.

```python
from goga.onboarding import Question, QuestionGroup

def declare_session(context):
    if not context.invited:
        return                      # contract rule: return immediately
    context.declare(Question(id="token", kind="input", prompt="Service token"))
    context.declare(QuestionGroup(id="reporting", prompt="Reporting",
                                  children=[Question(id="enabled", kind="confirm",
                                                     prompt="Enable reporting?", default=False)]))
    context.skip("docker_image.base_image")   # unprefixed — core tree or own block
```

- `context.invited` — False means the session did not invite this tool:
  return immediately, call nothing.
- `context.declare(item)` — a `Question` or a one-level `QuestionGroup`;
  local names, the engine qualifies them with the tool identity. A
  repeated local name is rejected with a warning; the rest of the
  declaration stands.
- `context.skip(path)` — unprefixed for the core tree or the tool's own
  block, `<tool>.`-prefixed for another tool's block. A skip removes the
  whole subtree; unknown paths are a no-op with a warning.

## Moment two — amend_config(context)

Read the isolated answers and buffer the contribution.

```python
def amend_config(context):
    if not context.invited:
        return
    if context.answers.get("reporting", {}).get("enabled"):
        context.answer("pipeline.env", {"REPORT_URL": "https://example.com"})
        context.answer("tools", {"my-tool": "latest"})
        context.write_config("service.yml", {"token_source": "env", "interval": 60})
```

- `context.answers` — the core answers plus this tool's own answers under
  local names; other tools' answers are never visible.
- `context.answer(id, value)` — buffer an amendment: mappings merge
  recursively, scalars and lists replace; substituting a user's answer is
  silent; registrations in `tools`/`usages` are ordinary amendments.
- `context.write_config(file, data)` — buffer a config file; the engine
  serializes YAML and writes `.goga/tools/<tool>/<file>`; the same file
  written again is replaced.

## Failure behavior

- An exception in a hook drops the tool's whole contribution with a
  warning naming the tool and the reason; `goga init` continues and exits
  0.
- A broken package import is the single fatal case — a clean session
  error naming the package.
```

### 6. `goga/onboarding/survey` — CODEMANIFEST *(create)*

```yaml
Imports:
  - Types:
      - Question
      - QuestionGroup
      - SessionAnswers
    Usages:
      - question-records
    From: goga/onboarding/questions
  - Types:
      - ToolDeclaration
    From: goga/onboarding/participation

Usages:
  convention: .goga/usages/conventions.md
  click: .goga/usages/cooks/click.md
  image_defaults: |
    The default Docker image hints depend on the selected language and carry
    the current minor tag supplied at runtime (the image-tag input of
    the core tree) — never a hardcoded tag. For languages with predefined
    images, display the suggestions; default to the last entry. Accept
    arbitrary user input for the image name. Language → image family
    mapping (the tag completes the name):
    - python: qarium/goga-python-{3.10-3.14}:{tag}
    - golang: qarium/goga-golang-{1.23, 1.24, 1.25, 1.26}:{tag}
    - javascript: qarium/goga-node-{22, 24}:{tag}
    - kotlin: qarium/goga-kotlin-{2.0, 2.1, 2.2, 2.3}:{tag}
    - swift: qarium/goga-swift-{6.0, 6.1, 6.2}:{tag}
  agent_env_defaults: |
    Map each agent to a list of environment variable keys for prompting.
    Display the keys to the user; collect corresponding values.
    Agent → env key mapping:
    - claude: ANTHROPIC_BASE_URL, ANTHROPIC_DEFAULT_HAIKU_MODEL, ANTHROPIC_DEFAULT_SONNET_MODEL, ANTHROPIC_DEFAULT_OPUS_MODEL, ANTHROPIC_MODEL
    - codex: CODEX_MODEL
    - cursor: CURSOR_MODEL
    - opencode: OPENCODE_MODEL, OPENCODE_VARIANT
    - qwen: OPENAI_BASE_URL, OPENAI_MODEL

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and testing in the project

  This cell owns the survey of the onboarding session: the core question
  tree, the assembly of the session plan with the tool question blocks,
  the application of skip requests, and the interactive run. The survey is
  interactive on the host through the `click` practice; core sections are
  conditional on the filesystem state. Questions are declarative data —
  the engine asks them itself; a tool hook is never called to survey. Use
  relative imports.

---

"core_questions(image_tag: str, project_name: str | None, convention_exists: bool) -> tree: QuestionGroup":
  location: core.py
  annotations: |
    Build the core question tree of the session — the eight core sections
    in survey order.

    `image_tag`: the current minor tag for image hints (the `image_defaults`
      practice completes image names with it)
    `project_name`: the git-derived project name for the built-image name
      default; None offers no default
    `convention_exists`: True when the base conventions file already exists
    `tree`: the core tree

    Apply the `convention` practice for docstring style and intra-package
    imports.
    Use the `image_defaults` practice for image hints.
    Use the `agent_env_defaults` practice for the env key suggestions.

    Algorithm:
    1. Compose the sections in order: language, convention, codemanifest,
       build, docker_image, pipeline, tools, usages
    2. Omit the convention section when `convention_exists` is True
    3. Set the image hints from the `image_defaults` practice completed
       with `image_tag`; the built-image name default follows
       `project_name`

    Requirements:
    - language — a choice of the supported languages
    - convention — an offer to adopt the base convention; acceptance
      pre-fills the codemanifest section
    - codemanifest — practice usages and annotations entries
    - build — the task executor: agent and env (suggested keys per
      `agent_env_defaults`)
    - docker_image — the Dockerfile decision, the base image of the FROM
      line, and the image name; the base image applies only when a
      Dockerfile path is given; the children carry the local names
      image, dockerfile, base_image — the mapping into the top-level
      config fields belongs to the generation
    - pipeline — agent and env (suggested keys per `agent_env_defaults`)
    - tools — a confirm-gated repeated collection of name and version
      pairs; version values follow the four-form version grammar, an
      absent version reads as latest
    - usages — a confirm-gated repeated record collection: group,
      dependency name, git repository, optional ref and root; the answer
      nests as {group: {dep: {git, ref, root}}}
    - Answer values nest as mappings mirroring the project config schema
    - The review section is not part of the tree — a future additive core
      section

"assemble_session_plan(core: QuestionGroup, declarations: list[ToolDeclaration]) -> plan: SessionPlan":
  location: plan.py
  annotations: |
    Assemble the session plan — the core tree plus the tool question
    blocks in one root.

    `core`: the core tree built by `core_questions`
    `declarations`: the collected declarations of the run, in enumeration
                    order
    `plan`: the assembled plan

    Apply the `convention` practice for docstring style and intra-package
    imports.
    Use the `question-records` practice for the record structure.

    Algorithm:
    1. Start from the children of `core`
    2. For each declaration in enumeration order: wrap its declared
       questions into one group named by the tool identity and append it
       after the core children
    3. A repeated local name within one tool's declaration is rejected —
       the element of the declaration is dropped with a warning naming the
       tool and the reason; the surviving elements of the same declaration
       stand

    Requirements:
    - Deterministic — the plan children order is the core order followed by
      the enumeration order of the tools
    - A tool without declarations contributes no block
    - Rejections never cancel the surviving elements of the same tool

"apply_skips(plan: SessionPlan, skips: list[tuple[str, str]]) -> plan: SessionPlan":
  location: plan.py
  annotations: |
    Apply the declared skip requests to the plan.

    `plan`: the assembled plan
    `skips`: the declared skips — the declaring tool identity and the raw
             path
    `plan`: the plan with the skipped subtrees removed

    Apply the `convention` practice for docstring style and intra-package
    imports.

    Algorithm:
    1. Resolve every path against the plan root: an unprefixed path
       addresses the core tree or the declaring tool's own block; a path
       prefixed with a tool identity addresses that tool's block
    2. Remove every resolved node — the whole subtree under it
    3. Apply all skips as one set — the result does not depend on the
       order of application
    4. A path resolving to nothing is a no-op announced with a warning

    Requirements:
    - A skipped question is never asked; the tool whose question was
      skipped tolerates the missing answer
    - Inside a pairs question the individual pairs are not addressable —
      only the node as a whole

"SessionPlan(root: QuestionGroup, tools: list[str])":
  location: plan.py
  annotations: |
    The assembled survey plan — one tree with the tool blocks as groups
    named by tool identity.

    `root`: the plan root — the core children followed by the tool blocks
    `tools`: the participating tools in block order

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
  properties:
    "root -> QuestionGroup": |
      The plan root — the core sections followed by the tool blocks.
    "tools -> list[str]": |
      The participating tools in block order.

"Questionnaire()":
  location: questionnaire.py
  annotations: |
    The interactive survey engine of the session.

    Apply the `convention` practice for the code style and intra-package
    imports.
    Use the `click` practice for prompting, confirmation, choices, and the
    repeated collections.
    Use the `image_defaults` practice to render image hints.
    Use the `agent_env_defaults` practice to render env key suggestions.
  methods:
    "run(plan: SessionPlan, answers: SessionAnswers) -> _: None": |
      Run the whole survey of one plan into the answer space.

      `plan`: the assembled plan with skips applied
      `answers`: the session answer space receiving the collected values

      Algorithm:
      1. Display the session header and the wizard description
      2. Survey the core sections of `plan` in order
      3. Survey every tool block after the core, in block order, under an
         attribution heading naming the tool
      4. Record every collected value into `answers` at its plan path

      Requirements:
      - The core survey keeps its conditional patterns: the base image
        applies only when a Dockerfile path was given; the image defaults
        follow the Dockerfile branch
      - A skipped subtree is never asked
    "ask_question(question: Question) -> value: str | bool | dict[str, str]": |
      Ask one simple question of its kind.

      `question`: the question record
      `value`: the answer value of the kind

      Requirements:
      - Render the prompt, the offered choices or keys, and the default of
        the record; a free-form input is accepted where the kind allows it
    "ask_group(group: QuestionGroup) -> value: dict": |
      Ask one group — its children in order.

      `group`: the group node
      `value`: the mapping of the children's answers keyed by child ids

      Requirements:
      - Section headings and explanatory text precede the children; the
        confirm-gated collections ask their gate first

---

Author: Goga
CreatedAt: 14/09/26
Description: |
  Survey of the onboarding session — the core question tree, the session
  plan assembly with skip requests, and the interactive run.
```

**Usage file — create:** `goga/onboarding/survey/.usages/survey-run.md`

```md
# Survey run — goga/onboarding/survey

## Domain

Assembling the onboarding survey plan and running it interactively: the
core question tree, the tool question blocks, the skip requests, and the
click-driven survey. Target audience: the session orchestrator that builds
a plan and collects answers into the answer space.

## Public API

    from goga.onboarding import core_questions, assemble_session_plan, apply_skips, Questionnaire

- `core_questions(image_tag, project_name, convention_exists) -> QuestionGroup`
  — the eight core sections in survey order; image hints carry
  `image_tag`; the convention section is omitted when the file exists.
- `assemble_session_plan(core, declarations) -> SessionPlan` — one root:
  core children, then one group per declaring tool in enumeration order.
  A repeated local name within a tool drops that element with a warning;
  the rest of the declaration stands.
- `apply_skips(plan, skips) -> SessionPlan` — removes the addressed
  subtrees; unprefixed paths address the core tree or the declaring
  tool's own block, `<tool>.`-prefixed paths address that tool's block;
  unknown paths are a no-op with a warning; pairs are addressed only as a
  whole.
- `Questionnaire().run(plan, answers)` — the interactive survey: session
  header, core sections, tool blocks with attribution headings; values are
  recorded into the answer space at their plan paths.

## Ready-to-use pattern

### Build the plan and run the survey

```python
from goga.onboarding import (
    SessionAnswers, Questionnaire, apply_skips, assemble_session_plan, core_questions,
)

core = core_questions(image_tag="1.3", project_name="my-app", convention_exists=False)
plan = assemble_session_plan(core, declarations)          # declarations: from tool participation
plan = apply_skips(plan, skips)                           # skips: (tool, raw path) pairs
answers = SessionAnswers()
Questionnaire().run(plan, answers)
```

## Notes for the consumer

- Skips are applied to the assembled plan as one set — order-independent;
  run the survey only after `apply_skips`.
- The core survey keeps its conditional patterns: the Dockerfile branch
  decides the image questions; a confirm-gated collection asks its gate
  first.
- Questions are declarative data — the engine asks them; nothing calls a
  tool hook to survey.
```

### 7. `goga/onboarding/generator` — CODEMANIFEST *(create)*

```yaml
Imports:
  - Types:
      - SessionAnswers
    Usages:
      - question-records
    From: goga/onboarding/questions
  - Types:
      - ToolContribution
    Usages:
      - session-participation
    From: goga/onboarding/participation

Usages:
  convention: .goga/usages/conventions.md
  yaml: |
    Use yaml.dump() to generate .goga/config.yml and the tool config files.
    PyYAML library. Set default_flow_style=False for human-readable output.
  lang_conventions: |
    Download base language conventions from the qarium/goga-lang-conventions repository (branch 0.0.x).
    URL template: https://raw.githubusercontent.com/qarium/goga-lang-conventions/refs/heads/0.0.x/{language}/project.md
    The language identifier maps directly to the URL path segment (no mapping layer).
    Save the downloaded file to .goga/usages/conventions.md.

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and testing in the project

  This cell owns the artifact generation of the session: the project
  config, the Dockerfile, the base conventions download, and the tool
  config files — written from the committed answer space and the committed
  tool contributions. An existing .goga/config.yml is never rewritten —
  whoever created it first wins; the guarantee lives here, not only at the
  caller. Use relative imports.

---

"FileGenerator()":
  location: generator.py
  annotations: |
    The artifact generator of the session.

    Apply the `convention` practice for the code style and intra-package
    imports.
    Use the `yaml` practice for every YAML serialization.
    Use the `question-records` practice for the answer space structure.
    Use the `session-participation` practice for the committed
    contributions.
  methods:
    "generate(answers: SessionAnswers, contributions: list[ToolContribution]) -> files: list[CreatedFile]": |
      Generate every artifact of the session and report the created files.

      `answers`: the committed answer space of the session
      `contributions`: the committed contributions, in enumeration order
      `files`: the created files with attribution — an engine file carries
               a None tool, a tool file carries the tool identity

      Algorithm:
      1. An existing .goga/config.yml skips the config and the Dockerfile
         generation — the file is never rewritten
      2. Otherwise: create the Dockerfile when the answers carry a
         Dockerfile path — FROM its base image; then generate the project
         config
      3. Generate the tool config files of `contributions`
      4. Return the created files with attribution, in generation order

      Requirements:
      - The return value is the single source of the final file report
    "generate_goga_config(answers: SessionAnswers) -> _: None": |
      Generate .goga/config.yml from the answer snapshot.

      `answers`: the committed answer space

      Algorithm:
      1. Take the snapshot of `answers`
      2. An empty required language field is a clean error of the session
         naming the field
      3. Download the base conventions file per the `lang_conventions`
         practice when the codemanifest usages carry the conventions entry
         — a download failure is a clean error with the URL and the cause
      4. Create the .goga/ directory when missing
      5. Serialize the YAML document per the `yaml` practice, preserving
         the field order and rendering the annotations as a literal block

      Snapshot → YAML field mapping:
      - language → language (top level)
      - docker_image.image → image (top level)
      - docker_image.dockerfile → dockerfile (top level, omitted when absent)
      - docker_image.base_image → the Dockerfile FROM line only — never
        emitted to the config
      - build.task_executor.agent → build.task_executor.agent (omitted when absent)
      - build.task_executor.env → build.task_executor.env (omitted when absent or empty)
      - pipeline.agent / pipeline.env → the pipeline block (same omission rules)
      - codemanifest.usages / codemanifest.annotations → the codemanifest block
      - tools → tools (omitted when absent or empty)
      - usages → usages (omitted when absent or empty)
      - convention and the confirm gates are presentational — their answers
        are never carried into the config (the convention acceptance
        pre-fills codemanifest; a gate only gates its collection)

      Requirements:
      - Field order in the document: language, image, dockerfile, build,
        pipeline, codemanifest, tools, usages
      - The build and pipeline blocks appear only when they carry content
      - The written file passes the core schema loader of the project
        config
    "generate_tool_configs(contributions: list[ToolContribution]) -> _: None": |
      Generate the tool config files from the committed contributions.

      `contributions`: the committed contributions, in enumeration order

      Algorithm:
      1. For every contribution, for every buffered file in call order:
         serialize the data per the `yaml` practice and write it into the
         tool's config directory under the buffered file name
      2. Writing the same file name again replaces the file

      Requirements:
      - The engine is the single write path of the tool configs — the
        buffered data is written verbatim, without interpretation

"CreatedFile(path: str, tool: str | None)":
  location: generator.py
  annotations: |
    One entry of the final file report — a created file with its
    attribution.

    `path`: the created file path relative to the project root
    `tool`: the tool identity for a tool file; None for an engine file

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
  properties:
    "path -> str": |
      The created file path relative to the project root.
    "tool -> str | None": |
      The tool identity of the file; None for an engine file.

---

Author: Goga
CreatedAt: 14/09/26
Description: |
  Artifact generation of the onboarding session — the project config, the
  Dockerfile, the base conventions, the tool configs, and the final file
  report.
```

**Usage file — create:** `goga/onboarding/generator/.usages/artifact-generation.md`

```md
# Artifact generation — goga/onboarding/generator

## Domain

Writing the onboarding session artifacts from the committed answer space
and the committed tool contributions: `.goga/config.yml`, the Dockerfile,
the base conventions file, and the tool config files. Target audience: the
session orchestrator.

## Public API

    from goga.onboarding import FileGenerator

- `FileGenerator().generate(answers, contributions) -> list[CreatedFile]` —
  every artifact in generation order with attribution (`CreatedFile.tool`
  is None for engine files, the tool identity for tool files). An existing
  `.goga/config.yml` skips the config and Dockerfile generation — never
  rewritten, whoever created it first wins.
- `generate_goga_config(answers)` — the project config from the answer
  snapshot: field order language, image, dockerfile, build, pipeline,
  codemanifest, tools, usages; empty build/pipeline blocks omitted;
  annotations rendered as a literal block. An empty required `language` is
  a clean session error naming the field; the conventions download failure
  is a clean error with the URL and the cause.
- `generate_tool_configs(contributions)` — every buffered tool file
  serialized as YAML into `.goga/tools/<tool>/<file>`; the same file name
  written again replaces the file.

## Ready-to-use pattern

### Generate after the survey and the committed contributions

```python
from goga.onboarding import FileGenerator

files = FileGenerator().generate(answers, contributions)
for entry in files:
    if entry.tool is None:
        print(f"created {entry.path}")
    else:
        print(f"created {entry.path} (tool: {entry.tool})")
```

## Notes for the consumer

- Call `generate` once, after the tool contributions are committed — the
  snapshot is read at that moment.
- The return value is the single source of the final file report — render
  it with the tool attribution.
- The written config must pass the project config loader — the mapping
  above is normative.
```

### 8. `goga/onboarding` — CODEMANIFEST *(facade, modify)*

**Diff — full document replacement** (the facade becomes a domain facade; the old body is deleted).
Deleted elements of the old manifest: the `InitAnswers`, `GogaConfigAnswers`, `Questionnaire`,
`FileGenerator`, and `InitLogic` blocks; the `click`, `yaml`, `lang_conventions`, `image_defaults`,
and `agent_env_defaults` practices (they move into the survey/generator leaves); the import of
`resolve_project_name` from `goga/config` stays. The new document in full:

```yaml
Imports:
  - Types:
      - Question
      - QuestionGroup
      - SessionAnswers
    From: goga/onboarding/questions
  - Types:
      - Questionnaire
      - SessionPlan
      - core_questions
      - assemble_session_plan
      - apply_skips
    Usages:
      - survey-run
    From: goga/onboarding/survey
  - Types:
      - ToolParticipation
      - ToolDeclaration
      - ToolContribution
    Usages:
      - session-participation
    From: goga/onboarding/participation
  - Types:
      - FileGenerator
      - CreatedFile
    Usages:
      - artifact-generation
    From: goga/onboarding/generator
  - Types:
      - minor_version
      - host_goga_version
    Usages:
      - minor-line
    From: goga/version
  - Types:
      - resolve_project_name
    From: goga/config

Usages:
  convention: .goga/usages/conventions.md

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and testing in the project

  This cell is the facade of the onboarding domain: it owns the session
  orchestration and re-exports the public session API of the leaf cells —
  the question-and-answer model, the survey, the tool participation, and
  the artifact generation. Consumers address the domain through this
  facade only. Use relative imports.

---

"InitLogic(questionnaire: Questionnaire, generator: FileGenerator, participation: ToolParticipation)":
  location: logic.py
  annotations: |
    The orchestrator of one initialization session.

    `questionnaire`: the survey engine
    `generator`: the artifact generator
    `participation`: the tool participation mediator

    Apply the `convention` practice for the code style and intra-package
    imports.
    Use the `minor-line` practice for reading the installed version and
    deriving the image tag.
    Use the `session-participation` practice for the two tool moments.
    Use the `survey-run` practice for the plan assembly and the survey.
    Use the `artifact-generation` practice for the generation and the file
    report.
  methods:
    "run() -> exit_code: int": |
      Run the whole session.

      `exit_code`: 0 on success, nonzero on a session error

      Algorithm:
      1. An existing .goga/config.yml ends the session — no question is
         asked, no tool event is delivered, no artifact is written
      2. Read the installed goga version — `host_goga_version` — and derive
         its minor line — `minor_version` — for the image hints; an
         unreadable version is a clean session error without a traceback
      3. Deliver the declaration moment via `ToolParticipation` — it warns
         for every invited identity that is not among the installed tool
         packages
      4. Build the core tree — `core_questions`, with `image_tag` from
         step 2, the project name from `resolve_project_name`, and
         convention_exists read from the existence of
         .goga/usages/conventions.md; assemble the plan with the collected
         declarations; flatten every declaration's buffered skips into
         (tool identity, raw path) pairs and apply them via `apply_skips`
      5. Run the survey into the answer space via `Questionnaire`
      6. Deliver the amendment moment and commit the surviving tool
         contributions via `ToolParticipation`
      7. Generate the artifacts via `FileGenerator` and render the final
         file report with the attribution
      8. Return 0

      Requirements:
      - A tool failure never changes the exit code — the softness of the
        tool moments is theirs
      - A session error is one clean message — a broken package import, an
        unreadable version, an empty required field at generation — never
        a traceback

->Question: {}
->QuestionGroup: {}
->SessionAnswers: {}
->SessionPlan: {}
->Questionnaire: {}
->core_questions: {}
->assemble_session_plan: {}
->apply_skips: {}
->ToolParticipation: {}
->ToolDeclaration: {}
->ToolContribution: {}
->FileGenerator: {}
->CreatedFile: {}

---

Author: Goga
CreatedAt: 14/09/26
Description: |
  Facade of the onboarding domain — the initialization session
  orchestration and the public session API.
```

**Usage file — rewrite:** `goga/onboarding/.usages/onboarding-usage.md`

```md
# Project Onboarding — goga/onboarding

## Domain

Interactive initialization of a goga project: one session that surveys the
core configuration and the invited tool questions, applies the tool
amendments, and writes the project artifacts. Target audience: the init
command and embedding code.

## Facade

Import all types directly from `goga.onboarding`:

```python
from goga.onboarding import (
    CreatedFile, FileGenerator, InitLogic, Question, QuestionGroup,
    Questionnaire, SessionAnswers, SessionPlan, ToolParticipation,
    apply_skips, assemble_session_plan, core_questions,
)
```

## Usage

### Run a session with invited tools

```python
from goga.onboarding import FileGenerator, InitLogic, Questionnaire, ToolParticipation

logic = InitLogic(
    questionnaire=Questionnaire(),
    generator=FileGenerator(),
    participation=ToolParticipation(invited=["my-tool", "viewer"]),
)
exit_code = logic.run()
```

**Returns:** exit code (0 — success, nonzero — a session error).

**Session flow:** an existing `.goga/config.yml` ends the session
immediately — no questions, no tool events, no artifacts; otherwise the
session reads the installed version (clean error when unreadable),
collects the tool declarations, surveys the core tree and the tool blocks
with attribution, collects and commits the tool contributions, generates
`.goga/config.yml`, the Dockerfile, and the tool configs, and reports the
created files with tool attribution.

### Behavior guarantees

- A failing tool is soft: its contribution is discarded with a warning
  naming the tool and the reason; the session continues and returns 0.
- An invited but not installed tool name is a warning; the session
  continues.
- Session errors are single clean messages without a traceback: a broken
  package import (named), an unreadable installed version, an empty
  required `language` at generation (named).
- The image hints carry the minor tag of the installed goga version.

## Notes for the consumer

- Onboarding is filesystem-conditional: an existing `.goga/config.yml` is
  never rewritten — whoever created it first wins.
- Pass the deduplicated invited names in flag order to
  `ToolParticipation`; without invitations the session contains no tool
  blocks and matches the plain behavior.
```

### 9. `goga/commands/init` — CODEMANIFEST *(modify)*

**Diff — Imports:** add the type `ToolParticipation` to the existing import record from `goga/onboarding`:

```yaml
  - Types:
      - InitLogic
      - Questionnaire
      - FileGenerator
      - ToolParticipation
    Usages:
      - onboarding-usage
    From: goga/onboarding
```

**Diff — Body:** replace the `init` routine block in full with:

```yaml
"init(tpl: str | None, upgrade: bool, ref: str | None, tools: tuple[str, ...]) -> exit_code: int":
  location: init.py
  annotations: |
    CLI wrapper for the initialization command. Integrates two independent
    domains — onboarding and scaffold — and owns the mode routing,
    execution order, already-initialized guard, and the tool invitation
    flag. Delegates execution to `InitLogic` (onboarding) and `Scaffold`
    (scaffold).

    `tpl`: optional positional — git URL of a copier template, optionally with a ref fragment (url.git#ref)
    `upgrade`: when True, run template migration only (no onboarding)
    `ref`: explicit git ref overriding the URL fragment (`tpl`) or the migration target ref (`upgrade`)
    `tools`: the invited tool names from the repeated -t/--tool flag; an empty tuple when absent
    `exit_code`: 0 on success, nonzero on error, already-initialized, or invalid argument combination

    Use the `onboarding-usage` practice for the session API and the
    invitation semantics.
    Use the `scaffold-usage` practice for the Scaffold API.

    Algorithm:
    1. Validate `ref` placement: if `ref` is not None and `tpl` is None and not `upgrade` -> emit
       "--ref requires <tpl> or --upgrade" and return nonzero (ref is meaningful only with a template
       source — primary generation or migration target)
    2. Determine mode: if `upgrade` and `tpl` are both given -> emit "<tpl> and --upgrade are mutually
       exclusive (--upgrade updates existing state tied to a specific repository)" and return nonzero;
       otherwise `upgrade` -> UPGRADE; `tpl` is not None -> SCAFFOLD_THEN_ONBOARDING; otherwise
       BARE_ONBOARDING
    3. Validate the invitation flag: if `tools` is non-empty and the mode is UPGRADE -> emit a message
       stating that -t/--tool requires an onboarding session and --upgrade runs none; return nonzero
    4. Deduplicate `tools` preserving the flag order — one invitation per name, one block per tool
    5. Already-initialized guard: if BARE_ONBOARDING and the .goga/ directory exists -> emit
       "Project already initialized" and return nonzero (the guard does NOT fire when `tpl` is given)
    6. Dispatch:
       - UPGRADE: construct `Scaffold`; return Scaffold.upgrade(`ref`)
       - SCAFFOLD_THEN_ONBOARDING: construct `Scaffold`; sc = Scaffold.generate(`tpl`, `ref`); if sc
         nonzero return sc; otherwise construct `InitLogic`(`Questionnaire`, `FileGenerator`,
         `ToolParticipation`(`tools`)) and return its run()
       - BARE_ONBOARDING: construct `InitLogic`(`Questionnaire`, `FileGenerator`,
         `ToolParticipation`(`tools`)) and return its run()

    Requirements:
    - The invitation acts in both modes that run onboarding (bare and template-given); a repeated name
      deduplicates into one block
    - The command passes the names through as opaque data — installation checks and warnings belong
      to the onboarding domain
    - scaffold runs before onboarding when `tpl` is given (template may bring .goga/ artefacts that
      onboarding then skips)
    - the already-initialized marker is the .goga/ directory, not a specific file

    Constraints:
    - Do not combine --upgrade with <tpl> or with a non-empty `tools` — both combinations are rejected
      with a nonzero exit and a clear message
    - Do not run onboarding in UPGRADE mode
    - Do not fire the already-initialized guard when `tpl` is given
    - Do not accept a bare --ref (no <tpl>, no --upgrade)
    - The command delegates execution — it does not implement onboarding, invitation, or copier logic
      itself
```

The rest (Usages: `click`, `conventions`; the global Annotations; the footer) — verbatim.

**Usage file — update:** `goga/commands/init/.usages/init.md` — the syntax
`goga init [<tpl>] [-t <name>]... [--upgrade] [--ref <git-ref>]`; the `-t/--tool` option
(repeatable, dedup preserving the flag order, acts in the bare and `<tpl>` modes,
rejected with `--upgrade` with a nonzero exit); extend the mode rows, examples, and
exit codes accordingly; the material is aligned with `onboarding-usage` (the
invitation semantics belong to the onboarding domain).

## Dependency Map

```
goga/version ──(minor_version, host_goga_version)───────────────────────────▶ goga/onboarding (InitLogic)
goga/config  ──(resolve_project_name)────────────────────────────────────────▶ goga/onboarding (InitLogic)

goga/hooks/catalog  ──(declared_actions)──────────────────▶ goga/hooks (facade)
goga/hooks/registry ──(HookRegistry, ToolHooks)───────────▶ goga/hooks (facade)
goga/hooks/dispatch ──(emit_hook_event, wrap_context,
                       build_hook_arguments)──────────────▶ goga/hooks (facade)
goga/hooks/tools    ──(enumerate_tool_packages)───────────▶ goga/hooks (facade)

goga/hooks ──(wrap_context, build_hook_arguments, HookRegistry,
              enumerate_tool_packages)────────────────────▶ goga/onboarding/participation

goga/onboarding/questions ──(Question, QuestionGroup, SessionAnswers)──▶ survey, participation, generator, onboarding facade
goga/onboarding/participation ──(ToolDeclaration)──▶ survey
goga/onboarding/participation ──(ToolContribution)──▶ generator

goga/onboarding (facade) ──(re-export of the 13 types + InitLogic)──▶ questions, survey, participation, generator
goga/onboarding ──(InitLogic, Questionnaire, FileGenerator, ToolParticipation)──▶ goga/commands/init
goga/scaffold   ──(Scaffold)───────────────────────────────────────────▶ goga/commands/init (unchanged)
```

The dependency direction is fixed and one-way; the graph has no reverse edges or cycles.
Consumers of the domain capabilities address the facades (`goga/hooks`, `goga/onboarding`);
inside the domains, the leaves connect directly.

## Verification Checklist

After materializing each artifact:

- [ ] `goga lint` — 0 errors across all project cells (DSL syntax, reference closure, import rules).
- [ ] `goga schema` — the tree assembles; the new cells `goga/onboarding/{questions,survey,participation,generator}` are present; the `goga/onboarding` facade re-exports the 13 types + `InitLogic`; `goga/version` contains `minor_version`.
- [ ] `goga hooks` — the `onboarding/declare_session` and `onboarding/amend_config` records (soft) are visible.
- [ ] Cell `goga/onboarding/questions`: immutable question records; `SessionAnswers` — merge/last-wins/isolation per the tests in `tests/onboarding/questions/`.
- [ ] Cell `goga/onboarding/participation`: per-tool delivery (without `emit_hook_event` for the onboarding addresses), staged discarding of a failing tool's contribution, warnings (name/action/reason), fatal only on a broken import; tests in `tests/onboarding/participation/` (+ a `goga_tool_*` fixture package through the public surface).
- [ ] Cell `goga/onboarding/survey`: plan assembly (a duplicate id — element rejection), skips (subtree, order independence, no-op for an unknown path), block attribution; tests in `tests/onboarding/survey/`.
- [ ] Cell `goga/onboarding/generator`: config.yml passes `load_project_config`; the generator never rewrites an existing config.yml; an empty `language` — a clean error naming the field; tool configs in `.goga/tools/<tool>/`; the final list with attribution; tests in `tests/onboarding/generator/`.
- [ ] Facade `goga/onboarding`: `InitLogic.run` — the existing-config guard (no questions/events/artifacts), the `N.M` tag from the installed version, clean errors without a traceback; tests in `tests/onboarding/`.
- [ ] `goga/commands/init`: `-t` repeatable (deduplication), `-t`+`--upgrade` — a nonzero exit with a message; without `-t` — the existing behavior; tests in `tests/commands/test_init.py` per the `cli-commands` convention.
- [ ] The existing behavior/contracts/tests of the hooks, scaffold, and config platforms — unchanged (additivity).
- [ ] Author-contract documentation: `docs/features/init/hooks.md` (modeled on the domain
      hooks pages: action declaration, moment 1/2, the non-invited tool contract,
      answer isolation, staged failure resilience) + cross-references from
      `docs/features/tools/hooks.md`; the material matches `.usages/tool-contexts.md`.
- [ ] Final acceptance: S1–S14 from task.md (see [CELL_ASSEMBLY_REPORT]; all 14 are covered).
