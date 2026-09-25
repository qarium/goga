# Automation

Pipelines can run where no human is present — CI jobs, schedulers, containers.
This page collects what changes when nobody is watching: interactive stages,
topics, credentials, the image, and exit codes.

## Make stages non-interactive

By default, stages authored with `communication: true` pause and prompt for
user input — in an unattended run there is nobody to answer, and the stage
waits forever. Apply the [`approve`](workflows.md#auto-approval-approve-auto-plan-dialog)
directive to such stages in a workflow-file to suppress the pause
(`approve: plan` suppresses only the user-input pause; `approve: auto` also
auto-approves agent actions on `planner`-role stages):

```yaml
# <cwd>/.goga/workflows/<pipeline-name>.yml — auto-matched by name
stages:
  define:
    approve: auto   # no pause, no approval prompt
```

Avoid `trigger: manual` stages and `notes` note buttons in unattended runs:
a manual stage pauses until explicitly launched, and a note button waits for
a click.

## Topics without a terminal

`-t/--topic` works non-interactively. The identifier resolves through exact
branch name → exact topic slug → prefix, and the first tier with a match
wins:

- a **unique** match switches (or stays) on the hosting branch and the run
  proceeds;
- **several** candidates with no terminal is a clean error and exit 1 — the
  numbered picker cannot render;
- **nothing** hosts the identifier — a fresh branch and its topic directory
  are created, and the run proceeds;
- a **dirty working tree** on a mutating switch exits 1 before anything is
  touched.

See [Topic switch](cli.md#topic-switch) for the full resolution rules.

## Credentials

Nothing is mounted automatically — the launcher adds no credential mounts
(see [Runtime — Credentials](runtime.md#credentials)). On an ephemeral
runner, forward the agent's env variables — through `pipeline.env`
in `.goga/config.yml` or the `-e KEY=VALUE` option:

```bash
goga pipeline sync -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY"
```

On a self-hosted runner with persistent credential files, mount them
read-only via a `docker.run` volume token in the home configuration.

See [Agents](../../configuration/agents.md) for which variables (or files)
each agent needs.

## The image and the version check

Every launch checks that the goga versions on the host and inside the image
agree at the (major, minor) level — on CI, where fresh goga versions arrive
with every job, a stale image is the most common refusal. Pull (or rebuild)
the image as part of the job with `--update`:

```bash
goga pipeline sync --update
```

The check itself can be disabled with `GOGA_SKIP_VERSION_CHECK=1` when the
image lifecycle is managed externally (see
[Runtime — Pre-launch version check](runtime.md#pre-launch-version-check)).

## Exit codes

The container's exit code is propagated unchanged, which makes the run
directly usable as a CI step: `0` — the pipeline ran successfully; `1` — a
form or configuration error, a handled compile failure, or a failing hard
`pipeline/amend_workflow` hook — the run stops before any compile or
launch (see [Hooks](hooks.md)); `126`/`127` — the pipeline engine inside
the image is not executable / missing; `130`/`143` — interrupted by
SIGINT/SIGTERM. See [Exit codes](cli.md#exit-codes) for the full table.

## CI skeletons

`goga pipeline` launches the work container by shelling out to the
`docker` CLI. When the CI job itself runs inside a container, two things
break: there is no Docker daemon the job can talk to, and every bind
mount goga declares — the project directory, the pipeline's persistent
state, the agent prompts — resolves on the **daemon's** filesystem, not
the job's. A job container with a bare `docker` binary would launch the
pipeline against empty directories.

A viable job therefore needs Docker-in-Docker: a privileged `dind`
sidecar daemon, `DOCKER_HOST` pointing at it, and the workspace plus the
goga runtime directory (`~/.goga/runtime`) shared as **identical paths**
on both sides — goga computes the mount sources on the job side, and the
daemon must serve the same bytes. On top of that come the regular
unattended needs: a pinned goga version matching the image, a
non-interactive stage configuration, a git identity for the stages that
commit, and agent credentials from env variables (an ephemeral runner has
no credential files to mount).

The job container — Python, git, and the docker CLI in one image:

```dockerfile
# ci-image/Dockerfile
FROM python:3.12-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends git docker.io \
 && rm -rf /var/lib/apt/lists/*
```

Check into the repository — the run form requires the `pipeline` section
and the top-level `image`:

```yaml
# .goga/config.yml
image: qarium/goga-python-3.12:1.3
pipeline:
  agent: claude
```

The shipped `sync` pipeline pauses at its `resolve` stage
(`communication: true`) — add an auto-matched workflow-file that lets it
run unattended:

```yaml
# .goga/workflows/sync.yml
stages:
  resolve:
    approve: auto   # suppress the user-input pause
```

### GitHub Actions

On GitHub Actions nothing is shared between the job container and the
service container — declare the workspace and the goga runtime as named
volumes mounted at identical paths on both sides, and copy the checkout
into the shared path:

```yaml
# .github/workflows/goga.yml
name: goga-sync
on:
  push:
    branches: [main]
jobs:
  sync:
    runs-on: ubuntu-latest
    container:
      image: ghcr.io/you/goga-ci:1
      volumes:                     # identical paths on the job and the daemon
        - goga-work:/work
        - goga-runtime:/root/.goga/runtime
    services:
      docker:                      # the daemon goga talks to
        image: docker:27-dind
        env:
          DOCKER_TLS_CERTDIR: ""   # plain tcp inside the job's private network
        volumes:
          - goga-work:/work
          - goga-runtime:/root/.goga/runtime
        options: --privileged      # dind cannot start without it
    env:
      DOCKER_HOST: tcp://docker:2375
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0           # stages compare branches, not just the last commit
      - run: cp -a "$GITHUB_WORKSPACE/." /work/   # serve the checkout to the daemon
      # Pin goga to the image's (major, minor) — the pre-launch version
      # check refuses a mismatched pair
      - run: pip install 'goga==1.3.*'
      # goga reads the git identity from the local git config; stages
      # that commit need it
      - run: |
          git config --global user.name "goga-ci"
          git config --global user.email "goga-ci@example.com"
      - working-directory: /work
        run: goga pipeline sync --update -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY"
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

Notes:

- `DOCKER_TLS_CERTDIR: ""` disables TLS on the sidecar daemon —
  acceptable inside the job's private service network; switch to the
  dind TLS certificates when your CI policy requires it.
- The pipeline's commits land in the shared `/work` volume — pushing
  them back (with `GITHUB_TOKEN` or a deploy key) is the job's own
  concern, not goga's.
- A job on a plain VM runner with Docker (no `container:`) needs none of
  the dind machinery — the mounts resolve on the runner's filesystem
  directly.

### GitLab CI

The docker executor shares the `/builds` directory with the service
containers, so the checkout (`$CI_PROJECT_DIR`, where the script runs by
default) is already visible to the daemon under the same path — no
volume plumbing for the workspace. What is **not** shared is `$HOME` —
redirect it under `$CI_BUILDS_DIR` so the pipeline state and the agent
prompts, which goga materializes on the job side, land where the daemon
can mount them:

```yaml
# .gitlab-ci.yml
goga-sync:
  image: ghcr.io/you/goga-ci:1        # python + git + docker CLI
  services:
    - name: docker:27-dind
      alias: docker
  variables:
    DOCKER_HOST: tcp://docker:2375
    DOCKER_TLS_CERTDIR: ""             # plain tcp on the job's private network
    GIT_DEPTH: 0                       # stages compare branches, not just the last commit
    HOME: "$CI_BUILDS_DIR/.goga-home"  # goga's runtime dir lives under $HOME
  script:
    # Pin goga to the image's (major, minor) — the pre-launch version
    # check refuses a mismatched pair
    - pip install 'goga==1.3.*'
    - git config --global user.name "goga-ci"
    - git config --global user.email "goga-ci@example.com"
    - goga pipeline sync --update -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY"
```

The runner must be allowed to start a privileged dind container — on
self-hosted runners that means `privileged = true` in the runner's
`config.toml`; GitLab.com shared runners allow it. On self-hosted runners
with a custom `volumes` configuration, verify that the builds directory
is still shared with the service containers — the whole recipe depends
on it.
