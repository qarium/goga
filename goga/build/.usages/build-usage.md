# Build API — goga/build

## Обзор

Модуль `goga.build` реализует логику сборки кода через ralphex —
подготовку окружения, создание конфигураций AI-агента и запуск процесса сборки.

## Использование

```python
from goga.config import load_config
from goga.build import build

# Загрузить конфигурацию
config = load_config()

# Запустить сборку
exit_code = build(
    plan="docs/plans/my-plan.md",
    config=config,
    cli_options={
        "dry_run": False,
        "worktree": True,
        "skip_finalize": False,
        "skip_manifest_check": False,
    }
)
```

## Параметры

- `plan` — путь к файлу плана (markdown)
- `config` — объект Config, загруженный через `load_config`
- `cli_options` — словарь опций:
  - `dry_run` (bool) — показать команду без выполнения
  - `worktree` (bool) — режим git worktree
  - `skip_finalize` (bool) — пропустить финализацию
  - `skip_manifest_check` (bool) — пропустить проверку CODEMANIFEST
  - `session_timeout`, `idle_timeout`, `wait` (str) — таймауты
  - `max_iterations`, `review_patience` (int) — лимиты

## Возвращаемое значение

- `0` — успех
- `1` — ошибка (uncommitted manifests, ralphex не найден, ошибка сборки)

## Побочные эффекты

- Создаёт/обновляет `.claude/settings.json`
- Создаёт `.ralphex/claude-wrapper.sh` и `.ralphex/config`
- Копирует prompts и agents в `.ralphex/`
- Запускает subprocess (`ralphex`)
