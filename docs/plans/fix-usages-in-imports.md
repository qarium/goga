# Plan: `fix-usages-in-imports`

## Goal

Привести реализацию `ImportsNode` в соответствие с CODEMANIFEST контрактом: заменить гетерогенный `items: list[ImportTypeItemNode | ImportUsageItemNode]` на два гомогенных списка `types: list[ImportTypeItemNode]` и `usages: list[ImportUsageItemNode]`. Каскадно обновить Factory, все 14 правил (11 DocumentRule + 3 ASTRule), команду schema и все тесты.

## Context

### Contract Surface

**Entity: `ImportsNode`**
- Kind: class (dataclass)
- Declared `location`: header.py
- Facade obligation: must be importable from `goga.ast.nodes`
- Properties:
  - `types -> list[ImportTypeItemNode]` — Список импортов типов
  - `usages -> list[ImportUsageItemNode]` — Список импортов практик
- Imported dependencies: `DocumentNode` (from goga/ast/nodes)
- Annotations: При разработке и тестировании использовать практику `conventions`

**Entity: `ImportTypeItemNode`** (без изменений)
- Properties: `type_name: set[str]`, `from_path: str`, `alias: str`

**Entity: `ImportUsageItemNode`** (без изменений)
- Properties: `usage_name: set[str]`, `from_path: str`, `alias: str`

### Re-exports

Нет новых re-exports. `ImportTypeItemNode` и `ImportUsageItemNode` уже экспортированы из `goga/ast/nodes/__init__.py`.

### Usages Context

- `conventions` (.usages/development/conventions.md): python >=3.10, dataclasses kw_only=True, relative imports, pytest, ruff. Строго относительные импорты.
- `yaml` (pyyaml): `yaml.safe_load_all(raw)` для парсинга CODEMANIFEST. Не меняется.
- `nodes` (goga/ast/nodes manifest): API для работы со структурой документа. Доступ к `imports.types/usages` вместо `imports.items`.

### External Dependencies

- pyyaml — для парсинга YAML (не меняется)
- pytest — запуск тестов
- ruff — линтинг и форматирование

## Facts

- CODEMANIFEST `ImportsNode` определяет два свойства: `types` и `usages`
- Текущая реализация использует одно свойство `items`
- 11 правил в `document.py` и 3 правила в `ast.py` обращаются к `imports.items`
- Factory парсит Types и Usages корректно, создавая правильные типы нод
- Интеграционные тесты (`.expected.yaml`) не ломаются — они проверяют `node.data`, а не структуру `ImportsNode`
- `_build_embeddings` использует только `ImportTypeItemNode` — isinstance фильтр можно убрать

## Assumptions

- Разделение на два списка не изменяет семантику валидации: правила проверяют те же инварианты, только через другие списки (criticality: low, safe: yes)
- `ImportsHasOnlyValidKeys` проверяет `item.data` — это корректно при разделении, т.к. каждый item несёт копию исходного entry dict (criticality: low, safe: yes)
- Fallback при `From:` без Types/Usages создаёт оба пустых объекта: ImportTypeItemNode(type_name=set()) в types и ImportUsageItemNode(usage_name=set()) в usages (criticality: medium, safe: yes, confirmed by user)

## Open Questions

- Нет открытых вопросов

## Gap Analysis

- Missing contract entities: нет — все типы нод уже определены
- Missing facade exposure: нет — `__init__.py` уже экспортирует оба класса
- Wrong `location` placement: нет — все entities в правильных файлах
- API mismatches: `ImportsNode.items` вместо `types + usages`
- Behavioral mismatches: нет — логика правил правильная, нужен только доступ к новым спискам
- Existing code that can be reused: весь код Factory и правил — 100% reusable, меняется только доступ к полям
- Test coverage gaps: тесты используют `imports.items` — нужно обновить assertions

---

## Tasks

> **Ordering**: Инфраструктура → обновление тестов (до coding) → core-изменение → consumers → интеграция

### Task 1: ImportsNode — замена items на types + usages (infrastructure)

