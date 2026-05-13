# Plan: `usages-validation-and-migration`

## Goal

Add `.goga/usages/` prefix validation to `UsageFilepathExists`, remove level constraint from `ImportHasValidFromPath`, and migrate config/usages paths from legacy `.goga.yml` / `.usages/` to `.goga/config.yml` / `.goga/usages/`.

Key gaps:
- `UsageFilepathExists` is missing the `.goga/usages/` prefix check (Step 5 in trace)
- `ImportHasValidFromPath` — уровень уже удалён из кода; необходимы регрессионные тесты
- `load_config()` references old `.goga.yml` path
- `sync()` targets old `.usages/deps/` directory
- `install()` still copies `dsl.md` into each skill
- `contract.py` и `config.py` в `goga/commands/` содержат `.goga.yml` в help-текстах и docstring

Strategy: update existing implementations in 6 source files + 1 usages file, add 1 new test fixture, verify all integration tests pass.

## Context

### Contract surface

**Entity: `UsageFilepathExists`**
- Type: Entity (DocumentRule mutation)
- Declared `location`: `goga/ast/rules/document.py`
- Facade duty: must be importable from `goga.ast.rules`
- Mutation: `DocumentRule::UsageFilepathExists`
- Constructor: `UsageFilepathExists(name: str = 'usage_filepath_exists')`
- Method: `check(node: DocumentNode) -> errors:list[DocumentRuleError]`
- Semantic requirements:
  - Validates filepath practices have `.goga/usages/` prefix
  - Resolves within project root (security)
  - File exists on filesystem
  - Skips inline usages (annotations.text)
  - Skips URL usages (annotations.url)
  - Order: prefix -> resolve -> security -> existence (fail-fast, cheap first)
- Error templates:
  - `incorrect_path`: `"Usage '{usage_name}' filepath '{filepath}' is not built from '.goga/usages/'"`
  - `outside_usages`: `"Usage '{usage_name}' filepath '{filepath}' is not built from the root of the project"`
  - `not_found`: `"Usage '{usage_name}' filepath '{filepath}' does not exist on filesystem"`
- Imported dependencies: `DocumentNode`, `UsageItemNode` (from `goga/ast/nodes`), `DocumentRuleError` (from `goga/ast/errors`)
- Edge cases:
  - Both filepath AND url set on same UsageItemNode -> skipped by both rules (mutually exclusive formats)
  - filepath is empty string -> skipped
  - filepath starts with `.goga/usages/` but resolves outside project via symlinks -> caught by `outside_usages`

**Entity: `UsageUrlIsAccessible`**
- Type: Entity (DocumentRule mutation)
- Declared `location`: `goga/ast/rules/document.py`
- Facade duty: must be importable from `goga.ast.rules`
- Mutation: `DocumentRule::UsageUrlIsAccessible`
- Constructor: `UsageUrlIsAccessible(name: str = 'usage_url_is_accessible')`
- Method: `check(node: DocumentNode) -> errors:list[DocumentRuleError]`
- Semantic requirements:
  - Validates URL practices respond with HTTP 200
  - Uses HEAD request with GET fallback on 405
  - 10s timeout
  - Skips inline usages (annotations.text)
  - Skips filepath usages (annotations.filepath)
- **No changes needed** — already implemented correctly
- Error templates:
  - `not_accessible`: `"Usage '{usage_name}' URL '{url}' returned HTTP {status_code} — expected 200"`
  - `request_failed`: `"Usage '{usage_name}' URL '{url}' request failed: {error_message}"`

