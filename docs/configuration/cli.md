# goga config

Read and output configuration values from `.goga/config.yml`.

## Synopsis

```bash
goga config OPTION [OPTION]...
```

## Description

`goga config` loads the project configuration and prints the requested values to stdout. Options are specified as dot-notation paths that traverse the configuration data structure.

Paths use the authored vocabulary of the configuration model — `language`, `image`, `build.agent`, `pipeline.env.KEY`, and so on. The former `lang` key no longer resolves: it was renamed to `language`, and `goga config lang` now fails with `Option not found: lang`.

## Arguments

| Argument | Required | Description |
|---|---|---|
| `OPTION` | yes | One or more dot-notation paths to configuration values (at least one required). |

## Output

Each requested option is printed with a comment header followed by the value:

- Scalar values (`str`, `int`, `bool`) are printed as plain text.
- `null` values are printed as `null`.
- Complex values (`dict`, dataclass) are printed as YAML.

Multiple options are separated by a blank line.

When installed tool packages amend the configuration, a short summary prints to **stderr** — one header plus one line per applied amendment (the tool, the path, `set` or `forced`):

```
config amendments: 2 applied
- hardener set build.agent
- hardener forced topics.base_ref
```

stdout stays values only; no configuration value ever appears in the summary. The printed values are the **effective** (amended) ones. See [Configuration — Hooks](hooks.md).

## Examples

Read the project language:

```bash
goga config language
```

Read the entire build configuration:

```bash
goga config build
```

Read the top-level image and the build executor agent:

```bash
goga config image build.agent
```

## Configuration File

Values are read from `.goga/config.yml`. A minimal configuration:

```yaml
language: python
image: qarium/goga-python-3.12:1.3   # top-level image, shared by build and pipeline (build.image is rejected)
build:
  agent: claude                      # optional at the loader level; goga build raises a ClickException when it is None
  env: {}
```

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | All requested options found and printed |
| `1` | Configuration file not found, invalid, or requested option does not exist; or a hard `config/amend_config` hook failure (a clean error naming the tool and the action — see [Hooks](hooks.md)) |
