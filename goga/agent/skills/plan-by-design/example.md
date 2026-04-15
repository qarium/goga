# Example: DSL-to-Ralphex Plan Compilation

This example shows how a `CODEMANIFEST` DSL is compiled into a ralphex-compatible execution plan.

---

## Input: CODEMANIFEST

```yaml
Imports:
  - Types:
      - User
    From: "identity"

Usages:
  - pydantic: .specs/pydantic.md

Annotations: |
  User management service with validation.

---

"->User": {}

"UserService()":
  location: service.py
  annotations: |
    Service for creating and managing users.
  methods:
    "create_user(name: str) -> result:User": |
      Creates a new user and validates input before creating the entity.
      Name must be non-empty and contain only alphanumeric characters.
    "get_user(user_id: int) -> user:User": |
      Returns user by ID. Raises ValueError if not found.

"format_user(user: User) -> formatted:str":
  location: formatters.py
  annotations: |
    Formats user data as a display string.
```

---

## Output: Ralphex Plan (`docs/plans/user-service.md`)

```markdown
# Plan: user-service

## Goal

Implement user management service package with:
- `UserService` class in `service.py` with `create_user` and `get_user` methods
- `format_user` standalone function in `formatters.py`
- Re-export `User` type through package facade
- Full contract test coverage

## Context

### Contract Surface

**Entity: `UserService()`**
- Kind: class
- Declared `location`: `service.py`
- Facade obligation: must be importable from package
- Properties: (none declared)
- Methods:
  - `create_user(name: str) -> result:User` — validates input (non-empty, alphanumeric), creates User entity
  - `get_user(user_id: int) -> user:User` — returns user by ID, raises ValueError if not found
- Semantic requirements from descriptions: name validation (non-empty, alphanumeric), ValueError on missing user
- Imported dependencies: `User` from `identity`
- Annotations context: "Service for creating and managing users."

**Entity: `format_user(user: User) -> formatted:str`**
- Kind: function
- Declared `location`: `formatters.py`
- Facade obligation: must be importable from package
- Semantic requirements from descriptions: formats user data into display string
- Imported dependencies: `User` from `identity`
- Annotations context: "Formats user data as a display string."

### Re-exports
- `User` — from `identity` via `Imports`, must be importable from `__init__.py`
- Hierarchy constraint (for `Imports` only): source must be at a lower filesystem level

### Usages Context
- `pydantic` — spec at `.specs/pydantic.md`, may be used for data validation

### External Dependencies
- `User` type from `identity` (internal contract dependency)
- `pydantic` from `Usages` (external library for data validation)

## Facts
- Package facade must expose `UserService`, `format_user`, and `User`
- `UserService` must be in `service.py`
- `format_user` must be in `formatters.py`
- `User` is an imported contract dependency, not locally defined
- `create_user` must validate name is non-empty and alphanumeric
- `get_user` must raise `ValueError` when user not found

## Assumptions
- Assumption: `User` from `identity` is a class with at least `name` and `id` attributes
- Basis: method signatures reference `User` as return type and parameter
- Criticality: medium
- Safe to proceed without confirmation: yes

## Open Questions
- (none in default mode)

## Gap Analysis
- No existing code in package — all entities need implementation from scratch
- No existing tests — full test suite needed
- No existing `__init__.py` — needs creation

---

## Tasks

### Task 1: Create package structure and facade (infrastructure)

Set up the package directory structure and `__init__.py` to expose all contract entities on the facade. The package must make `UserService`, `format_user`, and re-exported `User` importable.

- [ ] Create `__init__.py` with imports for `UserService` (from `service.py`), `format_user` (from `formatters.py`), and re-export `User` from its source
- [ ] Create empty `service.py` and `formatters.py` placeholder files
- [ ] Verify facade availability: `python -c "from package import UserService, format_user, User"`
- [ ] Lint: `ruff check src/` — fix formatting if needed

### Task 2: Implement UserService with create_user and get_user

Implement the `UserService` class in `service.py` with constructor, `create_user`, and `get_user` methods. `User` is imported from `identity` contract — do not redefine it locally.

Annotations context: "Service for creating and managing users."

- [ ] **Contract tests**: Create `tests/test_user_service.py` with tests for: `from package import UserService` (facade), `UserService` has `create_user(name: str) -> User` and `get_user(user_id: int) -> User` methods (API shape) — expected to fail
- [ ] **Code**: Implement `UserService` class in `service.py` with `__init__` and internal storage `_users: dict[int, User]`
- [ ] **Code**: Implement `create_user(name: str) -> User` — validate name (non-empty, alphanumeric), create `User`, store and return it
- [ ] **Code**: Implement `get_user(user_id: int) -> User` — lookup by ID, raise `ValueError` if not found, return `User` when found
- [ ] **Verify interfaces**: `pytest tests/test_user_service.py -v` — contract tests must pass
- [ ] **Logic tests**: Add tests for: positive `create_user` with valid name, negative `create_user` with empty name, negative `create_user` with non-alphanumeric name, positive `get_user` with existing ID, negative `get_user` with non-existent ID
- [ ] **Debug**: `pytest tests/ -x` — fix implementation until all tests pass
- [ ] **Re-check contracts**: `python -c "from package import UserService; svc = UserService()"` — verify facade
- [ ] **Lint**: `ruff check src/` — fix formatting, decompose if needed

### Task 3: Implement format_user function

Implement `format_user(user: User) -> str` in `formatters.py`. Standalone function, not a class method.

Annotations context: "Formats user data as a display string."

- [ ] **Contract tests**: Create `tests/test_format_user.py` with tests for: `from package import format_user` (facade), `format_user` is callable with `(user: User) -> str` (API shape) — expected to fail
- [ ] **Code**: Implement `format_user(user: User) -> str` in `formatters.py` — format user data into readable string
- [ ] **Verify interfaces**: `pytest tests/test_format_user.py -v` — contract tests must pass
- [ ] **Logic tests**: Add tests for: returns non-empty string for valid `User`, handles `User` with unusual characters in name
- [ ] **Debug**: `pytest tests/ -x` — fix implementation until all tests pass
- [ ] **Re-check contracts**: `python -c "from package import format_user"` — verify facade
- [ ] **Lint**: `ruff check src/` — fix formatting if needed

### Task 4: Integration tests for user management flow

Create integration tests verifying cross-entity interactions between `UserService` and `format_user`.

- [ ] Create test file `tests/test_user_integration.py`
- [ ] Test full flow: create user via `UserService`, format via `format_user`, verify output
- [ ] Test edge case: format user with special characters after creation
- [ ] Run validation: `pytest tests/test_user_integration.py -v`

---

## Validation Commands

- `python -c "from package import UserService, format_user, User"`: Verify all facade entities are importable
- `pytest tests/ -x`: Run all tests
- `ruff check src/`: Lint check

---

## Done Criteria

- [ ] `UserService` is implemented in `service.py`
- [ ] `format_user` is implemented in `formatters.py`
- [ ] `User` is re-exported from package facade
- [ ] All entities are importable from package `__init__.py`
- [ ] `create_user` validates name (non-empty, alphanumeric)
- [ ] `get_user` raises `ValueError` when user not found
- [ ] Contract tests cover all facade entities and behaviors
- [ ] All validation commands pass
- [ ] No new packages created outside the current package boundary
```

