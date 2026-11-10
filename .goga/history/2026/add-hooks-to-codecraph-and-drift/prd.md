# Hook Events for Codegraph and Drift

## Problem

The goga hooks platform lets installed tool packages (`goga_tool_*`) extend and observe goga domains. Today that power is unevenly distributed: the declared view (`goga schema`) exposes two levers — a per-cell amendment (tools attach JSON facts to view nodes) and a whole-tree validation gate (tools veto an invalid tree) — while the code-derived view (`goga codegraph`) and the drift report (`goga drift`) expose no hook actions at all and are documented as extension-free.

This creates two equal parts of one problem:

1. **View asymmetry.** A tool-package author can attach facts to, and enforce policy over, the declared view, but has no lever on the code-derived view. Tools that reason about the project's actual code — rather than its authored contracts — cannot carry their facts into goga's outputs or enforce policy over the code-derived tree.
2. **Tool-blind drift gating.** A team gating on `goga drift` in CI gets an exit code that reflects only the raw comparison of the two views. Accepted (baseline) drift cannot be suppressed, tool-known discrepancies cannot be added, and the report cannot be adjusted by any tool — so the drift gate is unusable in real projects or must be rebuilt outside goga, if it can exist at all.

## Users

- **Tool-package author** (primary). Builds `goga_tool_*` packages that subscribe to hook actions through the existing registration contract. Wants one uniform extension model over both views and the drift report. Enters the flow by subscribing in `register_hooks`; experiences the problem as missing subscription addresses and missing influence over the drift outcome.
- **CI gate maintainer** (primary, equal). Runs `goga drift` as a merge/commit gate. Wants the gate's report and exit code to reflect tool-adjusted reality: known drift suppressed, tool-detected discrepancies surfaced. Does not write hooks; installs a tool package that does.
- **Report and view readers** (secondary). Humans and downstream automation consuming the JSON output of `goga codegraph` and `goga drift` (CI logs, review tooling). Need the output to remain a well-formed, deterministic, interpretable document.

## Goals

1. **View symmetry.** Tool-package authors can attach their facts to the code-derived view and enforce policy over it, uniformly with the declared view — removing the extension asymmetry between the two views of one project.
2. **Tool-adjustable drift gate.** Teams gating on `goga drift` get a report and exit code that reflect tool-adjusted reality — accepted drift suppressed, tool-known discrepancies added — while the adjusted output remains a well-formed drift report.
3. **Drift observability.** Tool packages can observe drift runs and their outcomes within the platform, so drift tracking and notification workflows are built on goga rather than around it.

## User Experience

### A. Extending the code-derived view (codegraph)

**Entry.** A tool-package author subscribes to the codegraph domain actions in `register_hooks`, exactly as they already do for schema.

**Primary flow.** During `goga codegraph` (and inside every codegraph producer call that `goga drift` makes), for each node surviving the filters, the tool's hook receives the node's code-derived facts — cell path, types, resolved dependencies, children — as a read-only view, one fresh view per tool. The hook contributes JSON facts; the facts land on the node under the tool's identity inside the `tools` area of the JSON output. Tools are mutually blind; contributions merge per the established schema rules (key-wise, later-wins within a tool; empty commits nothing; the `tools` key appears iff at least one tool wrote at least one fact).

**Validation.** After assembly and filters, before serialization, a validator hook receives the final tree — committed tools overlay included — and may veto. Vetoes (and crashes, recorded as vetoes with the crash reason) merge into one clean error naming tool, hook, and reason; the command stops before any output. An empty graph fires nothing.

**What the reader sees.** `goga codegraph` output gains per-node `tools` areas only when tools contribute. With no subscriptions the output is byte-identical to today.

### B. Observing drift runs (moments)

**Entry.** A tool subscribes to the drift start and completion moments.

**Primary flow.** The start moment fires at the beginning of every `goga drift` run carrying the requested filters (cells, max_depth, depends_on). The completion moment fires on every terminal state of the run, failed ones included, carrying the last computed report stage — the final report on finished runs, the scoped pre-amendment report when a later stage failed, nothing when the run failed before the report was computed — and the run outcome: a terminal finished/crashed marker plus, on crashed runs, a credential-free reason (no tokens, keys, passwords, or other secrets; paths and tool names are permitted). Moments are soft: a failing observer hook is a warning in the log; it never changes the report or the exit code.

### C. Adjusting and enriching the drift report (amendments)

**Entry.** A tool subscribes to the drift report amendment.

**Primary flow.** After the complete views are compared and the filters applied, each amending tool receives the finished scoped report as a read-only view and produces an adjusted report: it may remove entries (down to clearing the report entirely) and add entries (down to surfacing discrepancies in an otherwise clean report). The command prints the final report as clean JSON on stdout and exits by it: empty report → exit 0, non-empty → exit 1. Entries a tool adds carry exactly the report-entry fields — kind, cell, types.

