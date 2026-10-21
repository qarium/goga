# Contributor Profiles: render in-container, carry personal data as host-derived values, and use closure wrappers as the only per-executor env boundary

Status: accepted (2026-10-15)

Contributors must run shared committed processes with their own agents, credentials, and models. We decided to keep workflow rendering inside the container (where workflows are parsed today; the host is forbidden to read workflow files), to carry personal data across the host/container boundary as derived values only (the established launcher pattern — home is never mounted), and to make generated closure wrapper scripts the single mechanism for attaching an environment to a specific executor — pipeline stages and build pass roles alike — because the external runners (afm, ralphex) offer no native per-executor env.

## Decisions

### Profiles and rendering

1. Profile lookup: `.goga/profiles/<name>.yml` (project, committed) then `~/.goga/profiles/<name>.yml` (home, personal); on the same name the project wins; `.yml` extension only; a profile is a free-form YAML mapping; management is files-only.
2. Profile names are strictly validated — `[A-Za-z0-9][A-Za-z0-9._-]*`, `.` and `..` forbidden — because the name becomes a filesystem path component; a violation is a strict pre-run failure (path-traversal guard).
3. Whole-file Jinja rendering runs before workflow parsing, configured with `trim_blocks`, `lstrip_blocks`, `keep_trailing_newline`, and the standard `Undefined` (a missing key is falsy/empty; nested access on a missing key fails at render time — standard semantics). Block tags vanish cleanly inside YAML; after rendering, the standard structural validation applies unchanged.
4. Activation edge cases: (a) no workflow in effect — activation is ignored entirely (not loaded, no launch line); (b) workflow in effect with external activation (`--profile`/`GOGA_PROFILE`) — the profile is loaded and validated (strict failure when missing or malformed) and rendering proceeds; (c) templates present but no activation channel fired — render with an empty context (enables optional personalization and profile-driven stage skipping via `{% if %}` guards).
5. Home carriage: the host launcher encodes the whole `~/.goga/profiles/*.yml` bundle into one engine payload variable `GOGA_HOME_PROFILES` (base64 compact JSON, the `GOGA_EXTRA_ENV` precedent). Rationale: the effective profile name may only become known in-container (the workflow `profile:` default), and host home directories are never mounted. A malformed home profile file fails strictly on the host before launch.

### Activation discipline

6. Precedence: `--profile` > `GOGA_PROFILE` > workflow `profile:`. The launcher carries `GOGA_PROFILE` into the container env-file; an explicit `-e GOGA_PROFILE=...` beats the ambient host environment.
7. `GOGA_WORKFLOW` is written only by the pipeline-run launcher (alongside `GOGA_PROFILE` and the home bundle) and interpreted only by in-container `goga build` (workflow inheritance for builds invoked inside a pipeline runtime); host builds select a workflow only via `-w`; the CLI flag beats the env value. The reserved inert names (`GOGA_WORKFLOW_NAME`, `GOGA_WORKFLOW_DISABLED`, `GOGA_SKIP_STAGES`) are untouched; `GOGA_WORKFLOW` is a new, distinct name — a deliberate, documented exception to the "run options never travel through the environment" rule, scoped to launcher-written values consumed in-container.

### Env delivery — pipeline path

8. The per-stage instruction `stages.<name>.env` (a string map, literal and/or rendered) is delivered by generating a per-stage sh closure wrapper — `export` the stage env, then `exec` the stage agent's wrapper, else the effective global wrapper (`pipeline.agent`, the same resolution `write_afm_config` applies), else a strict pre-run failure — and pointing the afm stage `command:` at it. afm's `command:` follows the absolute-executable-path convention, not a shell command line, so a generated script is the only reliable boundary. Wrappers live in a container-local temp directory (ephemeral, like the env-file; never under `/workspace`, which is dashboard-browsable); per-stage values layer above all global env layers. `env` is valid only under `stages.<name>`, not in extend-entries.

### Env delivery — build path

9. The workflow grammar gains a top-level `build:` block with a strict six-field set: `agent`, `env`, `review.agent`, `review.env`, `review.additional.agent`, `review.additional.env`. Anything else — including `proxy` and `hosts`, which are consumed on the host before the container starts — is a structural error; the host launcher must not read workflow files.
10. New configuration field `build.review.additional.env`: an independent env layer for the external reviewer. Today the additional agent is spawned by ralphex inside the review pass and inherits that pass's single env layer; a separate layer is impossible without wrapping its command.
11. Env maps merge key-wise (workflow keys override same-named config keys, the rest of the config env survives — the single-variable override use case). Settings layering: `config < workflow build: < CLI` (insertion between config and CLI at the resolution point).
12. Every build pass executor (tasks, review, additional) always runs through a generated per-role closure wrapper — a uniform, predictable mechanism (chosen over wrapping only the additional role). The wrapper exports the role's env with the decoded CLI entries applied on top (CLI keeps winning over role env; engine keys dropped), so today's "CLI above the task layer" precedence is preserved exactly; task env layers no longer ride the ralphex launch env (the ralphex subprocess inherits the container env). Layers stay independent — additional does not inherit review env, mirroring "review env never inherits root env". Under the `medium` strategy the additional layer is inert (external review disabled), as `additional.agent` is today; under `short`, `claude_command` is the additional wrapper. Wrappers are regenerated when each pass's `.ralphex/config` is written, in a container-local temp directory (`/tmp/goga-build-env/`). Wrappers are per-role, not per-agent: the same underlying agent can carry different env per role.

### Feedback and compatibility

13. Launch feedback extends the existing line design: `Pipeline running with workflow "<w>" and profile "<p>"` and `Build running with workflow "<w>" and profile "<p>"`; with no effective profile the output is unchanged.
14. Info/card forms apply the profile through the same activation channels (profiles can affect rendering up to skipping stages, so the card invariant — "the card reflects what a run with the same flags would apply" — requires it); the launcher adds an env-file to info forms only when there is something to carry (explicit `--profile`, non-empty host `GOGA_PROFILE`, or non-empty home bundle).

## Considered Options

- **Home carriage:** single-profile carriage (breaks lookup semantics whenever a workflow-default name exists only at home) and read-only home mounts (breaks the no-credential-mounts launcher discipline) — rejected in favour of the full encoded bundle.
- **`env K=V` command prefix** for per-stage env — rejected: afm's `command:` is an executable path by convention, not a shell line.
- **Replace vs merge** for workflow-provided env maps — replace loses the "override one model variable, keep the rest" case; merge chosen.
- **Minimal (additional-only) vs uniform build wrappers** — uniform chosen for predictability, accepting the backward-compatibility amendment below.
- **Wrapper location `.ralphex/wrappers/` vs container-local `/tmp`** — `/tmp` chosen: secret ephemerality (env-file precedent), no collision between concurrent builds sharing the runtime dir, regenerated per pass so interrupted-build resume is unaffected.

## Consequences

- The PRD backward-compatibility clause is amended (aligned during discovery): the pipeline path stays byte-identical (wrappers are generated only for stages declaring `env`); the build path is behaviour-identical — agents receive the same effective environment and builds produce the same results, while `.ralphex/config` command fields now point at generated wrappers instead of agent wrapper paths directly.
- jinja2 becomes a declared third-party dependency (project convention: every third-party library in `pyproject.toml` with a minimum version).
- `GOGA_WORKFLOW` deliberately relaxes the "run options never travel through the environment" contract; the relaxation is narrow (launcher-written, in-container-consumed) and must be documented in the affected contracts.
