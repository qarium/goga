# План: `commands-split`

## Цель

Разделить монолитные CLI-команды в `goga/commands/` на двухуровневую архитектуру:
тонкие CLI-обёртки остаются в `goga/commands/`, бизнес-логика извлекается в 4 новых cell
(`goga/sync`, `goga/schema`, `goga/build`, `goga/install`).
После реализации каждая делегирующая команда (`build`, `install`, `schema`, `sync`)
в `goga/commands/` будет только парсить click-параметры и делегировать вызов
соответствующей бизнес-функции из нового cell.

## Контекст

### Поверхность контракта

**Сущность: `sync(source: str, token: str | None, branch: str | None) -> exit_code:int`**
- Тип: Routine
- Объявленный `location`: `sync.py` (goga/sync)
- Обязанность фасада: должна быть импортируема из `goga.sync`
- Свойства/методы: нет (Routine)
- Семантические требования: синхронизация .usages/ из локального пути или git-репозитория; диспетчеризация git/local по префиксу URL; exit codes 0/1; вывод ошибок через sys.stderr
- Импортированные зависимости: нет (автономна)
- Контекст аннотаций: использовать `convention`, вывод через sys.stderr, shutil/subprocess/tempfile/pathlib

**Сущность: `schema(cells: list[str], max_depth: int | None, depends_on: list[str]) -> json:str`**
- Тип: Routine
- Объявленный `location`: `schema.py` (goga/schema)
- Обязанность фасада: должна быть импортируема из `goga.schema`
- Свойства/методы: нет (Routine)
- Семантические требования: формирование JSON-схемы из AST; три уровня фильтрации; ValueError при ошибках AST; пустое дерево → "[]"
- Импортированные зависимости: `AST` из `goga/ast`
- Контекст аннотаций: использовать `convention`, `documents` для работы с AST, `beautiful_json` для форматирования

**Сущность: `build(plan: str, config: Config, cli_options: dict) -> exit_code:int`**
- Тип: Routine
- Объявленный `location`: `build.py` (goga/build)
- Обязанность фасада: должна быть импортируема из `goga.build`
- Свойства/методы: нет (Routine)
- Семантические требования: pre-check git → прекондишены по агенту → copy defaults → assemble ralphex cmd → subprocess; exit codes 0/1
- Импортированные зависимости: `Config`, `BuildConfig`, `TaskExecutor` из `goga/config`
- Контекст аннотаций: использовать `convention`, `ralphex` для сборки, вывод через sys.stderr, subprocess

**Сущность: `install(agent: str | None, config: Config) -> exit_code:int`**
- Тип: Routine
- Объявленный `location`: `install.py` (goga/install)
- Обязанность фасада: должна быть импортируема из `goga.install`
- Свойства/методы: нет (Routine)
- Семантические требования: resolve agent → cleanup → install commands/skills → download dsl; exit codes 0/1
- Импортированные зависимости: `Config` из `goga/config`
- Контекст аннотаций: использовать `convention`, urllib.request, shutil, вывод через sys.stderr

**Изменённые сущности в goga/commands:**
- `build(plan)` — CLI-обёртка, делегирует `build_logic` из `goga/build`
- `install(agent)` — CLI-обёртка, делегирует `install_logic` из `goga/install`
- `schema(cells, max_depth, depends_on)` — CLI-обёртка, делегирует `schema_logic` из `goga/schema`, обработка ValueError
- `sync(source, token, branch)` — CLI-обёртка, делегирует `sync_logic` из `goga/sync`

### Реэкспорты

Для `goga/commands` CODEMANIFEST:
- `build AS build_logic` из `goga/build` — должна быть импортируема
- `install AS install_logic` из `goga/install` — должна быть импортируема
- `schema AS schema_logic` из `goga/schema` — должна быть импортируема
- `sync AS sync_logic` из `goga/sync` — должна быть импортируема

### Контекст Usages

