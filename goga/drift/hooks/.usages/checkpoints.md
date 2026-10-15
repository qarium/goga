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
