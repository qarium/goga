# CLI Commands — goga/commands

## Обзор

Пакет `goga.commands` предоставляет CLI-интерфейс для работы с CODEMANIFEST. Все команды запускаются через `goga <command> [options]`.

Все команды импортируются из фасада:

```python
from goga.commands import install, contract, build, linter, schema, config
```

Или через корневой CLI:

```python
from goga.cli import app
```

## Конфигурация

Файл `.goga.yml` обязателен для команд `install` и `contract`. Он загружается через `load_config()` из `goga.config`.

Минимальный `.goga.yml`:

```yaml
language: python
build:
  task_executor:
    agent: claude
```

Приоритет значений: CLI-аргумент > Config. Если CLI-аргумент не указан (None), используется значение из `.goga.yml`.

Ошибки конфигурации (`FileNotFoundError`, `KeyError`, `ValueError`, `yaml.YAMLError`) преобразуются в `click.ClickException`.

## Команды

### install

Установка goga-скиллов и команд в конфигурацию целевого AI-агента.

Синтаксис:

```
goga install [--agent <name>]
```

Опции:

| Опция | Тип | Дефолт | Описание |
|-------|-----|--------|----------|
| `--agent` | str | из конфига | Целевой AI-агент (`claude`). Приоритет: CLI > `build.task_executor.agent` |

Поведение:
- Загружает конфигурацию через `load_config()`
- Если `--agent` не указан, берётся из `config.build.task_executor.agent`
- Удаляет все подпапки с префиксом goga- из целевой директории skills/
- Копирует команды и скиллы в целевую директорию агента (например, `~/.claude/`)
- Выводит summary установленных команд и скиллов в stdout

Код возврата:
- 0 — успех
- 1 — ошибка (неподдерживаемый агент, ресурсы не найдены, ошибка конфигурации, ошибка копирования)

Примеры:

```bash
# Использовать agent из конфига
goga install

# Явно указать agent (переопределяет конфиг)
goga install --agent claude
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
| `--lang` | str | из конфига | Язык реализации. Приоритет: CLI > `config.lang`. Зарезервирован для будущих языков |

Поведение:
- Загружает конфигурацию через `load_config()`
- Если `--lang` не указан, берётся из `config.lang`
- Строит AST проекта через `AST(".").load()`
- Для каждой клетки: извлекает контракт из CODEMANIFEST и реализацию через `python_contract()`
- Выводит JSON со сравнением (codemanifest vs implementation) для каждой сигнатуры, свойства и метода

Код возврата:
- 0 — успех
- 1 — ошибка (клетка не найдена, пакет не импортируем, ошибка конфигурации)

Примеры:

```bash
# Сравнить клетки, используя lang из конфига
goga contract goga/config goga/ast

# Явно указать lang (переопределяет конфиг)
goga contract goga/config --lang python
```

### build

Сборка кода через ralphex. Подготавливает окружение и запускает ralphex.

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

Поведение:
- Проверяет наличие uncommitted CODEMANIFEST файлов (если не `--skip-manifest-check`)
- Загружает конфигурацию через `load_config()`
- Создаёт `.claude/settings.json` и `.ralphex/claude-wrapper.sh`
- Копирует дефолтные промпты и агенты в `.ralphex/`
- Собирает и запускает ralphex команду

Код возврата:
- 0 — успех
- 1 — ошибка (uncommitted manifests, ошибка конфига, ralphex не найден, ошибка ralphex)

Примеры:

```bash
goga build docs/plans/my-plan.md
goga build docs/plans/my-plan.md --dry-run --worktree
```

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

Поведение:
- Меняет CWD на указанный путь
- Загружает AST проекта через `AST(".").load()`
- Выводит ошибки валидации с правилом, сообщением и путём к документу

Код возврата:
- 0 — успех (нет ошибок)
- 1 — найдены ошибки валидации

Примеры:

```bash
goga linter
goga linter goga/config
```

### schema

Вывод структуры проекта CODEMANIFEST в виде JSON-дерева.

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

Поведение:
- Загружает AST проекта через `AST(".").load()`
- Строит JSON-дерево с информацией о клетках: путь, описание, типы, практики, зависимости
- Фильтрует по указанным клеткам, глубине и зависимостям

Код возврата:
- 0 — успех
- 1 — найдены ошибки парсинга AST

Примеры:

```bash
goga schema
goga schema goga/config goga/ast --max-depth 2
goga schema --depends-on goga/ast
```

### config

Вывод значений опций из конфигурации проекта .goga.yml.
Каждая опция выводится отдельно с заголовком-путём.

Синтаксис:

```
goga config <option>...
```

Аргументы:

| Аргумент | Тип | Описание |
|----------|-----|----------|
| `options` | list[str] | Один или несколько путей к опциям в точечной нотации (например build.task_executor.agent build.worktree) |

Поведение:
- Загружает конфигурацию через `load_config()`
- Для каждого пути: разрешает по атрибутам объекта Config
- Выводит заголовок `# <path>` перед значением каждой опции
- Для примитивов (str, int, bool) — выводит сырое значение
- Для None — выводит "null"
- Для сложных (dict, dataclass) — выводит YAML

Поддерживаемые пути:
- `language` — язык проекта
- `build` — вся секция build (YAML)
- `build.task_executor` — конфигурация AI-агента (YAML)
- `build.task_executor.agent` — имя AI-executor
- `build.task_executor.env` — переменные окружения (YAML)
- `build.worktree` — флаг worktree
- `build.skip_finalize` — флаг пропуска финализации
- `build.session_timeout` — таймаут сессии
- `build.idle_timeout` — таймаут простоя
- `build.wait` — время ожидания
- `build.max_iterations` — максимум итераций
- `build.review_patience` — порог ревью
- `build.prompts_dir` — путь к промптам
- `build.agents_dir` — путь к агентам
- `build.codex_review` — флаг codex ревью
- `commands` — кастомные команды (YAML)

Код возврата:
- 0 — успех
- 1 — ошибка (опция не найдена, ошибка конфигурации)

Примеры:

```bash
goga config language
# language
python

goga config language build.task_executor.agent build.worktree
# language
python

# build.task_executor.agent
claude

# build.worktree
True

goga config build.task_executor.env
# build.task_executor.env
ANTHROPIC_API_KEY: sk-xxx
MODEL: claude-sonnet-4-6
```
