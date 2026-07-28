# Functional Domains — goga facade

The `goga` package is the root facade of the project. It re-exports the public surface (`AST`, `app`) and decomposes the system into top-level functional domain cells. Each domain owns an independent responsibility zone with a stable API boundary.

This document is an orientation map for consumers of the `goga` facade — it lists the top-level domains, their cell paths, and a one-line responsibility statement per domain. It does not impose any obligation on the domain cells; for behavioral contracts, consult the CODEMANIFEST of each cell.

## Domain packages

Each domain is imported directly from its subpackage:

```python
from goga.ast import AST
from goga.build import build
from goga.connect import connect
from goga.contract import contract
from goga.init import InitLogic, Questionnaire
from goga.pipeline import run_pipeline
from goga.runtime import resolve_runtime_dir
from goga.schema import schema
from goga.usages import sync
```

Note: `goga.ast` is the only domain re-exported at the facade level (`from goga import AST`). All other domains must be imported via their full subpackage path.

## Domain list

| Domain     | Cell                | Responsibility                                                                              |
|------------|---------------------|---------------------------------------------------------------------------------------------|
| `ast`      | `goga/ast/`         | Construct and validate a tree of CODEMANIFEST documents                                     |
| `build`    | `goga/build/`       | Orchestrate code builds through ralphex                                                     |
| `connect`  | `goga/connect/`     | Centralized install of goga skills/commands/pipelines into `~/.goga/` with per-agent registry and re-sync |
| `contract` | `goga/contract/`    | Work with an implemented contract in a specific programming language                        |
| `init`     | `goga/init/`        | Interactive goga project initialization — user survey and configuration file generation    |
| `pipeline` | `goga/pipeline/`    | End-to-end pipeline workflow — discovery, entity model, run coordination, in-container CLI  |
| `runtime`  | `goga/runtime/`     | Pure leaf utilities for runtime-directory path composition (`~/.goga/runtime/...`)          |
| `schema`   | `goga/schema/`      | Generate the CODEMANIFEST project JSON schema                                              |
| `usages`   | `goga/usages/`      | Config-driven synchronization of cell-level usages from declared git dependencies           |

## Per-domain brief

### ast
Defines a project that constructs and validates a tree of CODEMANIFEST documents. Exposes the `AST` facade for navigation and the rule engine that enforces DSL correctness across the project.

### build
Owns the code build orchestration logic through ralphex. Coordinates container launch, runtime-directory preparation, and ralphex invocation.

### connect
Centralized goga skill/command/pipeline installation logic. Assets are installed once into `~/.goga/`, agents receive symlinks into `~/.goga/`, and a per-agent connection registry is maintained at `~/.goga/connect.yml`. Provides the shared re-sync that re-applies activation to every registered agent after a package change.

### contract
Working with an implemented contract in a programming language. Dispatches to language-specific subcells (`goga/contract/python`, `goga/contract/golang`, `goga/contract/kotlin`, `goga/contract/swift`, `goga/contract/javascript`) and compares CODEMANIFEST signatures against the live implementation.

### init
Interactive goga project initialization — user survey and configuration file generation. Drives the questionnaire, collects answers, and emits the project's `.goga/config.yml`.

### pipeline
Cell that owns the entire pipeline workflow: discovery of `*.yml` pipeline files across the project and user pipeline directories, the pipeline-file entity model, run coordination (including optional workflow resolution), and the in-container CLI entrypoint `pipeline_cli`.

### runtime
Pure leaf utilities module for runtime-directory path composition. Owns the single shared formula `~/.goga/runtime/<purpose>/<normalized_project>/<branch>/<*suffix_parts>` and exposes two atomic helpers plus one composite routine. Consumers call `resolve_runtime_dir` with their purpose and optional suffix.

### schema
This manifest defines how the `schema` routine generates the CODEMANIFEST project JSON schema.

### usages
Config-driven synchronization of cell-level usages from declared git dependencies into `.goga/usages/<group>/<dep>/`.