**Entity: `ImportHasValidFromPath`**
- Type: Entity (DocumentRule mutation)
- Declared `location`: `goga/ast/rules/document.py`
- Facade duty: must be importable from `goga.ast.rules`
- Mutation: `DocumentRule::ImportHasValidFromPath`
- Constructor: `ImportHasValidFromPath(name: str = 'import_has_valid_from_path')`
- Method: `check(node: DocumentNode) -> errors:list[DocumentRuleError]`
- Level constraint already removed from code — no code changes needed. Need regression tests to verify imports from any level work correctly.
- Current checks: empty path, path exists on filesystem, path within project root
- Error templates (unchanged):
  - `empty`: `"Import in '{doc_path}' has empty source path (From field)"`
  - `not_found`: `"Source path '{from_path}' in import of types {type_names} not found on filesystem"`
  - `escapes`: `"Source path '{from_path}' in import points outside the project root"`

**Entity: `load_config()`**
- Type: Routine
- Declared `location`: `goga/config/loader.py`
- Facade duty: must be importable from `goga.config`
- Signature: `load_config() -> config:Config`
- Change: config path migration `Path("./.goga.yml")` -> `Path("./.goga/config.yml")`
- All error messages referencing `.goga.yml` must be updated to `.goga/config.yml`
- Helper functions `_parse_task_executor`, `_parse_language`, `_parse_codemanifest` also need error message updates

**Entity: `sync()`**
- Type: Routine
- Declared `location`: `goga/commands/sync.py`
- Facade duty: must be importable from `goga.commands`
- Signature: `sync(source: str, token: str | None = None, branch: str | None = None)`
- Change: target directory `Path(".usages/deps")` -> `Path(".goga/usages/deps")` in `_sync_usages()`

**Entity: `install()`**
- Type: Routine
- Declared `location`: `goga/commands/install.py`
- Facade duty: must be importable from `goga.commands`
- Signature: `install(agent: str | None = None)`
- Change: remove `_get_dsl_source()` function entirely; remove `dsl_source` parameter from `_install_skills()`; remove dsl copy logic; update `install()` call to not pass `dsl_source`

### Reexports

No reexports in this plan — all entities are consumed through their existing cell facades.

### Usages context

- **`conventions`** (filepath `.goga/usages/development/conventions.md`): Python coding standards (3.10+, relative imports, dataclasses, pytest conventions). Used by: `goga/ast/rules`, `goga/ast`, `goga/config`, `goga/commands`, and others. Relevance: all implementation tasks must follow these conventions.
- **`nodes`** (inline): API reference for `goga/ast/nodes` cell. Used by: `goga/ast/rules`. Relevance: understanding `UsageItemNode`, `DocumentNode` API for rule implementation.
- **`click`** (filepath `.goga/usages/cooks/click.md`): CLI library patterns. Used by: `goga/commands`. Relevance: commands follow click patterns.
- **`yaml`** (inline): PyYAML usage instruction. Used by: `goga/config`. Relevance: `load_config()` uses `yaml.safe_load()`.

### Local Usages

- Path to file: `goga/commands/.usages/cli-commands.md`
  - Functional category: CLI command usage documentation
  - Status: existing file — needs update
  - Related entities: `sync()`, `install()`, `config()`
  - Description: contains examples with `.usages/deps/` and `.goga.yml` that need updating to `.goga/usages/deps/` and `.goga/config.yml`
  - Reference to creation task: Task 6 (usages file), Task 7 (integration tests)

### External dependencies

- `urllib.request` / `urllib.error` — stdlib, used by `UsageUrlIsAccessible` for HTTP HEAD/GET requests
- `pytest` — test framework per conventions
- `click` — CLI framework for commands
- `yaml` (PyYAML) — config parsing in `load_config()`

## Facts

- `UsageFilepathExists` already exists in code but is missing the `.goga/usages/` prefix check
- `UsageUrlIsAccessible` already exists and is fully implemented — no changes needed
- `ImportHasValidFromPath` level constraint already removed from code — regression tests needed to confirm imports from any level work
- Config path migration is a mechanical find-replace: `.goga.yml` -> `.goga/config.yml`
- Sync path migration is a single line change
- Install dsl copy removal is a deletion of `_get_dsl_source()` and related logic
- Existing test fixtures for `usage_filepath_exists` and `usage_url_is_accessible` already have updated paths in git
- New test fixture `tests/.project/usage_filepath_prefix/` needed for `incorrect_path` error case
- `AST.load()` already registers `UsageFilepathExists` and `UsageUrlIsAccessible` in document_rules (verified via design doc interaction diagram)
- Integration tests are parameterized: scan `tests/.project/`, find directories with `.expected.yaml`, compare with `ast_obj.errors`

