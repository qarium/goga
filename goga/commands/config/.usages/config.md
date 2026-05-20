# CLI Command: config

## Назначение

Вывод значений опций из конфигурации проекта .goga/config.yml. Поддерживает навигацию по всем полям через точечную нотацию.

## Синтаксис

```
goga config <option>...
```

## Аргументы

| Аргумент | Тип | Описание |
|----------|-----|----------|
| `options` | list[str] | Пути к опциям в точечной нотации (например build.task_executor.agent) |

## Формат вывода

```
# language
python

# build.task_executor.agent
claude

# build.worktree
True
```

- Каждая опция начинается с заголовка `# <path>`
- Между опциями — пустая строка
- Примитивы выводятся как есть
- Сложные типы выводятся в YAML-формате

## Код возврата

- 0 — успех
- 1 — ошибка (опция не найдена, ошибка конфигурации)

## Примеры

```bash
goga config language
goga config language build.task_executor.agent build.worktree
```