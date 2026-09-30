# Split the run context from the host launch context (pipeline and build)

Status: accepted (2026-09-30)

When `goga pipeline` runs, the project configuration is never loaded inside
the container: the host bakes `pipeline.env` into the container env-file and
`pipeline.agent` into a read-only afm-config tmpfile, so tool packages
installed in the image never receive the `amend_config` checkpoint and cannot
influence the run's env or agent. In `goga build` the configuration is loaded
in-container, but authored-only (the documented "in-container loads stay
authored-only" rule), so no tool can influence `build.env` / `build.agent`
either — and the task env layers beat the CLI `-e` layer. We decided to split
the context along the only boundary that matches reality — the docker launch:
the host owns the launch mechanics, the container owns the run parameters —
and to deliver `amend_config` at both load moments as one action with one
vocabulary. The amendment surface is identical on the host and in the
container; only the consumption differs, by field ownership.

## Terms

- **host launch context** — what the host must resolve before the container
  starts: image, dockerfile, port, mounts, `--add-host`, proxy variables,
  env-file base layers (home.env, git identity, CLI `-e`), `AFM_DIR`,
  `AFM_DOCKER_FILE_ROOTS`, container name, signal handling, structural
  section guards.
- **container run context** — what resolves inside the container: the
  effective task env layers, the agent resolution, the workflow overlay, the
  prompts, and the build session knobs.
- **task env layer** — a domain's effective env mapping (`pipeline.env`,
  `build.env`, `build.review.env`) applied in-container between the inherited
  launch env and the CLI layer, for the target binary's launch only.

## Decisions

- **Both domains, one denominator.** The in-container entrypoints
  (`python -m goga.pipeline` run form, `python -m goga.build`) perform
  load-and-amend: authored `load_project_config` → `amend_config` delivered to
  the image's tool packages → the effective configuration feeds everything
  downstream. The pipeline coordination loads and amends at the start of the
  run coordination, before workflow resolution and `amend_workflow`; only the
  run form does it — the listing, overview, and card forms load nothing and
  deliver nothing.
- **The host keeps its delivery, for its fields.** The host commands keep
  delivering `amend_config` at their load moment and consume the effective
  configuration for host launch context fields (image, dockerfile, proxy,
  hosts) and the structural section guards.
- **One action, two moments.** `amend_config` is not split by environment:
  the path vocabulary and the amendment semantics are the same on the host
  and in the container — there is no host-specific or container-specific
  amendable key set. A contribution commits into the effective configuration
  of the moment that delivered it; each side consumes only the fields it
  owns; contributions into the other side's fields stay applied but
  unconsumed, silently (visible through the summary lines, never a warning).
- **Env ladder, both domains:** home.env < git identity < task env layer
  (effective) < CLI `-e` < engine variables (`AFM_DIR`,
  `AFM_DOCKER_FILE_ROOTS`, `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY`). The CLI
  layer beats the configuration layers — explicit user input wins over config
  and tool amendments. Because docker `--env-file` flattens layers, the CLI
  `-e` entries additionally travel as a distinguishable payload (the
  `AFM_DOCKER_FILE_ROOTS` precedent) so the in-container side can apply them
  above the task env layer; they also stay in the env-file — same values,
  one source — so every reader of `os.environ` keeps seeing them. Engine
  variables are launch mechanics; nothing overrides them. Consequence: git
  identity now sits below the task env layer (their keys practically never
  collide).
- **afm config.yaml moves in-container.** The host stops generating and
  bind-mounting the afm-config tmpfile; the in-container run coordination
  writes the whole config.yaml — client.command resolved from the effective
  agent, plus theme, open_browser, proxy.enabled, prompts_dir — before
  launching afm.
- **Guards split by nature.** Structural guards (a required config section)
  stay on the host; value guards move in-container. The build "agent
  required" guard moves in-container: the effective agent may arrive as a
  container-side amendment, so a host check on the authored value would
  reject a run an amendment could have satisfied. The pipeline section guard
  stays host-side, on the host-effective configuration.
- **Failure semantics stay hard and symmetric.** The first failing tool at
  either delivery moment stops the command with a clean error naming the tool
  and the action; the target binary (afm / ralphex) never launches; the
  amendment summary lines print to stderr; configuration values never appear
  in any output.

## Considered options (rejected)

- Moving the whole amendment into the container (host authored-only): proxy,
  hosts, and image cannot be amended from inside an already-running container
  — the host would lose its only extension point for launch fields.
- Keeping the host afm tmpfile and injecting the agent per-stage into the
  compiled flow-file: afm reads exactly one config.yaml (the read-only mount
  would block the container-side write), and per-stage injection would fight
  the workflow layer's authored per-stage `command:` overrides.
- Task env layer above the CLI layer (today's build behavior, and the simple
  "build model" for pipeline): rejected — explicit CLI input must win over
  config and tool amendments in both domains.

## Consequences

- The documented rule "in-container loads stay authored-only" is retired; the
  config hooks usage is rewritten to the one-action-two-moments rule. The afm
  usage and both command manifests are affected — owned by the change plan,
  not by this record.
- Host-side tool amendments into `pipeline.env` / `pipeline.agent` (fields
  the host no longer consumes) become inert; container-side amendments into
  docker-level fields are inert by the same rule.
- In-container tool packages now receive the authored configuration with env
  values included — the same read-and-amend view host tools get today;
  secrecy stays an output-side rule (no value ever prints).

## Unresolved (for the design stage)

- How the task env layer and the distinguishable CLI payload reach the afm
  launch — `run_flow` today inherits the process environment unchanged. The
  contract shapes, the payload encoding, and the cell boundaries are
  design-stage work, outside this record.
