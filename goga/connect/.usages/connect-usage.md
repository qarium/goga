# Connect API — goga/connect

## Обзор

Модуль `goga.connect` реализует логику подключения скиллов и команд goga
в конфигурацию одного или нескольких целевых AI-агентов.

## Использование

```python
from goga.connect import connect

# Подключение для одного агента
exit_code = connect(agents=["claude"])

# Подключение для нескольких агентов
exit_code = connect(agents=["claude", "codex"])

# Подключение с перезаписью tool skills
exit_code = connect(agents=["claude"], force_overwrite=True)
```

## Параметры

- `agents` — список целевых AI-агентов (обязательный, не пустой). Поддерживаемые: "claude", "codex", "cursor"
- `force_overwrite` — разрешить перезапись существующих скиллов из пакетов инструментов. По умолчанию False

## Возвращаемое значение

- `0` — успех
- `1` — ошибка (пустой список агентов, неподдерживаемый агент, ресурсы не найдены, ошибка скачивания)

## Побочные эффекты

Для каждого агента из списка:
- Удаляет подпапки goga-* в <target>/skills/
- Копирует goga/agent/commands/* → <target>/commands/goga/
- Копирует goga/agent/skills/* → <target>/skills/
- Скачивает dsl.md из GitHub и записывает в <target>/skills/goga-cell/dsl.md
- Обнаруживает Python-пакеты с префиксом `goga_tool_*` через importlib.metadata
- Копирует скиллы из обнаруженных пакетов в <target>/skills/ с префиксом `goga-tool-`
- При `force_overwrite=False` — пропускает существующие скиллы с предупреждением
- При `force_overwrite=True` — перезаписывает существующие скиллы

## Целевые каталоги

| Агент  | Путь       | Команды | Скиллы |
|--------|------------|---------|--------|
| claude | ~/.claude/ | Да      | Да     |
| codex  | ~/.codex/  | Нет     | Да     |
| cursor | ~/.cursor/ | Нет     | Да     |
