# goga sync

Synchronize `.usages/` directories from external dependencies into the local project.

## Synopsis

```bash
goga sync SOURCE [--token TOKEN] [--branch BRANCH]
```

## Description

`goga sync` copies `.usages/` directories from a local path or a remote git repository into `.goga/usages/deps/<dep_name>/` in the current project. This allows you to reuse usage definitions from shared libraries or other goga-managed projects.

The dependency name is extracted automatically from the source path or git URL.

## Arguments

| Argument | Required | Description |
|---|---|---|
| `SOURCE` | yes | A local directory path or a git repository URL. |

## Supported Source Types

### Local Path

Provide a filesystem path to the dependency root. Goga walks the directory tree and discovers all `.usages/` folders.

```bash
goga sync /path/to/dependency
```

### Git Repository (HTTPS)

Provide an HTTPS URL. The repository is cloned to a temporary directory, `.usages/` folders are discovered, and the temp directory is cleaned up.

```bash
goga sync https://github.com/org/repo.git
```

For private repositories, pass a token via `--token`. The token is injected into the URL for authentication:

```bash
goga sync https://github.com/org/private-repo.git --token ghp_xxxx
```

### Git Repository (SSH)

SSH URLs (`git@...` and `ssh://...`) are also supported:

```bash
goga sync git@github.com:org/repo.git
```

## Options

| Option | Default | Description |
|---|---|---|
| `--token` | none | Authentication token for HTTPS git URLs. The token is redacted from error messages. |
| `--branch` | default branch | Git branch to clone. |

## Destination

Files are placed under `.goga/usages/deps/<dep_name>/`, preserving the relative directory structure from the source. Any previous sync for the same dependency is replaced.

## Examples

Sync from a local directory:

```bash
goga sync ../shared-lib
```

Sync from a public GitHub repository:

```bash
goga sync https://github.com/qarium/shared-types.git
```

Sync from a private repository with a token:

```bash
goga sync https://github.com/company/internal-lib.git --token ghp_abc123
```

Sync a specific branch:

```bash
goga sync https://github.com/org/repo.git --branch feature/new-usages
```

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Sync completed successfully |
| `1` | Sync failed (path not found, git not installed, clone failed, no `.usages/` found) |
