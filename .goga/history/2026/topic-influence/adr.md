# ADR: Topics Workflow — Stdin Todo, Own-Branch Board, JSON Output

Discovered decisions for the topic-influence change (see `prd.md` in this
directory). Each record below was settled in an interview with the repository
owner; together they supersede the PRD passages they touch.

## The topics domain owns the whole todo acquisition ladder

`goga topics create` resolves its todo in one place — the domain: an explicit
value, else declared stdin, else the interactive editor, else a clean error,
including the no-source guard and the skip of the publication ask when the todo
came from stdin. The CLI layer only maps the value-less `--todo` into a source
declaration. We chose domain ownership over CLI ownership because the editor
session and terminal detection already live there, and the "came from stdin"
fact is born and consumed inside one procedure — stdin is already drained by
the time the ask would read it — so splitting the ladder across layers would
push two extra signals through the boundary for a single decision.

## Stdin semantics: TTY never read, one full read, verbatim content

A TTY stdin is never read and never counts as content — a blocking read would
hang every interactive create. A non-TTY stdin is read fully, exactly once, at
todo-resolution time — after preflight, before the editor and the ask — because
a stream cannot be re-read and the guard and the resolution must share one
read. "Carries content" means at least one non-whitespace character; the
content itself is used verbatim (only the emptiness test strips), with the same
trailing-newline normalization as a value. Bytes that do not decode as UTF-8
are a clean error naming `--todo` — silently dropping piped content is exactly
what the PRD forbids. No size cap: todo.md is text and the caller owns the
volume.

## A topic without its own branch is not shown on the default board

The default board shows exactly the topics that still have an own branch — a
host whose normalized slug equals the topic slug; the remote-tracking form
counts, so remote-only topics stay visible and remote mode keeps working. A
topic whose history survives only in merged hosts has no own branch: only
history remains of it, and the record is not displayed. This decision replaces
the PRD's deterministic fallback ladder (current → local → most advanced
statuses → alphabet) entirely — a record's statuses are always the own
branch's statuses, and `--per-host` remains the full audit view where
merged-only topics stay visible per hosting branch. When several own branches
collide (distinct branches normalizing to one slug), the current branch wins
if it is among them, then a local branch over a remote-tracking one, then the
display-name alphabet.

## One collection, two projections

The per-host record collection — the previous row model, one record per topic
× host with that host's statuses — stays the single source of board facts. The
aggregated default view is computed from it (own-branch detection, hosts list,
own-branch statuses, current marker), so both views derive from one read pass
over the ref trees and cannot drift apart, and `--per-host` keeps its
semantics byte-for-byte.

## The board host filter

`--host` (repeatable) filters the already-collected records by exact display
name with union semantics across values; an unknown name yields an empty
result, never an error. The default view filters on the record's hosts list —
an own branch is still required, the filter never resurrects a hidden topic;
`--per-host` keeps the rows of the named hosts.

## JSON output uses the project's beautiful_json practice

`board --json` serializes through the established `beautiful_json` practice —
`json.dumps(data, indent=4, sort_keys=True, ensure_ascii=False)`, echoed with
one trailing newline — instead of a board-specific format. Keys therefore
print alphabetically; the stable consumer contract is the field names and
record shapes, not the key order.

## Table column order

The default table reads topic, branch, hosts, todo, statuses — branch and
hosts form one "where" group; the `--per-host` table stays exactly today's;
column widths re-balance by the existing render principle (equal shares of the
text columns, statuses takes the remainder, minimum 8).