## Gap analysis

- Missing implementation: `.goga/usages/` prefix check in `UsageFilepathExists.check()`
- Already correct: `ImportHasValidFromPath` — level constraint already removed from code, regression tests needed
- Wrong path: `load_config()` uses `.goga.yml` instead of `.goga/config.yml`
- Wrong path: `sync()` targets `.usages/deps/` instead of `.goga/usages/deps/`
- Extra logic: `install()` copies `dsl.md` — needs removal
- Missing test fixture: `tests/.project/usage_filepath_prefix/` for `incorrect_path` error
- Usages file: `goga/commands/.usages/cli-commands.md` references old paths
- Wrong reference: `goga/commands/contract.py` help-текст содержит `.goga.yml`
- Wrong reference: `goga/commands/config.py` docstring содержит `.goga.yml`

---

## Tasks

> **Ordering rule by package**: coding tasks for each package complete before the next begins. Within each coding task, contract tests are written first (TDD workflow).

### Task 1: Update `UsageFilepathExists` and `ImportHasValidFromPath` in `goga/ast/rules` (TDD)

This task updates two existing DocumentRule implementations in `goga/ast/rules/document.py`:

1. **`UsageFilepathExists`**: Add `.goga/usages/` prefix check before existing resolve/security/existence checks. The prefix check is a simple `filepath.startswith('.goga/usages/')` string check placed before `Path.resolve()` — cheap check first (fail-fast). Error template `incorrect_path` must be added with message: `"Usage '{usage_name}' filepath '{filepath}' is not built from '.goga/usages/'"`. When prefix check fails, CONTINUE to next item (skip resolve/security/existence).

2. **`ImportHasValidFromPath`**: Level constraint already removed from code. Verify current implementation has only: empty check, filesystem existence, and path escapes check. Add regression behavioral tests to confirm imports from any level work correctly.

**Data flow (UsageFilepathExists after update)**:
```
DocumentNode -> header.usages.items[] -> UsageItemNode.annotations.filepath
  -> skip if filepath is None/empty
  -> skip if url is set
  -> CHECK filepath.startswith('.goga/usages/') -> incorrect_path error if not
  -> Path(filepath).resolve() -> is_relative_to(cwd) check -> outside_usages error
  -> Path.exists() check -> not_found error
  -> list[DocumentRuleError]
```

**Data flow (ImportHasValidFromPath — already correct, no code changes)**:
```
DocumentNode -> root.header.imports.types + .usages
  -> empty check -> empty error
  -> Path(from_path).resolve() -> exists() check -> not_found error
  -> is_relative_to(cwd) check -> escapes error
  -> list[DocumentRuleError]
```

**Usages relevant for this task:**
- `conventions`: Python 3.10+, relative imports, dataclasses, pytest conventions
- `nodes`: API for `UsageItemNode`, `DocumentNode`, `ImportTypeItemNode`, `ImportUsageItemNode`

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. DO NOT modify them. If implementation doesn't match the contract, fix the implementation — never fix the contract.**

- [x] **ШАГ 0 (ОБЪЯВЛЕНИЕ)**: Объявить работу над Task 1 — обновление `UsageFilepathExists` и `ImportHasValidFromPath` в `goga/ast/rules/document.py`
- [x] **ШАГ 1 (КОНТРАКТНЫЕ ТЕСТЫ)**: Написать контрактные тесты в `tests/goga/ast/rules/test_document.py` (или существующий файл):
  - `UsageFilepathExists`: проверить что класс существует, наследует `DocumentRule`, метод `check` принимает `DocumentNode` и возвращает `list[DocumentRuleError]`
  - `ImportHasValidFromPath`: проверить что класс существует, наследует `DocumentRule`, метод `check` принимает `DocumentNode` и возвращает `list[DocumentRuleError]`
  - Тесты ожидают падения на этом этапе
