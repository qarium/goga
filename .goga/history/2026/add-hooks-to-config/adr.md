# Open the config domain to tool hooks via an in-memory amendment checkpoint

The config domain becomes the sixth opened domain: one hard checkpoint —
`config / amend_config` — fires at the project-config load moment, delivered
over the existing hooks platform (per-tool staged delivery, mutual blindness,
tool-granularity commit, one registry per run). Subscribed hooks read the
authored loaded configuration — values included, environment mappings
included — through the platform's read-only proxy, and contribute `set` /
`force` amendments that merge deterministically in memory for the current
run; the authored file is never modified. The decisions below settle the
contract axes the PRD left open; where they supersede PRD wording, the PRD
has been aligned to this record (see Consequences).

## Considered options

- **Action address** — `config / amend_config` (the `amend_<artifact>`
  convention; the (domain, name) pair keeps it distinct from
  `onboarding / amend_config`). Rejected: `amend_settings`, `amend_run`
  (read better but break the naming convention).
- **Authored silence** — a path is silent when the loaded model carries the
  absence marker (`None`, `{}`, `[]`); authored emptiness loses to `set`.
  Rejected: raw-YAML key-presence (a second representation to reason about,
  fighting the loader's own `"" -> None` normalization).
- **Addressing granularity** — leaves only: scalar leaves, list-valued
  leaves replaced wholesale, individual mapping entries (`pipeline.env.K`,
  `tools.<name>`). Whole-section replacement is not offered; tools compose
  containers themselves from the read view. Rejected: any-node wholesale
  replacement (subtle cross-level clobbering between enumeration order
  steps).
- **Merge algebra** — on one path `force` beats any `set` regardless of
  enumeration order; among amendments of equal intent the later tool in
  enumeration order wins; a `set` on a non-silent authored path is dropped
  silently. Rejected: pure later-wins (a polite late `set` would clobber a
  deliberate `force`).
- **Checkpoint ownership** — a config-domain hooks zone surface: the command
  hands it the loaded authored config (operation data), it runs the per-tool
  delivery and returns the effective config plus applied-amendment data;
  every config-consuming command switches to this entry (uniform reach);
  the loader contract stays "authored load only". Rejected: firing inside
  `load_project_config` itself (zero-touch for callers, but it redefines
  the loader's contract and leaves the summary no return path).
- **Summary** — the zone composes the lines; every command prints them to
  stderr: one header plus one line per applied amendment (tool, set/forced,
  path) in enumeration order; values never printed; nothing when nothing
  applied. Rejected: stdout (pollutes the machine-readable `goga config`
  data surface), zone-side printing (breaks the platform precedent that
  acting on returned data belongs to the operation).
- **Protected paths** — none: every model-known path is uniformly `set`- and
  `force`-able; abuse is visible in the summary. Rejected: a protected list
  (special cases; the "enforce a safer value" scenario needs full-strength
  `force`).
- **Structural malformedness** — a path is known iff it resolves in the
  configuration model's type tree (dataclass fields; arbitrary keys under
  mapping-typed fields); the value's type is checked at the node (`commands`
  is free-form); a non-leaf address, an unknown path, or a wrong-typed value
  is a hard delivery failure for that tool — its whole contribution is
  discarded and the command stops with a clean error naming the tool and the
  action. Semantic validation stays with consumers.
- **Read view** — the loaded authored configuration itself, with values
  (environment mappings included), delivered read-only through the
  platform's proxy (attribute assignment blocked). Rejected: a facts mirror
  with env as names only. The build domain's names-only rule protects the
  assembled runtime environment; the authored project configuration is what
  tools are expected to read and extend — including composing new env values
  from existing ones. Secrecy is enforced on the output side instead.
- **Path vocabulary** — the authored YAML keys (`language`, `build.agent`,
  `pipeline.env.KEY`): one vocabulary for the file, `goga config`, and the
  amendment surface. The model field `lang` is renamed to `language` in the
  same major release so the model, the file, the CLI, and the surface
  coincide; no other name diverges.
- **Absent branches** — a model-known path stays addressable when its
  intermediate branch is absent; the amendment materializes the missing
  nodes (the "prepared parameter set on a minimal config" scenario).
  Rejected: present-branches-only addressing.

## Consequences

- Two PRD statements are superseded, and the PRD has been edited to match
  this record (no drift): the env names-only read-view exception (R3/SC1
  and the related constraint/scope wording) is removed — env secrecy is
  enforced on the output side (the summary and any informational output
  never print values) — and the `lang` -> `language` rename touches the
  configuration model without redesigning it (no new sections, fields, or
  defaults).
- `goga config` prints effective (amended) values, per R10; its stdout
  remains the command's data surface, which is why the amendment summary
  goes to stderr.
- The checkpoint is usually the first checkpoint a config-consuming command
  reaches, so registry assembly happens there (platform first-checkpoint
  behavior); later checkpoints of the same run reuse the same registry.
- Within one tool, a later amendment on the same path replaces its earlier
  one (the platform's staged-buffer semantics, as with `contribute` in the
  pipeline domain).
- Home configuration stays closed; the checkpoint belongs to the act of
  loading the project configuration, and with no subscribed tools the load
  is byte-identical to today (no registry assembly, no summary).