Заменить структуру `ImportsNode` в `goga/ast/nodes/header.py`: поле `items: list[ImportTypeItemNode | ImportUsageItemNode]` → два поля `types: list[ImportTypeItemNode]` и `usages: list[ImportUsageItemNode]`. Оба поля — `field(default_factory=list)`. `kw_only=True` на dataclass (conventions).

**Data flow (verified trace):**
```
Factory._parse_imports
    ├── _parse_type_entries → list[ImportTypeItemNode] → ImportsNode.types
    └── _parse_usage_entries → list[ImportUsageItemNode] → ImportsNode.usages
```

**Usages relevant to this task:**
- `conventions`: kw_only=True для dataclass, default values для всех полей, relative imports

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them. If the implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] В `goga/ast/nodes/header.py` заменить `ImportsNode` dataclass: убрать `items`, добавить `types: list[ImportTypeItemNode] = field(default_factory=list)` и `usages: list[ImportUsageItemNode] = field(default_factory=list)`
- [x] Проверить что `__init__.py` не нуждается в обновлении — `ImportsNode` уже экспортируется
- [x] Verify facade availability: `python -c "from goga.ast.nodes import ImportsNode, ImportTypeItemNode, ImportUsageItemNode"`
- [x] Lint: `ruff check goga/ast/nodes/` — fix formatting if needed

### Task 2: Обновить все тесты — заменить imports.items на types/usages (infrastructure)

Обновить все тестовые файлы, заменив доступ к `imports.items` на `imports.types` и `imports.usages`. Эта задача выполняется ДО coding tasks, чтобы debug шаги в Tasks 3-6 могли запускать `pytest tests/ -x` без падений на старых assertions.

**Трассировка изменений по файлам:**

**`tests/goga/ast/test_factory_node_props.py`:**
- Строка 91: `root.header.imports.items[0]` → `root.header.imports.types[0]`
- Строка 105: `root.header.imports.items[2]` → `root.header.imports.types[2]`
- Строка 253: `for item in root.header.imports.items:` → `for item in root.header.imports.types + root.header.imports.usages:`
- Строка 476-480: `assert isinstance(imports.items, list)` → проверить `imports.types` и `imports.usages` отдельно

**`tests/goga/ast/test_factory.py`:**
- Все `root.header.imports.items[N]` → `root.header.imports.types[N]` (т.к. _FULL_MANIFEST содержит только Types)
- Все `len(root.header.imports.items)` → `len(root.header.imports.types) + len(root.header.imports.usages)` или отдельно

**`tests/goga/ast/factory/test_parse_imports_usages.py`:**
- Все `root.header.imports.items` → разделить на `root.header.imports.types` + `root.header.imports.usages`
- `isinstance` фильтры `[i for i in items if isinstance(i, ImportTypeItemNode)]` → `root.header.imports.types` напрямую

**Usages relevant to this task:**
- `conventions`: тесты зеркалируют структуру source, `test_<what>_<scenario>` naming

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them. If the implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Code**: обновить `tests/goga/ast/test_factory_node_props.py` — заменить все `imports.items` на `imports.types` / `imports.usages`
- [x] **Code**: обновить `tests/goga/ast/test_factory.py` — заменить все `imports.items` на `imports.types` (только Types в манифесте)
- [x] **Code**: обновить `tests/goga/ast/factory/test_parse_imports_usages.py` — заменить все `imports.items` на `imports.types` / `imports.usages`
- [x] Run: `pytest tests/ -x` — тесты будут падать пока Factory не обновлён (Task 3), но синтаксис тестов должен быть корректным
- [x] Lint: `ruff check tests/` — fix formatting

### Task 3: Factory — обновить _parse_imports, _wire_references, _build_embeddings, _parse_header

Обновить Factory в `goga/ast/factory/factory.py` для работы с `ImportsNode.types` и `ImportsNode.usages`.

**Verified code stack trace — `_parse_imports`:**
1. `_parse_header` вызывает `_parse_imports(data.get("Imports"), filepath)` → data может быть None/list
2. Для каждого entry: `types_raw = entry.get("Types")`, `usages_raw = entry.get("Usages")`, `from_path = os.path.normpath(entry.get("From", ""))`
3. `type_items.extend(self._parse_type_entries(types_raw, from_path, entry))`
4. `usage_items.extend(self._parse_usage_entries(usages_raw, from_path, entry))`
5. Fallback: если `types_raw is None and usages_raw is None` → добавить пустой `ImportTypeItemNode(type_name=set())` в `type_items` И пустой `ImportUsageItemNode(usage_name=set())` в `usage_items`
6. Return `ImportsNode(types=type_items, usages=usage_items)`

