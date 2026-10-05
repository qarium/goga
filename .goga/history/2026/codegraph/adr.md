# Codegraph: contract extractors are the single source of type truth

Status: accepted

`goga codegraph` derives its CODEMANIFEST-true type view by reusing the
existing per-language extractors through the `goga/contract` dispatcher
(`contract(lang, cell_path)`) — one call per scanned directory per analyzed
language, keeping only the names. The alternative — a codegraph-owned analyzer
duplicating the per-language facade rules — was rejected: the rules would
inevitably drift from the extractors, and reuse is what makes the view
CODEMANIFEST-true by construction (PRD C1, SC5): codegraph shows exactly what
`goga contract` compares. Signatures are discarded; only names are needed.

## Considered options

- Reuse the `goga/contract` extractors per directory (accepted).
- A dedicated codegraph analyzer re-implementing the facade rules (rejected —
  rule drift, double maintenance).
- TypeScript folded into the javascript facade (rejected for this change —
  the tree-sitter-js grammar does not parse TS properly; extending
  `goga/contract/javascript` is future work, `.js`/`index.js` only for now).

## Language selection and detection

Priority: `--lang` > `language` from `.goga/config.yml` > auto-detect by
marker files. When the config exists, its `language` restricts discovery to
that one language — other languages are not considered (the `goga contract`
precedent). Markers are the files the extractor of the language actually
consumes: python `.py`; golang `.go` excluding `_test.go`; javascript
`index.js`; kotlin `.kt`; swift `.swift`. An unsupported language — from
`--lang` or from the config (e.g. `language: cpp`, valid goga config with no
extractor) — is a clean stderr error, exit 1, mirroring
`goga/contract/dispatcher.py` (`ValueError("unsupported language")` wrapped
into `click.ClickException`).

## Consequences

- A present-but-invalid `.goga/config.yml` is a clean error (exit 1, one
  stderr message, no stdout, no traceback) — the schema error convention. This
  deliberately diverges from `goga lint`, which runs unfiltered on any config
  failure: codegraph is a one-shot analysis where silently ignoring a broken
  config would produce wrong exclusions with no explanation. An absent config,
  a missing `lint` section, or an empty `lint.ignore` simply means no
  exclusions (success).
- Walk semantics follow `AST` verbatim: only directories whose normalized
  relative path exactly matches a `lint.ignore` entry are skipped (globs are
  literal, files are never matched), `.project` is always skipped, and there
  is no special-casing of hidden directories — strictly PRD C3, so a `.venv`
  walk cost is the user's `lint.ignore` responsibility. Symlinked directories
  are not descended (determinism, cycle safety).
- Failure semantics refined against PRD R17: an exception while reading or
  extracting a file (e.g. PermissionError, broken encoding) is a clean error
  naming the file and the language, exit 1; a syntactically broken but
  readable file is not an error — tree-sitter degrades gracefully and whatever
  is extractable is extracted.
- Node contract: `cell` is the normalized relative POSIX path from the
  invocation directory (root is `.`); `types` is the deduplicated union of
  extractor names per directory (a CODEMANIFEST cannot declare duplicate
  names), sorted lexicographically in byte order; `children` are sorted by
  `cell` path so output never depends on filesystem enumeration order.
- Open question deferred to the design stage: the cell layout and CODEMANIFEST
  wiring of the codegraph command itself (discover does not design cells).
