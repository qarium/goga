# Analysis Stages — consuming the three-stage pipeline

Domain: how the orchestrator consumes the codegraph analysis stages. Target
audience: the caller that runs the whole analysis — collect the file facts,
derive the units, resolve the links — over one configured language.

## Import

All stages are importable from the cell facade:

```python
from goga.codegraph.analysis import collect_facts, derive_units, resolve_links
```

## Stage order

The stages form one pipeline; each consumes the previous output. Never call a
later stage with partial input — every stage expects the complete project-wide
collection. `files` is the complete list of discovered source paths — discovery
belongs to the caller (the orchestrator cell), not to the analysis stages:

```python
from pathlib import Path

from goga.codegraph.analysis import collect_facts, derive_units, resolve_links

root = Path.cwd()

facts = collect_facts(files, language="python")
units = derive_units(facts, language="python")
links = resolve_links(units, facts, language="python", root=root)
```

- `collect_facts` — parse each file exactly once; an unparseable file raises an
  error naming the file, and the caller surfaces it as a command failure
- `derive_units` — pure grouping over the collected facts; reads no files
- `resolve_links` — collect-then-resolve over the complete set; never
  unit-locally

## Failure behavior relevant to the caller

- The only failing stage is `collect_facts` — an unparseable file (a parse
  tree with an ERROR or MISSING node) aborts the run
- External names never fail resolution: they produce no link silently
- The returned records are immutable — pass them on as they are

## Constraints

- One language per run — pass the same `language` to every stage
- Do not re-order the stages; resolution needs all units and all facts
- The result is deterministic for identical inputs