**Verified code stack trace — `_wire_references`:**
1. `for item in header.imports.types:` → `item.root = document_root; item.parent = header.imports`
2. `for item in header.imports.usages:` → `item.root = document_root; item.parent = header.imports`

**Verified code stack trace — `_build_embeddings`:**
1. Сигнатура: `import_items: list[ImportTypeItemNode]` (было `list[ImportTypeItemNode | ImportUsageItemNode]`)
2. Убрать isinstance фильтр — список уже гомогенный
3. Вызов: `self._build_embeddings(header.imports.types, embedded_entities, embedded_routines)`

**Verified code stack trace — `_parse_header`:**
1. `for item in imports_node.types: types.extend(item.type_name)` — isinstance фильтр не нужен

**Usages relevant to this task:**
- `conventions`: relative imports, dataclass defaults
- `yaml`: парсинг не меняется, только обработка результата

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them. If the implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: проверить что `ImportsNode` имеет атрибуты `types` и `usages`; проверить что `Factory(path).create()` создаёт `ImportsNode` с правильными списками (expected to fail)
- [x] **Code**: `_parse_imports` — заменить `items: list[...]` на два accumulator: `type_items: list[ImportTypeItemNode]` и `usage_items: list[ImportUsageItemNode]`; fallback добавляет оба пустых объекта; return `ImportsNode(types=type_items, usages=usage_items)`
- [x] **Code**: `_wire_references` — заменить `for item in header.imports.items:` на два цикла: `for item in header.imports.types:` + `for item in header.imports.usages:`
- [x] **Code**: `_build_embeddings` — изменить сигнатуру параметра на `list[ImportTypeItemNode]`, убрать isinstance фильтр, обновить вызов на `header.imports.types`
- [x] **Code**: `_parse_header` — заменить `for item in imports_node.items: if isinstance(item, ImportTypeItemNode): types.extend(item.type_name)` на `for item in imports_node.types: types.extend(item.type_name)`
- [x] **Verify interfaces**: `pytest tests/goga/ast/factory/test_parse_imports_usages.py -x` — тесты из Task 2 должны пройти
- [x] **Logic tests**: `test_imports_node_has_types_and_usages_properties` (Types+Usages entry → types.len=1, usages.len=1), `test_types_only_imports_populates_only_types_list` (types.len=2, usages.len=0), `test_usages_only_imports_populates_only_usages_list` (types.len=0, usages.len=1), `test_no_imports_both_lists_empty` (types=[], usages=[]), `test_from_only_entry_creates_two_empty_items` (fallback: types.len=1 type_name=set(), usages.len=1 usage_name=set()), `test_wire_references_sets_parent_for_both_lists`, `test_build_embeddings_uses_types_only`, `test_multiple_from_paths_types_and_usages_separated` (3 entries из разных путей → types=[Foo,Bar], usages=[my_usage,shared], from_path проверка)
- [x] **Debug**: `pytest tests/ -x` — fix implementation code until all tests pass (do NOT fix test code)
- [x] **Re-check contracts**: verify ImportsNode имеет `types` и `usages` (не `items`), Factory заполняет оба списка корректно
- [x] **Lint**: `ruff check goga/ast/factory/ goga/ast/nodes/` — fix formatting

### Task 4: Document rules — обновить все 11 правил в document.py

Обновить все правила в `goga/ast/rules/document.py`, заменив `imports.items` на `imports.types + imports.usages` (для both-type правил) или на конкретный список (для specialized правил).

**Mapping правил → списки (verified):**

