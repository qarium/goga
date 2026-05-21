# CLI Command: build

## Назначение

CLI-обёртка команды сборки. Парсит click-опции, загружает конфигурацию и делегирует бизнес-логику в `goga/build`.

## Синтаксис

```
goga build <plan> [--dry-run] [--worktree] [--skip-finalize] [--skip-manifest-check]
                 [--session-timeout T] [--idle-timeout T] [--wait T]
                 [--max-iterations N] [--review-patience N]
```

## Аргументы

| Аргумент | Тип | Описание |
|----------|-----|----------|
| `plan` | str | Путь к плану для ralphex |

## Опции

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

## Код возврата

- 0 — успех
- 1 — ошибка

## Примеры

```bash
goga build docs/plans/my-plan.md
goga build docs/plans/my-plan.md --dry-run --worktree
```