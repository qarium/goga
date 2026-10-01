# Change Plan + Change Execution Report — board delivery column

Task Classification: bugfix (contract-level vocabulary fix of the board info view)

## Summary
The `goga topics board --info` view named its fifth column `Base` while the cell carried the
divergence marker, and the marker value `current` (the topic carries the base) collided with
the asterisk that marks the current topic — the current topic's row read as a duplicate of the
star and carried no legible delivery status. The marker domain was restated with the user's
approval: `base` (the own tip equals every base projection — the topic sits exactly on the
base), `up-to-date` (the own tip strictly carries every projection — no lag), `propagated`
(the base carries the whole topic), `need-update` (the pair diverged). The column header was
renamed `Base` → `Delivery`. No structural display change: `base_ref` keeps appearing among
the hosts exactly as before. The breaking character was disclosed in the approval dialogs and
overridden by the user.

## Root Cause
Vocabulary collision on one row: `BoardEntry.current` (the star — the current working branch)
and the divergence marker value `current` (the topic carries the base) shared one word with
two meanings, and the column header named the reference while the cell carried the delivery
state. Evidence: live board output (`* topic-u… | current | [done]`), render.py header/cell
code, the marker rule pinned by both CODEMANIFESTs, and the test matrix.

## Modified Cells
| Cell | Files Modified |
|---|---|
| goga/topics | goga/topics/board.py, goga/topics/CODEMANIFEST, goga/topics/.usages/topic-board.md |
| goga/commands/topics | goga/commands/topics/render.py, goga/commands/topics/topics.py, goga/commands/topics/CODEMANIFEST, goga/commands/topics/.usages/topics-command.md |
| docs | docs/features/topics/api.md, docs/features/topics/cli.md |
| tests | tests/topics/test_board.py, tests/commands/topics/test_render.py, tests/commands/topics/test_topics.py |

## Implemented Changes
| Change | File | Description |
|---|---|---|
| Four-valued marker | goga/topics/board.py | resolve_divergence: equality probe (every projection equals the own tip) → `base` runs before the containment probes; strict containment → `up-to-date`; reverse → `propagated`; otherwise `need-update`; module and entity docstrings restated |
| Delivery column | goga/commands/topics/render.py | header `Base` → `Delivery` in both info views; module/renderer docstrings restated |
| Command wording | goga/commands/topics/topics.py | board docstring and `--info` help re-worded to the todo and delivery columns and the four-valued domain |
| Contract updates | goga/topics/CODEMANIFEST | resolve_divergence Algorithm steps 1-6 and Requirements; BoardRecord/BoardEntry divergence annotations (type and property levels) |
| Contract updates | goga/commands/topics/CODEMANIFEST | board routine (six-column layout, Delivery cells), both renderer Requirements (Delivery header, marker domain), JSON divergence-key domain |
| Usage updates | goga/topics/.usages/topic-board.md | both divergence bullets state the four values with their semantics |
| Usage updates | goga/commands/topics/.usages/topics-command.md | boarding/audit/JSON sections state the Delivery column and the value domain |
| User docs | docs/features/topics/{api,cli}.md | marker domain and delivery-cell description restated |
| Tests | tests/topics/test_board.py, tests/commands/topics/{test_render,test_topics}.py | matrix and pins updated; new directional and legibility tests |

## Tests Added
| Test | File | What It Validates |
|---|---|---|
| test_resolve_divergence_equal_tips_read_base | tests/topics/test_board.py | equal tips read `base` and the containment probes never run — equality decides first |
| test_resolve_divergence_strictly_carried_base_reads_up_to_date | tests/topics/test_board.py | a topic strictly ahead of its base reads `up-to-date` — the star and the status no longer share a word |
| matrix: equal tips read base | tests/topics/test_board.py | the equality case inside the parametrized marker matrix |
| test_render_topic_board_info_current_entry_reads_its_delivery_status | tests/commands/topics/test_render.py | the starred current entry renders `up-to-date` in the Delivery column |

## Specification Updates
| Cell | CODEMANIFEST Changes | Usage Changes |
|---|---|---|
| goga/topics | resolve_divergence: the four-valued directional contract (equality → base, containment → up-to-date, reverse → propagated, else need-update); BoardRecord/BoardEntry divergence domain | topic-board.md: the four values with their semantics and the entry projection |
| goga/commands/topics | board six-column layout with the Delivery column; renderer Requirements and JSON divergence-key domain | topics-command.md: Delivery column, marker cell, audit layout, JSON value domain |

## Validation Results
VERIFIED. pytest: 6429 passed, 8 skipped (pre-existing); ruff check: all passed; goga lint:
81 cells, 0 errors; facade import ok; live verification: the current topic reads
`* topic-u… | up-to-date`, the board shows 1 `base`, 2 `up-to-date`, 11 `propagated`.

## Compatibility Status
BREAKING (user-overridden): resolve_divergence returns `base` or `up-to-date` where it
returned `current`; the info-table header reads `Delivery`; the JSON `divergence` value domain
changes accordingly. Signature `(own_tip, base_ref) -> str | None`, file paths, output shapes,
and error behavior unchanged. No in-repo consumer branches on the marker value (renderers and
JSON pass it verbatim). The breaking character was disclosed in the approval dialogs and
overridden by the user (plan approval with the four-valued domain amendment).

## Risks
| Risk | Severity | Mitigation |
|---|---|---|
| External JSON consumers keyed on the old `current` token | Low | value domain documented in topics-command.md and docs; migration note is this report |
| `base` reads ambiguously without the equality definition | Low | the equality semantics stated in every layer (manifest, usages, docs, tests) |
| Semantic drift between the marker and update/propagate outcomes | Low | update keeps its own already-current rule (unchanged); wording keeps the two rules distinct |

## Updated Files
- docs/features/topics/api.md
- docs/features/topics/cli.md
- goga/commands/topics/.usages/topics-command.md
- goga/commands/topics/CODEMANIFEST
- goga/commands/topics/render.py
- goga/commands/topics/topics.py
- goga/topics/.usages/topic-board.md
- goga/topics/CODEMANIFEST
- goga/topics/board.py
- tests/commands/topics/test_render.py
- tests/commands/topics/test_topics.py
- tests/topics/test_board.py
