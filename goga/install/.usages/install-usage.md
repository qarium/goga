# Install API — goga/install

## Обзор

Модуль `goga.install` реализует логику установки скиллов и команд goga
в конфигурацию целевого AI-агента.

## Использование

```python
from goga.config import load_config
from goga.install import install

# Загрузить конфигурацию
config = load_config()

# Установка с agent из конфига
exit_code = install(agent=None, config=config)

# Установка с явным agent
exit_code = install(agent="claude", config=config)
```

## Параметры

- `agent` — целевой AI-агент ("claude"). Если None — из config
- `config` — объект Config, загруженный через `load_config`

## Возвращаемое значение

- `0` — успех
- `1` — ошибка (неподдерживаемый агент, ресурсы не найдены, ошибка скачивания)

## Побочные эффекты

- Удаляет подпапки goga-* в <target>/skills/
- Копирует goga/agent/commands/* → <target>/commands/goga/
- Копирует goga/agent/skills/* → <target>/skills/
- Скачивает dsl.md из GitHub и записывает в <target>/skills/goga-cell/dsl.md

## Целевые каталоги

| Агент  | Путь       |
|--------|------------|
| claude | ~/.claude/ |
