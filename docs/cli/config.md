# goga config

Read and output configuration values from `.goga/config.yml`.

## Synopsis

```bash
goga config OPTION [OPTION]...
```

## Description

`goga config` loads the project configuration and prints the requested values to stdout. Options are specified as dot-notation paths that traverse the configuration data structure.

The alias `language` can be used in place of `lang` for convenience.

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

## Examples

Read the project language:

```bash
goga config lang
```

Read the entire build configuration:

```bash
goga config build
```

Read the top-level image and the task executor agent:

```bash
goga config image build.task_executor.agent
```

Use the `language` alias:

```bash
goga config language
```

## Configuration File

Values are read from `.goga/config.yml`. A minimal configuration:

```yaml
language: python
image: qarium/goga-python-3.12:1.0   # top-level image, shared by build and pipeline (build.image is rejected)
build:
  task_executor:
    agent: claude                    # optional at the loader level; goga build raises a ClickException when it is None
    env: {}
```

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | All requested options found and printed |
| `1` | Configuration file not found, invalid, or requested option does not exist |
