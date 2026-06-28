# pip post-install hook (goga connect)

Trigger `goga connect` automatically after the `goga` package is installed or upgraded, so that `~/.goga/{skills,commands,flows}` and the agent symlinks stay in sync with the freshly installed package contents.

## Hard constraint: pip install isolation

`pip install` runs **without** invoking any project-defined post-install shell script. Mechanisms like `setup.py install` custom commands, `bash` snippets in wheel metadata, or `[tool.setuptools]` hooks are **not executed** by modern pip — they are silently ignored or break the build.

Therefore goga cannot rely on a shell hook fired by `pip` itself. Two viable strategies:

1. **Wrapper command (recommended).** Ship a dedicated CLI subcommand — `goga post-install` — that performs the re-sync. Document it as the manual step users run after `pip install -U goga`. This is the only approach that works uniformly across pip, uv, poetry, virtualenvs, and system Python.

2. **Custom `build_backend` wrapper (advanced).** Wrap `setuptools.build_meta` with a thin PEP 517 backend whose `build_wheel` injects a marker, and pair it with an entry point that the first invocation of `goga` detects. Use only if a fully automatic flow is required; it adds maintenance burden and surprises users who inspect wheels.

goga uses strategy **1**: a `goga post-install` command plus clear documentation. Do not attempt to register a shell post-install hook — it will not fire under pip.

## Strategy 1 — wrapper command

```toml
# pyproject.toml
[project.scripts]
goga = "goga.cli:app"
```

```python
# goga/commands/post_install/post_install.py
import click
from goga.connect import connect

@click.command("post-install")
def post_install() -> int:
    # ~/.goga/connect.yml is the source of truth for which agents to re-sync
    agents = read_connect_yml()  # returns ['claude', ...]
    return connect(agents, force_overwrite=True)
```

The command reads `~/.goga/connect.yml` to discover the previously connected agents, then re-runs `connect()` with `force_overwrite=True` so that updated skills/commands/flows replace the old versions in `~/.goga/` and propagate to agent symlinks.

## Detection of first run (optional)

If a fully automatic re-sync on first invocation is desired, write a version marker file:

```python
# ~/.goga/.installed_version
# contains the installed package version, e.g. 1.2.3
```

On every `goga` invocation, compare the marker against `importlib.metadata.version("goga")`. If they differ, run the post-install re-sync and update the marker. This avoids depending on pip hooks while still auto-syncing after an upgrade.

## Constraints

- Never execute code at import time of the `goga` package — that breaks tools which import goga as a library and runs network/disk work unexpectedly.
- The post-install command must be idempotent: running it twice produces the same `~/.goga/` state.
- The command must not fail hard if `~/.goga/connect.yml` is missing — treat it as "no agents connected yet" and exit 0.
