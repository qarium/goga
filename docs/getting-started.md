# Getting Started

## Prerequisites

- Python 3.10 or later
- pip or uv package manager

## Install goga

```bash
pip install goga
```

## Initialize a project

Run the interactive initialization wizard:

```bash
goga init
```

The wizard will prompt you for:

1. **Language** -- Select your project language: `python`, `golang`, `kotlin`, `swift`, or `javascript`
2. **Convention** -- Optionally download language-specific conventions from the goga-lang-conventions repository
3. **Codemanifest usages** -- Optional named practices (key-value pairs) for your project
4. **Codemanifest annotations** -- Optional free-text instructions for AI agents
5. **Agent** -- Select your AI executor: `claude` (more agents coming soon)
6. **Docker image** -- Choose a prebuilt language image or enter a custom one
7. **Dockerfile** -- Optionally generate a `Dockerfile` based on the selected image
8. **Environment variables** -- Set agent-specific env vars (e.g., `ANTHROPIC_API_KEY`)

### What `goga init` creates

```
.goga/
  config.yml              # Project configuration
  usages/
    conventions.md        # Language conventions (if downloaded)
Dockerfile                # Optional, if you chose to create one
```

## Create a CODEMANIFEST

A CODEMANIFEST file describes the contract of a cell (a self-contained module). Place it in the root directory of your cell.

### Basic structure

A CODEMANIFEST consists of three YAML documents separated by `---`:

**Header** -- Imports, usages, and annotations:

```yaml
Imports:
  - Types:
      - MyType
    From: path/to/other/cell

Usages:
  conventions: .goga/usages/conventions.md

Annotations: |
  Description of this cell's purpose and instructions.
```

**Body** -- Type declarations (entities and routines):

```yaml
"process_data(input: str) -> result:dict":
  location: processor.py
  annotations: |
    Processes the input and returns a result.
```

**Footer** -- Metadata:

```yaml
---
Author: Your Name
CreatedAt: 08/06/26
Description: |
  A brief description of this cell.
```

### Minimal example

```yaml
---

---

"hello() -> void:null":
  location: main.py
  annotations: |
    Prints hello world.

---
Author: Developer
CreatedAt: 08/06/26
Description: Hello world cell
```

## Validate

Run the linter to check all CODEMANIFEST files in your project:

```bash
goga linter .
```

The linter applies 21 document-level rules and 3 project-level rules to verify structural correctness, import consistency, usage validity, and more.

## Next steps

- [Configuration](configuration.md) -- Full config reference for `.goga/config.yml`
- [Examples](examples.md) -- CODEMANIFEST examples for all DSL features
- [CLI Reference](cli-reference.md) -- All available commands and options