- **`convention`** (.goga/usages/development/conventions.md): конвенции разработки (Python 3.10+, dataclass, relative imports, pytest)
- **`ralphex`** (.goga/usages/cooks/ralphex.md): спецификация ralphex CLI (формат планов, конфигурация, режимы работы) — для goga/build
- **`click`** (.goga/usages/cooks/click.md): паттерны работы с Click CLI — для goga/commands
- **`documents`** (inline): паттерн работы с AST (load, tree, errors) — для goga/schema
- **`beautiful_json`** (inline): json.dumps(data, indent=4, sort_keys=True, ensure_ascii=False) — для goga/schema
- **`configuration`** (импортирована из goga/config): загрузка конфигурации — для goga/commands build/install

### Импортированные Usages

- **`python_contract`** из `goga/contract`: спецификация извлечения контракта из Python-кода — для команды contract
- **`configuration`** из `goga/config`: спецификация загрузки конфигурации — для CLI wrappers build/install

### Локальные Usages

- **`goga/sync/.usages/sync-usage.md`**: существующий, описывает API sync для потребителей
- **`goga/schema/.usages/schema-usage.md`**: существующий, описывает API schema для потребителей
- **`goga/build/.usages/build-usage.md`**: существующий, описывает API build для потребителей
- **`goga/install/.usages/install-usage.md`**: существующий, описывает API install для потребителей
- **`goga/commands/.usages/cli-commands.md`**: существующий, обновлён — переструктурирован на делегирующие/самостоятельные команды

### Внешние зависимости

- `click` — CLI-фреймворк (только для goga/commands)
- `pytest` — тестовый фреймворк
- `pytest-mock` — mocker fixture
- `pyyaml` — загрузка конфигурации

## Факты

- Новые cell каталоги (`goga/sync`, `goga/schema`, `goga/build`, `goga/install`) уже содержат `CODEMANIFEST` и `.usages/` файлы
- Существующий код в `goga/commands/` содержит полную реализацию бизнес-логики для всех 4 команд
- Существующие тесты покрывают CLI-команды через `CliRunner` — их нужно адаптировать к новой структуре
- Порядок реализации: sync → schema → build → install → commands (от листьев к корню)
- В бизнес-логике `click.echo(err=True)` заменяется на `print(..., file=sys.stderr)`
- В бизнес-логике `click.ClickException` не используется — ошибки возвращаются через exit_code
- CLI-обёртки сохраняют `click.echo(err=True)` и `click.ClickException`
- `goga/sync` автономна — нет Imports
- `goga/schema` ← `goga/ast` [AST]
- `goga/build` ← `goga/config` [Config, BuildConfig, TaskExecutor, load_config + configuration]
- `goga/install` ← `goga/config` [Config]
- Нет циклических зависимостей

## Анализ разрывов

- **Отсутствующие сущности контракта**: все 4 бизнес-функции (sync, schema, build, install) не существуют в новых cell
- **Отсутствующие `__init__.py`**: новые cell не содержат `__init__.py` для фасада
- **Отсутствующая декомпозиция**: бизнес-логика смешана с CLI-логикой в `goga/commands/*.py`
- **Существующий код для переиспользования**: полная реализация в `goga/commands/{build,install,schema,sync}.py`
- **Разрывы в тестовом покрытии**: тесты покрывают CLI-команды, но не business functions напрямую

---

## Tasks

> **Правило упорядочивания по пакетам**: задачи кодирования каждого пакета завершаются перед началом следующего. Внутри каждой задачи кодирования контрактные тесты пишутся первыми (рабочий процесс TDD).

### Task 1: Инфраструктура goga/sync (инфраструктура)

Создать структуру cell `goga/sync` — фасад `__init__.py` для экспорта функции `sync`. Cell автономна, не имеет Imports.

**КРИТИЧЕСКИ: файлы `CODEMANIFEST` — определения контракта только для чтения. НЕ изменяйте их. Если реализация не соответствует контракту, исправляйте реализацию — никогда не исправляйте контракт.**

- [x] Создать файл `goga/sync/__init__.py` с реэкспортом: `from .sync import sync`
- [x] Проверить доступность фасада: `python -c "from goga.sync import sync; print(sync)"` (верификация пройдёт после создания sync.py в Task 2)

