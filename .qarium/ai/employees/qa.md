## Config

| Setting          | Value                              |
|------------------|------------------------------------|
| run_tests_cmd    | `pytest --tb=short`                |
| lint_cmd         | `ruff check goga/ tests/`          |
| lint_fix_cmd     | `ruff check --fix goga/ tests/`    |
| format_cmd       | `ruff format --check goga/ tests/` |
| format_fix_cmd   | `ruff format goga/ tests/`         |

## Rules

Project test configuration. Used by the `qarium:employees:qa:feature` skill.

### Mapping

| Source path pattern | Test directory     | Notes         |
|---------------------|--------------------|---------------|
| `goga/**/*.py`      | `tests/goga/`      | Mirror layout |

### Mock Patterns

| Pattern | Example |
|---------|---------|
| tmp_path for CODEMANIFEST fixtures | `tmp_path / "pkg" / "CODEMANIFEST"` write YAML, pass dir to Factory |

### Helpers

| Helper | Location | Purpose |
|--------|----------|---------|
| `_write_codemanifest(directory, content) -> str` | `tests/goga/codemanifest/test_factory.py` | Writes a CODEMANIFEST YAML file into a directory and returns the dir path |

### Conventions

- Naming: `test_<what>_<scenario>`
- Never mock `builtins.open` — use `tmp_path` fixture
- Integration tests use `pytest.mark.skipif` when external tools unavailable
- Python 3.10 compatibility: use `from __future__ import annotations` in source files; use `Optional[X]` not `X | None` in dataclass fields (ruff UP045)
- `CodemanifestRuleError` is an alias for `ManifestRuleError` — import from `goga.codemanifest.errors`

## Lessons

| Problem | Why | How to prevent |
|---------|-----|----------------|