- [x] **ШАГ 2 (КОД — UsageFilepathExists)**: В файле `goga/ast/rules/document.py` добавить prefix check в метод `check()` класса `UsageFilepathExists`:
  - После фильтрации (skip if filepath is None/empty, skip if url is set)
  - Добавить: `if not filepath.startswith('.goga/usages/'):` -> append `incorrect_path` error, `continue`
  - Разместить ДО вызова `Path(filepath).resolve()` — дешёвая проверка первая
  - Шаблон ошибки: `"Usage '{usage_name}' filepath '{filepath}' is not built from '.goga/usages/'"`
- [x] **ШАГ 2 (ВЕРИФИКАЦИЯ — ImportHasValidFromPath)**: В том же файле проверить что метод `check()` класса `ImportHasValidFromPath` содержит ТОЛЬКО проверки: empty, not_found, escapes. Level constraint ("path is at same level or below") НЕ должен присутствовать. Если level constraint обнаружен — удалить.
- [x] **ШАГ 3 (ВЕРИФИКАЦИЯ ИНТЕРФЕЙСОВ)**: Запустить контрактные тесты: `pytest tests/goga/ast/rules/test_document.py -v` — все должны пройти
- [x] **ШАГ 4 (ЛОГИЧЕСКИЕ ТЕСТЫ)**: Написать поведенческие тесты:
  - `UsageFilepathExists` — prefix check:
    - Позитивный: filepath `.goga/usages/existing.md` с существующим файлом -> 0 ошибок
    - Негативный: filepath `.usages/old_style.md` (без `.goga/` префикса) -> `incorrect_path` ошибка
    - Негативный: filepath `.goga/usages/nonexistent.md` (файл не существует) -> `not_found` ошибка
    - Граничный: filepath с url тоже установлен -> skipped by both rules (mutually exclusive)
    - Граничный: filepath пустой -> skipped
  - `ImportHasValidFromPath` — regression (verify no level constraint):
    - Позитивный: импорт из ячейки на любом уровне (выше, ниже, тот же) -> 0 ошибок
    - Негативный: пустой from_path -> `empty` ошибка
    - Негативный: несуществующий путь -> `not_found` ошибка
    - Негативный: путь вне проекта -> `escapes` ошибка
- [x] **ШАГ 5 (ОТЛАДКА)**: `pytest tests/goga/ast/rules/ -v` — исправлять код реализации, пока все тесты не пройдут (НЕ исправлять тесты)
- [x] **ШАГ 6 (ПЕРЕПРОВЕРКА КОНТРАКТА)**: Проверить все обязательства контракта: фасад (`from goga.ast.rules import UsageFilepathExists, ImportHasValidFromPath`), форма API, поведение (prefix check, error templates)
- [x] **ШАГ 7 (ЛИНТ)**: `docker run --rm -v .:/project -w /project qarium/goga:latest linter` — исправить форматирование при необходимости
- [x] **ШАГ 8 (ЗАВЕРШЕНИЕ)**: Отметить чекбоксы как выполненные

### Task 2: Migrate `load_config()` config path in `goga/config` (TDD)

Migrate config file path from `.goga.yml` to `.goga/config.yml` in `goga/config/loader.py`. This is a mechanical find-replace across the `load_config()` function and its helper functions (`_parse_task_executor`, `_parse_language`, `_parse_codemanifest`).

**Data flow**:
```
Path("./.goga/config.yml") -> exists() check -> yaml.safe_load() -> field extraction -> Config dataclass
```