### Task 2: Реализация sync routine (TDD кодирование)

Реализовать функцию `sync(source: str, token: str | None = None, branch: str | None = None) -> exit_code:int` в `goga/sync/sync.py`. Извлечь бизнес-логику из существующего `goga/commands/sync.py`.

Контракт (из CODEMANIFEST): Routine, location `sync.py`. Синхронизация .usages/ из локального пути или git-репозитория.

**Usages, релевантные для этой задачи:**
- `convention`: Python 3.10+ типы (str | None), relative imports, pytest для тестов

**Ключевые трансформации из существующего кода:**
- Все `click.echo(msg, err=True)` → `print(msg, file=sys.stderr)`
- Все `ctx.exit(1)` → `return 1`
- Все `ctx.exit(0)` → `return 0`
- Убрать зависимость от `click.Context` — функция возвращает int
- Приватные helper-функции (`_is_git_url`, `_extract_dep_name`, `_prepare_clone_url`, `_find_usages_dirs`, `_sync_usages`, `_sync_from_git`, `_sync_from_local`) переносятся без изменений логики, но с заменой click.echo/ctx.exit

**Алгоритм (из дизайн-документа, дословно):**
```
1. IF source starts with http://, https://, git@, ssh://:
   → git_mode = True
   ELSE:
   → git_mode = False

2. IF git_mode:
   a. dep_name = extract_dep_name(source)
   b. clone_url = prepare_clone_url(source, token)
   c. tmp_dir = tempfile.mkdtemp()
   d. TRY:
      - subprocess.run(["git", "clone", ...])
      - usages_dirs = _find_usages_dirs(tmp_dir)
      - IF not usages_dirs: return 1
      - _sync_usages(tmp_dir, dep_name)
   e. FINALLY:
      - shutil.rmtree(tmp_dir)

3. IF NOT git_mode:
   a. resolved = Path(source).resolve()
   b. IF not resolved.is_dir(): return 1
   c. usages_dirs = _find_usages_dirs(resolved)
   d. IF not usages_dirs: return 1
   e. dep_name = resolved.name
   f. _sync_usages(resolved, dep_name)

4. RETURN 0
```

**КРИТИЧЕСКИ: файлы `CODEMANIFEST` — определения контракта только для чтения. НЕ изменяйте их. Если реализация не соответствует контракту, исправляйте реализацию — никогда не исправляйте контракт.**

- [x] **ШАГ 0 (ОБЪЯВЛЕНИЕ)**: объявить, что работа ведётся над Task 2 — sync routine в goga/sync
- [x] **Контрактные тесты**: написать в `tests/goga/sync/test_contract.py` — проверить импортируемость `sync` из `goga.sync`, сигнатуру функции `sync(source, token, branch) -> int`, наличие параметров с правильными типами и дефолтами (ожидаемо падают)
- [x] **Код**: создать `goga/sync/sync.py` с функцией `sync(source: str, token: str | None = None, branch: str | None = None) -> int`, извлечь бизнес-логику из `goga/commands/sync.py`, заменив click-вызовы на print(..., file=sys.stderr) и return exit_code
- [x] **Код**: перенести приватные helpers: `_is_git_url`, `_extract_dep_name`, `_prepare_clone_url`, `_find_usages_dirs`, `_sync_usages`, `_sync_from_git`, `_sync_from_local` — адаптировать для возврата int вместо ctx.exit
- [x] **Верификация интерфейсов**: запустить контрактные тесты `python -m pytest tests/goga/sync/test_contract.py -v` — все должны пройти
- [x] **Логические тесты**: написать в `tests/goga/sync/test_sync.py` — позитивные (local sync, git sync), негативные (path not exists, no usages, git clone fail, token leak), краевые (idempotent, token+branch, relative path, empty usages dir, SSH URL ignores token, GIT_TERMINAL_PROMPT=0, cleanup tmp_dir on success/failure)
- [x] **Отладка**: запустить `python -m pytest tests/goga/sync/ -v` — исправлять код, пока все тесты не пройдут (НЕ исправлять тестовый код)
- [x] **Перепроверка контрактов**: проверить что `from goga.sync import sync` работает, сигнатура `(source: str, token: str | None = None, branch: str | None = None) -> int`, вывод через sys.stderr, exit codes 0/1
- [x] **Линт**: `docker run --rm -v .:/project -w /project qarium/goga:latest linter` — исправить форматирование

