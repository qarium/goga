Need to support assistants and the team in the workflow.

- Documentation at flow.yaml DSL https://akopichin.github.io/afm/flow-reference/
- Documentation on setting up profiles at https://akopichin.github.io/afm/collaboration/

During the task analysis, we need to address delegation settings and the number of tasks, as well as linking assistants to stages.

We should use assistants mode.

## Engine verification at implementation time (plan Task 10, 2026-11-01)

Binary: `/srv/afm`, `afm version v2.0.9` (the only afm on PATH). Procedure:
fixtures compiled through the REAL chain (`parse_workflow` → `compile_flow`,
plus `write_afm_config` for the config layer), `HOME` redirected at a scratch
home carrying `.afm/config.yaml`, project layer via `afm --dir <tmp>/.afm`;
`afm validate` plus bounded `afm run --idle-timeout 3s --port 0` probes
(client command `/bin/true` — no network, no side effects) to observe the
run-time halves the validate surface cannot see.

ADR assumptions (design Additional Instruction 7):

1. Profile ids tolerate `goga-<name>` — HOLDS. `afm validate` resolves
   `profile: goga-reviewer` from `collaboration.profiles.goga-reviewer`
   (`OK: "demo" — 1 stage(s), valid`); removing the profile yields
   `team member "reviewer": unknown assistant profile "goga-reviewer"
   (not in collaboration.profiles)`. Runs add `goga-`-bound members.
2. `limits.max_tasks` follows project > global precedence — HOLDS. Global
   `max_tasks: 1` rejects the 2nd/3rd team member at run start
   (`team_warning: agent not added: operation rejected (budget_exceeded):
   quota 1 + 1 exceeds max 1`); a project-layer `.afm/config.yaml` carrying
   `max_tasks: 50` (global still 1) removes the rejections — the project
   value replaced the global one.
3. `max_depth: 0` suppresses helper creation but not team members —
   DEVIATES at the run surface. Helper suppression holds (a helper-bearing
   stage ran with no helper turns; run completed). But afm v2.0.9 ALSO
   declines team-member agent creation at `max_depth: 0` —
   `team_warning: "reviewer": agent not added: operation rejected
   (delegation_depth_exceeded): max_depth=0` (a warning; the run proceeds;
   members ARE added at depth >= 1). `afm validate` still requires every
   team member's profile to be configured regardless of `max_depth`.

Further deviation found (falsifies a `.goga/usages/cooks/afm.md` claim):
stage `stages[].assistants` entries carrying `skills` (list or scalar) are
REJECTED by afm v2.0.9's strict parse —
`Error: invalid flow.yaml: parse yaml: assistants: unknown field "skills";
use "profile"`. The usage doc claims unknown assistant keys (specifically
`skills`) pass silently. Consequence: a goga-compiled flow-file carrying
stage attachments fails `afm validate` as emitted; deleting ONLY the
stage-entry `skills` key (team-member `skills` is accepted) validates OK.
The emission shape (profile, title, instruction, mode, trigger, skills) is
pinned by the CODEMANIFEST/read-only contract — recorded here, not silently
widened. Follow-up decision needed: drop stage-entry `skills` from the
emission, or require an engine build that accepts it.

## Decision record (2026-11-01, review iteration)

RESOLVED — option (a): stage-entry `skills` is dropped from the emission.
Rationale: the pinned engine (Dockerfile `AFM_VERSION=2.0.9`, the only afm
available) rejects the key, so option (b) has no engine to target; and the
assistant's `skills` already reach the engine through its `team:` member
entry (accepted there), so the drop loses nothing. `FlowAssistant` now
carries five fields (profile, title, instruction, mode, trigger); the
compiler CODEMANIFEST, the `.usages` documents, and the test goldens are
updated to match; `.goga/usages/cooks/afm.md` now records the strict-parse
fact. Verified end-to-end: `parse_workflow` → `compile_flow` →
`serialize_flow` → `write_afm_config` then `afm validate` → `OK` (exit 0)
on a flow carrying a catalog, delegation, and a gated stage attachment.

Amendment (second review iteration, 2026-11-01): the "loses nothing"
rationale holds only for CATALOG entries — they are the sole source of
team members, the only skills channel the engine accepts. An inline
declaration's authored `skills` therefore had NO channel: the parser
accepts the field (the plan pins `skills`-only inline declarations) but
the compiler silently discarded it. Rejecting the field at parse time
would contradict the pinned parser contract, and emitting a team member
for inline declarations would contradict the pinned team = catalog-only
rule, so the gap is closed with a compile-time WARNING (once per name,
naming the stage and the assistant) through the existing
`compile_flow` logger idiom — the drop is now diagnosed, never silent.
The CODEMANIFEST, `.usages/collaboration-emission.md`, and
`docs/features/pipelines/workflows.md` state the catalog-only delivery
rule. Same iteration: a `goga lint` regression from the first-iteration
commit (a backticked `skip: true` in the apply_skip_stages annotation
parsed as an unresolvable link) is reworded; the gate is back to
0 errors / 91 cells.

Reproduction (scratch dirs):

    # compile the fixture through the real chain, then:
    HOME=<scratch-home> afm validate <flow.yml>                 # exit 0 with profiles configured
    HOME=<scratch-home> afm --dir <scratch-dir> validate <flow.yml>
    HOME=<scratch-home> afm --dir <scratch-dir> run --idle-timeout 3s --port 0 <flow.yml>
    # team/budget notices land in <scratch-dir>/.afm/runs/<run>/notices.jsonl