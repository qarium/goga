# Connect — API

The facade of the domain package **`goga.connect`** — the installation of goga skills and commands into AI agents.

The signatures below are the CODEMANIFEST contract of the cell.

```python
connect(agents: list[str], force_overwrite: bool = False) -> int
install_pipelines(pipelines_dir: Path, force_overwrite: bool = False) -> int
resync_registered_agents(goga_home: Path) -> int
```

- `connect` — the full connection run for the named agents: install the goga skill bundle centrally into `~/.goga/skills/`, symlink it into each agent's skills directory, auto-discover the installed `goga_tool_*` packages and surface their skills and pipelines, and record the agents in `~/.goga/connect.yml`. `force_overwrite` replaces existing skills that goga does not own. Returns the exit code.
- `install_pipelines` — copy a source directory's flat `*.yml` pipeline-files into `~/.goga/pipelines/` namespaced as `<tool>:<name>.yml` (a residual conflict on the destination is resolved with the `force_overwrite` semantics).
- `resync_registered_agents` — re-run the connection for every agent recorded in the home `connect.yml` — the re-sync invoked by `goga install`, `goga uninstall`, and `goga upgrade` after they change the installed package set.

## Example

```python
from goga.connect import connect

exit_code = connect(["claude", "opencode"], force_overwrite=False)
```