### Task 3: Инфраструктура goga/schema (инфраструктура)

Создать структуру cell `goga/schema` — фасад `__init__.py` для экспорта функции `schema`.

**КРИТИЧЕСКИ: файлы `CODEMANIFEST` — определения контракта только для чтения. НЕ изменяйте их.**

- [x] Создать файл `goga/schema/__init__.py` с реэкспортом: `from .schema import schema`
- [x] Проверить доступность фасада: `python -c "from goga.schema import schema; print(schema)"` (верификация пройдёт после создания schema.py в Task 4)

### Task 4: Реализация schema routine (TDD кодирование)

Реализовать функцию `schema(cells: list[str], max_depth: int | None, depends_on: list[str]) -> str` в `goga/schema/schema.py`. Извлечь бизнес-логику из существующего `goga/commands/schema.py`.

Контракт (из CODEMANIFEST): Routine, location `schema.py`. Зависит от `AST` из `goga/ast`.

**Usages, релевантные для этой задачи:**
- `convention`: Python 3.10+ типы, relative imports, pytest
- `documents`: `AST(".")` → `ast.load()` → `ast.tree` — доступ к документам; ошибки из `ast.errors`
- `beautiful_json`: `json.dumps(data, indent=4, sort_keys=True, ensure_ascii=False)`

**Ключевые трансформации из существующего кода:**
- Функция `schema()` возвращает JSON-строку (str), не вызывает click.echo
- При наличии ошибок AST (ast.errors не пустое) — выбрасывает ValueError
- Приватные helpers (`_find_usages_files`, `_cell_in_set`, `_build_dependencies`, `_build_cell_tree`, `_prune_depth`, `_filter_tree`, `_has_dependency`, `_filter_by_depends_on`) переносятся без изменений
- Убрать зависимость от click

**Алгоритм (из дизайн-документа, дословно):**
```
1. ast = AST(".")
   ast.load()
   IF ast.errors: raise ValueError(f"... {len(ast.errors)} error(s)")

2. result = _build_cell_tree(tree)

3. IF cells is not empty:
   result = _filter_tree(result, cells)

4. IF depends_on is not empty:
   result = _filter_by_depends_on(result, depends_on)

5. IF max_depth is not None:
   result = [_prune_depth(cell, max_depth) for cell in result]

6. RETURN json.dumps(result, indent=4, sort_keys=True, ensure_ascii=False)
```

**КРИТИЧЕСКИ: файлы `CODEMANIFEST` — определения контракта только для чтения. НЕ изменяйте их.**

- [x] **ШАГ 0 (ОБЪЯВЛЕНИЕ)**: объявить, что работа ведётся над Task 4 — schema routine в goga/schema
- [x] **Контрактные тесты**: написать в `tests/goga/schema/test_contract.py` — импортируемость `schema` из `goga.schema`, сигнатура `(cells, max_depth, depends_on) -> str`, типы параметров (ожидаемо падают)
- [x] **Код**: создать `goga/schema/schema.py` с функцией `schema(cells, max_depth, depends_on)`, извлечь бизнес-логику из `goga/commands/schema.py`, добавить ValueError при ошибках AST
- [x] **Код**: перенести helpers: `_find_usages_files`, `_build_dependencies`, `_build_cell_tree`, `_prune_depth`, `_filter_tree`, `_has_dependency`, `_filter_by_depends_on`, `_cell_in_set`
- [x] **Верификация интерфейсов**: запустить контрактные тесты `python -m pytest tests/goga/schema/test_contract.py -v` — все должны пройти
- [x] **Логические тесты**: написать в `tests/goga/schema/test_schema.py` — позитивные (full tree, cells filter, depends_on filter, max_depth), негативные (AST errors → ValueError), краевые (empty tree → "[]", no usages dir, unicode, deduplicated dependencies, combined filters)
- [x] **Отладка**: запустить `python -m pytest tests/goga/schema/ -v` — исправлять код, пока все тесты не пройдут
- [x] **Перепроверка контрактов**: проверить `from goga.schema import schema`, сигнатуру, ValueError при ошибках AST, красивый JSON
- [x] **Линт**: `docker run --rm -v .:/project -w /project qarium/goga:latest linter` — исправить форматирование

