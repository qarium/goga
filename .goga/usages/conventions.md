# General Conventions

Mandatory rules for all Python code in this project. Strict deterministic specification.

## Engineering Principles

Code in this repository MUST prioritize:

- readable, explicit code
- predictable, straightforward control flow
- stable abstractions
- operational stability and maintainability

---

# Development

## Constraints

- Compatible with Python 3.10 and above only
- Use `pyproject.toml` for configuration
- Execute all code within a virtualenv environment — create it if missing

## Imports

RULES:

1. Use relative imports for all intra-package references
2. Use absolute imports only for stdlib and third-party packages

```python
# Valid: intra-package
from .models import User
from ..utils import helper

# Valid: stdlib and third-party
import logging
from pydantic import BaseModel

# Forbidden: absolute import within the same package
from myapp.models import User
```

All subsequent import patterns MUST follow relative imports for intra-package references.

## Data Models

RULES:

1. Use pydantic for all data models and request/response schemas
2. All data model classes MUST use `kw_only=True` (Python 3.10+ syntax)
3. Set empty defaults (empty string, zero, etc.) for all fields — use `None` only for fields that represent the explicit
   absence of a value

## Logging

RULES:

1. Use `logging` as the default logging library
2. Use `structlog` when structured logging is required across the service
3. Use `loguru` only in single-file CLI utilities with a single entry point

```python
import logging

logger = logging.getLogger(__name__)
```

Operational logs **MUST**:

- include contextual metadata
- be machine-readable
- support filtering and aggregation

```python
logger.info(
    "user created",
    extra={
        "user_id": user.id,
        "email": user.email,
    },
)
```

All log output MUST follow structured format with contextual metadata.

Formatting:

- lowercase messages
- concise operational wording
- stable log event names

Log levels MUST reflect operational importance and required reaction.

### DEBUG

DEBUG is used for diagnostic information useful during development or incident investigation.

Use DEBUG for:

- intermediate state
- request/response details
- branch decisions
- retries
- external payload previews
- performance diagnostics

### INFO

INFO is used for important normal business operations.

INFO logs SHOULD describe:

- lifecycle events
- significant state transitions
- externally observable operations

### WARNING

WARNING indicates abnormal but recoverable situations.
The operation continues, but attention MAY be required.

Use WARNING when:

- fallback logic is activated
- retryable failures occur
- degraded behavior is detected
- unexpected input is received

### ERROR

ERROR is used when an operation cannot be completed.

Use ERROR when:

- a request fails
- data cannot be persisted
- external dependency prevents operation completion
- invariant violation affects functionality

### CRITICAL

CRITICAL is reserved for conditions requiring immediate operator intervention.

Use CRITICAL only when:

- the process cannot continue execution
- data corruption is detected or imminent
- core infrastructure dependencies are unreachable
- manual operator intervention is required within minutes

### Log Content Restrictions

Log messages MUST contain only non-sensitive operational data. Exclude secrets, credentials, tokens, and personal
sensitive data from all log output.

## Code Formatting

Inside function and method bodies, logical blocks are separated by **one blank line**:

- Variable initialization is separated from conditional constructs and loops
- Loops and conditions are separated by a blank line
- Data preparation is separated from its processing
- Processing is separated from returning the result

## Docstrings

All public functions, methods, and classes **MUST** have docstrings. Format — **Google style**:

```python
def function_name(param1: str, param2: int = 0) -> bool:
    """Brief description of the function.

    Detailed description when necessary.

    Args:
        param1: Description of the first parameter.
        param2: Description of the second parameter.

    Returns:
        Description of the return value.

    Raises:
        ValueError: Condition that triggers this exception.
    """
```

Docstring rules:

- The first line is required, starts with a capital letter, ends with a period
- Include `Args` section when the function accepts parameters
- Include `Returns` section when the function returns a value
- Include `Raises` section when the function raises exceptions beyond built-in types

## Dependencies

All third-party libraries **MUST** be added to `pyproject.toml`. Specify a minimum version for every dependency.

---

# Testing

## Constraints

- Test code must be compatible with Python 3.10 and above

## Tools

- pytest — running tests
- ruff — linting and formatting test code
- pytest-cov — coverage

## Running Tests

- Execute all tests within a virtualenv environment — create it if missing

## Test Structure

Tests mirror the source code structure **directly**, without an intermediate root package directory:

- `<src>/module/file.py` → `tests/module/test_file.py`
- The `tests/` directory contains subdirectories corresponding to nested packages of the root package
- Tests for root package modules (`__main__.py`, `__init__.py`) are placed directly in `tests/` (e.g.,
  `tests/test_main.py`)

RULES:

1. Each test directory MUST contain an `__init__.py`
2. Place local fixtures in `tests/<package>/conftest.py`, shared fixtures in `tests/conftest.py`
3. Place integration tests covering multiple packages directly in `tests/` (e.g., `tests/test_integration.py`)

## Naming

- Files: `test_<module>.py`
- Functions: `test_<what>_<scenario>` (e.g., `test_complexity_with_empty_input`)
- Grouping: `class Test<Component>:`

## Test Types

- **Unit** — every public function/method/class, main scenario and typical data
- **Edge cases**:
    - Empty inputs: `None`, `""`, `[]`, `{}`
    - Boundary values: `0`, negative, very large
    - Invalid types
    - Expected exceptions via `pytest.raises`
- **Integration** — only for interaction between modules/packages

## REST API Testing

Test endpoints by calling the handler function directly via Python call.

## CLI Testing

Test CLI commands by calling the command handler function directly via Python call.

## Boundary Tests

For thresholds, ranges, state transitions — use `@pytest.mark.parametrize` with a table of values including each
boundary.

## Mocks

- Pure logic — write tests without mocks
- File I/O — use the `tmp_path` fixture exclusively
- Subprocesses — `mock.patch` the subprocess call
- External dependencies — `mock.patch` at the import point

Mock only at external boundaries. Keep business logic tests mock-free.

## Miscellaneous

- Use self-documenting test names. Keep comments minimal.
- Skip integration tests with unavailable external dependencies via `pytest.mark.skipif`

## Dependencies

All test libraries **MUST** be added to `pyproject.toml` in the `[project.optional-dependencies]` section under the
`test` key.

---

# Validation Commands

All commands must run in a virtualenv environment. Python 3.10+ compatibility required.

| Purpose             | Command                                  |
|---------------------|------------------------------------------|
| Run all tests       | `pytest tests/ -x`                       |
| Run a specific test | `pytest tests/test_<name>.py -v`         |
| Lint                | `ruff check <src>/`                      |
| Facade check        | `python -c "from package import Entity"` |
