# CLI Commands — goga/commands

## Обзор

Пакет `goga.commands` предоставляет CLI-интерфейс для работы с CODEMANIFEST. Все команды запускаются через `goga <command> [options]`.

Команды разделены на две категории:

1. **Делегирующие** — CLI-обёртки, которые парсят click-опции и делегируют бизнес-логику в отдельные cells:
   - `build` → `goga/build`
   - `install` → `goga/install`
   - `schema` → `goga/schema`
   - `sync` → `goga/sync`

2. **Самостоятельные** — реализуют логику напрямую:
   - `linter` — валидация CODEMANIFEST
   - `contract` — сравнение контракта с реализацией
   - `config` — вывод опций конфигурации

Все команды импортируются из фасада:

```python
from goga.commands import install, contract, build, linter, schema, config
```

Или через корневой CLI:

```python
from goga.cli import app
```

## Конфигурация

Файл `.goga/config.yml` обязателен для команд `install`, `contract`, `build`. Он загружается через `load_config()` из `goga.config`.

Минимальный `.goga/config.yml`:

```yaml
language: python
build:
  task_executor:
    agent: claude
```

Приоритет значений: CLI-аргумент > Config. Если CLI-аргумент не указан (None), используется значение из `.goga/config.yml`.

Ошибки конфигурации (`FileNotFoundError`, `KeyError`, `ValueError`, `yaml.YAMLError`) преобразуются в `click.ClickException`.

## Делегирующие команды

Эти команды являются тонкими CLI-слоями. Они парсят click-аргументы, загружают конфигурацию при необходимости и вызывают бизнес-логику из соответствующей cell.

### build

CLI-обёртка команды сборки. Делегирует бизнес-логику в `goga.build.sync`.

Синтаксис:

```
goga build <plan> [--dry-run] [--worktree] [--skip-finalize] [--skip-manifest-check]
                 [--session-timeout T] [--idle-timeout T] [--wait T]
                 [--max-iterations N] [--review-patience N]
```

Аргументы:

| Аргумент | Тип | Описание |
|----------|-----|----------|
| `plan` | str | Путь к плану для ralphex |

Опции:

| Опция | Тип | Дефолт | Описание |
|-------|-----|--------|----------|
| `--dry-run` | flag | false | Показать команду без выполнения |
| `--worktree` | flag | false | Режим изолированного git worktree |
| `--skip-finalize` | flag | false | Пропустить финализацию |
| `--skip-manifest-check` | flag | false | Пропустить проверку uncommitted CODEMANIFEST |
| `--session-timeout` | str | из конфига | Таймаут сессии |
| `--idle-timeout` | str | из конфига | Таймаут простоя |
| `--wait` | str | из конфига | Ожидание при rate limit |
| `--max-iterations` | int | из конфига | Максимум итераций |
| `--review-patience` | int | из конфига | Порог остановки ревью |

Алгоритм:
1. Загрузить конфигурацию через `load_config` (практика `configuration`)
2. Собрать cli_options из click-параметров
3. Вызвать `build_logic`(`plan`, config, cli_options)
4. Вернуть exit_code

Код возврата:
- 0 — успех
- 1 — ошибка (uncommitted manifests, ошибка конфига, ralphex не найден, ошибка ralphex)

Примеры:

```bash
goga build docs/plans/my-plan.md
goga build docs/plans/my-plan.md --dry-run --worktree
```

### install

CLI-обёртка команды установки. Делегирует бизнес-логику в `goga.install.install`.

Синтаксис:

```
goga install [--agent <name>]
```

Опции:

| Опция | Тип | Дефолт | Описание |
|-------|-----|--------|----------|
| `--agent` | str | из конфига | Целевой AI-агент (`claude`). Приоритет: CLI > `build.task_executor.agent` |

Алгоритм:
1. Загрузить конфигурацию через `load_config` (практика `configuration`)
2. Вызвать `install_logic`(`agent`, config)
3. Вернуть exit_code

Код возврата:
- 0 — успех
- 1 — ошибка (неподдерживаемый агент, ресурсы не найдены, ошибка конфигурации, ошибка скачивания)