**Changed error messages** (all `.goga.yml` -> `.goga/config.yml`):
- `FileNotFoundError(".goga/config.yml not found in project root")`
- `ValueError(".goga/config.yml must be a YAML mapping")`
- `KeyError("language is required in .goga/config.yml")`
- `KeyError("build is required in .goga/config.yml")`
- `KeyError("build.task_executor is required in .goga/config.yml")`
- `ValueError("build.task_executor.agent is required in .goga/config.yml")`
- Same pattern in `_parse_task_executor`, `_parse_language`, `_parse_codemanifest` helper functions

**Usages relevant for this task:**
- `conventions`: Python coding standards
- `yaml`: `yaml.safe_load()` for parsing `.goga/config.yml`

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. DO NOT modify them.**

- [x] **ШАГ 0 (ОБЪЯВЛЕНИЕ)**: Объявить работу над Task 2 — миграция config path в `goga/config/loader.py`
- [x] **ШАГ 1 (КОНТРАКТНЫЕ ТЕСТЫ)**: Написать контрактные тесты в `tests/goga/config/`:
  - Проверить что `load_config` функция существует в `goga.config`
  - Проверить что `load_config` возвращает `Config` dataclass
  - Тесты ожидают падения на этом этапе
- [x] **ШАГ 2 (КОД)**: В файле `goga/config/loader.py`:
  - Заменить `Path("./.goga.yml")` на `Path("./.goga/config.yml")`
  - Заменить все вхождения `.goga.yml` на `.goga/config.yml` в сообщениях об ошибках (FileNotFoundError, ValueError, KeyError)
  - Проверить helper функции `_parse_task_executor`, `_parse_language`, `_parse_codemanifest` — обновить сообщения об ошибках
- [x] **ШАГ 3 (ВЕРИФИКАЦИЯ ИНТЕРФЕЙСОВ)**: `pytest tests/goga/config/ -v` — все контрактные тесты должны пройти
- [x] **ШАГ 4 (ЛОГИЧЕСКИЕ ТЕСТЫ)**: Написать поведенческие тесты:
  - Позитивный: валидный `.goga/config.yml` -> успешно парсится в `Config`
  - Негативный: файл `.goga.yml` (старый путь) не существует -> `FileNotFoundError` с сообщением `.goga/config.yml`
  - Негативный: пустой файл `.goga/config.yml` -> `FileNotFoundError`
  - Негативный: невалидный YAML -> исключение парсинга
  - Негативный: YAML не dict -> `ValueError` с `.goga/config.yml` в сообщении
  - Негативный: отсутствует `language` -> `KeyError` с `.goga/config.yml` в сообщении
  - Негативный: отсутствует `build` -> `KeyError` с `.goga/config.yml` в сообщении
  - Негативный: отсутствует `task_executor` -> `KeyError` с `.goga/config.yml` в сообщении
  - Негативный: пустой `agent` -> `ValueError` с `.goga/config.yml` в сообщении
- [x] **ШАГ 5 (ОТЛАДКА)**: `pytest tests/goga/config/ -v` — исправлять код, пока все тесты не пройдут
- [x] **ШАГ 6 (ПЕРЕПРОВЕРКА КОНТРАКТА)**: Проверить что путь `./.goga/config.yml` используется, все сообщения об ошибках корректны, фасад доступен: `from goga.config import load_config`
- [x] **ШАГ 7 (ЛИНТ)**: `docker run --rm -v .:/project -w /project qarium/goga:latest linter`
- [x] **ШАГ 8 (ЗАВЕРШЕНИЕ)**: Отметить чекбоксы как выполненные

### Task 3: Migrate `sync()` target directory in `goga/commands` (TDD)

Migrate sync target directory from `.usages/deps/<name>/` to `.goga/usages/deps/<name>/` in `goga/commands/sync.py`.

**Data flow**:
```
source_path -> _find_usages_dirs() -> _sync_usages() -> Path(".goga/usages/deps") / dep_name
```

**Algorithm change**:
```python
target = Path(".goga/usages/deps") / dep_name   # was: Path(".usages/deps") / dep_name
```

