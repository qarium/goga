# CLI Command: build

## Назначение

CLI-обёртка команды сборки. Парсит click-опции, загружает конфигурацию и запускает goga.build внутри Docker-контейнера.

## Синтаксис

```
goga build <plan> [--dry-run] [--worktree] [--skip-finalize] [--skip-manifest-check]
                 [--session-timeout T] [--idle-timeout T] [--wait T]
                 [--max-iterations N] [--review-patience N]
                 [-e KEY=VALUE ...]
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
| `-e` / `--env` | str (multiple) | — | Передать переменные окружения в контейнер (KEY=VALUE) |

## Код возврата

- 0 — успех
- 1 — ошибка

## Примеры

```bash
goga build docs/plans/my-plan.md
goga build docs/plans/my-plan.md --dry-run --worktree
goga build docs/plans/my-plan.md -e ANTHROPIC_API_TOKEN=sk-xxx -e MODEL=claude-sonnet-4-6
```

## Требования

- Docker должен быть установлен и доступен в PATH