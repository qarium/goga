# Plan: `add-usages-to-imports`

## Goal

Добавить поддержку `Usages` в секцию `Imports` DSL CODEMANIFEST: разделить `ImportItemNode` на `ImportTypeItemNode` + `ImportUsageItemNode`, обновить парсер Factory, добавить правила валидации `ImportItemIsValid` и `ImportUsageExists`, расширить существующие правила для работы с обоими типами нод. Команда `schema` уже реализована — минимальные изменения не требуются.

## Context

### Contract Surface

**Entity: `ImportTypeItemNode`**
- Kind: class (dataclass)
- Declared `location`: `goga/ast/nodes/header.py`
- Facade obligation: must be importable from `goga/ast/nodes`
- Properties: `type_name -> set[str]`, `from_path -> str`, `alias -> str`
- Mutations: `DocumentNode::ImportTypeItemNode` (наследует от DocumentNode)

**Entity: `ImportUsageItemNode`**
- Kind: class (dataclass)
- Declared `location`: `goga/ast/nodes/header.py`
- Facade obligation: must be importable from `goga/ast/nodes`
- Properties: `usage_name -> set[str]`, `from_path -> str`, `alias -> str`
- Mutations: `DocumentNode::ImportUsageItemNode` (наследует от DocumentNode)

**Entity: `ImportItemIsValid`**
- Kind: class
- Declared `location`: `goga/ast/rules/document.py`
- Facade obligation: must be importable from `goga/ast/rules`
- Signature: `"DocumentRule::ImportItemIsValid(name: str = 'import_item_is_valid')"`
- Method: `check(node: DocumentNode) -> errors:list[DocumentRuleError]`

**Entity: `ImportUsageExists`**
- Kind: class
- Declared `location`: `goga/ast/rules/document.py`
- Facade obligation: must be importable from `goga/ast/rules`
- Signature: `"DocumentRule::ImportUsageExists(name: str = 'import_usage_exists')"`
- Method: `check(node: DocumentNode) -> errors:list[DocumentRuleError]`

### Re-exports

- `ImportTypeItemNode` — из `goga/ast/nodes/__init__.py`, импортируется в `goga/ast/factory`, `goga/ast/rules`
- `ImportUsageItemNode` — из `goga/ast/nodes/__init__.py`, импортируется в `goga/ast/factory`, `goga/ast/rules`
- `ImportItemIsValid` — из `goga/ast/rules/__init__.py`, импортируется в `goga/ast/ast.py`
- `ImportUsageExists` — из `goga/ast/rules/__init__.py`, импортируется в `goga/ast/ast.py`

### Usages Context

- `conventions` (.usages/development/conventions.md): Python 3.10+, dataclasses с kw_only, relative imports, ruff target py310, line-length 120, тесты через pytest, тестовая структура зеркалит исходную
- `dsl` (.usages/codemanifest/dsl.md): спецификация DSL формата CODEMANIFEST — Imports с Types/Usages/From, AS alias, .usages/ директория
- `nodes` (inline): использовать манифест goga/ast/nodes и его API для работы с структурой документа
- `yaml` (inline): библиотека pyyaml для парсинга yaml документов
- `testing` (inline из ast/CODEMANIFEST): интеграционные тесты правил AST — tests/.project/<rule_name>/ с CODEMANIFEST и .expected.yaml

### External Dependencies

- `pyyaml` — парсинг YAML (уже в зависимостях)
- `pytest` — тестирование (уже в зависимостях)
- `ruff` — линтер (уже в зависимостях)

## Facts

- DSL (dsl.md) уже описывает `Usages` в Imports: `Types` + `Usages` + `From` в одной записи
- Текущая реализация `factory.py._parse_imports` парсит только `Types`, полностью игнорирует `Usages`
- `ImportItemNode` — единый класс с полем `type_name`, не различающий тип и практику
- DSL допускает `AS` alias для практик так же как для типов
- Практики хранятся в `<cell>/.usages/<name>.md`
- Команда `schema` уже реализована в `schema.py` и подключена в `cli.py` и `commands/__init__.py`
- `_build_embeddings` строит lookup только для типов (практики не встраиваются)

## Assumptions

- Существующие тесты для `import_has_type` будут адаптированы к `ImportItemIsValid`: критичность medium, safe to proceed: yes
- Парсинг: `entry.get("Types")` возвращает None если ключ отсутствует → skip; `[]` → создать item с пустым множеством: критичность high, safe to proceed: yes

