# Sync API — goga/sync

## Overview

The `goga.sync` module synchronizes .usages/ files from a local path
or git repository into `.goga/usages/deps/`.

## Usage

```python
from goga.sync import sync

# Local path
exit_code = sync(source="/path/to/external/project/goga")

# Public git repository
exit_code = sync(source="https://github.com/owner/repo")

# Private git repository (token and branch)
exit_code = sync(
    source="https://github.com/owner/private-repo",
    token="ghp_xxx",
    branch="v2.0"
)

# SSH
exit_code = sync(source="git@github.com:owner/repo.git")
```

## Return Value

- `0` — success
- `1` — failure (path does not exist, missing .usages/, I/O error, git error)

## Side Effects

- Creates or overwrites the `.goga/usages/deps/<name>/` directory tree
- In git mode, allocates and removes a temporary directory
- Requires `git` available in PATH for git-mode operation

## Synchronization Result

```
Source path: /path/to/external/goga/
  .usages/dsl.md
  commands/.usages/cli-commands.md

Result: .goga/usages/deps/goga/
  .usages/dsl.md
  commands/.usages/cli-commands.md
```