**Multi-tool rule.** Amending tools are mutually blind — every amending tool reads the same finished scoped report; no tool sees another tool's adjustments. The last adjusting tool in enumeration order wins: the final report is the last tool that actually adjusted; tools that adjust nothing leave the current report unchanged.

**Facts.** Once the final list is settled, every surviving entry — comparison-produced and tool-added alike — is delivered to each subscribed tool as a fresh read-only view of the entry facts (kind, cell, types). The tool contributes JSON facts; they land on the entry under the tool's platform-assigned identity inside the `tools` area of the JSON output. Tools are mutually blind; contributions merge per the established schema rules (key-wise, later-wins within a tool; empty commits nothing; the `tools` key appears iff at least one tool wrote at least one fact). Facts never affect the exit code, and an empty final list fires nothing.

**Silence.** No adjustment provenance appears anywhere in the output — no markers, no annotations, no flags signaling that an entry was removed, added, or adjusted. The `tools` facts areas are the established goga contribution idiom (as in `goga schema` and `goga codegraph` output) and appear iff tools contribute facts; with no subscriptions the output is byte-identical to today.

**Failure.** A raising amendment hook or a malformed adjustment (an entry that is not a well-formed report entry — exactly the fields kind, cell, types, no others) is a hard failure: the command stops with a clean error naming the hook, the tool, the action, and the reason — exit code 2, nothing on stdout, the raw report not printed. A raising or malformed-contribution entry-facts hook fails the same way, with the failing entry named.

### Consequences and recovery

Installing an adjusting tool changes what the drift gate enforces; uninstalling it restores the raw report and exit codes. Repeated runs with the same project state, configuration, and tools reproduce identical output deterministically.

## Requirements

### Codegraph domain

1. The codegraph domain must expose a per-node amendment action through which each subscribed tool receives the surviving node's code-derived facts (cell path, types, resolved dependencies, children) as a fresh read-only view and contributes JSON facts that land on the node under the tool's identity in the `tools` area of the output.
2. The codegraph domain must expose a whole-tree validation action: each subscribed tool receives the final assembled tree (committed tools overlay included) as a fresh read-only view and may veto; the gate is observe-and-veto only and never modifies the tree.
3. Both codegraph actions are hard. A raising or malformed-contribution hook stops the command with a clean error naming the hook, the tool, the action, and the failing node; a crashing validator counts as its tool's veto; all vetoes merge into one clean error; nothing is printed on stdout.
4. Contribution merging must follow the established schema rules: per-tool buffers merged key-wise with later-wins on conflict, JSON-map shape enforced, empty merged buffers commit nothing.
5. An empty codegraph (no surviving nodes) fires no codegraph action.
6. Codegraph checkpoints fire wherever the codegraph routine runs, including inside drift runs' producer calls — symmetric to the schema checkpoints today.

### Drift domain