## Open Questions

- (нет — контракт однозначен после уточнения в clarify-design)

## Gap Analysis

- Missing contract entities: `ImportTypeItemNode`, `ImportUsageItemNode`, `ImportItemIsValid`, `ImportUsageExists`
- Missing facade exposure: новые экспорты в `nodes/__init__.py`, `rules/__init__.py`, `ast.py`
- API mismatches: `ImportItemNode` → два класса с разными полями; `ImportHasType` → `ImportItemIsValid`
- Behavioral mismatches: `_parse_imports` не парсит Usages; все правила с `item.type_name` упадут на ImportUsageItemNode
- Existing code that can be reused: `ImportHasType.check` → основа для `ImportItemIsValid`; `_parse_imports` → расширение; `schema.py` → без изменений
- Test coverage gaps: нет тестов для новых правил и DSL-конструкций

---

## Tasks

### Task 1: Replace ImportItemNode with ImportTypeItemNode + ImportUsageItemNode (infrastructure)

Заменить `ImportItemNode` на два класса в `goga/ast/nodes/header.py`, обновить все экспорты и импорты по всему проекту. Это базовая инфраструктурная задача — все последующие задачи зависят от этих классов.

**Usages relevant to this task:**
- `conventions`: Python 3.10+, dataclasses с kw_only=True, default empty values вместо None
- `dsl`: спецификация Imports — Types и Usages как отдельные ключи, AS alias для обоих

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them. If the implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] В `goga/ast/nodes/header.py`: удалить класс `ImportItemNode`, создать `ImportTypeItemNode(type_name: set[str], from_path: str, alias: str)` и `ImportUsageItemNode(usage_name: set[str], from_path: str, alias: str)`. Оба наследуют от `DocumentNode`, поля через `field(default_factory=...)`
- [x] В `goga/ast/nodes/__init__.py`: убрать `ImportItemNode` из импортов и `__all__`, добавить `ImportTypeItemNode` и `ImportUsageItemNode`
- [x] В `goga/ast/factory/factory.py`: обновить import — `from ..nodes import ImportTypeItemNode, ImportUsageItemNode` (вместо ImportItemNode). Временно заменить все `ImportItemNode(...)` на `ImportTypeItemNode(...)` в `_parse_imports`, `_build_embeddings` и других местах чтобы код компилировался. Парсинг Usages будет добавлен в Task 3
- [x] В `goga/ast/rules/document.py`: обновить import — `from ..nodes import ImportTypeItemNode` (вместо ImportItemNode). Временно заменить обращения `item.type_name` на `item.type_name` (пока без isinstance — будет обновлено в Task 4)
- [x] В `goga/ast/rules/__init__.py`: убрать `ImportHasType` из импортов и `__all__` (будет заменён в Task 4), временно оставить остальные
- [x] В `goga/ast/ast.py`: обновить import — убрать `ImportHasType`, временно закомментировать строку `ImportHasType()` в document_rules (будет заменена в Task 4)
- [x] Verify facade availability: `python -c "from goga.ast.nodes import ImportTypeItemNode, ImportUsageItemNode"`
- [x] Run existing tests: `pytest tests/ -x` — некоторые тесты упадут (import_has_type, import_is_used и др.) — это ожидаемо, будет исправлено в последующих задачах
- [x] Lint: `ruff check goga/` — fix formatting if needed

### Task 2: Update Factory._parse_imports to parse Usages from Imports YAML

Расширить `_parse_imports` в `goga/ast/factory/factory.py` для парсинга секции `Usages` из Imports YAML. Также обновить `_wire_references`, `_build_embeddings` и `_parse_header` для работы с обоими типами нод.

**Usages relevant to this task:**
- `dsl`: спецификация Imports — `Types: [names]`, `Usages: [names]`, `From: path` в одной YAML-записи. AS alias для обоих. Пример: `{"Types": ["Foo", "Bar AS B"], "Usages": ["my_usage"], "From": "path/to/cell"}`
- `yaml`: pyyaml — `yaml.safe_load_all` уже используется

**Interaction diagram (from design):**
```
CODEMANIFEST YAML (Imports with Types+Usages+From)
        │
        ▼
  Factory._parse_imports()
        │
        ├─ Types[] → ImportTypeItemNode (per type entry)
        └─ Usages[] → ImportUsageItemNode (per usage entry)
        │
        ▼
  ImportsNode.items: list[ImportTypeItemNode | ImportUsageItemNode]
```

