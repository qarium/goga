# CLI Command: connect

## Назначение

CLI-обёртка команды подключения. Парсит click-опции, загружает конфигурацию и делегирует бизнес-логику в `goga/connect`.

## Синтаксис

```
goga connect [--agent <name>]
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
goga connect
goga connect --agent claude
goga connect --force-overwrite
goga connect --agent claude --force-overwrite
```
