# Architecture Plan — Hook Events for Codegraph and Drift

## Topic

**Hook Events for Codegraph and Drift** — six new hook actions on the existing hooks platform, two new hooks zones, catalog records, `tools` areas in outputs, docs, example package, tests.

Plan path: `.goga/history/2026/add-hooks-to-codecraph-and-drift/arch.md` (this file).

Approved through the prototype pipeline: primary analysis, type map, type detailing, cell distribution, contracts, cell assembly (per-cell approvals on record).

---

## Implementation Order

Cells ordered leaves → root; each cell's artifacts are complete only after its dependencies exist.

| # | Cell | Status | Rationale |
|---|---|---|---|
| 1 | `goga/hooks/catalog` | modify | Data-only cell; no new dependencies — the six action records must exist before the zones resolve their addresses |
| 2 | `goga/codegraph/facts` | modify | Leaf record cell; `CodegraphNode.tools` must exist before the gate view delivers the record |
| 3 | `goga/codegraph/hooks` | create | Leaf zone; imports only the platform facade and `goga/codegraph/facts` |
| 4 | `goga/drift/hooks` | create | Leaf zone; imports only the platform facade |
| 5 | `goga/codegraph` | modify | Domain routine; imports its zone (3) and facts (2) |
| 6 | `goga/drift` | modify | Domain routine; imports its zone (4) and existing producers |
| 7 | `goga/commands/codegraph` | modify | CLI wrapper; imports the domain (5), facts (2), and the zone's practice (3) |
| 8 | `goga/commands/drift` | modify | CLI wrapper; imports the domain (6) and the zone's practice (4) |

Facade usage files travel with their cells: `goga/codegraph/.usages/registering-hooks.md` and `codegraph-usage.md` update with cell 5's scope; `goga/drift/.usages/registering-hooks.md` and `drift-usage.md` with cell 6's scope.

---

## Artifacts

### 1. `goga/hooks/catalog/CODEMANIFEST` — modify

No header changes. Inside `declared_actions` Requirements, ADD six bullets (final text; placed with the other domain groups, before the Constraints section; existing records unchanged):

```yaml
    - The catalog carries the codegraph node-amendment action — the record
      domain="codegraph", name="amend_node", error_class="hard": the first
      failing hook of the action — a crashed hook or a structurally
      malformed contribution — stops the command with a clean error naming
      the tool, the action, and the failing node cell path
    - The catalog carries the codegraph validation-gate action — the
      record domain="codegraph", name="validate_graph",
      error_class="hard": a veto or a crashed hook of the action stops the
      codegraph command; the walk runs every subscribed tool's hooks to
      completion and collects one violation per tool
    - The catalog carries the drift run-start notification action — the
      record domain="drift", name="run_started", error_class="soft": a
      failing hook of the action is skipped with a warning and the run
      continues
    - The catalog carries the drift run-completion notification action —
      the record domain="drift", name="run_completed", error_class="soft":
      a failing hook of the action is skipped with a warning; the
      completion facts are already delivered
    - The catalog carries the drift report-amendment action — the record
      domain="drift", name="amend_report", error_class="hard": the first
      failing hook of the action — a crashed hook or a malformed
      adjustment (an entry not of the closed kind/cell/types shape) —
      stops the command with a clean error naming the hook, the tool, the
      action, and the reason
    - The catalog carries the drift entry-facts amendment action — the
      record domain="drift", name="amend_entry", error_class="hard": the
      first failing hook of the action — a crashed hook or a structurally
      malformed contribution — stops the command with a clean error naming
      the tool, the action, and the failing entry
```

### 2. `goga/codegraph/facts/CODEMANIFEST` — modify

REPLACE the `CodegraphNode` declaration with its final form (signature gains `tools` with an empty default; new property; extended requirements; all other properties unchanged):

```yaml
"CodegraphNode(cell: str, types: list[str], dependencies: dict[str, list[str]], children: list[CodegraphNode], tools: dict[str, dict[str, object]] = {})":
  location: facts.py
  annotations: |
    One node of the output tree — the code-derived analogue of a
    schema node.

    `cell`: cell path relative to the project root
    `types`: facade type names of the cell
    `dependencies`: target cell path to the imported facade types
    `children`: nested child nodes
    `tools`: the committed tools overlay of the node — empty when no
             tool contributed

    Requirements:
    - Immutable data class per `convention`
    - Manifest-only fields never appear on a node
    - The node fields are exactly cell, types, dependencies, children,
      plus tools; the output and the validation-gate view share this one
      record shape
    - `tools` is empty iff no tool wrote at least one fact on the node;
      the analysis never populates it — the amendment checkpoint alone
      places non-empty overlays
  properties:
    "cell -> str": |
      Cell path relative to the project root.
    "types -> list[str]": |
      Facade type names of the cell.
    "dependencies -> dict[str, list[str]]": |
      Target cell path to its imported facade types; no usages key.
    "children -> list[CodegraphNode]": |
      Nested child nodes.
    "tools -> dict[str, dict[str, object]]": |
      The committed tools overlay of the node; empty when no tool
      contributed.
```

All other declarations in the cell are unchanged.

### 3. `goga/codegraph/hooks/` — create

#### 3a. `goga/codegraph/hooks/CODEMANIFEST` (full)

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
      - CodegraphNode
    From: goga/codegraph/facts

Usages:
  convention: .goga/usages/conventions.md

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of
    development and testing in the project

  This cell owns the hooks zone of the codegraph domain: the node
  facts read view of the code-derived facts, the per-tool contribution
  model with its key-wise merge, and the checkpoint surface that
  delivers the node amendment and the tree validation gate over the
  platform facade. One registry per run carries every checkpoint of a
  command — the checkpoints never multiply the package enumeration.
  Every context is built from the operation data the caller passes —
  no repository, git, or file reads happen here. The zone does not
  import the codegraph domain — the read view is built from the facts
  the caller passes.

  The amendment action is hard: the first failing hook of the delivery
  walk — a crashed hook or a structurally malformed contribution —
  stops the command with a clean error naming the tool, the action,
  and the failing node cell path, and the tool's whole contribution
  is discarded. Tools are mutually blind — every delivered view reads
  the code-derived node facts only, never another tool's
  contribution; each tool's contributions commit as a unit, in
  enumeration order, per node. The contributions live in memory for
  the current run — no file is modified.

  The validation gate is the domain's hard observe-and-veto action
  with the walk-to-completion deviation: the per-tool walk runs every
  subscribed tool's validation hooks to completion — no early stop
  between tools — and collects one violation per tool; a vetoing or a
  crashed hook contributes exactly one violation of its tool. The
  delivered view is the final assembled tree — the committed tools
  overlay included, a recorded exception to the code-derived-facts-
  only delivery rule; a validator observes and vetoes, and the tree is
  never modified by a validator.

  Use the `per-tool-delivery` practice for the staged delivery loop of
  the amendment checkpoint — its loop skeleton, primitives, and
  tool-grouped commit apply as written.
  Use the `registering-hooks` practice for the hook signature and the
  failure handling behind both checkpoints.
  Use relative imports.

---

"NodeFacts(cell: str, types: list[str], dependencies: dict[str, list[str]], children: list[str])":
  location: facts.py
  annotations: |
    The code-derived facts of one node — the per-node read view
    delivered to a subscribed hook.

    `cell`: cell path relative to the project root
    `types`: facade type names of the cell
    `dependencies`: target cell path to its imported facade types
    `children`: the nested child cell paths of the node in the
                 complete code-derived tree, in tree order

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Pure facts — the constructing operation passes resolved values;
      nothing is read here
    - Code-derived projection only — identical in every run regardless
      of filters; never another tool's contributions, generated data,
      or the run's filter parameters
    - The filters prune delivery, never the facts — a delivered node
      carries the same facts in every run of the same code; the child
      list is the complete code-derived subtree of the node and may
      name cells pruned from the current run's output
  properties:
    "cell -> str": |
      Cell path relative to the project root.
    "types -> list[str]": |
      Facade type names of the cell.
    "dependencies -> dict[str, list[str]]": |
      Target cell path to its imported facade types.
    "children -> list[str]": |
      The nested child cell paths of the node in the complete
      code-derived tree, in tree order.

"Violation(tool: str, hook: str, reason: str)":
  location: facts.py
  annotations: |
    One collected veto of the validation walk.

    `tool`: the tool identity assigned by the platform
    `hook`: the hook name that vetoed or crashed
    `reason`: the veto reason — a hook-authored message or the crash
              reason; never a raw traceback

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
  properties:
    "tool -> str": |
      The tool identity of the vetoing tool.
    "hook -> str": |
      The hook name that vetoed or crashed.
    "reason -> str": |
      The veto reason — authored or crash-derived; never a raw
      traceback.

"GateVerdict(violations: list[Violation])":
  location: facts.py
  annotations: |
    The collected verdict of the validation walk — every veto of every
    subscribed tool, in enumeration order.

    `violations`: the collected violations; an empty list means
                  approved

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - The verdict is data only — acting on it (the merged error, the
      exit code) belongs to the operation
  properties:
    "violations -> list[Violation]": |
      The collected violations in enumeration order.
    "approved -> bool": |
      True when no violation was collected — the generation may
      proceed.