**Data flow trace (from design — Flow 1):**
1. YAML: `{"Types": ["Foo"], "Usages": ["bar"], "From": "path/to/cell"}`
2. `from_path = os.path.normpath(entry.get("From", ""))`
3. `types_raw = entry.get("Types")` — None → skip; [] → ImportTypeItemNode(type_name=set()); list → parse each with AS
4. `usages_raw = entry.get("Usages")` — None → skip; [] → ImportUsageItemNode(usage_name=set()); list → parse each with AS
5. If both None → ImportTypeItemNode(type_name=set()) for backward compat
6. All items share same `from_path` and `data=dict(entry)`

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them. If the implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: написать тесты в `tests/goga/ast/factory/test_parse_imports_usages.py`:
  - test_parse_imports_with_types_and_usages: YAML с Types+Usages+From → items содержит ImportTypeItemNode и ImportUsageItemNode
  - test_parse_imports_usages_only: YAML только с Usages → только ImportUsageItemNode
  - test_parse_imports_types_only: YAML только с Types → только ImportTypeItemNode (как раньше)
  - test_parse_imports_empty_types_creates_empty_item: Types=[] → ImportTypeItemNode с type_name=set()
  - test_parse_imports_empty_usages_creates_empty_item: Usages=[] → ImportUsageItemNode с usage_name=set()
  - test_parse_imports_no_types_no_usages: только From → ImportTypeItemNode с type_name=set()
  - test_parse_imports_usage_alias: Usages=["long_name AS short"] → usage_name={"long_name"}, alias="short"
  - (expected to fail at this stage)
- [x] **Code**: переписать `_parse_imports` в `factory.py`:
  - Для каждого entry: извлечь `from_path` через `os.path.normpath`
  - `types_raw = entry.get("Types")`: если None → skip; если list → парсить каждый элемент (AS split), создавать ImportTypeItemNode; если пустой list → ImportTypeItemNode(type_name=set())
  - `usages_raw = entry.get("Usages")`: если None → skip; если list → парсить каждый (AS split), создавать ImportUsageItemNode; если пустой list → ImportUsageItemNode(usage_name=set())
  - Если оба None → ImportTypeItemNode(type_name=set())
- [x] **Code**: обновить `_wire_references` — цикл по `header.imports.items` уже обходит оба типа нод (type_name и usage_name не используются здесь, только root/parent wiring) — проверить что wire работает корректно
- [x] **Code**: обновить `_build_embeddings` — `import_lookup` строится только из ImportTypeItemNode (isinstance check): `for type_name in item.type_name: import_lookup[type_name] = item.from_path`
- [x] **Code**: обновить `_parse_header` — сбор `types: list[str]` только из ImportTypeItemNode (isinstance check): `for item in imports_node.items: if isinstance(item, ImportTypeItemNode): types.extend(item.type_name)`
- [x] **Verify interfaces**: `pytest tests/goga/ast/factory/test_parse_imports_usages.py -v` — all must pass
- [x] **Logic tests**: добавить поведенческие тесты:
  - test_parse_imports_multiple_entries: несколько YAML-записей с разными From
  - test_parse_imports_invalid_usages_type: Usages="not_a_list" → skip (не падает)
  - test_parse_imports_mixed_types_and_usages: одна запись с Types+Usages, другая только с Types
- [x] **Debug**: `pytest tests/ -x` — fix implementation until all pass
- [x] **Re-check contracts**: verify ImportsNode.items содержит оба типа нод, data dict сохранён для каждого
- [x] **Lint**: `ruff check goga/` — fix formatting

### Task 3: Implement ImportItemIsValid rule (replace ImportHasType)

Заменить класс `ImportHasType` на `ImportItemIsValid` — обобщённое правило, проверяющее что каждый import item (type или usage) содержит хотя бы одно имя. Обновить экспорты и подключение в AST.

**Usages relevant to this task:**
- `testing`: интеграционные тесты правил — `tests/.project/<rule_name>/` с CODEMANIFEST и `.expected.yaml`

