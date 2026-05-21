# CLI Command: schema

## Назначение

CLI-обёртка команды схемы. Делегирует бизнес-логику в `goga/schema`. Выводит JSON-дерево CODEMANIFEST ячеек проекта.

## Синтаксис

```
goga schema [cells...] [--max-depth N] [--depends-on PATH]
```

## Аргументы

| Аргумент | Тип | Описание |
|----------|-----|----------|
| `cells` | list[str] | Пути к клеткам для фильтрации (необязательно) |

## Опции

| Опция | Тип | Дефолт | Описание |
|-------|-----|--------|----------|
| `--max-depth` | int | None | Ограничение глубины вложенности |
| `--depends-on` | list[str] | None | Фильтр клеток по зависимости (повторяемый) |

## Код возврата

- 0 — успех
- 1 — найдены ошибки парсинга AST

## Примеры

```bash
goga schema
goga schema goga/config goga/ast --max-depth 2
goga schema --depends-on goga/ast
```