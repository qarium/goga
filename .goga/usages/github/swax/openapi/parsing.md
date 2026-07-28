# Parsing — разбор спецификаций OpenAPI/Swagger

## Предметная область

Шаблоны обнаружения файлов спецификаций и их разбора в полностью разыменованный dict. Целевая аудитория: cell `applications/discover/` (находит все спецификации в локальном каталоге и разбирает каждую через Prance).

Prance разворачивает $ref в памяти, поэтому последующему коду никогда не приходится разрешать ссылки вручную. Swagger 2.0 и OpenAPI 3.x обрабатываются прозрачно.

---

## Обнаружение спецификаций

`discover_specs` сканирует каталог по расширению и лёгкой эвристике (файл должен содержать ключ openapi или swagger в начале):

```python
from pathlib import Path

from swax.openapi import discover_specs

def collect_spec_files(specs_root: Path) -> list[Path]:
    return discover_specs(specs_root)
```

Соглашения потребителя:
- `root` — локальный путь из `SpecsConfig.location`.
- Эвристика дешёвая (читает только head файла) — полный разбор выполняется позже через `parse_spec`.
- Возвращает отсортированный список для детерминированного порядка обработки.

---

## Разбор спецификации

`parse_spec` возвращает полностью разырешённый dict — $ref уже инлайнены:

```python
from pathlib import Path

from swax.openapi import parse_spec

def load_one_spec(spec_path: Path) -> dict:
    return parse_spec(spec_path)
```

Соглашения потребителя:
- Принимает .yaml, .yml, .json файлы.
- Возвращает dict с paths (пути) и схемами (в components.schemas для OpenAPI 3.x или definitions для Swagger 2.0).
- При ошибке разбора выбрасывает `SpecParseError` с путём файла и причиной — CLI-handler маппит в `click.ClickException`.

---

## Объединение: сканирование → разбор

Типичный сценарий в use-case:

```python
from swax.openapi import discover_specs, parse_spec

def load_all_specs(specs_root: Path) -> list[dict]:
    return [parse_spec(p) for p in discover_specs(specs_root)]
```

RAM-ограничение: Prance разворачивает $ref в памяти, поэтому для очень больших спецификаций потребление RAM может быть значительным — известное ограничение, принимается архитектурно.

---

## Рекурсивные схемы

`parse_spec` поддерживает самоссылающиеся и взаимно-рекурсивные схемы — валидную конструкцию OpenAPI. Пример:

```yaml
components:
  schemas:
    Polygon:
      type: object
      properties:
        children:
          type: array
          items:
            $ref: "#/components/schemas/Polygon"   # цикл
```

Поведение:

- Все **некольцевые** `$ref` разворачиваются в памяти как обычно.
- Цикл разворачивается один раз (recursion limit = 1), затем в точке повторного входа подставляется маркер `{"$ref": "#/components/schemas/Polygon"}` вместо бесконечного вложения.

```python
spec = parse_spec(path)
polygon = spec["components"]["schemas"]["Polygon"]
# Первый уровень children развёрнут (видны все свойства Polygon),
# точка цикла — на один уровень глубже.
children_items = polygon["properties"]["children"]["items"]
assert children_items["properties"]["children"]["items"] == {
    "$ref": "#/components/schemas/Polygon"
}
```

Соглашения потребителя:

- Downstream-код (extract_paths, extract_schemas, LLM-context) должен толерантно относиться к маркеру `$ref` в значениях схем — это ожидаемый сигнал цикла, а не необработанная ссылка.
- Пост-resolve валидация OpenAPI намеренно отключена: она отбраковывает валидные рекурсивные схемы после разворачивания. Контракт `parse_spec` — структура dict, а не соответствие схеме OpenAPI.