**Trace (from design):**
1. Visitor вызывает `ImportItemIsValid.check(node)` для каждого документа
2. Обходит `node.root.header.imports.items` (ImportTypeItemNode + ImportUsageItemNode)
3. ImportTypeItemNode: `item.type_name` не пусто → ok / пусто → ошибка "has no Types listed"
4. ImportUsageItemNode: `item.usage_name` не пусто → ok / пусто → ошибка "has no Usages listed"

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them. If the implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: в `tests/goga/ast/rules/test_import_item_is_valid.py`:
  - test_import_item_is_valid_happy_path: ImportTypeItemNode(type_name={"Foo"}) + ImportUsageItemNode(usage_name={"bar"}) → нет ошибок
  - test_import_item_is_valid_empty_type: ImportTypeItemNode(type_name=set()) → ошибка с "has no Types listed"
  - test_import_item_is_valid_empty_usage: ImportUsageItemNode(usage_name=set()) → ошибка с "has no Usages listed"
  - (expected to fail at this stage)
- [x] **Code**: в `goga/ast/rules/document.py`: удалить класс `ImportHasType`, создать `ImportItemIsValid`:
  - `__init__`: `super().__init__(name="import_item_is_valid")`
  - `check`: итерация по `node.root.header.imports.items` с isinstance:
    - ImportTypeItemNode: if not item.type_name → error "Import from '{from_path}' has no Types listed — specify at least one type to import"
    - ImportUsageItemNode: if not item.usage_name → error "Import from '{from_path}' has no Usages listed — specify at least one type to import"
- [x] **Code**: в `goga/ast/rules/__init__.py`: заменить `ImportHasType` на `ImportItemIsValid` в imports и `__all__`
- [x] **Code**: в `goga/ast/ast.py`: заменить `ImportHasType` на `ImportItemIsValid` в import и в `document_rules` list. Добавить `ImportUsageExists()` после `ImportItemIsValid()` (placeholder — будет реализован в Task 4)
- [x] **Verify interfaces**: `pytest tests/goga/ast/rules/test_import_item_is_valid.py -v`
- [x] **Logic tests**: мигрировать существующий интеграционный тест `tests/.project/import_has_type/` → `tests/.project/import_item_is_valid/`:
  - Переименовать директорию
  - Обновить `.expected.yaml`: rule: "import_item_is_valid", message template "has no Types listed"
- [x] **Debug**: `pytest tests/ -x` — fix until all pass
- [x] **Re-check contracts**: verify rule name = "import_item_is_valid", message template matches CODEMANIFEST
- [x] **Lint**: `ruff check goga/` — fix formatting

### Task 4: Implement ImportUsageExists rule

Создать новое правило `ImportUsageExists` — проверяет что каждая импортируемая практика существует как `.md` файл в `.usages/` директории указанной клетки.

**Usages relevant to this task:**
- `testing`: интеграционные тесты — `tests/.project/import_usage_exists/` с CODEMANIFEST и .expected.yaml
- `dsl`: практики хранятся в `<cell>/.usages/<name>.md`

**Trace (from design):**
1. Visitor вызывает `ImportUsageExists.check(node)` для каждого документа
2. Обходит `node.root.header.imports.items`, фильтрует только `ImportUsageItemNode` (isinstance)
3. Для каждого `usage_name` в item: `Path(item.from_path) / ".usages" / f"{name}.md"` → Path.exists()
4. Если не существует → error "Usage '{usage_name}' does not exists on filesystem by path '{usage_md_file_path}'"

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them. If the implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: в `tests/goga/ast/rules/test_import_usage_exists.py`:
  - test_usage_exists_found: ImportUsageItemNode + файл существует → нет ошибок
  - test_usage_exists_not_found: ImportUsageItemNode + файл не существует → ошибка
  - test_usage_exists_skips_type_items: ImportTypeItemNode → правило не проверяет
  - (expected to fail at this stage)
- [x] **Code**: в `goga/ast/rules/document.py`: создать класс `ImportUsageExists(DocumentRule)`:
  - `__init__`: `super().__init__(name="import_usage_exists")`
  - `check`: фильтрация `isinstance(item, ImportUsageItemNode)`, для каждого `name` в `item.usage_name`:
    `Path(item.from_path) / ".usages" / f"{name}.md"` → exists check