Примеры:

```bash
goga install
goga install --agent claude
```

### schema

CLI-обёртка команды схемы. Делегирует бизнес-логику в `goga.schema.schema`.

Синтаксис:

```
goga schema [cells...] [--max-depth N] [--depends-on PATH]
```

Аргументы:

| Аргумент | Тип | Описание |
|----------|-----|----------|
| `cells` | list[str] | Пути к клеткам для фильтрации (необязательно) |

Опции:

| Опция | Тип | Дефолт | Описание |
|-------|-----|--------|----------|
| `--max-depth` | int | None | Ограничение глубины вложенности |
| `--depends-on` | list[str] | None | Фильтр клеток по зависимости от указанных путей (повторяемый) |

Алгоритм:
1. Вызвать `schema_logic`(`cells`, `max_depth`, `depends_on`)
2. Вывести результат через click.echo

Код возврата:
- 0 — успех
- 1 — найдены ошибки парсинга AST

Примеры:

```bash
goga schema
goga schema goga/config goga/ast --max-depth 2
goga schema --depends-on goga/ast
```

### sync

CLI-обёртка команды синхронизации. Делегирует бизнес-логику в `goga.sync.sync`.

Синтаксис:

```
goga sync <source> [--token TOKEN] [--branch BRANCH]
```

Аргументы:

| Аргумент | Тип | Описание |
|----------|-----|----------|
| `source` | str | Путь к каталогу (локальный) или URL git-репозитория |

Опции:

| Опция | Тип | Описание |
|-------|-----|----------|
| `--token` | str | Токен авторизации для HTTPS git-репозитория |
| `--branch` | str | Ветка или тег для checkout при клонировании |

Алгоритм:
1. Вызвать `sync_logic`(`source`, `token`, `branch`)
2. Вернуть exit_code

Код возврата:
- 0 — успех
- 1 — ошибка (путь не существует, нет .usages/, ошибка I/O, ошибка git)

Примеры:

```bash
goga sync /path/to/external/project/goga
goga sync https://github.com/owner/repo
goga sync --token ghp_xxx https://github.com/owner/private-repo
goga sync --token glpat-xxx --branch v2.0 https://gitlab.com/org/repo
goga sync git@github.com:owner/repo.git
```

## Самостоятельные команды

Эти команды реализуют логику напрямую без делегирования.

### linter

Валидация CODEMANIFEST файлов в проекте.

Синтаксис:

```
goga linter [path]
```

Аргументы:

| Аргумент | Тип | Дефолт | Описание |
|----------|-----|--------|----------|
| `path` | str | `.` | Путь к директории для валидации |

Код возврата:
- 0 — успех (нет ошибок)
- 1 — найдены ошибки валидации

Примеры:

```bash
goga linter
goga linter goga/config
```

### contract

Сравнение CODEMANIFEST контракта с реализацией.

Синтаксис:

```
goga contract <cell_path>... [--lang <language>]
```

Аргументы:

| Аргумент | Тип | Описание |
|----------|-----|----------|
| `cells` | list[str] | Один или несколько путей к клеткам для сравнения |

Опции:

| Опция | Тип | Дефолт | Описание |
|-------|-----|--------|----------|
| `--lang` | str | из конфига | Язык реализации. Приоритет: CLI > `config.lang` |

Код возврата:
- 0 — успех
- 1 — ошибка (клетка не найдена, пакет не импортируем, ошибка конфигурации)

Примеры:

```bash
goga contract goga/config goga/ast
goga contract goga/config --lang python
```

### config

Вывод значений опций из конфигурации проекта .goga/config.yml.

Синтаксис:

```
goga config <option>...
```

Аргументы:

| Аргумент | Тип | Описание |
|----------|-----|----------|
| `options` | list[str] | Один или несколько путей к опциям в точечной нотации (например build.task_executor.agent build.worktree) |

Код возврата:
- 0 — успех
- 1 — ошибка (опция не найдена, ошибка конфигурации)

Примеры:

```bash
goga config language
goga config language build.task_executor.agent build.worktree
```
