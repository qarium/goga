# Task: `codegraph` command

Create a `codegraph` command for all supported languages (python, golang, javascript, kotlin, swift).

The command must show a schema similar to `goga schema`. The main goal of the command is to serve as the init process for creating cells based on code that already exists in a project. Therefore, `codegraph` must show only those types that will be represented in CODEMANIFEST, and must obey the general rules of building cells.

Cell links must account for imports between cells, not only for the types listed inside each cell. This requires a two-pass algorithm:

1. First pass: collect all facades and all imports across the project.
2. Second pass: resolve imports against the facades and build the cell-to-cell links.