- [x] **Code**: в `goga/ast/rules/__init__.py`: добавить `ImportUsageExists` в imports и `__all__`
- [x] **Code**: в `goga/ast/ast.py`: убедиться что `ImportUsageExists()` добавлен в `document_rules` (после ImportItemIsValid)
- [x] **Verify interfaces**: `pytest tests/goga/ast/rules/test_import_usage_exists.py -v`
- [x] **Logic tests**: создать интеграционный тест `tests/.project/import_usage_exists/`:
  - CODEMANIFEST с `Imports: [{"Usages": ["missing_usage"], "From": "helper"}]` и helper с .usages/
  - .expected.yaml с ошибкой import_usage_exists
  - Создать helper-папку с .usages/ и одним .md файлом для позитивного кейса
- [x] **Debug**: `pytest tests/ -x` — fix until all pass (integration test passes after Task 5 fixes other rules; all unit tests pass)
- [x] **Re-check contracts**: verify rule name, message template, isinstance filter
- [x] **Lint**: `ruff check goga/` — fix formatting

### Task 5: Update existing rules for ImportUsageItemNode compatibility

Обновить все существующие правила, которые итерируют `imports.items` и обращаются к `item.type_name` — добавить isinstance фильтрацию или расширить для работы с ImportUsageItemNode.

**Usages relevant to this task:**
- `nodes`: API DocumentNode — доступ к header.imports.items, body.entities, body.routines

**Rules to update (from design Additional Instructions):**
1. `ImportsHasOnlyValidKeys` — расширить `valid_keys` до `{"Types", "Usages", "From"}`
2. `ImportHasNotDuplicate` — isinstance: ImportTypeItemNode → type_name, ImportUsageItemNode → usage_name. Шаблон: "{Type || Usage} '{name}' is imported more than once: from '{path_a}' and '{path_b}'"
3. `ImportHasValidFromPath` — работает с обоими типами (from_path общий), isinstance не нужен
4. `ImportIsUsed` — isinstance: ImportTypeItemNode → links+signatures; ImportUsageItemNode → links only (include_embedded=True для _collect_links)
5. `AnnotationLinksExists._collect_valid_names` — добавить ImportUsageItemNode: usage_name и alias
6. `EntitiesAndRoutinesHasNotConflicts` — добавить ImportUsageItemNode.usage_name к active_type_names
7. `UsageLinksHasNotConflicts._collect_import_type_names` — добавить ImportUsageItemNode.usage_name
8. `MutationExists` — isinstance ImportTypeItemNode (мутации ссылаются на типы)
9. `ImportTypeExists` (ast.py) — isinstance ImportTypeItemNode (проверка существования типа)

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them. If the implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Code**: `ImportsHasOnlyValidKeys` — `valid_keys = {"Types", "Usages", "From"}` (строка 768)
- [x] **Code**: `ImportHasNotDuplicate` — переписать check(): isinstance для каждого item, ImportTypeItemNode → type_name, ImportUsageItemNode → usage_name. Шаблон ошибки: `"Type '{name}' is imported more than once..."` или `"Usage '{name}' is imported more than once..."`
- [x] **Code**: `ImportIsUsed` — в check() добавить isinstance ветвление: для ImportTypeItemNode — как раньше (links + signatures + property_types + embeddings); для ImportUsageItemNode — только all_links (include_embedded=True). Расширить `_collect_links` параметром `include_embedded=False`
- [x] **Code**: `_collect_valid_names` (module-level в document.py) — для ImportUsageItemNode: `valid_names.update(item.usage_name); if item.alias: valid_names.add(item.alias)`
- [x] **Code**: `EntitiesAndRoutinesHasNotConflicts.check` — для ImportUsageItemNode без alias: `active_type_names.update(item.usage_name)`
- [x] **Code**: `UsageLinksHasNotConflicts._collect_import_type_names` — для ImportUsageItemNode без alias: `names.update(item.usage_name)`
- [x] **Code**: `MutationExists.check` — isinstance ImportTypeItemNode при сборе valid_names из imports
- [x] **Code**: `ImportTypeExists.check` (ast.py) — isinstance ImportTypeItemNode при итерации imports.items
- [x] **Verify interfaces**: `python -c "from goga.ast import AST"` — импорт работает
- [x] **Logic tests**: обновить существующие .expected.yaml файлы:
  - `tests/.project/imports_has_only_valid_keys/.expected.yaml` — если rule name или message изменились
  - `tests/.project/import_has_not_duplicate/.expected.yaml` — если rule name или message изменились
  - `tests/.project/import_is_used/.expected.yaml` — если message изменился
  - Создать `tests/.project/import_has_not_duplicate_usage/` для проверки дублирования usage names
