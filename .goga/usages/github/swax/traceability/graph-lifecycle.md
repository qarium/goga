# Traceability graph — жизненный цикл и персистентность

## Предметная область

Шаблоны построения и сохранения графа отслеживаемости API. Целевая аудитория: cell `applications/discover/` (накапливает рёбра из ЛЛМ-вывода и сохраняет граф в .swax/traceability.yml).

Граф оперирует только путями — без HTTP-методов, без абстракции ресурсов. Это архитектурное правило Swax: минимальная абстракция. Узлы = пути API, рёбра = выявленные зависимости между эндпоинтами.

Формат файла .swax/traceability.yml:
```yaml
/payment:
  - /users
  - /orders
/orders:
  - /payment
```
Ключи — пути, значения — списки зависимых путей.

---

## Построение графа

`TraceabilityGraph` накапливает рёбра через `add_edge` во время ЛЛМ-анализа:

```python
from swax.traceability import TraceabilityGraph

def build_from_llm_output(dependencies: dict[str, list[str]]) -> TraceabilityGraph:
    graph = TraceabilityGraph(edges={})
    for source, targets in dependencies.items():
        for target in targets:
            graph.add_edge(source=source, target=target)
    return graph
```

Соглашения потребителя:
- `source` — путь, который зависит от другого.
- `target` — путь, от которого зависит `source`.
- Дубликаты в момент добавления допустимы — они устраняются позже через deduplicate.

---

## Дедупликация перед сохранением

Перед сериализацией граф обязательно дедуплицируется — это убирает повторяющиеся рёбра и самозависимости, обеспечивая детерминированный вывод:

```python
from swax.traceability import TraceabilityGraph

def finalize(graph: TraceabilityGraph) -> TraceabilityGraph:
    graph.deduplicate()
    return graph
```

Соглашения потребителя:
- Идемпотентен — безопасно вызывать несколько раз.
- Возвращает отсортированные списки рёбер внутри каждого ключа.
- Пустые adjacency-списки сохраняются — путь без зависимостей остаётся узлом графа. `run_discover` полагается на это, гарантируя что каждый endpoint из спецификаций присутствует в `.swax/traceability.yml`.

---

## Сохранение графа

`save_traceability` пишет детерминированный YAML: ключи и значения отсортированы явно в Python для стабильного diff-а между запусками:

```python
from pathlib import Path

from swax.traceability import TraceabilityGraph, save_traceability

def persist(graph: TraceabilityGraph, project_root: Path) -> None:
    save_traceability(graph, project_root / ".swax" / "traceability.yml")
```

Соглашения потребителя:
- Передать граф, для которого уже вызван deduplicate.
- Функция создаёт родительские каталоги при необходимости.
- mode="json" для pydantic-dump гарантирует YAML-совместимые примитивы.

---

## Чтение графа

`load_traceability` читает .swax/traceability.yml обратно в модель. Пустой файл даёт пустой граф, а не ошибку:

```python
from pathlib import Path

from swax.traceability import load_traceability

def reload(project_root: Path):
    return load_traceability(project_root / ".swax" / "traceability.yml")
```

Чтение используется в задачах 2-3 (plan, update) — задача 1 (discover) только пишет граф.
