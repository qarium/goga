# CLI Command: install

## Назначение

CLI-обёртка команды установки. Парсит click-опции, загружает конфигурацию и делегирует бизнес-логику в `goga/install`.

## Синтаксис

```
goga install [--agent <name>]
```

## Опции

| Опция | Тип | Дефолт | Описание |
|-------|-----|--------|----------|
| `--agent` | str | из конфига | Целевой AI-агент |
| `--force-overwrite` | flag | False | Перезаписывать существующие скиллы при установке из пакетов инструментов |

## Код возврата

- 0 — успех
- 1 — ошибка

## Примеры

```bash
goga install
goga install --agent claude
goga install --force-overwrite
goga install --agent claude --force-overwrite
```