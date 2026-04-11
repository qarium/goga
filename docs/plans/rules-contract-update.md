# Plan: `rules-contract-update`

## Goal

Обновить реализацию пакетов `factory` и `rules` в соответствии с изменёнными контрактами CODEMANIFEST:

1. **Factory** — обеспечить заполнение `data`, `parent` и `links` при сборке каждой ноды:
   - каждая созданная нода должна содержать в свойстве `data` исходные данные из которых она была создана
   - каждая созданная нода должна содержать в свойстве `parent` ссылку на родительскую ноду
   - при сборке `AnnotationsNode` необходимо извлекать ссылки (backtick-ссылки) из текста аннотации и заполнять свойство `links`
2. **Rules** — обновить `ImportsCanNotBeEmptyRule`:
   - правило применяется только если `Imports` декларирован в документе (ключ `Imports` присутствует в заголовке)
   - если `Imports` отсутствует в документе — правило не применяется (нет ошибок)
   - обновить тип ошибки в `ProjectRule.check` на `ProjectRuleError` вместо `CodemanifestRuleError` (контракт переименован)

## Context

### Contract Surface

**Пакет `factory` — сущность `Factory(path: str)`**
- Kind: class
- Declared `location`: `factory.py`
- Facade obligation: must be importable from `goga.codemanifest.factory`
- Methods:
  - `create(parent: Node = None) -> document:DocumentRoot` — создаёт дерево документа
- Новые требования из CODEMANIFEST (добавленные строки в Annotations):
  1. Каждая созданная нода должна содержать в свойстве `data` исходные данные из которых она была создана
  2. Каждая созданная нода должна содержать в свойстве `parent` ссылку на родительскую ноду
  3. При сборке `AnnotationsNode` необходимо извлекать ссылки из текста аннотации и заполнять свойство `links` согласно практике `dsl`
- Imported dependencies: `Node`, `DocumentRoot`, `HeaderNode`, `ImportsNode`, `ImportItemNode`, `UsagesNode`, `UsageItemNode`, `AnnotationsNode`, `BodyNode`, `RoutineTypeNode`, `EntityTypeNode`, `MethodNode`, `PropertyNode`, `FooterNode` from `goga/codemanifest/nodes`; `ManifestParseError` from `goga/codemanifest/errors`
- Usages: `dsl` (.usages/codemanifest/dsl.md) — спецификация DSL для понимания ссылок в backtick-нотации; `yaml` — pyyaml

**Пакет `rules` — сущности правил**

**Entity: `DocumentRule(name: str)`**
- Kind: class (base)
- Declared `location`: `document.py`
- Properties: `name -> str`
- Methods: `check(node: DocumentNode) -> errors:list[ManifestRuleError]`

**Entity: `DocumentRule::ImportsCanNotBeEmptyRule(name: str = 'imports_can_not_be_empty')`**
- Kind: class (mutation of DocumentRule)
- Declared `location`: `document.py`
- Аннотации обновлены: "Правило применяется только в том случаи если импорт декларирован в документе."
- Imported dependencies: `DocumentRoot`, `DocumentNode`, `ImportsNode`, `ImportItemNode` from `goga/codemanifest/nodes`; `ManifestRuleError` from `goga/codemanifest/errors`

**Entity: `ProjectRule(tree: list[DocumentRoot], name: str)`**
- Kind: class (base)
- Declared `location`: `project.py`
- Methods: `check(document: DocumentRoot) -> errors:list[ManifestRuleError]` — **тип возврата изменён** с `CodemanifestRuleError` на `ManifestRuleError` (это переименование уже сделано в коде, но контракт обновлён)

**Entity: `ProjectRule::ImportsHasNotCyclicalDepsRule(...)`** — без изменений в поведении
**Entity: `ProjectRule::AllUsagesIsUsed(...)`** — без изменений в поведении

### Re-exports

Нет новых re-export требований.

### Usages Context

- `dsl` (`.usages/codemanifest/dsl.md`) — спецификация DSL. Ссылки в аннотациях обрамляются backtick'ами: `` `link_name` ``. Ссылки могут быть на: переменные в сигнатуре, типы из Imports (включая alias), имена практик из Usages. Factory должна извлекать эти ссылки при парсинге и заполнять `links` в `AnnotationsNode`.

### External Dependencies

- `pyyaml` — для парсинга YAML документов
- `goga.codemanifest.nodes` — структуры данных нод
- `goga.codemanifest.errors` — типы ошибок