"NodeAmendment(node: NodeFacts)":
  location: amendments.py
  annotations: |
    The read-and-contribute view of one tool for one node — the
    delivered facts of the amendment checkpoint and the buffer of
    this tool's contributions.

    `node`: the code-derived facts of the node being amended —
             read-only and identical for every tool

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
    Use the `registering-hooks` practice for the hook signature that
    receives this view.

    Requirements:
    - One fresh view per tool, once per node — the container fields
      are rebuilt per view, so an in-place mutation stays local
    - The reads deliver the code-derived facts — a tool never sees
      another tool's contribution
    - The buffered contributions belong to this tool alone
  properties:
    "node -> NodeFacts": |
      The code-derived facts of the node; read-only for the receiving
      hook.
  methods:
    "contribute(facts: dict[str, object])": |
      Buffer one fact-mapping contribution of this tool.

      `facts`: the contribution mapping — fact names to
               JSON-representable values

      Requirements:
      - The call buffers into the buffer of this tool alone and
        changes nothing until the delivery commits it
      - The buffer merges key-wise — a later write replaces an
        earlier one on key conflict
      - An empty mapping contributes nothing

      Constraints:
      - Do not cancel, redirect, or defer the operation — a
        contribution extends the node's tools area only

"GraphValidation(tree: list[CodegraphNode])":
  location: contexts.py
  annotations: |
    The gate's delivered view of one tool — the read-only final tree
    plus the veto buffer of this tool alone.

    `tree`: the final assembled tree in tree order — the tools
            overlay included

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
    Use the `registering-hooks` practice for the hook signature that
    receives this view.

    Requirements:
    - One fresh view per tool, once per run
    - The reads deliver the final tree — read-only; a hook observes
      and cannot alter anything
    - The veto buffer belongs to this tool alone
  properties:
    "tree -> list[CodegraphNode]": |
      The final assembled tree, in tree order; read-only for the
      receiving hook.
  methods:
    "veto(reason: str)": |
      Buffer this tool's veto of the final tree.

      `reason`: the human-readable violation reason

      Requirements:
      - The call buffers into the buffer of this tool alone and
        changes nothing until the walk collects it
      - The replacement is whole — a later call replaces the earlier
        reason
      - The view records no hook identity — the walk attributes the
        veto to a hook by observing the buffer change around each
        call
      - An empty or whitespace-only reason is stored as given — the
        merged error renders it verbatim

      Constraints:
      - Do not cancel, redirect, or defer the operation — a veto stops
        the generation through the collected verdict only

"ToolContribution(tool: str, facts: dict[str, object])":
  location: overlay.py
  annotations: |
    The committed contribution of one tool for one node — the pairing
    of the tool identity with its merged fact mapping.

    `tool`: the tool identity assigned by the platform
    `facts`: the committed contribution of the tool

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Pure data — constructed by the checkpoint delivery alone
  properties:
    "tool -> str": |
      The tool identity assigned by the platform.
    "facts -> dict[str, object]": |
      The committed contribution of the tool.

"merge_node_contributions(contributions: list[ToolContribution]) -> tools: dict[str, dict[str, object]]":
  location: overlay.py
  annotations: |
    The deterministic tools-area composition — the tools mapping of
    one node from the committed contributions.

    `contributions`: the committed contributions in enumeration order
    `tools`: the tools area of the node — empty when nothing
             contributed

    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. Take the contributions in enumeration order
    2. Skip a contribution whose mapping is empty — a tool's key
       exists iff that tool wrote at least one fact
    3. Place each remaining mapping under its tool identity key
    4. Return the composed mapping — empty when every contribution
       was empty or none committed

    Requirements:
    - Deterministic — the same contributions give the same mapping
    - Pure — the inputs stay unmutated; the result is a new mapping
    - Structural validation is not here — it happened at the tool
      commit point of the delivery

    Constraints:
    - Do not read or write the filesystem
    - Do not mutate `contributions` or their maps

"CodegraphHooks()":
  location: events.py
  annotations: |
    The checkpoint surface of the codegraph domain — the node-amendment
    delivery and the tree validation gate over the platform facade.

    Apply the `convention` practice for the code style and
    intra-package imports.
    Use the `per-tool-delivery` practice for the staged delivery loop of
    the amendment checkpoint.
    Use the `registering-hooks` practice for the registration contract
    behind both checkpoints.

    Requirements:
    - Cheap construction — no enumeration and no imports happen at
      construction
    - One `HookRegistry` per run carries every checkpoint of a command
      — the assembly runs once per run whatever the number of
      checkpoints
    - Every context is built from the values the caller passes — no
      repository, git, or file reads happen at the checkpoint
  methods:
    "amend_node(node: NodeFacts) -> tools: dict[str, dict[str, object]]": |
      Deliver the node-amendment checkpoint for one node and return
      its tools area.

      `node`: the code-derived facts of the node being amended —
               operation data handed over by the calling walk
      `tools`: the tools area of the node — empty when nothing
               contributed

      Use the `per-tool-delivery` practice for the delivery loop.

      Algorithm:
      1. Resolve the address domain="codegraph", action="amend_node"
         against `declared_actions`
      2. Walk the subscriptions of the address per tool in enumeration
         order: build the tool's `NodeAmendment` view over the
         delivered facts — every tool reads the same code-derived
         `node` — wrap it via `wrap_context`, project the call
         arguments via `build_hook_arguments` with the tool's own
         context, and call each hook of the tool
      3. A tool whose every hook returned without raising passes the
         structural check of its merged buffer — a payload not
         representable in the JSON map (a non-mapping payload,
         non-string keys, non-serializable values, or an empty mapping
         at any nesting level) is the same hard failure as a crashed
         hook
      4. A passing tool commits as one `ToolContribution` — what
         commits is an owned copy of the validated buffer; an empty
         merged buffer commits nothing
      5. A hard failure stops the delivery at the first failure in the
         walk — a clean error naming the tool, the action, and the
         failing node cell path; the tool's contribution is discarded
      6. Compose the tools area of the committed contributions via
         `merge_node_contributions` and return it

      Requirements:
      - The commit granularity is the tool — a tool's whole
        contribution commits only after every hook of the tool
        succeeds and the merged buffer is structurally representable
      - An address without subscriptions returns an empty mapping —
        the delivery is unobservable, the caller's output stays
        byte-identical
      - With no tool packages installed the checkpoint returns an
        empty mapping

      Constraints:
      - Do not apply any contribution outside the single composition
        after the walk
      - Do not skip a subscriber of the address
      - Do not read repositories, git, or the filesystem at the
        checkpoint
      - Do not print — the caller owns all output
    "validate_graph(tree: list[CodegraphNode]) -> verdict: GateVerdict": |
      Deliver the validation gate over the final assembled tree and
      return the collected verdict.

      `tree`: the final assembled tree in tree order
      `verdict`: the collected verdict — approved when no tool vetoed

      Use the `per-tool-delivery` practice for the staged walk — with
      the recorded refinement: the walk runs to completion and
      collects vetoes; no early stop, no contribution commit.

      Algorithm:
      1. Resolve the address domain="codegraph", action="validate_graph"
         against `declared_actions`
      2. Walk the subscriptions of the address per tool in enumeration
         order: build the tool's `GraphValidation` view over the
         delivered tree, wrap it via `wrap_context`, project the call
         arguments via `build_hook_arguments` with the tool's own
         context, and call each hook of the tool; snapshot the view's
         veto buffer before each hook call — a buffer change during a
         call attributes the veto to that hook's subscription name
      3. A tool whose every hook returned without raising and whose
         view carries no buffered veto approves silently — no record
      4. A tool whose view carries a buffered veto contributes exactly
         one `Violation` — the tool, the attributed vetoing hook, the
         reason
      5. A tool with a raising hook contributes exactly one
         `Violation` with the crash reason as the reason — never a raw
         traceback — and the walk continues; a crash overrides the
         tool's buffered veto; the walk never stops between tools
      6. Return the `GateVerdict` with the violations in enumeration
         order

      Requirements:
      - Every subscribed tool's hooks run — no early stop; a
        non-vetoing subscriber is invoked even when another tool
        already vetoed
      - Exactly one `Violation` per tool
      - An address without subscriptions returns an approved verdict;
        with no tool packages installed the gate is inert
      - The gate modifies nothing — no mutation of the delivered tree

      Constraints:
      - Do not stop the walk at the first veto or crash — verdict
        collection requires every tool's outcome
      - Do not skip a subscriber of the address
      - Do not read repositories or the filesystem at the checkpoint
      - Do not print — the caller owns all output

---

Author: Goga
CreatedAt: 15/10/26
Description: |
  Owner of the codegraph domain hooks zone — the node facts read view,
  the per-tool contribution merge, and the checkpoint surface over the
  hooks platform.
```

#### 3b. `goga/codegraph/hooks/.usages/checkpoints.md` (full)

```markdown
# codegraph — amending nodes with tool facts

How the codegraph analysis uses the hooks zone of the codegraph domain:
delivering the node-amendment checkpoint at the assembly moment and the
tree validation gate over the final tree. For every entry path that
derives the code graph — the codegraph routine, the drift comparison's
producer calls, and the CLI command.

## The checkpoint surface

One `CodegraphHooks` object serves the checkpoints of a run — the surface
shares one registry per run, so a run that reaches both checkpoints
enumerates the tool packages once.

```python
from goga.codegraph.hooks import CodegraphHooks

hooks = CodegraphHooks()
```

## Amend each surviving node

Build the code-derived facts of each node surviving the filters, hand them
to the zone entry, and place the returned tools area on the node — the key
exists iff the mapping is non-empty. Deliver only the nodes surviving the
filters — filters prune delivery exactly as they prune output.

```python
from goga.codegraph.hooks import NodeFacts

# complete: cell path -> node of the unfiltered code-derived tree
for node in walk_in_tree_order(tree):
    full = complete[node.cell]
    facts = NodeFacts(
        cell=node.cell,
        types=node.types,
        dependencies=node.dependencies,
        children=[child.cell for child in full.children],
    )
    tools = hooks.amend_node(node=facts)
    if tools:
        node = node_with_tools(node, tools)  # never an empty object
```

