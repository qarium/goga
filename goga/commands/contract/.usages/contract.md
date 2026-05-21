# CLI Command: contract

## Назначение

Сравнение CODEMANIFEST контракта с реализацией. Для каждого типа в контракте находит соответствие в коде и строит структуру сравнения.

## Синтаксис

```
goga contract <cell_path>... [--lang <language>]
```

## Аргументы

| Аргумент | Тип | Описание |
|----------|-----|----------|
| `cells` | list[str] | Один или несколько путей к клеткам для сравнения |

## Опции

| Опция | Тип | Дефолт | Описание |
|-------|-----|--------|----------|
| `--lang` | str | из конфига | Язык реализации. Приоритет: CLI > config.lang |

## Формат вывода

JSON-структура, где CODEMANIFEST — источник истины:

```json
{
  "norm/path/to/cell": {
    "TypeName": {
      "signature": { "codemanifest": "...", "implementation": "..." },
      "properties": { "name": { "codemanifest": "...", "implementation": "..." } },
      "methods": { "name": { "codemanifest": "...", "implementation": "..." } }
    },
    "RoutineName": {
      "signature": { "codemanifest": "...", "implementation": "..." }
    }
  }
}
```

## Код возврата

- 0 — успех
- 1 — ошибка (клетка не найдена, ошибка конфигурации)

## Примеры

```bash
goga contract goga/config goga/ast
goga contract goga/config --lang python
```