### Task 5: Инфраструктура goga/build (инфраструктура)

Создать структуру cell `goga/build` — фасад `__init__.py` для экспорта функции `build`.

**КРИТИЧЕСКИ: файлы `CODEMANIFEST` — определения контракта только для чтения. НЕ изменяйте их.**

- [x] Создать файл `goga/build/__init__.py` с реэкспортом: `from .build import build`
- [x] Проверить доступность фасада: `python -c "from goga.build import build; print(build)"` (верификация пройдёт после создания build.py в Task 6)

### Task 6: Реализация build routine (TDD кодирование)

Реализовать функцию `build(plan: str, config: Config, cli_options: dict) -> int` в `goga/build/build.py`. Извлечь бизнес-логику из существующего `goga/commands/build.py`.

Контракт (из CODEMANIFEST): Routine, location `build.py`. Зависит от `Config`, `BuildConfig`, `TaskExecutor` из `goga/config`.

**Usages, релевантные для этой задачи:**
- `convention`: Python 3.10+ типы, relative imports, pytest
- `ralphex` (.goga/usages/cooks/ralphex.md): спецификация ralphex CLI — subprocess.call(["ralphex", plan, "--config-dir", ".ralphex/", ...])

**Ключевые трансформации из существующего кода:**
- Все `click.echo(msg)` → `print(msg, file=sys.stderr)`
- Все `click.echo(msg, err=True)` → `print(msg, file=sys.stderr)`
- Все `raise click.ClickException(msg)` → `print(msg, file=sys.stderr); return 1`
- Все `ctx.exit(code)` → `return code`
- Приватные helpers переносятся с заменой click на print/return
- `DEFAULTS_PACKAGE_DIR` — использовать `Path(__file__).parent.parent / "config" / "defaults"` (относительно cell, а не commands)

**Алгоритм (из дизайн-документа, дословно):**
```
1. IF NOT cli_options.get("skip_manifest_check"):
   uncommitted = _find_uncommitted_manifests()
   IF uncommitted: print error, RETURN 1

2. agent = config.build.task_executor.agent
   IF agent == "claude":
     _create_claude_settings(config)
     _create_claude_wrapper(config)
   ELSE:
     print error, RETURN 1

3. _copy_defaults(config)

4. cmd = _assemble_command(plan, config, cli_options)

5. IF cli_options.get("dry_run"):
   print(cmd), RETURN 0

6. exit_code = subprocess.call(cmd)
   RETURN exit_code
```

**КРИТИЧЕСКИ: файлы `CODEMANIFEST` — определения контракта только для чтения. НЕ изменяйте их.**