- [x] **Debug**: `pytest tests/ -x` — fix until all pass
- [x] **Re-check contracts**: verify все правила корректно работают с обоими типами нод
- [x] **Lint**: `ruff check goga/` — fix formatting

### Task 6: Integration tests for usages-in-imports

Интеграционные тесты для полного потока: парсинг Imports с Usages, валидация всех правил, команда schema.

**Usages relevant to this task:**
- `testing`: интеграционные тесты — tests/.project/<rule_name>/ с CODEMANIFEST и .expected.yaml, параметризованный тест в test_project_integration.py

**Test scenarios from design (19 tests):**

Positive:
1. test_import_item_is_valid_type_and_usage_happy_path
2. test_import_item_is_valid_usage_only
3. test_import_usage_exists_file_found
4. test_import_is_used_usage_in_annotations
5. test_schema_output_structure

Negative:
6. test_import_item_is_valid_empty_type_name
7. test_import_item_is_valid_empty_usage_name
8. test_import_item_is_valid_empty_usage_with_filled_types
9. test_import_item_is_valid_no_types_no_usages
10. test_import_usage_exists_not_found
11. test_import_is_used_usage_not_used
12. test_imports_has_only_valid_keys_with_usages

Edge cases:
13. test_import_usage_alias_used_in_annotations
14. test_import_usage_exists_no_usages_dir
15. test_schema_empty_tree
16. test_schema_with_max_depth
17. test_import_has_valid_from_path_with_usage_item
18. test_import_has_not_duplicate_usage_names
19. test_schema_with_cells_filter

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them. If the implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Создать интеграционные тестовые фикстуры в `tests/.project/` для новых правил:
  - `import_item_is_valid/` — CODEMANIFEST + .expected.yaml (мигрировано из import_has_type)
  - `import_usage_exists/` — CODEMANIFEST + .expected.yaml + helper с .usages/
  - `import_item_is_valid_usage_only/` — Imports только с Usages
  - `import_item_is_valid_empty_usage/` — Usages: []
  - `import_has_not_duplicate_usage/` — дублирование usage names
- [ ] Создать/обновить `tests/goga/commands/test_schema.py` — тесты для schema команды:
  - test_schema_output_structure
  - test_schema_empty_tree
  - test_schema_with_max_depth
  - test_schema_with_cells_filter
- [ ] Обновить `tests/.project/import_is_used/.expected.yaml` если message изменился
- [ ] Run full integration: `pytest tests/ -x -v`
- [ ] Run project linter: `docker run --rm -v .:/project -w /project goga linter` — 0 errors expected

---

## Validation Commands

- `pytest tests/ -x`: Run all tests
- `ruff check goga/`: Lint check
- `python -c "from goga.ast.nodes import ImportTypeItemNode, ImportUsageItemNode"`: Verify node classes facade
- `python -c "from goga.ast.rules import ImportItemIsValid, ImportUsageExists"`: Verify rule classes facade
- `python -c "from goga.ast import AST"`: Verify AST facade with new rules
- `docker run --rm -v .:/project -w /project goga linter`: CODEMANIFEST linter validation

---

## Done Criteria

- [ ] `ImportTypeItemNode` реализован в `goga/ast/nodes/header.py` с полями type_name, from_path, alias
- [ ] `ImportUsageItemNode` реализован в `goga/ast/nodes/header.py` с полями usage_name, from_path, alias
- [ ] Оба класса доступны из `goga/ast/nodes` facade
- [ ] `ImportItemIsValid` реализован в `goga/ast/rules/document.py`, заменяет ImportHasType
- [ ] `ImportUsageExists` реализован в `goga/ast/rules/document.py`
- [ ] Оба правила доступны из `goga/ast/rules` facade и подключены в AST.load()
- [ ] `Factory._parse_imports` парсит Types и Usages из Imports YAML
- [ ] Все существующие правила обновлены для работы с обоими типами нод
- [ ] `schema` команда работает корректно с обоими типами нод
- [ ] `ImportItemNode` и `ImportHasType` полностью удалены из кодовой базы
- [ ] Все интеграционные тесты проходят (tests/.project/)
- [ ] Все unit-тесты проходят
- [ ] CODEMANIFEST linter — 0 errors
- [ ] Ruff — 0 errors
- [ ] CODEMANIFEST файлы не были изменены