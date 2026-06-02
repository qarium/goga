# Connect API — goga/connect

## Обзор

Модуль `goga.connect` реализует логику подключения скиллов и команд goga
в конфигурацию целевого AI-агента.

## Использование

```python
from goga.config import load_config
from goga.connect import connect

# Загрузить конфигурацию
config = load_config()

# Подключение с agent из конфига
exit_code = connect(agent=None, config=config)

# Подключение с явным agent
exit_code = connect(agent="claude", config=config)

# Подключение с перезаписью tool skills
exit_code = connect(agent="claude", config=config, force_overwrite=True)
```

## Параметры

- `agent` — целевой AI-агент ("claude"). Если None — из config
- `config` — объект Config, загруженный через `load_config`
- `force_overwrite` — разрешить перезапись существующих скиллов из пакетов инструментов. По умолчанию False

## Возвращаемое значение

- `0` — успех
- `1` — ошибка (неподдерживаемый агент, ресурсы не найдены, ошибка скачивания)

## Побочные эффекты

- Удаляет подпапки goga-* в <target>/skills/
- Копирует goga/agent/commands/* → <target>/commands/goga/
- Копирует goga/agent/skills/* → <target>/skills/
- Скачивает dsl.md из GitHub и записывает в <target>/skills/goga-cell/dsl.md
- Обнаруживает Python-пакеты с префиксом `goga_tool_*` через importlib.metadata
- Копирует скиллы из обнаруженных пакетов в <target>/skills/ с префиксом `goga-tool-`
- При `force_overwrite=False` — пропускает существующие скиллы с предупреждением
- При `force_overwrite=True` — перезаписывает существующие скиллы

## Целевые каталоги

| Агент  | Путь       |
|--------|------------|
| claude | ~/.claude/ |