- [x] **ШАГ 0 (ОБЪЯВЛЕНИЕ)**: объявить, что работа ведётся над Task 6 — build routine в goga/build
- [x] **Контрактные тесты**: написать в `tests/goga/build/test_contract.py` — импортируемость `build` из `goga.build`, сигнатура `(plan, config, cli_options) -> int` (ожидаемо падают)
- [x] **Код**: создать `goga/build/build.py` с функцией `build(plan, config, cli_options)`, извлечь бизнес-логику из `goga/commands/build.py`
- [x] **Код**: перенести helpers: `_unquote_git_path`, `_parse_porcelain_path`, `_find_uncommitted_manifests`, `_run_precondition`, `_precondition_claude`, `_create_claude_settings`, `_create_claude_wrapper`, `_copy_defaults`, `_assemble_command`, константы `CLAUDE_WRAPPER_SCRIPT`, `DEFAULTS_PACKAGE_DIR`, `RALPHEX_CONFIG_DEFAULTS`
- [x] **Код**: заменить click.echo/ClickException/ctx.exit на print(..., file=sys.stderr)/return
- [x] **Верификация интерфейсов**: запустить контрактные тесты `python -m pytest tests/goga/build/test_contract.py -v` — все должны пройти
- [x] **Логические тесты**: написать в `tests/goga/build/test_build.py` — позитивные (dry_run, full execution, env vars, settings merge, claude wrapper, defaults copying, codex_enabled, config flags), негативные (uncommitted manifests, unsupported agent, missing config, invalid settings.json, defaults dir not found, ralphex not found), краевые (overwrite files, repeated build, custom prompts/agents dir)
- [x] **Отладка**: запустить `python -m pytest tests/goga/build/ -v` — исправлять код, пока все тесты не пройдут
- [x] **Перепроверка контрактов**: проверить `from goga.build import build`, сигнатуру, exit codes, ralphex command assembly
- [x] **Линт**: `docker run --rm -v .:/project -w /project qarium/goga:latest linter` — исправить форматирование

### Task 7: Инфраструктура goga/install (инфраструктура)

Создать структуру cell `goga/install` — фасад `__init__.py` для экспорта функции `install`.

**КРИТИЧЕСКИ: файлы `CODEMANIFEST` — определения контракта только для чтения. НЕ изменяйте их.**

- [ ] Создать файл `goga/install/__init__.py` с реэкспортом: `from .install import install`
- [ ] Проверить доступность фасада: `python -c "from goga.install import install; print(install)"`

### Task 8: Реализация install routine (TDD кодирование)

Реализовать функцию `install(agent: str | None, config: Config) -> int` в `goga/install/install.py`. Извлечь бизнес-логику из существующего `goga/commands/install.py`.

Контракт (из CODEMANIFEST): Routine, location `install.py`. Зависит от `Config` из `goga/config`.

**Usages, релевантные для этой задачи:**
- `convention`: Python 3.10+ типы, relative imports, pytest

**Ключевые трансформации из существующего кода:**
- `click.echo(msg)` → `print(msg, file=sys.stderr)`
- `click.echo(msg, err=True)` → `print(msg, file=sys.stderr)`
- `ctx.exit(code)` → `return code`
- `_print_summary` — заменить click.echo на print
- Приватные helpers переносятся без изменений логики

**Алгоритм (из дизайн-документа, дословно):**
```
1. resolved_agent = agent or config.build.task_executor.agent

2. IF resolved_agent == "claude":
   target = Path.home() / ".claude"
   ELSE:
   print error, RETURN 1

3. source = Path(__file__).parent.parent / "agent"
   IF NOT source.is_dir(): RETURN 1

4. target.mkdir(parents=True, exist_ok=True)

5. _cleanup_goga_skills(target)

6. _install_commands(source, target)
   _install_skills(source, target)

7. _download_dsl_spec(target)

8. print summary
   RETURN 0
```

**КРИТИЧЕСКИ: файлы `CODEMANIFEST` — определения контракта только для чтения. НЕ изменяйте их.**

- [ ] **ШАГ 0 (ОБЪЯВЛЕНИЕ)**: объявить, что работа ведётся над Task 8 — install routine в goga/install
- [ ] **Контрактные тесты**: написать в `tests/goga/install/test_contract.py` — импортируемость `install` из `goga.install`, сигнатура `(agent, config) -> int` (ожидаемо падают)
- [ ] **Код**: создать `goga/install/install.py` с функцией `install(agent, config)`, извлечь бизнес-логику из `goga/commands/install.py`
- [ ] **Код**: перенести helpers: `_resolve_target_dir`, `_get_source_dir`, `_install_commands`, `_install_skills`, `_download_dsl_spec`, `_cleanup_goga_skills`, `_print_summary`, константы `AGENT_DIRS`, `DSL_SPEC_URL`
- [ ] **Код**: заменить click.echo/ctx.exit на print/return
- [ ] **Верификация интерфейсов**: запустить контрактные тесты `python -m pytest tests/goga/install/test_contract.py -v` — все должны пройти
- [ ] **Логические тесты**: написать в `tests/goga/install/test_install.py` — позитивные (default agent, explicit claude agent, config-based agent, full install cycle), негативные (unsupported agent, source missing, download failure HTTP/URL/timeout, permission error), краевые (idempotent, preserves existing files, preserves other skills, replaces old commands, cleanup goga-* skills, empty skills dir)
- [ ] **Отладка**: запустить `python -m pytest tests/goga/install/ -v` — исправлять код, пока все тесты не пройдут
- [ ] **Перепроверка контрактов**: проверить `from goga.install import install`, сигнатуру, exit codes, cleanup/install/download flow
- [ ] **Линт**: `docker run --rm -v .:/project -w /project qarium/goga:latest linter` — исправить форматирование

