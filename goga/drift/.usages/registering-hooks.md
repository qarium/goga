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
