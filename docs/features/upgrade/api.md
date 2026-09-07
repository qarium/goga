# Upgrade — API

The facade of the domain package **`goga.commands.upgrade`** — the pip upgrade of goga (and tools) with the agent re-sync.

The signature below is the CODEMANIFEST contract of the cell.

```python
upgrade(ctx: click.Context, sudo: bool, user: str | None, tools: bool,
        patch: bool, minor: bool) -> int
```

Upgrade the goga package in the running interpreter's pip and re-sync every agent recorded in the home `connect.yml`. `sudo` — run pip with `sudo --preserve-env=HOME` (a system-Python install); `user` — re-sync another user's goga installation (`SUDO_USER` resolution happens here); `tools` — additionally upgrade every installed `goga_tool_*` package; `patch` / `minor` — constrain the version line (`--patch`: the latest patch of the installed minor; `--minor`: the latest release of the installed major; neither: the latest release). Returns the exit code.

## Example

```python
import click
from goga.commands.upgrade import upgrade

@click.command()
def cmd():
    raise SystemExit(upgrade(click.get_current_context(), sudo=False, user=None,
                             tools=True, patch=True, minor=False))
```