### Task 9: Обновление CLI-обёрток goga/commands (TDD кодирование)

Преобразовать 4 CLI-команды в `goga/commands/` в тонкие обёртки, делегирующие бизнес-логику в новые cell. Обновить `__init__.py`.

**Usages, релевантные для этой задачи:**
- `click` (.goga/usages/cooks/click.md): паттерны работы с Click CLI
- `conventions` (.goga/usages/development/conventions.md): стандартные конвенции
- `configuration` (импортирована из goga/config): загрузка конфигурации через `load_config`

**Импорты из новых cells (из CODEMANIFEST):**
```python
from goga.sync import sync as sync_logic
from goga.schema import schema as schema_logic
from goga.install import install as install_logic
from goga.build import build as build_logic
```

**Изменения по файлам:**

`goga/commands/sync.py` — полная замена:
```python
@click.command()
@click.argument("source")
@click.option("--token", ...)
@click.option("--branch", ...)
@click.pass_context
def sync(ctx, source, token, branch):
    exit_code = sync_logic(source, token, branch)
    sys.exit(exit_code)
```

`goga/commands/schema.py` — полная замена:
```python
@click.command()
@click.argument("cells", nargs=-1)
@click.option("--max-depth", ...)
@click.option("--depends-on", multiple=True, ...)
@click.pass_context
def schema(ctx, cells, max_depth, depends_on):
    try:
        result = schema_logic(list(cells), max_depth, list(depends_on))
        click.echo(result)
    except ValueError as e:
        click.echo(str(e), err=True)
        ctx.exit(1)
```

`goga/commands/build.py` — полная замена:
```python
@click.command()
@click.argument("plan")
@click.option(...)  # все 9 опций
@click.pass_context
def build(ctx, plan, ...):
    try:
        config = load_config()
    except (...) as exc:
        raise click.ClickException(str(exc)) from exc
    cli_options = {...}
    exit_code = build_logic(plan, config, cli_options)
    ctx.exit(exit_code)
```

`goga/commands/install.py` — полная замена:
```python
@click.command()
@click.option("--agent", ...)
@click.pass_context
def install(ctx, agent):
    try:
        config = load_config()
    except (...) as exc:
        raise click.ClickException(str(exc)) from exc
    exit_code = install_logic(agent, config)
    ctx.exit(exit_code)
```

`goga/commands/__init__.py` — без изменений (уже реэкспортирует все 7 команд)

**КРИТИЧЕСКИ: файлы `CODEMANIFEST` — определения контракта только для чтения. НЕ изменяйте их.**

