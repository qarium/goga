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

Reproduction (scratch dirs):

    # compile the fixture through the real chain, then:
    HOME=<scratch-home> afm validate <flow.yml>                 # exit 0 with profiles configured
    HOME=<scratch-home> afm --dir <scratch-dir> validate <flow.yml>
    HOME=<scratch-home> afm --dir <scratch-dir> run --idle-timeout 3s --port 0 <flow.yml>
    # team/budget notices land in <scratch-dir>/.afm/runs/<run>/notices.jsonl