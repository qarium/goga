# Schema — Configuration

The schema domain reads **no section of `.goga/config.yml`** — the export is fully scoped by the CLI arguments (the positional cells, `--max-depth`, `--depends-on`).

The cells it walks come from the project structure itself (every directory with a `CODEMANIFEST` — see [Cell](../../cell/index.md)). The general configuration model of the product is covered in [Configuration](../../configuration/index.md).