## Facts

- Factory уже создаёт все ноды, но не заполняет `data` и `parent` для вложенных нод (только для `DocumentRoot`)
- Factory уже вызывает `_collect_links` для сбора ссылок на уровне `DocumentRoot`, но не извлекает ссылки из текста аннотаций в `AnnotationsNode.links`
- `AnnotationsNode` имеет свойство `links: list[str]` (по умолчанию пустой список) — оно НЕ заполняется при парсинге
- `Node` имеет свойство `parent` (тип `DocumentNode | DocumentRoot`), `data` (тип `dict[str, Any]`) — `data` не заполняется при создании нод
- `ImportsCanNotBeEmptyRule` сейчас всегда проверяет `imports.items` — если `Imports` не декларирован в документе, `items` пустой и правило выдаёт ошибку (это некорректно по новому контракту)
- Код `rules` уже использует `ManifestRuleError` (переименование сделано), но контракт `ProjectRule.check` теперь возвращает `list[ManifestRuleError]` вместо `list[ProjectRuleError]` (согласно CODEMANIFEST: `errors:list[ManifestRuleError]`)
- В errors/__init__.py экспортируется `CodemanifestRuleError` как алиас на `ManifestRuleError`

## Assumptions

- Assumption: «импорт декларирован в документе» означает, что в YAML-документе присутствует ключ `Imports` (даже если он `None` или пустой). Если ключ `Imports` отсутствует — документ не имеет секции импортов и правило не применяется.
  - Basis: аннотация «Правило применяется только в том случаи если импорт декларирован в документе»
  - Criticality: high — определяет условие проверки
  - Safe to proceed without confirmation: yes (единственное разумное толкование)

- Assumption: извлечение ссылок из текста аннотаций означает парсинг backtick-обрамлённых имён `` `name` `` и сохранение их в `AnnotationsNode.links`
  - Basis: dsl.md описывает ссылки как обрамлённые backtick'ами
  - Criticality: high
  - Safe to proceed without confirmation: yes

- Assumption: `parent` для вложенных нод должен указывать на их логического родителя в иерархии документа (например, `PropertyNode.parent` → `EntityTypeNode`, `MethodNode.parent` → `EntityTypeNode`, `EntityTypeNode.parent` → `BodyNode`, `BodyNode.parent` → `DocumentRoot`, etc.)
  - Basis: контракт требует «каждая нода содержит parent ссылку на родительскую ноду»
  - Criticality: high
  - Safe to proceed without confirmation: yes

- Assumption: `data` для каждой ноды — это словарь с исходными YAML-данными из которых была создана нода
  - Basis: «исходные данные из которых была сделана нода»
  - Criticality: medium
  - Safe to proceed without confirmation: yes

- Assumption: тип возврата `ProjectRule.check` в контракте `errors:list[ManifestRuleError]` означает что возвращаются ошибки типа `ManifestRuleError` или его подтипы (включая `ProjectRuleError` если он от него наследуется). Но сейчас `ProjectRuleError` наследуется от `BaseCodemanifestError`, не от `ManifestRuleError`. Это потенциальная нестыковка — `ProjectRule.check` возвращает `list[ProjectRuleError]`, а не `list[ManifestRuleError]`.
  - Basis: контракт CODEMANIFEST для `ProjectRule` указывает `errors:list[ManifestRuleError]`
  - Criticality: high — может потребовать изменения иерархии наследования
  - Safe to proceed without confirmation: no

## Open Questions

- Question: Должен ли `ProjectRuleError` наследоваться от `ManifestRuleError` (чтобы `ProjectRule.check` возвращал `list[ManifestRuleError]` согласно контракту), или контракт описывает обобщённый тип ошибки?
  - Why it matters: определяет нужно ли менять иерархию наследования в errors-пакете
  - Blocking in strict mode: yes

## Gap Analysis

- **Missing `data` on all nodes**: `Node.data` всегда пустой `dict` — фабрика не передаёт исходные данные в конструкторы нод
- **Missing `parent` on child nodes**: только `DocumentRoot.parent` устанавливается через `create(parent=...)`. Остальные ноды (HeaderNode, BodyNode, EntityTypeNode, PropertyNode, MethodNode, etc.) не получают `parent`
- **Missing link extraction in AnnotationsNode**: `AnnotationsNode.links` всегда пустой список. Factory не парсит backtick-ссылки из текста аннотации
- **ImportsCanNotBeEmptyRule unconditional**: правило проверяет пустоту `imports.items` всегда, даже если секция `Imports` не была декларирована
- **ProjectRule.check return type mismatch**: контракт говорит `list[ManifestRuleError]`, код возвращает `list[ProjectRuleError]` — разные ветки иерархии
- **Existing tests cover facade/API/behavior**: тесты factory и rules уже достаточно полны, нужно расширить для новых требований

