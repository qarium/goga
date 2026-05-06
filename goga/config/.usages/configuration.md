# Конфигурация проекта — goga/config

## Обзор

Пакет `goga.config` предоставляет единый доступ к конфигурации проекта через файл `.goga.yml`.

## Фасад

Все типы импортируются напрямую из `goga.config`:

```python
from goga.config import Config, BuildConfig, TaskExecutor, CodemanifestConfig, load_config
```

## Загрузка конфигурации

### load_config() -> Config

Читает и парсит `.goga.yml` из текущей рабочей директории (CWD).

**Вызов**:

```python
from goga.config import load_config

config = load_config()
```

**Поведение**:
- Файл `.goga.yml` обязателен — при отсутствии или пустом содержимом выбрасывает `FileNotFoundError`
- Корневой элемент YAML должен быть mapping — иначе `ValueError`
- Обязательные секции: `language`, `build`, `build.task_executor`, `build.task_executor.agent`
- При невалидном YAML выбрасывает `yaml.YAMLError`

**Обработка ошибок**:

```python
from goga.config import load_config

try:
    config = load_config()
except FileNotFoundError:
    # .goga.yml не найден или пустой
except KeyError as e:
    # Нарушение структуры — отсутствует обязательная секция
    print(e)
except ValueError as e:
    # Некорректное значение поля
    print(e)
except yaml.YAMLError as e:
    # Синтаксическая ошибка YAML
```

## Структура .goga.yml

Минимальный валидный файл:

```yaml
language: python
build:
  task_executor:
    agent: claude
```

Полный файл со всеми опциями:

```yaml
language: python
commands:
  test: pytest
build:
  task_executor:
    agent: claude
    env:
      ANTHROPIC_API_KEY: sk-xxx
      MODEL: claude-sonnet-4-6
  worktree: true
  skip_finalize: false
  session_timeout: "30m"
  idle_timeout: "1h"
  wait: "5m"
  max_iterations: 10
  review_patience: 3
  prompts_dir: /custom/prompts
  agents_dir: /custom/agents
  codex_review: true
codemanifest:
  usages:
    usage_name: path/to/file.md
  annotations: |
    Используй практику `usage_name`.
```

### Обязательные поля

| Поле | Тип | Описание |
|------|-----|----------|
| `language` | str | Язык проекта |
| `build.task_executor` | mapping | Конфигурация AI-агента |
| `build.task_executor.agent` | str | AI-executor: `claude`, `codex`, `copilot`, `gemini`, `custom:/path` |

### Опциональные поля

| Поле | Тип | Дефолт | Описание |
|------|-----|--------|----------|
| `commands` | mapping | `{}` | Кастомизация промптов (заготовка) |
| `build.task_executor.env` | mapping | `{}` | Переменные окружения {str: str} |
| `build.worktree` | bool | None | Изолированный git worktree |
| `build.skip_finalize` | bool | None | Пропустить финализацию |
| `build.session_timeout` | str | None | Таймаут сессии (Go duration) |
| `build.idle_timeout` | str | None | Таймаут простоя (Go duration) |
| `build.wait` | str | None | Ожидание при rate limit (Go duration) |
| `build.max_iterations` | int | None | Максимум итераций |
| `build.review_patience` | int | None | Порог остановки ревью |
| `build.prompts_dir` | str | None | Путь к кастомным промптам |
| `build.agents_dir` | str | None | Путь к кастомным агентам |
| `build.codex_review` | bool | None | Включить codex ревью |
| `codemanifest` | mapping | None | Конфигурация практик и аннотаций CODEMANIFEST |
| `codemanifest.usages` | mapping | `{}` | Маппинг {usage_name: path/to/file.md} |
| `codemanifest.annotations` | str | None | Текстовые аннотации для AI-агента |

## Доступ к данным

Все объекты — immutable dataclasses (frozen=True). Поля доступны только для чтения.

```python
config = load_config()

# Корневые поля
config.lang           # str — язык проекта
config.build          # BuildConfig
config.commands       # dict — кастомные команды

# BuildConfig
config.build.task_executor   # TaskExecutor
config.build.worktree        # bool | None
config.build.session_timeout # str | None

# TaskExecutor
config.build.task_executor.agent  # str
config.build.task_executor.env    # dict — {str: str}

# CodemanifestConfig
config.codemanifest                    # CodemanifestConfig | None
config.codemanifest.usages             # dict — {str: str}
config.codemanifest.annotations        # str | None
```

## Immutability

Объекты frozen — попытка модификации вызывает `FrozenInstanceError`:

```python
config = load_config()
config.lang = "go"  # dataclasses.FrozenInstanceError
```

Для изменения конфигурации создайте новый объект:

```python
from dataclasses import replace
from goga.config import Config

new_config = replace(config, lang="go")
```
