# Install — API

The facade of the domain package **`goga.commands.install`** — the pip install/uninstall of tool packages with the post-install hooks and agent activation.

The signatures below are the CODEMANIFEST contract of the cell.

```python
install(ctx: click.Context, name: str | None, sudo: bool, version: str | None,
        local: str | None, no_connect: bool = False) -> int
uninstall(ctx: click.Context, name: str, sudo: bool = False, yes: bool = False,
          target_user: str | None = None) -> int
```

- `install` — pip-install a tool into the running interpreter (single mode with `name`, local mode with `local`, bulk mode with neither — the `tools:` declarations), then run the post-install hooks and activate the registered agents (skipped with `no_connect`). Returns the exit code.
- `uninstall` — remove exactly one tool package after the confirmation (`yes` skips it; a non-interactive terminal without `yes` is a clean error), then re-sync the agents. `sudo` targets a system-Python install; `target_user` re-syncs another user's installation.

```python
resolve_initiating_user() -> str
run_install_hooks(tools: list[str]) -> None
call_install_hook(tool: str, user: str) -> bool
```

- `resolve_initiating_user` — the initiating user of the run (`SUDO_USER` under sudo, else the current OS user) — the value passed to keyword-capable hooks.
- `run_install_hooks` — run the post-install hook of each named tool (the pip-fresh set); a failing hook raises.
- `call_install_hook` — invoke one tool's `install` facade callable (`True` — the package declares one and it ran).

## Example

```python
import click
from goga.commands.install import install

exit_code = install(click.get_current_context(), name="mkdocs", sudo=False,
                    version="1.0.x", local=None, no_connect=False)
```