| Правило | Что итерировать | Примечание |
|---------|-----------------|------------|
| `ImportsCanNotBeEmpty` | `not types and not usages` | Проверка пустоты |
| `ImportItemIsValid` | `imports.types + imports.usages` | Оба типа, isinstance внутри |
| `ImportUsageExists` | `imports.usages` | Только usages, isinstance не нужен |
| `ImportHasValidFromPath` | `imports.types + imports.usages` | Оба типа |
| `ImportHasNotDuplicate` | `imports.types + imports.usages` | Оба типа, separate seen dicts |
| `ImportIsUsed` | `imports.types + imports.usages` | Оба типа, разные методы для type/usage |
| `UsageLinksHasNotConflicts._collect_import_type_names` | `imports.types + imports.usages` | Оба типа |
| `EntitiesAndRoutinesHasNotConflicts._collect_active_import_names` | `imports.types + imports.usages` | Оба типа |
| `MutationExists` | `imports.types` | Только типы (mutations из типов) |
| `ImportsHasOnlyValidKeys` | `imports.types + imports.usages` | Оба типа |
| `_collect_valid_names` (helper for AnnotationLinksExists) | `imports.types + imports.usages` | Оба типа |

**Usages relevant to this task:**
- `conventions`: relative imports
- `nodes`: API для работы с ImportsNode — `imports.types`, `imports.usages`

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them. If the implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: проверить что все 11 правил корректно работают с `imports.types` и `imports.usages` (expected to pass — логика не меняется)
- [x] **Code**: `ImportsCanNotBeEmpty.check` — заменить `if not node.root.header.imports.items:` на `if not node.root.header.imports.types and not node.root.header.imports.usages:`
- [x] **Code**: `ImportItemIsValid.check` — заменить `for item in node.root.header.imports.items:` на `for item in node.root.header.imports.types + node.root.header.imports.usages:`
- [x] **Code**: `ImportUsageExists.check` — заменить `for item in node.root.header.imports.items: if not isinstance(item, ImportUsageItemNode): continue` на `for item in node.root.header.imports.usages:` (убрать isinstance)
- [x] **Code**: `ImportHasValidFromPath.check` — заменить `for item in node.root.header.imports.items:` на `for item in node.root.header.imports.types + node.root.header.imports.usages:`
- [x] **Code**: `ImportHasNotDuplicate.check` — заменить `for item in node.root.header.imports.items:` на `for item in node.root.header.imports.types + node.root.header.imports.usages:`
- [x] **Code**: `ImportIsUsed.check` — заменить `for item in node.root.header.imports.items:` на `for item in node.root.header.imports.types + node.root.header.imports.usages:`
- [x] **Code**: `UsageLinksHasNotConflicts._collect_import_type_names` — заменить `for import_item in node.root.header.imports.items:` на `for import_item in node.root.header.imports.types + node.root.header.imports.usages:`
- [x] **Code**: `EntitiesAndRoutinesHasNotConflicts._collect_active_import_names` — заменить `for import_item in node.root.header.imports.items:` на `for import_item in node.root.header.imports.types + node.root.header.imports.usages:`
- [x] **Code**: `MutationExists.check` — заменить `for import_item in node.root.header.imports.items: if isinstance(import_item, ImportTypeItemNode):` на `for import_item in node.root.header.imports.types:` (убрать isinstance)
- [x] **Code**: `ImportsHasOnlyValidKeys.check` — заменить `for item in node.root.header.imports.items:` на `for item in node.root.header.imports.types + node.root.header.imports.usages:`
- [x] **Code**: `_collect_valid_names` helper — заменить `for import_item in header.imports.items:` на `for import_item in header.imports.types + header.imports.usages:`
- [x] **Verify interfaces**: `pytest tests/goga/ast/test_ast_integration.py -x` — интеграционные тесты должны проходить
- [x] **Logic tests**: `test_imports_can_not_be_empty_checks_both_lists` (Imports: [] → error), `test_import_type_exists_rule_uses_types_list`, `test_import_usage_exists_rule_uses_usages_list`
- [x] **Debug**: `pytest tests/ -x` — fix implementation code until all tests pass
- [x] **Re-check contracts**: все 11 правил работают с `types/usages`, ни одно не использует `items`
- [x] **Lint**: `ruff check goga/ast/rules/` — fix formatting

### Task 5: AST rules — обновить 3 правила в ast.py

Обновить правила в `goga/ast/rules/ast.py`: `ImportsHasNotCyclicalDeps` и `ImportTypeExists`.