---

## Tasks

> **Per-package ordering rule**: Сначала `factory` (coding + tests), затем `rules` (coding + tests).

### Task 1: Extract backtick links from annotation text into AnnotationsNode.links

Обновить Factory для извлечения backtick-ссылок (`` `name` ``) из текста аннотаций при создании каждой `AnnotationsNode`. Согласно спецификации DSL (`.usages/codemanifest/dsl.md`), ссылки в аннотациях обрамляются backtick'ами. Factory должна парсить текст аннотации, извлекать имена внутри backtick'ов и сохранять их в `AnnotationsNode.links`.

Контекст: `AnnotationsNode` имеет свойство `links: list[str]` которое сейчас всегда пустое. Все места в factory.py где создаётся `AnnotationsNode(text=...)` должны быть обновлены для заполнения `links`.

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them. If the implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Create a helper method `_extract_links(text: str) -> list[str]` in `factory.py` that uses regex to find all backtick-enclosed names (`` `name` ``) and returns them as a list
- [ ] Update all `AnnotationsNode(text=...)` constructor calls to also pass `links=_extract_links(text_value)` — find all occurrences in `_parse_header`, `_parse_usages`, `_build_usage_annotations`, `_parse_body`, `_parse_entity`, `_parse_properties`, `_parse_methods`
- [ ] Verify link extraction works: create a small inline test `python -c "from goga.codemanifest.factory import Factory; import tempfile, os; d = tempfile.mkdtemp(); open(os.path.join(d,'CODEMANIFEST'),'w').write('Annotations: |\n  Use \`nodes\` and \`yaml\` here\n---\n---\n'); r = Factory(d).create(); print(r.header.annotations.links)"` — should contain `['nodes', 'yaml']`
- [ ] Run existing tests to verify no regressions: `pytest tests/ -x` (skip this step if no test files exist yet)
- [ ] If any tests fail, fix the code written in this task (not test code) and re-run tests until they pass

### Task 2: Populate `data` property on all nodes during factory parsing

Обновить Factory для заполнения `data` на каждой создаваемой ноде. Контракт требует: «каждая созданная нода должна содержать в свойстве data исходные данные из которых она была создана».

`data` — это исходный YAML-словарь (или значение) из которого нода была создана. Например, `ImportItemNode.data` должен содержать dict с `Types` и `From` для этого элемента импорта. `EntityTypeNode.data` — словарь с `location`, `annotations`, `properties`, `methods` из тела документа.

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them.**

- [ ] Update `_parse_imports` to pass `data=entry` (the raw import entry dict) to each `ImportItemNode` constructor
- [ ] Update `_parse_usages` to pass `data={name: value}` (the raw usage entry) to each `UsageItemNode` constructor
- [ ] Update `_build_usage_annotations` to accept and pass through data if needed (or leave as empty dict since annotations node has its own data)
- [ ] Update `_parse_header` to pass `data=data` (raw header dict) to `HeaderNode` constructor
- [ ] Update `_parse_body` to pass `data=data` (raw body dict) to `BodyNode` constructor
- [ ] Update `_parse_entity` to pass `data=value` (raw entity dict) to `EntityTypeNode` constructor
- [ ] Update `_parse_properties` to pass `data={prop_key: prop_value}` to each `PropertyNode` constructor
- [ ] Update `_parse_methods` to pass `data={method_key: method_value}` to each `MethodNode` constructor
- [ ] Update `_parse_footer` to pass `data=data` (raw footer dict) to `FooterNode` constructor
- [ ] For `RoutineTypeNode` in `_parse_body`: pass `data=value` (or the raw string for plain string routines)
- [ ] Verify data population: `python -c "from goga.codemanifest.factory import Factory; import tempfile, os; d = tempfile.mkdtemp(); open(os.path.join(d,'CODEMANIFEST'),'w').write('---\n\"MyEntity()\":\n  location: ent.py\n  properties:\n    \"x -> int\": val\n---\n'); r = Factory(d).create(); e = r.body.entities[0]; print('entity data:', e.data); print('prop data:', e.properties[0].data)"`
- [ ] Run existing tests to verify no regressions: `pytest tests/ -x`
- [ ] If any tests fail, fix the code written in this task (not test code) and re-run tests until they pass

