# Agent Skill Bundle: DSL-to-Ralphex Planning

This bundle compiles `CODEMANIFEST` DSL into ralphex-compatible execution plans.

## Files

- `SKILL.md` — main planning skill prompt (DSL-to-ralphex compiler)
- `dsl-spec.md` — DSL specification for `CODEMANIFEST`
- `output-template.md` — ralphex-compatible plan template
- `conventions.md` — project conventions + ralphex task design rules
- `example.md` — DSL-to-plan compilation example

## How it works

1. **Input**: `CODEMANIFEST` DSL defining package contract surface
2. **Processing**: Contract extraction, gap analysis, task decomposition
3. **Output**: Ralphex-compatible markdown plan in `docs/plans/<feature>.md`

The output plan uses:
- `### Task N:` headers for ralphex task discovery
- `- [ ]` checkboxes for task tracking
- `## Validation Commands` for verification
- Self-contained task context for AI execution

## Ralphex execution

The generated plan is fed to `ralphex` which:
1. Executes each task via Claude Code (one per iteration)
2. Runs validation commands after each task
3. Performs multi-phase code reviews
4. Commits after each completed task

See: https://github.com/umputun/ralphex

## Layering

1. Contract (`CODEMANIFEST`)
2. DSL spec (`dsl-spec.md`)
3. Planning skill (`SKILL.md`)
4. Output schema (`output-template.md`)
5. Conventions (`conventions.md`) — general + ralphex task design
6. Language-specific conventions (future layer)
