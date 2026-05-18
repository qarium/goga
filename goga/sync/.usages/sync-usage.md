# Sync API — goga/sync

## Обзор

Модуль `goga.sync` предоставляет синхронизацию .usages/ файлов из локального пути
или git-репозитория в `.goga/usages/deps/`.

## Использование

```python
from goga.sync import sync

# Локальный путь
exit_code = sync(source="/path/to/external/project/goga")

# Git-репозиторий (публичный)
exit_code = sync(source="https://github.com/owner/repo")

# Git-репозиторий (с токеном и веткой)
exit_code = sync(
    source="https://github.com/owner/private-repo",
    token="ghp_xxx",
    branch="v2.0"
)

# SSH
exit_code = sync(source="git@github.com:owner/repo.git")
```

## Возвращаемое значение

- `0` — успех
- `1` — ошибка (путь не существует, нет .usages/, ошибка I/O, ошибка git)

## Побочные эффекты

- Создаёт/перезаписывает каталог `.goga/usages/deps/<name>/`
- При git-режиме создаёт и удаляет временный каталог
- Требует `git` в PATH при git-режиме

## Результат синхронизации

```
Исходный путь: /path/to/external/goga/
  .usages/dsl.md
  commands/.usages/cli-commands.md

Результат: .goga/usages/deps/goga/
  .usages/dsl.md
  commands/.usages/cli-commands.md
```
