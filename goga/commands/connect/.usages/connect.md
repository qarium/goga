# CLI Command: connect

## Назначение

CLI-обёртка команды подключения. Парсит click-аргументы и делегирует бизнес-логику в `goga/connect`.

## Синтаксис

```
goga connect <agent> [<agent> ...] [--force-overwrite]
```

## Аргументы

| Аргумент | Тип | Обязательный | Описание |
|----------|-----|-------------|----------|
| `agents` | tuple[str, ...] | Да | Один или несколько целевых AI-агентов |

## Опции

| Опция | Тип | Дефолт | Описание |
|-------|-----|--------|----------|
| `--force-overwrite` | flag | False | Перезаписывать существующие скиллы при установке из пакетов инструментов |

## Код возврата

- 0 — успех
- 1 — ошибка

## Примеры

```bash
goga connect claude
goga connect codex
goga connect cursor
goga connect claude codex cursor
goga connect claude --force-overwrite
```