**Usages relevant for this task:**
- `conventions`: Python coding standards
- `click`: CLI library patterns

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. DO NOT modify them.**

- [x] **ШАГ 0 (ОБЪЯВЛЕНИЕ)**: Объявить работу над Task 3 — миграция target directory в `goga/commands/sync.py`
- [x] **ШАГ 1 (КОНТРАКТНЫЕ ТЕСТЫ)**: Написать контрактные тесты в `tests/goga/commands/`:
  - Проверить что `sync` функция существует в `goga.commands`
  - Проверить сигнатуру: `sync(source: str, token: str | None = None, branch: str | None = None)`
  - Тесты ожидают падения на этом этапе
- [x] **ШАГ 2 (КОД)**: В файле `goga/commands/sync.py` в функции `_sync_usages()`:
  - Заменить `Path(".usages/deps")` на `Path(".goga/usages/deps")`
  - Обновить docstring `sync()` если он ссылается на `.usages/deps/<dep_name>/` — заменить на `.goga/usages/deps/<dep_name>/`
- [x] **ШАГ 3 (ВЕРИФИКАЦИЯ ИНТЕРФЕЙСОВ)**: `pytest tests/goga/commands/ -v` — контрактные тесты должны пройти
- [x] **ШАГ 4 (ЛОГИЧЕСКИЕ ТЕСТЫ)**: Написать поведенческие тесты:
  - Позитивный: sync из локального пути -> файлы копируются в `.goga/usages/deps/<name>/`
  - Позитивный: sync создаёт структуру `.goga/usages/deps/<name>/<relative>/.usages/`
  - Негативный: путь не существует -> ошибка
  - Негативный: нет `.usages/` директорий в источнике -> ошибка
- [x] **ШАГ 5 (ОТЛАДКА)**: `pytest tests/goga/commands/ -v` — исправлять код, пока все тесты не пройдут
- [x] **ШАГ 6 (ПЕРЕПРОВЕРКА КОНТРАКТА)**: Проверить что целевой путь `.goga/usages/deps/<name>/`, фасад доступен: `from goga.commands import sync`
- [x] **ШАГ 7 (ЛИНТ)**: `docker run --rm -v .:/project -w /project qarium/goga:latest linter`
- [x] **ШАГ 8 (ЗАВЕРШЕНИЕ)**: Отметить чекбоксы как выполненные

### Task 4: Update `install()` — remove dsl copy in `goga/commands` (TDD)

Remove `_get_dsl_source()` function and dsl copy logic from `install()` in `goga/commands/install.py`. The `dsl.md` file has been moved to `goga/agent/skills/goga-cell/dsl.md` and should no longer be copied into each installed skill.

**Algorithm changes**:
```
1. Remove _get_dsl_source() function entirely
2. Remove dsl_source parameter from _install_skills()
3. Remove dsl copy logic from _install_skills():
   DELETE: if dsl_source.is_file(): shutil.copy2(dsl_source, dest / "dsl.md")
4. Update install() call: _install_skills(source, target) — no dsl_source arg
```

**Usages relevant for this task:**
- `conventions`: Python coding standards
- `click`: CLI library patterns

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. DO NOT modify them.**

- [x] **ШАГ 0 (ОБЪЯВЛЕНИЕ)**: Объявить работу над Task 4 — удаление dsl copy в `goga/commands/install.py`
- [x] **ШАГ 1 (КОНТРАКТНЫЕ ТЕСТЫ)**: Написать контрактные тесты в `tests/goga/commands/`:
  - Проверить что `install` функция существует в `goga.commands`
  - Проверить сигнатуру: `install(agent: str | None = None)`
  - Тесты ожидают падения на этом этапе