- [ ] **ШАГ 0 (ОБЪЯВЛЕНИЕ)**: объявить, что работа ведётся над Task 9 — обновление CLI-обёрток goga/commands
- [ ] **Контрактные тесты**: проверить что все 7 команд импортируемы из `goga.commands`, что build/install/schema/sync являются click.Command, что параметры (аргументы и опции) совпадают с текущими
- [ ] **Код**: переписать `goga/commands/sync.py` — тонкая обёртка с делегированием `sync_logic`
- [ ] **Код**: переписать `goga/commands/schema.py` — тонкая обёртка с делегированием `schema_logic`, обработка ValueError
- [ ] **Код**: переписать `goga/commands/build.py` — тонкая обёртка с делегированием `build_logic`, load_config + ClickException
- [ ] **Код**: переписать `goga/commands/install.py` — тонкая обёртка с делегированием `install_logic`, load_config + ClickException
- [ ] **Верификация интерфейсов**: запустить `python -m pytest tests/goga/commands/ -v` — все существующие тесты должны пройти (с адаптацией mock-путей если нужно)
- [ ] **Логические тесты**: адаптировать существующие тесты в `tests/goga/commands/` для новой структуры (mock module paths меняются с `goga.commands.build` на `goga.build.build` и т.д.)
- [ ] **Отладка**: запустить `python -m pytest tests/ -v` — исправлять до полного прохождения
- [ ] **Перепроверка контрактов**: проверить что все 7 команд доступны из фасада, click-параметры совпадают, делегирование работает
- [ ] **Линт**: `docker run --rm -v .:/project -w /project qarium/goga:latest linter` — исправить форматирование

### Task 10: Интеграционные тесты для commands-split

Проверить межсущностное взаимодействие: CLI-обёртки корректно делегируют бизнес-логику, error handling пробрасывается, exit codes корректны.

**КРИТИЧЕСКИ: файлы `CODEMANIFEST` — определения контракта только для чтения. НЕ изменяйте их.**

- [ ] Создать/обновить файл `tests/goga/commands/test_integration_split.py`
- [ ] Протестировать: sync CLI вызывает sync_logic с правильными аргументами и пробрасывает exit_code
- [ ] Протестировать: schema CLI вызывает schema_logic, обрабатывает ValueError (exit 1), выводит JSON через click.echo
- [ ] Протестировать: build CLI вызывает build_logic с config и cli_options, пробрасывает exit_code
- [ ] Протестировать: install CLI вызывает install_logic с agent и config, пробрасывает exit_code
- [ ] Запустить валидацию: `python -m pytest tests/ -v`

---

## Команды валидации

- `python -m pytest tests/goga/sync/ -v`: Тесты sync cell
- `python -m pytest tests/goga/schema/ -v`: Тесты schema cell
- `python -m pytest tests/goga/build/ -v`: Тесты build cell
- `python -m pytest tests/goga/install/ -v`: Тесты install cell
- `python -m pytest tests/goga/commands/ -v`: Тесты CLI-обёрток
- `python -m pytest tests/ -v`: Запустить все тесты
- `docker run --rm -v .:/project -w /project qarium/goga:latest linter`: Проверка линта
- `python -c "from goga.sync import sync; from goga.schema import schema; from goga.build import build; from goga.install import install; print('OK')"`: Проверить, что все фасады импортируемы
- `python -c "from goga.commands import build, install, schema, sync, linter, contract, config; print('OK')"`: Проверить, что все команды фасада импортируемы

---

## Критерии завершения

- [ ] Каждая сущность контракта реализована в правильном `location`
- [ ] Каждая сущность контракта доступна из фасада (goga.sync, goga.schema, goga.build, goga.install)
- [ ] CLI-обёртки в goga.commands делегируют бизнес-логику через `build_logic`, `install_logic`, `schema_logic`, `sync_logic`
- [ ] Описания отражены в поведении (exit codes, error handling, форматы вывода)
- [ ] Зависимости контракта соблюдены (Imports из CODEMANIFEST)
- [ ] Реэкспорты доступны из фасада
- [ ] Каждая задача кодирования следовала рабочему процессу TDD (контрактные тесты → код → верификация → логические тесты → отладка → перепроверка → линт)
- [ ] Контрактные тесты и логические тесты покрывают фасад, API и поведение в рамках каждой задачи кодирования
- [ ] Интеграционные тесты существуют для межсущностных сценариев
- [ ] Ни одна граница пакета не была расширена
- [ ] Файлы `CODEMANIFEST` не были изменены (контракт только для чтения)
- [ ] Все команды валидации проходят
- [ ] Каждая запись Usages упомянута как минимум в одной задаче
