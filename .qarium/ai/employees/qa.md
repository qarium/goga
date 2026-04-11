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

### Helpers

| Helper | Location | Purpose |
|--------|----------|---------|

### Conventions

- Naming: `test_<what>_<scenario>`
- Never mock `builtins.open` — use `tmp_path` fixture
- Integration tests use `pytest.mark.skipif` when external tools unavailable

## Lessons

| Problem | Why | How to prevent |
|---------|-----|----------------|