### Task 3: Populate `parent` property on all child nodes

Обновить Factory для установки `parent` на каждой создаваемой ноде. Контракт требует: «каждая созданная нода должна содержать в свойстве parent ссылку на родительскую ноду».

Логическая иерархия parent:
- `DocumentRoot` → parent from `create()` argument (уже работает)
- `HeaderNode.parent` = `DocumentRoot`
- `ImportsNode.parent` = `HeaderNode`
- `ImportItemNode.parent` = `ImportsNode`
- `UsagesNode.parent` = `HeaderNode`
- `UsageItemNode.parent` = `UsagesNode`
- `AnnotationsNode.parent` = свой владелец (HeaderNode, UsageItemNode, EntityTypeNode, etc.)
- `BodyNode.parent` = `DocumentRoot`
- `EntityTypeNode.parent` = `BodyNode`
- `RoutineTypeNode.parent` = `BodyNode`
- `PropertyNode.parent` = `EntityTypeNode`
- `MethodNode.parent` = `EntityTypeNode`
- `FooterNode.parent` = `DocumentRoot`

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions.**

- [ ] Refactor the parent-wiring section in `Factory.create()` — currently it only sets `root` references. Add `parent` assignments for each hierarchical level listed above
- [ ] Ensure `parent` is set BEFORE or at the same time as `root` references
- [ ] Verify parent chain: `python -c "from goga.codemanifest.factory import Factory; import tempfile, os; d = tempfile.mkdtemp(); open(os.path.join(d,'CODEMANIFEST'),'w').write('---\n\"E()\":\n  location: e.py\n  properties:\n    \"x -> int\": val\n---\n'); r = Factory(d).create(); e = r.body.entities[0]; print('entity.parent is body:', e.parent is r.body); print('body.parent is root:', r.body.parent is r)"`
- [ ] Run existing tests to verify no regressions: `pytest tests/ -x`
- [ ] If any tests fail, fix the code written in this task (not test code) and re-run tests until they pass

### Task 4: Contract tests for factory node properties (data, parent, links)

Создать контрактные тесты проверяющие что Factory корректно заполняет `data`, `parent` и `links` на всех нодах.

Контекст: тесты должны проверять что:
- каждая нода в дереве содержит непустой `data` (кроме корня без данных)
- каждая нода имеет корректного `parent` (согласно иерархии)
- `AnnotationsNode.links` содержит backtick-ссылки извлечённые из текста

- [ ] Create test file `tests/goga/codemanifest/test_factory_node_props.py`
- [ ] Test `data` population: verify `ImportItemNode.data` contains raw import entry with `Types` and `From`
- [ ] Test `data` population: verify `EntityTypeNode.data` contains raw entity dict with `location`, `properties`
- [ ] Test `data` population: verify `PropertyNode.data` contains raw property entry
- [ ] Test `data` population: verify `MethodNode.data` contains raw method entry
- [ ] Test `data` population: verify `UsageItemNode.data` contains raw usage entry
- [ ] Test `data` population: verify `RoutineTypeNode.data` contains raw routine data
- [ ] Test `data` population: verify `HeaderNode.data` contains raw header dict
- [ ] Test `data` population: verify `BodyNode.data` contains raw body dict
- [ ] Test `data` population: verify `FooterNode.data` contains raw footer dict
- [ ] Test `parent` chain: `HeaderNode.parent` is `DocumentRoot`
- [ ] Test `parent` chain: `ImportsNode.parent` is `HeaderNode`
- [ ] Test `parent` chain: `ImportItemNode.parent` is `ImportsNode`
- [ ] Test `parent` chain: `UsagesNode.parent` is `HeaderNode`
- [ ] Test `parent` chain: `UsageItemNode.parent` is `UsagesNode`
- [ ] Test `parent` chain: `BodyNode.parent` is `DocumentRoot`
- [ ] Test `parent` chain: `EntityTypeNode.parent` is `BodyNode`
- [ ] Test `parent` chain: `PropertyNode.parent` is `EntityTypeNode`
- [ ] Test `parent` chain: `MethodNode.parent` is `EntityTypeNode`
- [ ] Test `parent` chain: `FooterNode.parent` is `DocumentRoot`
- [ ] Test `links` extraction: header annotations with backtick refs produce correct links list
- [ ] Test `links` extraction: entity annotations with backtick refs produce correct links list
- [ ] Test `links` extraction: method annotations with backtick refs produce correct links list
- [ ] Test `links` extraction: property annotations with backtick refs produce correct links list
- [ ] Test `links` extraction: routine annotations with backtick refs produce correct links list
- [ ] Run validation: `pytest tests/goga/codemanifest/test_factory_node_props.py -v`