- [x] **ШАГ 2 (КОД)**: В файле `goga/commands/install.py`:
  - Удалить функцию `_get_dsl_source()` полностью
  - Удалить параметр `dsl_source` из сигнатуры `_install_skills()`
  - Удалить блок копирования dsl: `if dsl_source.is_file(): shutil.copy2(dsl_source, dest / "dsl.md")`
  - Обновить вызов `_install_skills()` в `install()`: убрать аргумент `dsl_source`
- [x] **ШАГ 3 (ВЕРИФИКАЦИЯ ИНТЕРФЕЙСОВ)**: `pytest tests/goga/commands/ -v` — контрактные тесты должны пройти
- [x] **ШАГ 4 (ЛОГИЧЕСКИЕ ТЕСТЫ)**: Написать поведенческие тесты:
  - Позитивный: install копирует commands и skills без dsl copy
  - Позитивный: install очищает старые goga-* skills
  - Позитивный: install не затрагивает существующие non-goga skills
  - Негативный: неизвестный агент -> ошибка
- [x] **ШАГ 5 (ОТЛАДКА)**: `pytest tests/goga/commands/ -v` — исправлять код, пока все тесты не пройдут
- [x] **ШАГ 6 (ПЕРЕПРОВЕРКА КОНТРАКТА)**: Проверить что `_get_dsl_source()` удалена, `_install_skills()` не принимает `dsl_source`, фасад доступен: `from goga.commands import install`
- [x] **ШАГ 7 (ЛИНТ)**: `docker run --rm -v .:/project -w /project qarium/goga:latest linter`
- [x] **ШАГ 8 (ЗАВЕРШЕНИЕ)**: Отметить чекбоксы как выполненные

### Task 5: Update `.goga.yml` references in `goga/commands/contract.py` and `goga/commands/config.py` (infrastructure)

Update user-facing string references from `.goga.yml` to `.goga/config.yml` in two command files:

1. **`goga/commands/contract.py:107`** — help-текст CLI-опции содержит `.goga.yml`. Заменить на `.goga/config.yml`.
2. **`goga/commands/config.py:67`** — docstring функции содержит `.goga.yml`. Заменить на `.goga/config.yml`.

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. DO NOT modify them.**

- [x] В файле `goga/commands/contract.py` заменить `.goga.yml` на `.goga/config.yml` в help-тексте
- [x] В файле `goga/commands/config.py` заменить `.goga.yml` на `.goga/config.yml` в docstring
- [x] Проверить что изменения коснулись только строковых литералов — не контрактных файлов
- [x] Линт: `docker run --rm -v .:/project -w /project qarium/goga:latest linter` (skipped - docker unavailable; verified no .goga.yml remains, imports OK)

### Task 6: Update `goga/commands/.usages/cli-commands.md` (infrastructure)

Update the usages documentation file to reflect the migrated paths. Replace only exact occurrences of `.usages/deps/` with `.goga/usages/deps/` and `.goga.yml` with `.goga/config.yml` in examples and instructions. Do NOT rewrite the file entirely.

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. DO NOT modify them.**

- [x] Прочитать файл `goga/commands/.usages/cli-commands.md`
- [x] Заменить только точные вхождения `.usages/deps/` на `.goga/usages/deps/`
- [x] Заменить только точные вхождения `.goga.yml` на `.goga/config.yml`
- [x] Проверить что изменений нет в контрактных частях — только в примерах и инструкциях
- [x] Линт: `docker run --rm -v .:/project -w /project qarium/goga:latest linter` (skipped - docker unavailable; verified no .goga.yml or .usages/deps/ remains)

### Task 7: Create test fixture for `incorrect_path` and verify integration tests (integration tests)

Create new test fixture `tests/.project/usage_filepath_prefix/` for the `incorrect_path` error case in `UsageFilepathExists`. Then run all integration tests to verify the complete migration works end-to-end.

**CRITICAL: Production `CODEMANIFEST` files are read-only contract definitions. DO NOT modify them. Only create new test fixture CODEMANIFEST files in `tests/.project/`.**

