# Drift — Hooks

How a `goga_tool_*` package observes drift runs, adjusts the report, and annotates its entries. For tool-package authors; no goga code changes are needed. The platform mechanism behind every hook action is covered in [Hooks](../hooks/index.md); the registration contract for tool authors in [Hooks — The registration contract](../hooks/hooks.md).

The drift domain opens four actions of its own — the soft start and completion moments around every drift run, the hard report amendment over the finished scoped report, and the hard per-entry facts amendment over the settled final list. The declared view is produced by [`goga schema`](../schema/cli.md) and the code-derived view by [`goga codegraph`](../codegraph/cli.md), so their [checkpoints](../schema/hooks.md) — and the [codegraph checkpoints](../codegraph/hooks.md) — run inside every drift comparison too; all hard: a failing or vetoing hook stops the command as an execution failure (exit code `2`), the reason on stderr, nothing on stdout — a view that could not be built is not a discrepancy.

## The events

| Address | Error class | Fires |
|---|---|---|
| `drift / run_started` | soft | At the beginning of every drift run, before the first view is produced, carrying the requested filters (`cells`, `max_depth`, `depends_on`). |
| `drift / amend_report` | **hard** | After the comparison and scoping settle the scoped report. One delivery per tool over the same finished scoped report; the last adjusting tool in enumeration order wins. |
| `drift / amend_entry` | **hard** | After the report amendment settles the final list — one delivery per surviving entry per tool, comparison-produced and tool-added alike. An empty final list fires nothing. |
| `drift / run_completed` | soft | On every terminal state of a started run — finished and crashed alike — carrying the last computed report stage (the final report with facts areas on finished runs, the scoped pre-amendment report when a later stage failed, nothing when the run failed before the report was computed), the `finished`/`crashed` outcome, and a credential-free reason on crashed runs. |

Run ordering: start moment → view production, comparison, scoping → report amendment → entry facts amendment → completion moment.

## The contexts

### `run_started` — the filters (soft)

One shared frozen context handed to every subscribing tool unchanged.

| Read | Type | Meaning |
|---|---|---|
| `filters` | `DriftFilters` | The filters the run was asked to apply — `cells` (the requested cell paths), `max_depth` (the requested limit; `None` — no limit), `depends_on` (the requested dependency-scoping paths), exactly as the run received them. |

### `run_completed` — the terminal facts (soft)

One shared frozen context handed to every subscribing tool unchanged.

| Read | Type | Meaning |
|---|---|---|
| `completion` | `RunCompletion` | `report` — the last computed report stage as `ReportEntry` records (`kind`, `cell`, `types`, `tools`), `None` before the report was computed; `outcome` — `RunOutcome.finished` or `RunOutcome.crashed`; `reason` — a credential-free crash reason on crashed runs, empty on finished runs. |

```python
def track_run(context):
    notify(f"drift {context.completion.outcome}: {len(context.completion.report or [])} entries")
```

Both moments are soft: a failing observer hook is a warning in the log naming the hook, the tool, and the reason; the report and the exit code never change, and the completion moment never masks a propagated failure.

### `amend_report` — `ReportAmendment` (hard)

One fresh view per tool, once per run.

| Read | Type | Meaning |
|---|---|---|
| `report` | `list[EntryFacts]` | The finished scoped report as computed by the comparison pipeline — one entry record per discrepancy with `kind`, `cell`, `types`. Read-only; attribute assignment is blocked. |

| Method | Effect |
|---|---|
| `adjust(entries)` | Replaces the report whole — remove entries down to clearing the report entirely, add entries down to surfacing discrepancies in an otherwise clean report. Every entry must be a mapping of exactly the fields `kind` (`schema_only` or `codegraph_only`), `cell` (a non-empty string), and `types` (a list of strings, or omitted for a cell-level entry) — any other key or shape is a hard failure; nothing is ever sanitized into shape. |

```python
def suppress_known(context):
    kept = [e for e in context.report if not is_accepted(e.cell, e.kind)]
    kept += accepted_discoveries()  # mappings of kind/cell/types
    context.adjust(kept)
```