- The delivered view is built from the values you pass — the checkpoint
  reads no repository, no git, no files; the facts are the code-derived
  facts of the node only.
- The delivered facts come from the complete code-derived tree — a
  node's child list is its full code-derived subtree and may name cells
  pruned from the current output; the filters decide which nodes are
  delivered, never the facts a delivered node carries.
- Tools are mutually blind: every hook reads the same code-derived facts,
  never another tool's contribution; each tool's contribution commits as a
  unit, in enumeration order, per node.
- The action is hard: the first failing hook — or a structurally malformed
  contribution (a non-mapping payload, non-string keys, non-serializable
  values, or an empty mapping at any nesting level) — stops the command
  with a clean error naming the tool, the action, and the failing node cell
  path. No partial tree is returned.
- A tool package whose facade fails to import stops the command the same
  way — the error names the package; convert it to the same clean error,
  never a raw traceback.
- An address without subscriptions returns an empty mapping — place no
  `tools` key; with no tool packages installed the output is byte-identical
  to the run without the extension.
- The source files are never modified — the contributions live in memory
  for the run; repeated runs with the same tools reproduce the output
  deterministically.

## Validate the final tree

Assemble the final tree — every surviving node with its committed tools
overlay — and deliver the gate before returning the tree.

```python
from goga.codegraph.hooks import CodegraphHooks

hooks = CodegraphHooks()
verdict = hooks.validate_graph(final_tree)
if not verdict.approved:
    raise merge_veto_error(verdict.violations)
```

- The walk runs to completion: every subscribed tool's hooks run, one
  violation per vetoing or crashing tool (tool, hook, reason).
- The delivered tree is the final result, tools overlay included; a
  validator observes and vetoes — never modifies.
- An empty tree fires nothing — return before any checkpoint.
- No subscriptions (or no tool packages installed) → approved; the output
  stays byte-identical.

## The output shape

Amended nodes carry one wrapper key: `tools -> {tool identity ->
{fact -> value}}`. The namespace key is the platform tool identity — the
canonical hyphen form of the package name without the `goga_tool_`
prefix; a tool never names itself. Base fields and extensions stay
structurally separated; empty objects never appear at any of the three
levels.
```

### 4. `goga/drift/hooks/` — create

#### 4a. `goga/drift/hooks/CODEMANIFEST` (full)

```yaml
Imports:
  - Types:
      - HookRegistry
      - wrap_context
      - build_hook_arguments
      - declared_actions
      - emit_hook_event
    Usages:
      - per-tool-delivery
      - registering-hooks
      - declaring-actions
    From: goga/hooks

Usages:
  convention: .goga/usages/conventions.md

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of
    development and testing in the project

  This cell owns the hooks zone of the drift domain: the fact
  vocabulary of the run's start and completion moments, the
  report-amendment view with its whole-list adjustment, the
  entry-facts amendment view with its contribution buffer, and the
  checkpoint surface that emits the moments and delivers the
  amendments over the platform facade. One registry per run carries
  every checkpoint of a command — the moments and the amendments never
  multiply the package enumeration. Every context is built from the
  values the caller passes — no configuration reads, no repository,
  git, or file reads happen here. The zone does not import the drift
  domain — the views are built from the facts the caller passes. No
  fact carries a credential-bearing value — failure and crash reasons
  use the same credential-free formulations the operations themselves
  log.

  The moments are soft: a failing hook is a warning in the log naming
  the tool, the action, and the reason; the delivery continues in
  enumeration order, and the moment never changes the report or the
  exit code. The completion moment fires on every terminal state of a
  started run — finished and crashed alike — carrying the last
  computed report stage and the terminal outcome.

  The report amendment is hard with list-control semantics: amending
  tools are mutually blind — every tool reads the same finished scoped
  report, never another tool's adjustment; the last adjusting tool in
  enumeration order wins; a tool that adjusts nothing leaves the
  report unchanged. Every entry of an adjustment must fit the closed
  report-entry shape — exactly kind, cell, types — and any other key
  or shape is the same hard failure as a crashed hook: never
  sanitized, never adopted. No adjustment provenance is recorded or
  returned anywhere.

  The entry-facts amendment is hard: the first failing hook of the
  delivery walk — a crashed hook or a structurally malformed
  contribution — stops the command with a clean error naming the tool,
  the action, and the failing entry, and the tool's whole
  contribution is discarded. Facts never affect the exit-deciding
  entry list; the contributions live in memory for the current run.

  Use the `per-tool-delivery` practice for the staged delivery loop of
  both amendment checkpoints — its loop skeleton, primitives, and
  tool-grouped commit apply as written.
  Use the `declaring-actions` practice for the emission contract of
  the two moments.
  Use the `registering-hooks` practice for the hook signature and the
  failure handling behind every checkpoint.
  Use relative imports.

---

"DriftFilters(cells: list[str], max_depth: int | None, depends_on: list[str])":
  location: facts.py
  annotations: |
    The start-moment facts — the filters the run was asked to apply.

    `cells`: cell paths requested to scope the report
    `max_depth`: requested nesting limit; None — no limit
    `depends_on`: requested dependency-scoping paths

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Pure facts — the values mirror the run's own inputs; nothing is
      read or derived here
    - Identical on every run with the same arguments
  properties:
    "cells -> list[str]": |
      Cell paths requested to scope the report.
    "max_depth -> int | None": |
      Requested nesting limit; None — no limit.
    "depends_on -> list[str]": |
      Requested dependency-scoping paths.

"EntryFacts(kind: str, cell: str, types: list[str] | None)":
  location: facts.py
  annotations: |
    The entry facts record — the delivered read view of one report
    entry.

    `kind`: the direction — schema_only or codegraph_only
    `cell`: the normalized cell path of the subject
    `types`: the sorted type names; None marks a cell-level entry

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Pure facts — the caller projects the values; nothing is read
      here
    - Tools-free — the record never carries contributions; the
      delivered views of both amendments read these facts only
    - `kind` is one of the comparison's entry kinds; the shape is
      exactly kind, cell, types
  properties:
    "kind -> str": |
      The direction — schema_only or codegraph_only.
    "cell -> str": |
      The normalized cell path of the subject.
    "types -> list[str] | None": |
      Sorted type names; None marks a cell-level entry.

"ReportEntry(kind: str, cell: str, types: list[str] | None, tools: dict[str, dict[str, object]])":
  location: facts.py
  annotations: |
    The completion-moment report entry — the projection of one entry
    of the carried report stage.

    `kind`: the direction — schema_only or codegraph_only
    `cell`: the normalized cell path of the subject
    `types`: the sorted type names; None marks a cell-level entry
    `tools`: the committed tools overlay of the entry — empty when no
             tool contributed

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Pure facts — the caller projects the values
    - On failure-carried stages the tools mapping is empty — no facts
      areas were computed
  properties:
    "kind -> str": |
      The direction — schema_only or codegraph_only.
    "cell -> str": |
      The normalized cell path of the subject.
    "types -> list[str] | None": |
      Sorted type names; None marks a cell-level entry.
    "tools -> dict[str, dict[str, object]]": |
      The committed tools overlay of the entry; empty when no tool
      contributed.

"RunOutcome()":
  location: facts.py
  annotations: |
    Fixed value set of a drift run's terminal outcome.

    Members:
    - finished — the run reached its natural terminal state; the final
      report was produced
    - crashed — the run failed before the final report was produced

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Members map to the outcome markers carried by the completion
      facts

    Constraints:
    - Fixed value set (implement as enum.Enum)
  properties:
    "finished -> str": |
      "finished" — the run reached its natural terminal state; the
      final report was produced.
    "crashed -> str": |
      "crashed" — the run failed before the final report was produced.

"RunCompletion(report: list[ReportEntry] | None, outcome: RunOutcome, reason: str)":
  location: facts.py
  annotations: |
    The completion-moment facts — the terminal state of one drift run.

    `report`: the last computed report stage — the final report with
              facts areas on finished runs, the scoped pre-amendment
              report when a later stage failed, None when the run
              failed before the report was computed
    `outcome`: the terminal outcome marker
    `reason`: a credential-free crash reason on crashed runs — no
              tokens, keys, passwords, or other secrets; paths and
              tool names permitted; empty on finished runs

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Pure facts — the caller projects the values
    - No fact carries a credential-bearing value
  properties:
    "report -> list[ReportEntry] | None": |
      The last computed report stage; None before the report was
      computed.
    "outcome -> RunOutcome": |
      The terminal outcome marker.
    "reason -> str": |
      Credential-free crash reason; empty on finished runs.