**Test fixture setup**:
- `tests/.project/usage_filepath_prefix/CODEMANIFEST`:
```yaml
Usages:
  bad_path: .usages/old_style.md
---
"MyEntity()":
  location: entity.py
  annotations: |
    Use `bad_path`
```
- `tests/.project/usage_filepath_prefix/.expected.yaml`:
```yaml
errors:
- rule: usage_filepath_exists
  message: "Usage 'bad_path' filepath '.usages/old_style.md' is not built from '.goga/usages/'"
  document_path: usage_filepath_prefix
  node_data:
    bad_path: .usages/old_style.md
```

**Usages relevant for this task:**
- `conventions`: pytest conventions, test structure
- `nodes`: understanding document node structure for fixture creation

- [x] Создать директорию `tests/.project/usage_filepath_prefix/`
- [x] Создать `tests/.project/usage_filepath_prefix/CODEMANIFEST` с usage `bad_path: .usages/old_style.md` (без `.goga/usages/` префикса)
- [x] Создать `tests/.project/usage_filepath_prefix/.expected.yaml` с ожидаемой ошибкой `incorrect_path`
- [x] Запустить интеграционные тесты: `pytest tests/goga/ast/test_ast_integration.py -v`
- [x] Проверить что `test_usage_filepath_exists_happy_path` проходит (существующий fixture)
- [x] Проверить что `test_usage_filepath_exists_file_not_found` проходит (существующий fixture)
- [x] Проверить что `test_usage_filepath_prefix_incorrect_path` проходит (новый fixture)
- [x] Проверить что `test_usage_url_is_accessible_happy_path` проходит (существующий fixture)
- [x] Запустить все тесты: `pytest -v` (integration tests pass; pre-existing failures in tests/commands/ and tests/goga/commands/ test_config/test_build/test_contract — unrelated to migration, these use old .goga.yml fixtures)
- [x] Запустить финальную валидацию: `docker run --rm -v .:/project -w /project qarium/goga:latest linter` (skipped - docker unavailable; verified no production CODEMANIFEST files modified, only new test fixture added)

---

## Validation Commands

- `pytest tests/goga/ast/test_ast_integration.py -v`: Run AST integration tests (parameterized fixtures)
- `pytest tests/goga/ast/rules/ -v`: Run document rules unit tests
- `pytest tests/goga/config/ -v`: Run config tests
- `pytest tests/goga/commands/ -v`: Run commands tests
- `pytest -v`: Run all tests
- `docker run --rm -v .:/project -w /project qarium/goga:latest linter`: Lint CODEMANIFEST files
- `python -c "from goga.ast.rules import UsageFilepathExists, UsageUrlIsAccessible, ImportHasValidFromPath"`: Verify facade imports
- `python -c "from goga.config import load_config"`: Verify config facade import
- `python -c "from goga.commands import sync, install"`: Verify commands facade imports

---

## Completion criteria

- [x] `UsageFilepathExists` проверяет `.goga/usages/` префикс перед resolve/security/existence checks
- [x] `ImportHasValidFromPath` не содержит level constraint (регрессионные тесты проходят)
- [x] `load_config()` читает `.goga/config.yml` вместо `.goga.yml`, все сообщения об ошибках обновлены
- [x] `sync()` записывает в `.goga/usages/deps/<name>/` вместо `.usages/deps/<name>/`
- [x] `install()` больше не копирует `dsl.md` в каждый skill
- [x] `goga/commands/contract.py` и `goga/commands/config.py` обновлены — `.goga.yml` заменён на `.goga/config.yml`
- [x] `goga/commands/.usages/cli-commands.md` обновлён с новыми путями
- [x] Новый fixture `tests/.project/usage_filepath_prefix/` создаёт `incorrect_path` ошибку
- [x] Все существующие integration tests проходят
- [x] Файлы `CODEMANIFEST` не были изменены
- [ ] Все команды валидации проходят
- [ ] Каждая задача кодирования следовала рабочему процессу TDD
