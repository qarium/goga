# CLI Command: sync

## Назначение

CLI-обёртка команды синхронизации. Делегирует бизнес-логику в `goga/sync`. Копирует .usages/ из локального пути или git-репозитория.

## Синтаксис

```
goga sync <source> [--token TOKEN] [--branch BRANCH]
```

## Аргументы

| Аргумент | Тип | Описание |
|----------|-----|----------|
| `source` | str | Путь к каталогу (локальный) или URL git-репозитория |

## Опции

| Опция | Тип | Описание |
|-------|-----|----------|
| `--token` | str | Токен авторизации для HTTPS git-репозитория |
| `--branch` | str | Ветка или тег для checkout при клонировании |

## Код возврата

- 0 — успех
- 1 — ошибка

## Примеры

```bash
goga sync /path/to/external/project/goga
goga sync https://github.com/owner/repo
goga sync --token ghp_xxx https://github.com/owner/private-repo
goga sync --token glpat-xxx --branch v2.0 https://gitlab.com/org/repo
goga sync git@github.com:owner/repo.git
```