7. The drift domain must expose a soft start moment firing at the beginning of every drift run, carrying the requested filters (cells, max_depth, depends_on).
8. The drift domain must expose a soft completion moment firing on every terminal state of the run, failed ones included, carrying the last computed report stage — the final report (list settled, facts areas included) on finished runs, the scoped pre-amendment report when a later stage failed, nothing when the run failed before the report was computed — and the run outcome: a terminal finished/crashed marker plus a credential-free crash reason on failed runs (no tokens, keys, passwords, or other secrets; paths and tool names are permitted).
9. The drift domain must expose a hard report amendment action delivered after the scoped report is computed: each amending tool receives the finished scoped report as a read-only view and produces an adjusted report by removing and/or adding entries; every entry of an adjusted report must be well-formed — exactly the fields kind (one of the comparison's entry kinds), cell (a non-empty string), and types (a list of strings, or omitted for a cell-level entry); any other key or shape is malformed.
10. Multi-tool amendment semantics: amending tools are mutually blind — each reads the same finished scoped report; the last adjusting tool in enumeration order wins; a tool that adjusts nothing leaves the report unchanged.
11. The drift domain must expose a hard per-entry facts amendment action delivered after the report amendment settles the final list: every surviving entry — comparison-produced and tool-added alike — is delivered to each subscribed tool as a fresh read-only view of the entry facts (kind, cell, types); the tool contributes JSON facts that land on the entry under the tool's platform-assigned identity inside the `tools` area, merged per the established schema rules (key-wise later-wins within a tool, JSON-map shape enforced, empty commits nothing, `tools` appears iff at least one tool wrote at least one fact); facts never affect the exit code; an empty final list fires nothing.
12. Moment failures are soft: a failing moment hook is logged as a warning and never affects the report or the exit code.
13. Amendment failures are hard: a raising hook, a malformed adjusted report, or a malformed entry-facts contribution stops the command with a clean error naming the hook, the tool, the action, and the reason — exit code 2, nothing on stdout.
14. Ordering within a drift run: start moment → view production, comparison, scoping → report amendment → entry facts amendment → completion moment.

### Command behavior

15. `goga drift` exit codes keep their meanings — 0: completed, no entries in the final report; 1: completed, entries in the final report; 2: the run could not be performed — with 0 vs 1 decided by the final (post-amendment) entry list; facts areas never affect it.
16. `goga codegraph` and `goga drift` stdout stays clean JSON only; every diagnostic goes to stderr; no adjustment provenance appears anywhere in the output — the `tools` facts areas are the established contribution idiom and appear iff tools contribute.
17. With no tool packages installed or subscribed, `goga codegraph` and `goga drift` output and exit codes must be byte-identical to the behavior before this change.
18. Runs with identical project state, configuration, and installed tools produce identical outputs.

### Platform and documentation

19. Every new action must be declared in the single action catalog — `codegraph.amend_node`, `codegraph.validate_graph`, `drift.run_started`, `drift.amend_report`, `drift.amend_entry`, `drift.run_completed` — and subscribable through the existing registration contract — no new registration or extension mechanism.
20. The codegraph and drift hooks documentation must describe the new actions per the established per-feature hooks documentation pattern, complete for a tool author who has not read the goga source; the example observer package that subscribes to every catalog action must cover the new actions.

## Constraints

- The existing hooks platform is the only delivery mechanism: per-tool fresh views, mutual blindness, hard/soft error classes, enumeration-order delivery, and one registry per run. The new surfaces must not introduce a parallel mechanism.
- The action catalog is the single source of known subscription addresses; new addresses extend it.
- Codegraph and drift runs stay read-only: no file is created or modified by the runs themselves; tool contributions and adjustments live only in returned output.
- The drift comparison stays pure: entries are facts of the complete views, filters scope only, and both amendment actions operate solely on the finished scoped report — they never feed back into the views or the comparison.
- Codegraph analysis boundaries stay fixed: supported languages, no environment reads, no project code execution.
- Each domain owns its hooks surface (its hooks zone); the platform and other domains do not own it.
- The exit-code contract of both commands is stable in meaning; only which report decides 0 vs 1 changes.
- Determinism and idempotence of both commands must hold with tools present, including the last-wins amendment under a deterministic tool enumeration order.

## Scope

### In Scope

- The codegraph hooks surface: per-node amendment action and whole-tree validation action, both hard.
- The drift hooks surface: soft start and completion moments, the hard report amendment action, and the hard per-entry facts amendment action.
- New catalog entries for all six actions.
- The user-visible surfaces: the `tools` area in `goga codegraph` output, the `tools` areas on `goga drift` report entries, drift exit codes decided by the final report.
- Documentation: the codegraph and drift hooks pages rewritten per the established pattern; catalog-level documentation updated.
- The example observer tool package extended to the new actions.

### Out of Scope

- Any change to the hooks platform core (registry, dispatch, catalog mechanics, delivery semantics, error-class model).
- Any change to the drift comparison semantics (entry kinds, complete-view comparison, scoping rules) — the amendment is a post-comparison step only.
- A veto gate for drift (explicitly rejected).
- Adjustment provenance for the drift report — markers, annotations, or flags signaling that an entry was removed, added, or adjusted (explicitly rejected; the `tools` facts areas are contribution, not provenance, and stay in scope).
- Changes to the schema, contract, config, usages, build, pipeline, topics, or onboarding zones.
- New CLI commands, flags, or output formats beyond the `tools` area following the schema precedent.
- Baseline persistence or management tooling — baselining is a tool-package concern built on the new actions, not part of goga.
- Changes to codegraph language analysis (stages, supported languages).

## Success Criteria

1. A subscribed tool can attach JSON facts to `goga codegraph` output nodes under its tool identity, and the same subscription fires inside drift runs — the extension model is symmetric with `goga schema`.
2. A subscribed tool can veto the final codegraph tree; the veto stops `goga codegraph` with a clean error naming tool, hook, and reason, exit 1, nothing on stdout.
3. A subscribed tool receives the drift start moment (filters) and completion moment (last computed report stage, outcome) on every drift run — including failed runs (crashed marker with a credential-free reason); a failing observer changes neither report nor exit code.
4. A subscribed tool can clear a non-empty drift report → stdout prints `[]`, exit 0; and can add entries to a clean report → the entries print, exit 1.
5. With two adjusting tools, the final report is the last adjusting tool's output in enumeration order.
6. A subscribed tool can attach JSON facts to entries of the final drift report under its tool identity; the facts print inside the entry's `tools` area merged per the established rules, on comparison-produced and tool-added entries alike; the exit code still follows the entry list alone.
7. A raising or malformed drift-amendment or entry-facts hook yields exit 2, a clean error naming hook, tool, action, and reason, and nothing on stdout.
8. With no tools installed or subscribed, `goga codegraph` and `goga drift` outputs and exit codes are byte-identical to before the change.
9. All new actions are declared in the single catalog, subscribable through the existing registration contract, documented in the per-feature hooks pages, and covered by the example observer package.