Amending tools are mutually blind — every tool reads the same finished scoped report, never another tool's adjustment; the last adjusting tool in enumeration order wins, and calling `adjust` nothing leaves the report unchanged. The settled list decides the command's grading: a tool-emptied report prints `[]` and exits 0, a tool-added entry prints and exits 1.

### `amend_entry` — `EntryAmendment` (hard)

One fresh view per tool, once per surviving entry — the list fields are rebuilt per view, so an in-place append stays local.

| Read | Type | Meaning |
|---|---|---|
| `entry` | `EntryFacts` | The facts of the entry being enriched — `kind`, `cell`, `types`. Read-only; attribute assignment is blocked. |

| Method | Effect |
|---|---|
| `contribute(facts)` | Buffers one mapping of entry facts; merged key-wise, later-wins. The payload must be a plain JSON mapping — string keys, JSON scalars / lists / mappings, finite floats. |

```python
def annotate_entry(context):
    context.contribute({"ticket": ticket_for(context.entry.cell)})
```

Your facts land on the entry under your tool identity inside the `tools` wrapper area: `tools -> {<tool> -> {<fact>: <value>}}` — present iff at least one tool contributed, never an empty object. Facts never affect the exit-deciding entry list and never signal provenance.

## Subscribe

```python
def register_hooks(hooks):
    hooks.subscribe("drift", "amend_report", "baseline", suppress_known)
```

- `domain` — always `"drift"`; `action` — from the table; `name` — unique per tool per address; `hook` — the callable executed when the event fires.
- A hook receives values only for the parameters it declares by the fixed offered names: `context`, `self`.

## Integration scenarios

- **Baseline suppression** — subscribe to `amend_report`; remove the entries your team accepted and keep the rest — the gate stops failing on known drift.
- **Tool-detected discrepancies** — add entries your tool discovered outside the comparison — the gate starts failing on them.
- **Entry enrichment** — subscribe to `amend_entry`; attach tickets, owners, or any JSON facts to the surviving entries.
- **Run observability** — subscribe to the moments; build drift tracking and notification workflows on `run_started` / `run_completed` payloads.

## Failure treatment

The amendments are hard. A raising hook, a malformed adjustment (an entry outside the closed kind/cell/types shape), or a structurally malformed contribution stops the command with a clean error naming the hook or tool, the action, the entry subject where one exists, and the reason — exit code 2, nothing on stdout. The moments are soft — a failing observer is a warning. A tool package whose facade fails to import stops the command the same way, the error naming the package — and because the run never started, no completion moment fires.

## The run output

With no subscriptions — or no tool packages installed — the report, its entries, and the exit codes are byte-identical to the run without the extension: no `tools` key appears anywhere and the moments are unobservable. No adjustment provenance appears anywhere — no markers, annotations, or flags signaling that an entry was removed, added, or adjusted. Repeated runs with the same project state and tools reproduce the output deterministically; stdout stays data-clean JSON — every warning and diagnostic goes to stderr.

## API

The zone facade is importable as `goga.drift.hooks`:

```python
from goga.drift.hooks import (
    DriftFilters, DriftHooks, EntryAmendment, EntryFacts, ReportAmendment,
    ReportEntry, RunCompletion, RunOutcome, ToolContribution,
    merge_entry_contributions,
)
```

`DriftHooks().emit_run_started(filters)` / `emit_run_completed(completion)` are the moment surfaces the drift routine calls; `DriftHooks().amend_report(report)` returns the settled post-amendment list; `DriftHooks().amend_entry(entry)` returns the entry's tools area. `DriftFilters` / `EntryFacts` / `ReportEntry` / `RunCompletion` / `RunOutcome` are the fact records, `ReportAmendment` / `EntryAmendment` the delivered views, `ToolContribution` / `merge_entry_contributions` the committed-contribution pairing and the deterministic tools-area composition. See [Hooks — API](../hooks/api.md) and [Drift — API](api.md).