**Mapping правил → списки (verified):**

| Правило | Что итерировать | Примечание |
|---------|-----------------|------------|
| `ImportsHasNotCyclicalDeps.check` | `imports.types + imports.usages` | Оба типа, build import_map |
| `ImportTypeExists.check` | `imports.types` | Только типы, isinstance не нужен |

**Usages relevant to this task:**
- `nodes`: API для ImportsNode — `imports.types`, `imports.usages`

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them. If the implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: проверить что `ImportsHasNotCyclicalDeps` и `ImportTypeExists` корректно работают (expected to pass)
- [x] **Code**: `ImportsHasNotCyclicalDeps.check` — в обоих циклах заменить `doc.header.imports.items` на `doc.header.imports.types + doc.header.imports.usages`
- [x] **Code**: `ImportTypeExists.check` — заменить `for item in document.header.imports.items: if not isinstance(item, ImportTypeItemNode): continue` на `for item in document.header.imports.types:` (убрать isinstance)
- [x] **Verify interfaces**: `pytest tests/goga/ast/test_ast_integration.py -x`
- [x] **Logic tests**: проверить что cyclical deps и type exists правила работают с usages imports
- [x] **Debug**: `pytest tests/ -x` — fix implementation code until all tests pass
- [x] **Re-check contracts**: оба AST правила не используют `items`
- [x] **Lint**: `ruff check goga/ast/rules/` — fix formatting

### Task 6: commands/schema.py — обновить доступ к imports

Обновить `goga/commands/schema.py:45` — заменить `doc.header.imports.items` на `doc.header.imports.types + doc.header.imports.usages`.

**Usages relevant to this task:**
- `nodes`: API для ImportsNode

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them. If the implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Code**: в `_build_cell_tree` заменить `{os.path.normpath(item.from_path) for item in doc.header.imports.items}` на `{os.path.normpath(item.from_path) for item in doc.header.imports.types + doc.header.imports.usages}`
- [x] Verify: `pytest tests/ -x` — все тесты проходят
- [x] Lint: `ruff check goga/commands/` — fix formatting

### Task 7: Integration tests — полная верификация

Запустить полную верификацию: все тесты, все правила, интеграционные тесты с fixture-проектами.

**Usages relevant to this task:**
- `conventions`: pytest, ruff

- [ ] Run: `pytest tests/ -v` — все тесты проходят
- [ ] Run: `ruff check goga/ tests/` — нет lint ошибок
- [ ] Verify: `python -c "from goga.ast.nodes import ImportsNode; n = ImportsNode(); assert hasattr(n, 'types'); assert hasattr(n, 'usages'); assert not hasattr(n, 'items')"`
- [ ] Verify: интеграционные тесты с fixture-проектами проходят (test_ast_integration.py)

---

## Validation Commands

- `pytest tests/ -x`: Run all tests (stop on first failure)
- `pytest tests/ -v`: Run all tests with verbose output
- `ruff check goga/ tests/`: Lint check all source and test code
- `python -c "from goga.ast.nodes import ImportsNode; n = ImportsNode(); assert hasattr(n, 'types') and hasattr(n, 'usages') and not hasattr(n, 'items')"`: Verify ImportsNode contract compliance
- `python -c "from goga.ast.nodes import ImportTypeItemNode, ImportUsageItemNode"`: Verify facade availability
- `docker run --rm -v "$(pwd)":/project -w /project goga linter`: CODEMANIFEST linter

---

## Done Criteria

- [ ] `ImportsNode` имеет `types` и `usages` (не `items`)
- [ ] `ImportsNode` доступен из `goga.ast.nodes`
- [ ] Factory заполняет оба списка корректно
- [ ] Fallback при From-only entry создаёт оба пустых объекта
- [ ] Все 11 DocumentRule правил обновлены
- [ ] Все 3 ASTRule правил обновлены
- [ ] `commands/schema.py` обновлён
- [ ] Все тесты обновлены и проходят
- [ ] Интеграционные тесты с fixture-проектами проходят
- [ ] Ни один CODEMANIFEST файл не был модифицирован
- [ ] Все validation commands проходят