### Task 5: Update ImportsCanNotBeEmptyRule — conditional check

Обновить `ImportsCanNotBeEmptyRule` в `goga/codemanifest/rules/document.py`. Контракт обновлён: «Правило применяется только в том случаи если импорт декларирован в документе.»

Это означает: если в YAML-документе отсутствует ключ `Imports`, правило не должно выдавать ошибку. Правило проверяет только когда `Imports` был явно указан в заголовке документа.

Для реализации: `DocumentRoot` созданный Factory должен содержать информацию о том, был ли ключ `Imports` декларирован. Это можно определить через `data` — если в `data` (raw header dict) есть ключ `Imports`, значит он был декларирован.

Контекст: правило сейчас всегда проверяет `node.root.header.imports.items`. Нужно добавить условие: правило применяется только если `Imports` был декларирован в заголовке документа.

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions.**

- [ ] Check how to determine if `Imports` was declared: inspect `node.root.header.data` (from Task 2) or `node.root.header.imports.data` — if `Imports` key existed in the raw header data, the section was declared
- [ ] Update `ImportsCanNotBeEmptyRule.check()` to first check if `Imports` was declared in the document (e.g., `"Imports" in node.root.header.data` or equivalent mechanism). If not declared, return empty errors list immediately
- [ ] Verify: create a manifest WITHOUT `Imports` key — rule should return empty errors
- [ ] Verify: create a manifest WITH `Imports:` but empty items — rule should still return error
- [ ] Run existing tests to verify no regressions: `pytest tests/ -x`
- [ ] If any tests fail, fix the code written in this task (not test code) and re-run tests until they pass

### Task 6: Contract tests for ImportsCanNotBeEmptyRule conditional behavior

Создать контрактные тесты для обновлённого `ImportsCanNotBeEmptyRule`.

Контекст: правило теперь условное — применяется только если `Imports` декларирован.

- [ ] Add tests to existing `test_rules.py` or create new test class `TestImportsCanNotBeEmptyRuleConditional`
- [ ] Test positive: manifest with declared `Imports` and non-empty items → no errors
- [ ] Test negative: manifest with declared `Imports` and empty items → error returned
- [ ] Test positive: manifest WITHOUT `Imports` key → no errors (rule skipped)
- [ ] Test positive: manifest with `Imports: null` (declared but null) → depends on interpretation: if `Imports` is None, items are empty — this is an edge case; document the expected behavior
- [ ] Test edge: manifest with only `Usages` and `Annotations` but no `Imports` → no errors
- [ ] Run validation: `pytest tests/goga/codemanifest/test_rules.py -v`

---

## Validation Commands

- `pytest tests/ -x`: Run all tests
- `ruff check goga/codemanifest/`: Lint check
- `python -c "from goga.codemanifest.factory import Factory"`: Factory facade availability
- `python -c "from goga.codemanifest.rules import ImportsCanNotBeEmptyRule, DocumentRule, ProjectRule"`: Rules facade availability
- `python -c "from goga.codemanifest.nodes import AnnotationsNode; a = AnnotationsNode(text='Use \`nodes\` here'); print(a.links)"`: Verify AnnotationsNode has links field

---

## Done Criteria

- [ ] `Factory.create()` populates `data` on every created node with raw YAML data
- [ ] `Factory.create()` populates `parent` on every created node with correct hierarchical parent
- [ ] `Factory` extracts backtick links from annotation text into `AnnotationsNode.links`
- [ ] `ImportsCanNotBeEmptyRule` only applies when `Imports` is declared in the document
- [ ] All entities are still importable from package facades
- [ ] All existing tests pass without modification (or with minimal adjustments for new data)
- [ ] Contract tests cover data, parent, links for factory nodes
- [ ] Contract tests cover conditional ImportsCanNotBeEmptyRule behavior
- [ ] No `CODEMANIFEST` files were modified (read-only contract)
- [ ] All validation commands pass