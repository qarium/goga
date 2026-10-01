# Change Plan + Change Execution Report — board divergence directions

Task Classification: bugfix (contract-level semantic fix of the board divergence marker)

## Summary
The topic `add-pipeline-hooks` rendered on `goga topics board` with divergence marker `behind` although its branch tip was fully merged into the configured base `release/2.0.0` (0 commits outside the base). The marker rule probed one containment direction only — `current` when the topic tip contains every base projection — so every delivered topic (the normal post-`propagate`, pre-`clear` state) read as outstanding work. The rule was extended to both directions with an action-oriented three-valued domain approved by the user: `current` (topic carries base), `propagated` (base carries the whole topic), `need-update` (the pair diverged). The change was approved as a user override of the formal breaking-change STOP.

## Root Cause
`resolve_divergence` (goga/topics/board.py) computed the marker as `"current" if all(is_ancestor(tip, own_tip) for tip in projections) else "behind"` — a single-direction containment check pinned by the CODEMANIFEST. A delivered topic (own tip an ancestor of every base projection) failed the probe and read `behind`. Evidence: live board output (`add-pipeline-hooks`, `topic-influence`, `topics-clear` → `behind`), git ancestry (`is_ancestor(<topic>, release/2.0.0)` = YES, reverse NO, `rev-list <topic> ^release/2.0.0` = 0), the manifest text, and the test matrix pinning only the old direction.

## Modified Cells
| Cell | Files Modified |
|---|---|
| goga/topics | goga/topics/board.py, goga/topics/CODEMANIFEST, goga/topics/.usages/topic-board.md |
| goga/commands/topics | goga/commands/topics/topics.py, goga/commands/topics/render.py, goga/commands/topics/CODEMANIFEST, goga/commands/topics/.usages/topics-command.md |
| docs | docs/features/topics/api.md, docs/features/topics/cli.md |
| tests | tests/topics/test_board.py |

## Implemented Changes
| Change | File | Description |
|---|---|---|
| Directional marker | goga/topics/board.py | resolve_divergence: after the forward check (every projection ⊆ own tip → `current`), the reverse check (own tip ⊆ every projection → `propagated`), otherwise `need-update`; docstrings rewritten (module, BoardRecord, BoardEntry, resolve_divergence) |
| Command docstrings | goga/commands/topics/topics.py | board docstring: Base column domain current / propagated / need-update |
| Renderer docstrings | goga/commands/topics/render.py | both renderer Requirements: the same three-valued domain (rendering itself is verbatim — no behavior change) |
| Contract updates | goga/topics/CODEMANIFEST | resolve_divergence Algorithm extended to 5 steps, Requirements/Constraints re-worded; BoardRecord.divergence and BoardEntry.divergence annotations (type + property levels) |
| Contract updates | goga/commands/topics/CODEMANIFEST | renderer Requirements and JSON divergence-key domain re-worded |
| Usage updates | goga/topics/.usages/topic-board.md | both divergence bullets: three-valued domain, the propagated/partial-delivery semantics |
| Usage updates | goga/commands/topics/.usages/topics-command.md | Base-cell and JSON divergence-key domain |
| User docs | docs/features/topics/{api,cli}.md | marker definitions extended |
| Tests | tests/topics/test_board.py | matrix extended; new directional tests |

## Tests Added
| Test | File | What It Validates |
|---|---|---|
| test_resolve_divergence_delivered_topic_reads_propagated | tests/topics/test_board.py | every projection containing the own tip → propagated (tip containment carries every commit) |
| test_resolve_divergence_partially_delivered_topic_reads_need_update | tests/topics/test_board.py | a tip outside the base never reads propagated — partial delivery asks for an update |
| test_resolve_divergence_one_sided_delivery_reads_need_update | tests/topics/test_board.py | own tip inside one projection only — unreconciled base pair → need-update |
| test_resolve_divergence_equal_tips_read_current | tests/topics/test_board.py | own tip identical to its base → current (self-containment) |
| matrix: every projection contains the own tip | tests/topics/test_board.py | propagated through the parametrized matrix |
| matrix: diverged pair carries no containment | tests/topics/test_board.py | need-update when no direction holds |
| updated: one projection not contained / origin-prefixed / projection tests | tests/topics/test_board.py | existing cases re-pinned to need-update; the projection wiring unchanged |

## Specification Updates
| Cell | CODEMANIFEST Changes | Usage Changes |
|---|---|---|
| goga/topics | resolve_divergence: directional marker contract (Algorithm steps 3-5, Requirements current/propagated, Constraints need-update + no content probe); BoardRecord/BoardEntry divergence domain | topic-board.md: three-valued domain with the partial-delivery guarantee |
| goga/commands/topics | renderer Requirements + JSON divergence-key domain | topics-command.md: Base cell + JSON key domain |

## Validation Results
VERIFIED. pytest: 6426 passed, 8 skipped (pre-existing); ruff check: all passed; goga lint: 81 cells, 0 errors; facade import ok; live verification: `add-pipeline-hooks → propagated` (12 delivered topics read propagated, 2 carrying topics read current).

## Compatibility Status
BREAKING (user-overridden): resolve_divergence returns `propagated` where it returned `behind` for delivered topics and `need-update` for diverged pairs; CODEMANIFEST guarantees redefined accordingly. Signature (own_tip, base_ref) -> str | None, file paths, output shapes, and error behavior unchanged. No in-repo consumer branches on the marker value (renderer and JSON pass it verbatim). The breaking character was disclosed in the approval dialog and overridden by the user (plan approval, domain current / propagated / need-update).

## Risks
| Risk | Severity | Mitigation |
|---|---|---|
| Squash-delivered topics read need-update (no ancestry) | Low | documented CODEMANIFEST constraint; content-based detection explicitly out of scope |
| External JSON consumers keyed on the old `behind` token | Low | value domain documented in topics-command.md and docs; migration note is this report |
| Semantic drift between the marker and update/propagate outcomes | Low | update keeps its own already-current rule (unchanged); manifest wording keeps the two rules distinct |

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
- tests/topics/test_board.py