"ReportAmendment(report: list[EntryFacts])":
  location: amendments.py
  annotations: |
    The read-and-adjust view of one tool for the report — the
    delivered finished scoped report and the adjustment buffer of
    this tool alone.

    `report`: the finished scoped report — read-only and identical
              for every tool

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
    Use the `registering-hooks` practice for the hook signature that
    receives this view.

    Requirements:
    - One fresh view per tool, once per run
    - Amending tools are mutually blind — every tool reads the same
      finished scoped report, never another tool's adjustment
  properties:
    "report -> list[EntryFacts]": |
      The finished scoped report as computed by the comparison
      pipeline; read-only for the receiving hook.
  methods:
    "adjust(entries: list[dict[str, object]])": |
      Replace the report list whole for this run.

      `entries`: the adjusted report — each entry a mapping of exactly
                 the fields kind (one of the comparison's entry kinds),
                 cell (a non-empty string), and types (a list of
                 strings, or omitted for a cell-level entry)

      Requirements:
      - The call buffers the replacement into the buffer of this tool
        alone and changes nothing until the delivery validates and
        adopts it after the tool's hooks return
      - The replacement is whole — a later call replaces the earlier
        adjustment
      - The view records no hook identity — the delivery attributes
        the adjustment by observing the buffer change around each
        hook call
      - The adjusted list may be empty — clearing the report entirely
        is a valid adjustment

      Constraints:
      - Do not cancel, redirect, or defer the operation — an
        adjustment settles the final list only
      - Do not emit any provenance — no marker, annotation, or flag of
        the adjustment appears anywhere in the output

"EntryAmendment(entry: EntryFacts)":
  location: amendments.py
  annotations: |
    The read-and-contribute view of one tool for one entry — the
    delivered entry facts and the buffer of this tool's contributions.

    `entry`: the entry facts being enriched — read-only and identical
             for every tool

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
    Use the `registering-hooks` practice for the hook signature that
    receives this view.

    Requirements:
    - One fresh view per tool, once per entry — every surviving entry
      of the settled final list is delivered, comparison-produced and
      tool-added alike
    - The buffered contributions belong to this tool alone
  properties:
    "entry -> EntryFacts": |
      The entry facts; read-only for the receiving hook.
  methods:
    "contribute(facts: dict[str, object])": |
      Buffer one fact-mapping contribution of this tool.

      `facts`: the contribution mapping — fact names to
               JSON-representable values

      Requirements:
      - The call buffers into the buffer of this tool alone and
        changes nothing until the delivery commits it
      - The buffer merges key-wise — a later write replaces an
        earlier one on key conflict
      - An empty mapping contributes nothing

      Constraints:
      - Do not cancel, redirect, or defer the operation — a
        contribution extends the entry's tools area only

"ToolContribution(tool: str, facts: dict[str, object])":
  location: overlay.py
  annotations: |
    The committed contribution of one tool for one entry — the pairing
    of the tool identity with its merged fact mapping.

    `tool`: the tool identity assigned by the platform
    `facts`: the committed contribution of the tool

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Pure data — constructed by the checkpoint delivery alone
  properties:
    "tool -> str": |
      The tool identity assigned by the platform.
    "facts -> dict[str, object]": |
      The committed contribution of the tool.

"merge_entry_contributions(contributions: list[ToolContribution]) -> tools: dict[str, dict[str, object]]":
  location: overlay.py
  annotations: |
    The deterministic tools-area composition — the tools mapping of
    one entry from the committed contributions.

    `contributions`: the committed contributions in enumeration order
    `tools`: the tools area of the entry — empty when nothing
             contributed

    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. Take the contributions in enumeration order
    2. Skip a contribution whose mapping is empty — a tool's key
       exists iff that tool wrote at least one fact
    3. Place each remaining mapping under its tool identity key
    4. Return the composed mapping — empty when every contribution
       was empty or none committed

    Requirements:
    - Deterministic — the same contributions give the same mapping
    - Pure — the inputs stay unmutated; the result is a new mapping
    - Structural validation is not here — it happened at the tool
      commit point of the delivery

    Constraints:
    - Do not read or write the filesystem
    - Do not mutate `contributions` or their maps

"DriftHooks()":
  location: events.py
  annotations: |
    The checkpoint surface of the drift domain — the start and
    completion moments and the two amendments over the platform
    facade.

    Apply the `convention` practice for the code style and
    intra-package imports.
    Use the `per-tool-delivery` practice for the staged delivery loop of
    both amendment checkpoints.
    Use the `declaring-actions` practice for the emission contract of
    the two moments.
    Use the `registering-hooks` practice for the registration contract
    behind every checkpoint.

    Requirements:
    - Cheap construction — no enumeration and no imports happen at
      construction
    - One `HookRegistry` per run carries every checkpoint of a command
      — moments and amendments share it; the assembly runs once per
      run whatever the number of checkpoints
    - Every context is built from the values the caller passes — no
      configuration reads, no repository, git, or file reads happen
      at the checkpoint
    - No fact carries a credential-bearing value
  methods:
    "emit_run_started(filters: DriftFilters)": |
      Emit the run-start moment carrying the requested filters.

      `filters`: the requested filters, exactly as the run received
                 them

      Use the `declaring-actions` practice for the emission contract.

      Algorithm:
      1. Resolve the address domain="drift", action="run_started"
         against `declared_actions`
      2. Emit the moment via `emit_hook_event` — every subscribed hook
         receives its delivered view of the moment facts; the action is
         soft: a failing hook is a warning in the log naming the tool,
         the action, and the reason, and the delivery continues in
         enumeration order
      3. An address without subscriptions emits nothing

      Requirements:
      - The emission never affects the report or the exit code

      Constraints:
      - Do not print — the caller owns all output
      - Do not read the filesystem at the checkpoint
    "amend_report(report: list[EntryFacts]) -> report: list[EntryFacts]": |
      Deliver the report amendment over the finished scoped report and
      return the settled final list.

      `report`: the finished scoped report — the entries as computed
                by the comparison pipeline
      `report`: the settled final list

      Use the `per-tool-delivery` practice for the delivery loop.

      Algorithm:
      1. Resolve the address domain="drift", action="amend_report"
         against `declared_actions`
      2. Walk the subscriptions of the address per tool in enumeration
         order: build the tool's `ReportAmendment` view over the
         delivered finished scoped report — every tool reads the same
         list, never another tool's adjustment — wrap it via
         `wrap_context`, project the call arguments via
         `build_hook_arguments` with the tool's own context, and call
         each hook of the tool; snapshot the view's adjustment buffer
         before each hook call — a buffer change during a call
         attributes the adjustment to that hook's subscription name
      3. After the tool's hooks return, a tool that adjusted passes the
         closed-shape validation of its adjusted list: every entry is
         a mapping of exactly the fields kind (one of the
         comparison's entry kinds), cell (a non-empty string), and
         types (a list of strings, or omitted for a cell-level entry)
         — any other key or shape is the same hard failure as a
         crashed hook
      4. A validated adjustment replaces the current list whole — the
         last adjusting tool in enumeration order wins; a tool that
         adjusts nothing leaves the current list unchanged
      5. A hard failure — a raising hook or a malformed adjustment —
         stops the delivery at the first failure in the walk: a clean
         error naming the hook, the tool, the action, and the reason;
         nothing of the adjustment is adopted
      6. Return the settled list

      Requirements:
      - An address without subscriptions returns the input list
        unchanged — byte-identical behavior
      - With no tool packages installed the checkpoint returns the
        input list unchanged
      - No adjustment provenance is recorded or returned anywhere

      Constraints:
      - Do not skip a subscriber of the address
      - Do not validate or sanitize a malformed adjustment into shape
        — it is a hard failure
      - Do not read the filesystem at the checkpoint
      - Do not print — the caller owns all output
    "amend_entry(entry: EntryFacts) -> tools: dict[str, dict[str, object]]": |
      Deliver the entry-facts amendment for one entry and return its
      tools area.

      `entry`: the entry facts of one entry of the settled final list
      `tools`: the tools area of the entry — empty when nothing
               contributed

      Use the `per-tool-delivery` practice for the delivery loop.

      Algorithm:
      1. Resolve the address domain="drift", action="amend_entry"
         against `declared_actions`
      2. Walk the subscriptions of the address per tool in enumeration
         order: build the tool's `EntryAmendment` view over the
         delivered entry facts — every tool reads the same entry facts
         — wrap it via `wrap_context`, project the call arguments via
         `build_hook_arguments` with the tool's own context, and call
         each hook of the tool
      3. A tool whose every hook returned without raising passes the
         structural check of its merged buffer — a payload not
         representable in the JSON map (a non-mapping payload,
         non-string keys, non-serializable values, or an empty mapping
         at any nesting level) is the same hard failure as a crashed
         hook
      4. A passing tool commits as one `ToolContribution` — an owned
         copy of the validated buffer; an empty merged buffer commits
         nothing
      5. A hard failure stops the delivery at the first failure in the
         walk — a clean error naming the tool, the action, and the
         failing entry (its kind and cell path); the tool's
         contribution is discarded
      6. Compose the tools area of the committed contributions via
         `merge_entry_contributions` and return it

      Requirements:
      - The commit granularity is the tool
      - An address without subscriptions returns an empty mapping
      - With no tool packages installed the checkpoint returns an
        empty mapping

      Constraints:
      - Do not apply any contribution outside the single composition
        after the walk
      - Do not skip a subscriber of the address
      - Do not read the filesystem at the checkpoint
      - Do not print — the caller owns all output
    "emit_run_completed(completion: RunCompletion)": |
      Emit the run-completion moment carrying the terminal-state
      facts.

      `completion`: the terminal-state facts — the last computed
                    report stage, the outcome, the credential-free
                    reason

      Use the `declaring-actions` practice for the emission contract.

      Algorithm:
      1. Resolve the address domain="drift", action="run_completed"
         against `declared_actions`
      2. Emit the moment via `emit_hook_event` — every subscribed hook
         receives its delivered view of the completion facts; the
         action is soft: a failing hook is a warning in the log, the
         delivery continues
      3. An address without subscriptions emits nothing

      Requirements:
      - The emission never affects the report or the exit code
      - The completion fires on every terminal state of a started run
        — finished and crashed alike

---

Author: Goga
CreatedAt: 15/10/26
Description: |
  Owner of the drift domain hooks zone — the run moments, the report
  amendment, the entry-facts amendment, and the checkpoint surface over
  the hooks platform.
```

#### 4b. `goga/drift/hooks/.usages/checkpoints.md` (full)

```markdown
# drift — observing runs and amending the report

How the drift comparison uses the hooks zone of the drift domain:
emitting the run's start and completion moments, delivering the report
amendment over the finished scoped report, and the entry-facts amendment
over the settled final list. For the drift routine and the CLI command.

## The checkpoint surface

One `DriftHooks` object serves every checkpoint of a run — the surface
shares one registry per run, so a run that reaches the moments and the
amendments enumerates the tool packages once.

```python
from goga.drift.hooks import DriftHooks

hooks = DriftHooks()
```

## Emit the start moment

Emit the moment at the beginning of the run, before the first view is
produced, with the requested filters exactly as received.

```python
from goga.drift.hooks import DriftFilters

hooks.emit_run_started(DriftFilters(cells=cells, max_depth=max_depth, depends_on=depends_on))
```

- The action is soft: a failing observer hook is a warning in the log; the
  run continues unchanged.

## Amend the report

After the comparison and scoping settle the scoped report, project the
entries to `EntryFacts` and hand them to the zone entry — the settled
final list returns; it decides what the caller prints and how the run is
graded.

```python
from goga.drift.hooks import EntryFacts

scoped = [EntryFacts(kind=e.kind, cell=e.cell, types=e.types) for e in scoped_entries]
final_facts = hooks.amend_report(scoped)
```

- Amending tools are mutually blind — every tool reads the same finished
  scoped report; the last adjusting tool in enumeration order wins; a tool
  that adjusts nothing leaves the list unchanged.
- An adjustment replaces the list whole and may clear it entirely or add
  entries to an otherwise clean report; every entry must fit the closed
  shape — exactly the fields kind (schema_only or codegraph_only), cell (a
  non-empty string), and types (a list of strings, or omitted for a
  cell-level entry).
- The action is hard: a raising hook or a malformed adjustment (any other
  key or shape) stops the command with a clean error naming the hook, the
  tool, the action, and the reason — the adjustment is never sanitized
  into shape and never adopted.
- An address without subscriptions returns the input list unchanged — the
  output stays byte-identical.

## Amend the facts of each entry

Once the final list is settled, every surviving entry — comparison-
produced and tool-added alike — is delivered as entry facts; place the
returned tools area on the entry iff non-empty. An empty final list fires
nothing.

```python
for facts in final_facts:
    tools = hooks.amend_entry(facts)
    if tools:
        entry = entry_with_tools(facts, tools)  # never an empty object
```

- Tools are mutually blind; contributions merge per the platform rules
  (key-wise later-wins within a tool, JSON-map shape enforced, empty
  commits nothing, the tools key appears iff at least one tool wrote at
  least one fact).
- The action is hard: a raising hook or a structurally malformed
  contribution stops the command with a clean error naming the tool, the
  action, and the failing entry.
- Facts never affect the exit-deciding entry list.

## Emit the completion moment

Emit the moment on every terminal state of the started run — finished,
producer-failed, and amendment-failed alike — with the last computed
report stage, the terminal outcome, and a credential-free reason on
crashed runs.

```python
from goga.drift.hooks import ReportEntry, RunCompletion, RunOutcome

# finished run — the final report with facts areas
hooks.emit_run_completed(RunCompletion(
    report=[ReportEntry(kind=e.kind, cell=e.cell, types=e.types, tools=e.tools) for e in final_report],
    outcome=RunOutcome.finished,
    reason="",
))

# crashed run — wrap the pipeline and re-raise
try:
    ...  # the run's own work
except Exception as reason:
    hooks.emit_run_completed(RunCompletion(
        report=last_computed_stage,          # final / scoped pre-amendment / None
        outcome=RunOutcome.crashed,
        reason=credential_free(str(reason)), # no tokens, keys, passwords; paths and tool names permitted
    ))
    raise
```

- The carried report stage: the final report (list settled, facts areas
  included) on finished runs; the scoped pre-amendment report when a
  later stage failed; nothing when the run failed before the report was
  computed.
- The action is soft: a failing observer hook is a warning; the moment
  never masks the propagated failure — re-raise after the emission.

## The output shape

Amended entries carry one wrapper key: `tools -> {tool identity ->
{fact -> value}}` — the established goga contribution idiom; it appears
iff at least one tool contributes. No adjustment provenance appears
anywhere — no markers, annotations, or flags signaling that an entry was
removed, added, or adjusted.
```

### 5. `goga/codegraph/CODEMANIFEST` — modify

**ADD to Imports:**

```yaml
  - Types:
      - CodegraphHooks
      - NodeFacts
      - GateVerdict
    Usages:
      - checkpoints
    From: goga/codegraph/hooks
```

**ADD to global Annotations:**

```
The caller uses the `checkpoints` practice to deliver the
node-amendment checkpoint of the assembly walk, place the contributed
facts on the surviving nodes, and deliver the validation gate over the
final assembled tree.
```

**REPLACE the `codegraph` routine declaration with its final form:**

```yaml
"codegraph(cells: list[str], max_depth: int | None = None, depends_on: list[str] = []) -> tree: list[CodegraphNode]":
  location: codegraph.py
  annotations: |
    Derive the prospective cell graph of the project code, amend the
    surviving nodes with tool facts, validate the final tree, and
    return it as an object tree.

    `cells`: cell paths to include in the output
    `max_depth`: maximum nesting depth of the tree; None — no limit
    `depends_on`: keep only cells whose dependencies reach the given paths
    `tree`: the assembled tree of `CodegraphNode` records; an empty
            project yields an empty list

    Use the `checkpoints` practice for the checkpoint delivery of the
    assembly walk.

    Algorithm:
    1. Load the project configuration via `project-configuration` with
       `load_project_config` — an absent configuration is the
       uninitialized-project error; read the language of `ProjectConfig`
    2. Reject a language outside python, golang, javascript, kotlin,
       swift with a clear error
    3. Take the exclusion list from the lint section — an absent
       `LintConfig` means no exclusions
    4. Discover the source files with `discover_sources`
    5. Run the analysis stages in order via the `stages` practice —
       `collect_facts`, `derive_units`, `resolve_links`
    6. Assemble the output tree with `render_graph`; when filters are
       active, assemble the complete tree the same way — the facts
       projection of the amendment checkpoint reads it
    7. An empty tree returns an empty list before any checkpoint — an
       empty graph fires nothing
    8. For every node surviving the filters, in tree order: build the
       node's `NodeFacts` from the matching node of the complete
       code-derived tree and deliver them via the `CodegraphHooks`
       entry, its amend_node checkpoint; place the returned tools area
       on the node iff the mapping is non-empty
    9. Build the final tree — every surviving node with its committed
       tools overlay — and deliver the validation gate over the
       `CodegraphHooks` entry, its validate_graph checkpoint; a
       not-approved `GateVerdict` raises one merged error listing every
       violation (the tool, the hook, the reason) — no tree is returned
    10. Return the assembled tree

    Requirements:
    - Deterministic and idempotent — identical code and configuration
      produce identical trees
    - Read-only — no file is created or modified
    - The checkpoints fire wherever the routine runs — in this command
      and inside every producer call of a drift run
    - Filters prune delivery exactly as they prune output — a node is
      delivered iff its node appears in the output tree
    - The delivered view carries code-derived facts only — never
      another tool's contributions, generated data, or the run's filter
      parameters; the facts of a delivered node are identical in every
      run of the same code — the filters decide which nodes are
      delivered, never what facts a delivered node carries
    - The gate view carries the final result, the tools overlay
      included — the recorded exception
    - Delivery is node-major and deterministic — nodes in tree order,
      tools in enumeration order within each node; repeated runs over
      the same code with the same installed tools produce identical
      trees
    - A hard failure of the amendment checkpoint — a crashed hook or a
      structurally malformed contribution — and a vetoed gate
      propagate out of the routine as errors naming the tool, the
      action, and the failing node cell path (the merged veto error
      lists every violation); no partial tree is returned
    - A node's tools area is empty iff no tool wrote at least one fact
      on that node; with no subscriptions — or no tool packages
      installed — every tools area of the tree is empty and the output
      is byte-identical to the run without the extension

    Constraints:
    - Do not modify the filesystem — the contributions live in memory
      for the run
    - Do not read environment variables
    - Do not execute project code
```

**REPLACE the first bullet of `render_graph` Requirements with:**

```
- Node fields are exactly cell, types, dependencies, children — plus
  the empty `tools` overlay default; render never populates tools —
  the amendment checkpoint alone places non-empty overlays
```

(`render_graph` signature, algorithm, and all other requirements unchanged; `discover_sources` unchanged.)

#### 5b. `goga/codegraph/.usages/registering-hooks.md` — create (full)

```markdown
# codegraph — registering hooks

How a `goga_tool_*` package subscribes its hooks to the codegraph domain
actions. For tool package authors; no goga code changes are needed.

The domain opens two hard actions — the node amendment, a
read-and-contribute view over the code-derived facts of one node, and the
validation gate, an observe-and-veto pass over the final assembled tree.

## The events

| Address | Error class | Fires |
|---|---|---|
| `codegraph / amend_node` | hard | At the assembly moment of every entry path that derives the code graph (`goga codegraph`, the codegraph routine, and every codegraph producer call inside a drift run). One delivery per node surviving the filters — nodes in tree order, tools in enumeration order within each node. |
| `codegraph / validate_graph` | hard | Once over the final assembled tree of every entry path that derives the code graph — after assembly, filters, and the tools overlay, before serialization. The walk runs to completion; one violation per vetoing or crashing tool. |

An empty graph fires nothing.

## Subscribe

```python
def register_hooks(hooks):
    hooks.subscribe("codegraph", "amend_node", "coverage", cover_node)
```

- `domain` — always `"codegraph"`; `action` — from the table; `name` —
  unique per tool per address; `hook` — the callable executed when the
  event fires.
- A hook receives values only for the parameters it declares by the fixed
  offered names: `context`, `self`.

## The amendment view

`amend_node` delivers a `NodeAmendment` view per tool, once per node.
The reads: `node` — the code-derived facts of the node being built
(read-only; attribute assignment is blocked): `cell` (the cell path),
`types` (the facade type names), `dependencies` (target cell path to its
imported facade types), and `children` (the nested child cell paths of
the complete code-derived tree beneath the node — identical in every run
of the same code). The view never carries another tool's contributions or
the run's filter parameters.

```python
def cover_node(context):
    if is_interesting(context.node.cell):
        context.contribute(
            {
                "coverage": measure_coverage(context.node.cell),
                "owner": owning_team(context.node.types),
            }
        )
```

- `contribute(facts)` buffers one mapping of facts for this node — fact
  names to JSON-representable values; a later contribution of your tool
  on the same node merges key-wise, a later write replacing an earlier
  one on key conflict.
- Your facts land on the node under your tool identity inside the `tools`
  wrapper area: `tools -> {<tool> -> {<fact>: <value>}}`. The identity is
  assigned by goga from the package name — a tool never names itself.

## The validation view

`validate_graph` delivers a `GraphValidation` view per tool: the
read-only final tree (`context.tree` — recursive `CodegraphNode` with
`cell`, `types`, `dependencies`, `children`, `tools`, the overlay
included) and `veto(reason)`.

```python
def validate_tree(context):
    for node in context.tree:
        if broken(node):
            context.veto(f"{node.cell}: broken shape")
            return
```

- Veto or crash = exactly one violation of your tool (tool, hook,
  reason); every subscribed tool runs — no early stop.
- On any violation: nothing on stdout, one merged error, the command
  stops before any output — exit 1 for `goga codegraph`; inside a drift
  run the drift command exits 2. Observe and veto only — the tree is
  never modified.
- With no subscriptions the output is byte-for-byte unchanged.

## The merge rules

- One JSON mapping per tool per node; multiple hooks of your tool merge
  key-wise in registration order, later writes replacing earlier ones on
  key conflict.
- Tools never collide — each namespace lives under its own identity key.
- Empty objects never appear: the `tools` key exists on a node iff at
  least one tool wrote at least one fact there; your key exists iff you
  wrote at least one fact. An empty `contribute` contributes nothing.
- Tools are mutually blind — every hook reads the same code-derived
  facts; each tool's contribution commits as a unit, in enumeration
  order, per node.

## Failure treatment

Both actions are hard. For the amendment, the first failing hook in the
delivery walk stops the command with a clean error naming the tool, the
action, and the failing node cell path — no partial output is printed. A
structurally malformed contribution — a non-mapping payload, non-string
keys, non-JSON-serializable values, or an empty mapping at any nesting
level — fails the same way. A tool package whose facade fails to import
stops the command the same way, the error naming the package.

## The run output

With no subscriptions — or no tool packages installed — `goga codegraph`
output is byte-identical to the run without the extension: no `tools` key
appears anywhere. The four base fields of every node are exactly what
they would be without the extension. Repeated runs with the same tools
reproduce the output deterministically; stdout stays data-clean JSON.

## Integration scenarios

- **Per-node fact attachment** — subscribe to `amend_node`; attach
  coverage, ownership, or any JSON facts to each node you measure through
  `context.contribute`.
- **Whole-tree policy veto** — subscribe to `validate_graph`; walk
  `context.tree` and `veto(reason)` on violation — every veto merges into
  one clean error that stops the run before any output.
- **Drift symmetry** — the same subscriptions fire inside every codegraph
  producer call of a drift run: one subscription, both entry paths.
```

#### 5c. `goga/codegraph/.usages/codegraph-usage.md` — update

- Node format table: ADD row `| tools | The committed per-tool facts overlay — {tool identity -> {fact -> value}}; present iff at least one tool contributed |`; adjust the intro sentence to name the conditional tools area as the tool-contribution surface.
- Guarantees: ADD the hook-extension guarantee (the run delivers the codegraph checkpoints of installed tool packages; both hard — a failing or vetoing hook stops the run as a clean error before any output; the same checkpoints fire inside every codegraph producer call of a drift run; with no subscriptions the output is byte-identical).
- Failure behavior: ADD "hard failures of the codegraph hooks checkpoints — a crashed or malformed-contribution amendment hook, or a vetoed validation gate (the merged error lists every violation)".

### 6. `goga/drift/CODEMANIFEST` — modify

**ADD to Imports:**

```yaml
  - Types:
      - DriftHooks
      - DriftFilters
      - EntryFacts
      - ReportEntry
      - RunCompletion
    Usages:
      - checkpoints
    From: goga/drift/hooks
```

**ADD to global Annotations:**

```
The caller uses the `checkpoints` practice to wrap the comparison
pipeline with the run's start and completion moments, deliver the report
amendment over the finished scoped report, and deliver the entry-facts
amendment over the settled final list.
```

**REPLACE the `DriftEntry` declaration with its final form:**

```yaml
"DriftEntry(kind: str, cell: str, types: list[str] | None, tools: dict[str, dict[str, object]] = {})":
  location: compare.py
  annotations: |
    One flat entry of the drift report.

    `kind`: the direction of the discrepancy — schema_only when the
            subject exists only in the declared view, codegraph_only
            when it exists only in the code-derived view
    `cell`: the normalized cell path of the discrepancy subject
    `types`: the sorted type names of the cell missing from the other
             view; None marks a cell-level discrepancy
    `tools`: the committed tools overlay of the entry — empty when no
             tool contributed

    Apply the `convention` practice for the data-model rules.

    Requirements:
    - Immutable data class per `convention`
    - The `tools` field carries the committed per-tool facts overlay;
      it is empty iff no tool wrote at least one fact on the entry
    - The comparison never populates `tools` — it stays empty until
      the entry-facts amendment places a non-empty overlay
  properties:
    "kind -> str": |
      The direction of the discrepancy — schema_only or codegraph_only.
    "cell -> str": |
      The normalized cell path of the discrepancy subject.
    "types -> list[str] | None": |
      Sorted type names missing from the other view; None marks a
      cell-level discrepancy.
    "tools -> dict[str, dict[str, object]]": |
      The committed tools overlay of the entry; empty when no tool
      contributed.
```

**REPLACE the `drift` routine declaration with its final form:**

```yaml
"drift(cells: list[str], max_depth: int | None = None, depends_on: list[str] = []) -> report: list[DriftEntry]":
  location: drift.py
  annotations: |
    Produce the drift report of the project — the structural
    discrepancies between the declared contracts and the actual code,
    observed and adjusted by the installed tool packages.

    `cells`: cell paths to scope the report
    `max_depth`: maximum nesting depth to scope the report; None —
                 no limit
    `depends_on`: scope the report to cells depending on the given
                  paths
    `report`: the final post-amendment discrepancy entries in the
              stable order; an empty list when the final report is
              empty

    Use the `checkpoints` practice for the moments and the amendments
    of the run.

    Algorithm:
    1. Emit the start moment via the `DriftHooks` entry — its
       emit_run_started checkpoint — with `DriftFilters` mirroring the
       requested filters
    2. Wrap every following stage: produce the complete views — call
       `schema` and `codegraph` with no filters; produce the filtered
       views — call `schema` and `codegraph` with `cells`, `max_depth`,
       `depends_on`
    3. Compare the complete views with `compare_views`; scope the
       entries with `scope_entries` over the filtered views — the
       scoped report is computed
    4. Deliver the report amendment: project the scoped entries to
       `EntryFacts` and hand them to the `DriftHooks` entry, its
       amend_report checkpoint — the settled final list returns
    5. Deliver the entry-facts amendment: for every entry of the
       settled list — comparison-produced and tool-added alike —
       project it to `EntryFacts`, deliver via the amend_entry
       checkpoint, and place the returned tools area on the entry iff
       non-empty; an empty settled list fires nothing
    6. Emit the completion moment via the emit_run_completed checkpoint
       with the final report projected to `ReportEntry` records, the
       finished outcome, an empty reason; return the final report —
       the `DriftEntry` records with their tools overlays

    Failure paths inside the wrap:
    - A producer or comparison failure (steps 2-3): emit the completion
      moment with no report stage, the crashed outcome, and a
      credential-free reason derived from the propagated error;
      re-raise — the moment never masks the failure
    - A hard failure of the report amendment (step 4): emit the
      completion moment with the scoped pre-amendment report, the
      crashed outcome, a credential-free reason; re-raise
    - A hard failure of the entry-facts amendment (step 5): emit the
      completion moment with the scoped pre-amendment report, the
      crashed outcome, a credential-free reason; re-raise
    - A failing moment hook is soft — a warning in the log; it never
      changes the report or the exit code

    Requirements:
    - Run ordering is fixed: start moment → view production,
      comparison, scoping → report amendment → entry facts amendment →
      completion moment
    - The completion moment fires on every terminal state of a started
      run — finished, producer-failed, and amendment-failed alike —
      carrying the last computed report stage: the final report (list
      settled, facts areas included) on finished runs, the scoped
      pre-amendment report when a later stage failed, nothing when the
      run failed before the report was computed
    - The comparison always runs on the complete views; the filters
      scope the report only
    - The depends_on asymmetry — declared dependencies in the declared
      view, resolved imports in the code-derived view — never surfaces
      as fabricated cell-level entries
    - The amendments operate solely on the finished scoped report and
      never feed back into the views or the comparison
    - The returned report is the settled post-amendment list — a
      tool-added or tool-removed entry changes what the caller sees
      and how the caller grades the run
    - No adjustment provenance appears anywhere in the returned report
    - Facts areas never carry failure semantics — a raising or
      malformed amendment hook fails the run rather than altering
      entries
    - Deterministic and idempotent — identical project state,
      configuration, and installed tools produce identical reports
    - Read-only — no file is created or modified
    - Every error of a view producer propagates unchanged — the
      comparison adds no failures of its own
    - With no subscriptions — or no tool packages installed — the
      report, its entries, and the byte-level output are identical to
      the run without the extension; the moments are unobservable

    Constraints:
    - Do not read manifests or sources — the views arrive fully
      assembled from `schema` and `codegraph`
    - Do not apply filters inside the comparison
    - Do not emit provenance markers — the `tools` areas are the
      contribution idiom, not provenance
```

(`compare_views` and `scope_entries` unchanged.)

#### 6b. `goga/drift/.usages/registering-hooks.md` — create (full)

```markdown
# drift — registering hooks

How a `goga_tool_*` package subscribes its hooks to the drift domain
actions. For tool package authors; no goga code changes are needed.

The domain opens four actions — the soft start and completion moments
around every drift run, the hard report amendment over the finished
scoped report, and the hard per-entry facts amendment over the settled
final list.

## The events

| Address | Error class | Fires |
|---|---|---|
| `drift / run_started` | soft | At the beginning of every drift run, before the first view is produced, carrying the requested filters (cells, max_depth, depends_on). |
| `drift / amend_report` | hard | After the comparison and scoping settle the scoped report. One delivery per tool over the same finished scoped report; the last adjusting tool in enumeration order wins. |
| `drift / amend_entry` | hard | After the report amendment settles the final list — one delivery per surviving entry per tool, comparison-produced and tool-added alike. An empty final list fires nothing. |
| `drift / run_completed` | soft | On every terminal state of a started run — finished and crashed alike — carrying the last computed report stage (the final report with facts areas on finished runs, the scoped pre-amendment report when a later stage failed, nothing when the run failed before the report was computed), the finished/crashed outcome, and a credential-free reason on crashed runs. |

Run ordering: start moment → view production, comparison, scoping →
report amendment → entry facts amendment → completion moment.

## Subscribe

```python
def register_hooks(hooks):
    hooks.subscribe("drift", "amend_report", "baseline", suppress_known)
```

- `domain` — always `"drift"`; `action` — from the table; `name` —
  unique per tool per address; `hook` — the callable executed when the
  event fires.
- A hook receives values only for the parameters it declares by the fixed
  offered names: `context`, `self`.

## The moment views

`run_started` delivers the requested filters: `context.filters` —
`cells` (the requested cell paths), `max_depth` (the requested limit;
`None` — no limit), `depends_on` (the requested dependency-scoping
paths), exactly as the run received them.

`run_completed` delivers the terminal facts: `context.completion` —
`report` (the last computed report stage — entries with their `tools`
areas on finished runs), `outcome` (`finished` or `crashed`), and
`reason` (a credential-free crash reason on crashed runs; empty on
finished runs).

```python
def track_run(context):
    notify(f"drift {context.completion.outcome}: {len(context.completion.report or [])} entries")
```

- The actions are soft: a failing observer hook is a warning in the log;
  the report and the exit code never change.

## The report view

`amend_report` delivers a `ReportAmendment` view per tool. The reads:
`report` — the finished scoped report as computed by the comparison
pipeline (read-only; one entry record per discrepancy with `kind`,
`cell`, `types`). Every amending tool reads the same list — no tool sees
another tool's adjustment.

`adjust(entries)` replaces the list whole: remove entries down to clearing
the report entirely, add entries down to surfacing discrepancies in an
otherwise clean report. Every entry of your adjustment must be a mapping
of exactly the fields kind (`schema_only` or `codegraph_only`), cell (a
non-empty string), and types (a list of strings, or omitted for a
cell-level entry) — any other key or shape is a hard failure.

```python
def suppress_known(context):
    kept = [e for e in context.report if not is_accepted(e.cell, e.kind)]
    kept += accepted_discoveries()  # mappings of kind/cell/types
    context.adjust(kept)
```

- The last adjusting tool in enumeration order wins; calling `adjust`
  nothing leaves the report unchanged.
- The final list decides the command's grading: an emptied report prints
  `[]` and exits 0; added entries print and exit 1.

## The entry view

`amend_entry` delivers an `EntryAmendment` view per tool, once per
surviving entry. The reads: `entry` — the entry facts (`kind`, `cell`,
`types`; read-only). `contribute(facts)` buffers one mapping of facts for
this entry — merged per the platform rules; the facts land on the entry
under your tool identity inside the `tools` wrapper area.

```python
def annotate_entry(context):
    context.contribute({"ticket": ticket_for(context.entry.cell)})
```

- Facts never affect the exit code and never signal provenance — the
  `tools` areas are the established contribution idiom.

## Failure treatment

The amendments are hard. A raising hook, a malformed adjustment (an entry
outside the closed kind/cell/types shape), or a structurally malformed
contribution stops the command with a clean error naming the hook, the
tool, the action, and the reason — exit 2, nothing on stdout. The moments
are soft — a failing observer is a warning. A tool package whose facade
fails to import stops the command the same way, the error naming the
package.

## The run output

With no subscriptions — or no tool packages installed — the report, its
entries, and the exit codes are byte-identical to the run without the
extension: no `tools` key appears anywhere and the moments are
unobservable. No adjustment provenance appears anywhere — no markers,
annotations, or flags signaling that an entry was removed, added, or
adjusted. Repeated runs with the same project state and tools reproduce
the output deterministically.

## Integration scenarios

- **Baseline suppression** — subscribe to `amend_report`; remove the
  entries your team accepted and keep the rest — the gate stops failing
  on known drift.
- **Tool-detected discrepancies** — add entries your tool discovered
  outside the comparison — the gate starts failing on them.
- **Entry enrichment** — subscribe to `amend_entry`; attach tickets,
  owners, or any JSON facts to the surviving entries.
- **Run observability** — subscribe to the moments; build drift tracking
  and notification workflows on `run_started` / `run_completed` payloads.
```

#### 6c. `goga/drift/.usages/drift-usage.md` — update

- Report entries: ADD the `tools` area description (per-tool facts overlay, present iff a tool contributed, never affects the exit code, never signals provenance) and the post-amendment list statement (the final printed list is the post-amendment list).
- Guarantees: ADD the hook-extension guarantee (the run wraps the pipeline with the soft moments and delivers the hard report amendment plus the hard entry-facts amendment; the grading list is the final post-amendment list; with no subscriptions the output is byte-identical).
- Failure behavior: ADD "hard failures of the drift hooks checkpoints — a crashed or malformed amendment hook (the error names the hook, the tool, the action, and the reason), and an in-run codegraph veto or hard codegraph checkpoint failure — exit 2".

### 7. `goga/commands/codegraph/CODEMANIFEST` — modify

**ADD to Imports:**

```yaml
  - Usages:
      - checkpoints
    From: goga/codegraph/hooks
  - Usages:
      - registering-hooks
    From: goga/codegraph
```

**ADD to global Annotations:**

```
The caller uses the `checkpoints` practice for the hard-failure handling
of the codegraph generation — every checkpoint failure surfaces as a
clean command failure.
The caller uses the `registering-hooks` practice for the tool-package
hook subscription surface of the codegraph domain actions behind the
checkpoints of the generation.
```

**REPLACE the `codegraph` routine declaration with its final form:**

```yaml
"codegraph(cells: list[str], max_depth: int | None = None, depends_on: list[str] = [])":
  location: codegraph.py
  annotations: |
    CLI wrapper for the codegraph command. Delegates business logic
    to `codegraph_logic` and serializes the returned object tree.

    `cells`: cell paths to filter the output
    `max_depth`: maximum nesting depth of the tree
    `depends_on`: filter cells by dependency relationship

    Use the `click` practice to declare the command surface — the
    CELLS variadic argument and the --max-depth and repeatable
    --depends-on options, identical to the schema command.
    Use the `checkpoints` practice for the failure handling of the
    generation checkpoints.

    Algorithm:
    1. Invoke `codegraph_logic`(`cells`, `max_depth`, `depends_on`)
    2. On any error — an uninitialized project, an unsupported
       configured language, an unparseable source file, a hard failure
       of the node-amendment checkpoint (a crashed hook or a
       structurally malformed contribution; the error names the tool,
       the action, and the failing node cell path), a vetoed
       validation gate of the final tree (the merged error lists every
       violation — the tool, the hook, the reason), or a
       register-facade import failure (the error names the package) —
       write the error message to stderr and exit 1; nothing is
       printed to stdout and no raw traceback is shown
    3. Serialize the returned `CodegraphNode` tree via the
       `beautiful_json` practice — the record fields map one-to-one
       to the output node keys — cell, types, dependencies, children
       — plus the tools key, written only when the node's overlay is
       non-empty; never an empty object at any level — and output it
       via `click`.echo

    Requirements:
    - stdout carries the JSON document only — every diagnostic goes
      to stderr
    - Exit 0 only on a complete generation; a veto or any hard
      checkpoint failure is the command's ordinary error path —
      exit 1, nothing on stdout
    - With no subscriptions — or no tool packages installed — no
      `tools` key appears anywhere and the output is byte-identical
      to the run without the extension
    - The command help documents the JSON structure per root cell —
      the fields cell, types, dependencies, children, plus the
      conditional tools key — and the failure semantics of the two
      checkpoints, mirroring the schema command help
```

### 8. `goga/commands/drift/CODEMANIFEST` — modify

**ADD to Imports:**

```yaml
  - Usages:
      - checkpoints
    From: goga/drift/hooks
  - Usages:
      - registering-hooks
    From: goga/drift
```

**ADD to global Annotations:**

```
The caller uses the `checkpoints` practice for the failure handling of
the run's moments and amendments — every hard checkpoint failure surfaces
as a clean command failure, and soft moment failures surface as stderr
warnings only.
The caller uses the `registering-hooks` practice for the tool-package
hook subscription surface of the drift domain actions behind the
checkpoints of the run.
```

**REPLACE the `drift` routine declaration with its final form:**

```yaml
"drift(cells: list[str], max_depth: int | None = None, depends_on: list[str] = [])":
  location: drift.py
  annotations: |
    CLI wrapper for the drift command. Delegates business logic to
    `drift_logic` and prints the flat JSON report.

    `cells`: cell paths to scope the report
    `max_depth`: maximum nesting depth to scope the report
    `depends_on`: scope the report to cells depending on the given paths

    Use the `click` practice to declare the command surface — the
    CELLS variadic argument and the --max-depth and repeatable
    --depends-on options, identical to the schema and codegraph
    commands.
    Use the `checkpoints` practice for the failure handling of the
    run's checkpoints.

    Algorithm:
    1. Invoke `drift_logic`(`cells`, `max_depth`, `depends_on`)
    2. On any error from `drift_logic` — an uninitialized project, an
       unsupported configured language, an unparseable source file,
       manifest loading and validation failures, hard failures of the
       schema hooks checkpoints, hard failures of the drift report
       amendment or the entry-facts amendment (the error names the
       hook, the tool, the action, and the reason), an in-run
       codegraph veto or hard codegraph checkpoint failure, or a
       register-facade import failure — write the error message to
       stderr and exit 2; nothing is printed to stdout and no raw
       traceback is shown
    3. Serialize the returned `DriftEntry` report via the
       `beautiful_json` practice — each entry maps to the keys kind
       and cell plus types for type-level entries only, plus the
       tools key written only when the entry's overlay is non-empty;
       never an empty object at any level — and output it via
       `click`.echo
    4. Exit 0 when the final report is empty (an empty JSON list is
       printed), 1 when it carries entries — decided by the final
       post-amendment entry list alone; facts areas never affect the
       grading

    Requirements:
    - stdout carries the JSON report only — every diagnostic goes to
      stderr; soft moment failures surface as stderr warnings only
    - Exit 0 — comparison completed, no entries in the final report;
      an empty JSON list is printed
    - Exit 1 — comparison completed, entries in the final report; the
      full report is printed
    - Exit 2 — the comparison could not be performed; the exit-2
      deviation from the family exit-1 failure convention is
      deliberate and permanent — the three-outcome contract reserves
      exit 1 for discrepancies found
    - The grading list is the final post-amendment list — a cleared
      report grades 0, a tool-added entry grades 1
    - No adjustment provenance appears anywhere in the output
    - With no subscriptions — or no tool packages installed — the
      output and the exit codes are byte-identical to the run without
      the extension
    - The command help documents the arguments, the options, the JSON
      report structure (including the conditional tools key), and the
      completion statuses — mirroring the schema and codegraph
      command helps
```

---

## Dependency Map

Imports flow consumer → provider; each layer imports only lower layers.

```
Layer 4:  goga/commands/codegraph        goga/commands/drift
            │        │        │             │        │
            ▼        │        ▼             ▼        ▼
Layer 3:  goga/codegraph ◄───┐        ┌──► goga/drift
            │  ▲            │        │     │  ▲
            ▼  └────────────┼────────┼─────┘  │
            │ (the routine ─┼────────┘ (the routine imports
            │  imports its own zone)   its own zone)
            ▼               ▼
Layer 2:  goga/codegraph/hooks        goga/drift/hooks
            │        │                   │
            ▼        │                   ▼
Layer 1:  goga/codegraph/facts      goga/hooks (the platform)
         (goga/drift also imports goga/schema{,/hooks}, goga/codegraph,
          goga/codegraph/facts — existing edges)
```

Edge list (consumer ──imports──> provider):

- `goga/codegraph/hooks` ──> `goga/hooks` (HookRegistry, wrap_context, build_hook_arguments, declared_actions; Usages: per-tool-delivery, registering-hooks)
- `goga/codegraph/hooks` ──> `goga/codegraph/facts` (CodegraphNode)
- `goga/drift/hooks` ──> `goga/hooks` (the same plus emit_hook_event; Usages: per-tool-delivery, registering-hooks, declaring-actions)
- `goga/codegraph` ──> `goga/codegraph/hooks` (CodegraphHooks, NodeFacts, GateVerdict; Usages: checkpoints)
- `goga/codegraph` ──> `goga/codegraph/facts`, `goga/codegraph/analysis`, `goga/config` (existing)
- `goga/drift` ──> `goga/drift/hooks` (DriftHooks, DriftFilters, EntryFacts, ReportEntry, RunCompletion; Usages: checkpoints)
- `goga/drift` ──> `goga/schema{,/hooks}`, `goga/codegraph`, `goga/codegraph/facts` (existing)
- `goga/commands/codegraph` ──> `goga/codegraph` (logic + Usages: registering-hooks), `goga/codegraph/facts`, `goga/codegraph/hooks` (Usages: checkpoints)
- `goga/commands/drift` ──> `goga/drift` (logic + Usages: registering-hooks), `goga/drift/hooks` (Usages: checkpoints)

No cycles: the zones never import their parent domains or each other; the platform imports nobody above it.

---

## Verification Checklist

After implementing each artifact, verify:

- [ ] **Catalog** — `goga lint` passes; `declared_actions()` returns exactly the 34 records (28 existing + 6 new), ordered by domain then name; no existing record text changed; the catalog test's frozen list extended with the six records.
- [ ] **CodegraphNode** — `goga lint` passes; the record constructs with and without `tools`; frozen kw_only semantics preserved; existing construction sites unchanged.
- [ ] **Both zones** — `goga lint` passes on the new cells; facade importable (`python -c "from goga.codegraph.hooks import CodegraphHooks"` / `from goga.drift.hooks import DriftHooks`); each zone's `__all__` exposes the full contract API; no import of the parent domain or the other zone; one registry per surface per run (unit-pinned).
- [ ] **Zone unit tests** — mirror the source layout (`tests/codegraph/hooks/`, `tests/drift/hooks/`): fresh-view delivery, mutual blindness, key-wise merge, empty-commit, structural-validation failure paths, veto attribution and crash override, walk-to-completion, adjust whole-replacement + closed-shape validation + last-adjusting-wins, credential-free reason passthrough.
- [ ] **codegraph routine** — checkpoints fire for every surviving node in tree order; empty tree fires nothing; the delivered facts are filter-independent (the same node carries the same facts in complete and filtered runs); veto raises one merged error; hard failure names tool/action/cell path; no subscriptions → byte-identical tree (golden test).
- [ ] **drift routine** — fixed run ordering; completion fires on every terminal state with the correct report stage (final / scoped pre-amendment / None); re-raise after crash emission; no subscriptions → byte-identical report and entries (golden test).
- [ ] **CLI commands** — `goga codegraph`: veto/hard failure → stderr + exit 1 + clean stdout; `tools` key iff non-empty. `goga drift`: cleared report → `[]` + exit 0; added entries → printed + exit 1; hard amendment failures → exit 2; in-run codegraph veto → exit 2; help documents the conditional `tools` key and the failure semantics (help test).
- [ ] **Integration invariant** — with no tool packages installed, `goga codegraph` and `goga drift` outputs and exit codes are byte-identical to pre-change goldens.
- [ ] **Usage files** — the four new files exist with the approved content; the two updated files carry the approved additions; every practice imported by a CODEMANIFEST is referenced in at least one annotation of that CODEMANIFEST.
- [ ] **Docs and example (out-of-plan artifacts, see below)** — updated in the same change-set per the atomic change-set rule.

---

## Out-of-plan artifacts (tracked for the downstream stages; not cells)

These artifacts belong to the same change-set (atomic convergent change-set rule) and are listed here so no stage loses them:

| Artifact | Action | Requirement source |
|---|---|---|
| `docs/features/codegraph/hooks.md` | rewrite per the schema hooks-page pattern | task docs scope; template `docs/features/schema/hooks.md` |
| `docs/features/drift/hooks.md` | rewrite per the same pattern | task docs scope |
| `docs/features/codegraph/api.md`, `docs/features/codegraph/cli.md` | update — checkpoint flow, `tools` output key, failure semantics | task docs scope |
| `docs/features/drift/api.md`, `docs/features/drift/cli.md` | update — the same | task docs scope |
| `docs/features/hooks/hooks.md`, `docs/features/hooks/index.md` | update — the six addresses in the registration contract and the catalog overview | task docs scope |
| `example/goga-tool-events/goga_tool_events/__init__.py` | extend `_ADDRESSES` (28 → 34) and `_READS` (`codegraph/amend_node`: node; `codegraph/validate_graph`: tree; `drift/run_started`: filters; `drift/amend_report`: report; `drift/amend_entry`: entry; `drift/run_completed`: completion) + docstring count | task example scope |
| `tests/hooks/catalog/test_catalog.py` | update the frozen record list (+6) | catalog verification |
| `tests/codegraph/test_codegraph.py`, `tests/drift/test_drift.py` | extend — routine integrations | routine verification |
| `tests/commands/codegraph/`, `tests/commands/drift/` | extend — CLI semantics incl. byte-identical invariants | CLI verification |