---

## Key Compilation Patterns

### Pattern 1: Infrastructure-first with simplified workflow
Task 1 sets up the package structure and facade. Infrastructure tasks use a simplified workflow: code → verify → lint (no TDD cycle).

### Pattern 2: TDD workflow for entity implementation
Task 2 implements `UserService` using the full TDD cycle: contract tests first (they fail), then code, verify interfaces, logic tests, debug, re-check, lint. Methods sharing the same `location` are grouped in a single task.

### Pattern 3: Standalone functions as separate TDD tasks
Task 3 implements `format_user` independently since it has its own `location`, following the same TDD cycle.

### Pattern 4: Integration tests after all coding tasks
Task 4 is an integration test task placed **after all coding tasks for the same package**. It verifies cross-entity interactions that individual TDD tasks don't cover.

**Single package example** (this case): infra → TDD coding tasks → integration tests.
**Multi-package example** (conceptual):
```
Package A: Task 1 (infra) → Task 2 (entity TDD) → Task 3 (methods TDD) → Task 4 (integration tests for A)
Package B: Task 5 (infra) → Task 6 (entity TDD) → Task 7 (integration tests for B)
Package C (depends on A,B): Task 8 (infra) → Task 9 (entity TDD) → Task 10 (integration tests for C)
```

### Pattern 5: Each task is self-contained
Every task includes enough context for an AI agent to implement it without reading other tasks.

### Pattern 6: TDD cycle validates each task
Every coding task validates itself: contract tests verify the interface, logic tests verify behavior, debug fixes any issues — all within the same task.

---

## Anti-Patterns to Avoid

Bad plan would:
- Put all implementation in one giant task
- Write coding tasks without contract tests (violates TDD workflow)
- Use vague steps like "implement the service" without specifics
- Omit validation commands from tasks
- Create tasks that require reading previous tasks for context
- Forget re-export obligations
- Ignore `location` placement requirements
- Fix test code instead of implementation code during the debug step
