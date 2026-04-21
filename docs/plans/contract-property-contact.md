# Plan: `contract-property-contact`

## Goal

Реализовать два изменения в ячейке `goga/contract`:
1. Переопределить `PropertyContract.__post_init__` для формирования contract в формате `"name -> signature"` (вместо базового `"name{signature}"`)
2. Подтвердить что `cls` автоматически исключается из сигнатуры classmethod через `inspect.signature` (отдельный фильтр не нужен)

После реализации пакет `goga/contract` должен предоставлять тот же фасад, но с корректным форматированием contract для свойств.

## Context

### Contract Surface

**Entity: `BaseContract`**
- Kind: class
- Declared `location`: `contract.py`
- Facade obligation: must be importable from `goga.contract`
- Properties: `name -> str`, `signature -> str`, `contract -> str` (computed: `"{{ name }}{{ signature }}"`)
- Annotations cascade: global `Использовать формат contract_format` → entity-level `Использовать формат contract_format`

**Entity: `PropertyContract`** (mutates `BaseContract`)
- Kind: class
- Declared `location`: `contract.py`
- Facade obligation: must be importable from `goga.contract`
- Mutations: `BaseContract::PropertyContract()`
- Annotations: `Описание контракта свойства сущности. Поле contract определяется как "{{ name }} -> {{ signature }}"`
- Change: override `__post_init__` to format contract as `"name -> signature"`

**Entity: `MethodContract`** (mutates `BaseContract`)
- Kind: class
- Declared `location`: `contract.py`
- Facade obligation: must be importable from `goga.contract`
- Mutations: `BaseContract::MethodContract()`
- No changes to this entity

**Entity: `EntityContract`** (mutates `BaseContract`)
- Kind: class
- Declared `location`: `contract.py`
- Facade obligation: must be importable from `goga.contract`
- Properties: `properties -> list[PropertyContract]`, `methods -> list[MethodContract]`
- No changes to this entity

**Entity: `RoutineContract`** (mutates `BaseContract`)
- Kind: class
- Declared `location`: `contract.py`
- Facade obligation: must be importable from `goga.contract`
- No changes to this entity

**Function: `python_contract`**
- Kind: function
- Declared `location`: `python.py`
- Facade obligation: must be importable from `goga.contract`
- Signature: `python_contract(cell_path: str) -> contract:list[EntityContract | RoutineContract]`
- Annotations: алгоритм извлечения контракта; требования: `self, cls - исключается из сигнатуры`
- Key insight: `cls` исключается автоматически `inspect.signature` через `getattr(cls, name)` для classmethod

### Re-exports

Все 6 сущностей уже реэкспортируются из `goga/contract/__init__.py`. Изменения реэкспортов не требуются.

### Usages Context

- `contract_format` (инлайн): Формат JSON `[{"name": "...", "signature": "..."}]` — единый формат фасада контракта. Используется в `BaseContract.annotations`.
- `conventions` (файл `.usages/development/conventions.md`): Python 3.10+, dataclasses kw_only=True, относительные импорты. Тесты: зеркалируют структуру (`goga/contract/file.py` → `tests/goga/contract/test_file.py`), pytest, ruff, `test_<what>_<scenario>`, `class Test<Component>:`, чистая логика без моков, tmp_path для файлового I/O.

### Imported Usages

Нет импортированных usages.

### Local Usages

- File path: `.usages/python_contract.md`
- Description: Практика использования функции `python_contract` для извлечения контракта с фасада Python-пакета
- Creation task reference: Task 3

### External Dependencies

- `dataclasses` (stdlib) — для @dataclass, field
- `inspect` (stdlib) — для introspection сигнатур
- `types` (stdlib) — для isinstance проверок (FunctionType, staticmethod, classmethod)
- `importlib` (stdlib) — для import_module

## Facts

- `goga/contract` — изолированная ячейка без зависимых ячеек
- `PropertyContract` наследует `BaseContract` — текущий `__post_init__` формирует `f"{self.name}{self.signature}"`
- `inspect.signature(getattr(cls, name), eval_str=True)` на связанном classmethod **автоматически исключает `cls`**
- Dataclass `__post_init__` не вызывает родительский автоматически — переопределение безопасно
- CODEMANIFEST linter не нашёл ошибок
- Фасад уже полностью реализован в `__init__.py` — все 6 имён в `__all__`

## Assumptions

- Формат `"{name} -> {signature}"` применяется **только** к PropertyContract: основание — аннотация добавлена именно в PropertyContract (критичность: low, безопасно: yes)
- `cls` исключается автоматически для classmethod — отдельный код не нужен: основание — верифицировано эмпирически при ревью (критичность: low, безопасно: yes)

## Open Questions

Нет.

## Gap Analysis

- Missing contract entities: нет
- Missing facade exposure: нет
- Wrong `location` placement: нет
- API mismatches: `PropertyContract.contract` формирует `"{name}{signature}"` вместо `"{name} -> {signature}"` — **требует исправления**
- Behavioral mismatches: нет (cls автоматически исключается)
- Existing code that can be reused: весь существующий код — точечные изменения
- Test coverage gaps: нет существующих тестов

---

## Tasks

### Task 1: PropertyContract.__post_init__ override (TDD coding)

Переопределить `__post_init__` в `PropertyContract` для формирования `contract` в формате `"name -> signature"` вместо базового `"name{signature}"`.

**Контрактные сущности**: `PropertyContract` (location: `contract.py`)
**Файлы**: `goga/contract/contract.py`, тестовый файл

**Usages relevant to this task:**
- `contract_format`: формат контракта — JSON `[{"name": "...", "signature": "..."}]`. Поле `contract` — это `"{{ name }}{{ signature }}"` для базового формата, но для PropertyContract: `"{{ name }} -> {{ signature }}"`.
- `conventions` (из `.usages/development/conventions.md`):
  - Python 3.10+, dataclasses, kw_only=True
  - Тесты зеркалируют структуру: `goga/contract/contract.py` → `tests/goga/contract/test_contract.py`
  - Файлы тестов: `test_<module>.py`, функции: `test_<what>_<scenario>`, группировка: `class Test<Component>:`
  - Чистая логика — без моков

**Annotations cascade:**
- Global: `Использовать формат contract_format`
- Entity: `Описание контракта свойства сущности. Поле contract определяется как "{{ name }} -> {{ signature }}"`

**Архитектурное решение**: PropertyContract переопределяет `__post_init__` в dataclass. Python dataclass **НЕ** вызывает родительский `__post_init__` автоматически, поэтому `BaseContract.__post_init__` не будет выполнен.

**Поток данных:**
1. `_extract_properties` создаёт `PropertyContract(name="items", signature="list[str]")`
2. `__post_init__` вызывается → `self.contract = f"{self.name} -> {self.signature}"` → `"items -> list[str]"`
3. Граничный случай: пустая сигнатура → `"value -> "`

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them. If the implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: Create test file for `goga/contract`. Test that `PropertyContract` is importable from `goga.contract`. Test that `PropertyContract(name="items", signature="list[str]").contract == "items -> list[str]"`. Test that `BaseContract(name="foo", signature="(x: int) -> str").contract == "foo(x: int) -> str"` (regression — base format unchanged). Test that `MethodContract(name="calc", signature="(x: int) -> int").contract == "calc(x: int) -> int"`. Test that `EntityContract(name="Service", signature="(x: int)", properties=[], methods=[]).contract == "Service(x: int)"`. Test that `RoutineContract(name="helper", signature="(x: str) -> bool").contract == "helper(x: str) -> bool"`. (expected to fail — PropertyContract.__post_init__ not yet overridden)
- [x] **Code**: Add `__post_init__` method to `PropertyContract` in `goga/contract/contract.py`:
  ```python
  def __post_init__(self) -> None:
      self.contract = f"{self.name} -> {self.signature}"
  ```
- [x] **Verify interfaces**: `pytest tests/ -x` — contract tests for PropertyContract, BaseContract, MethodContract, EntityContract, RoutineContract must all pass
- [x] **Logic tests**: Test `PropertyContract(name="value", signature="").contract == "value -> "` (empty signature edge case). Test that `BaseContract.__post_init__` is NOT called for `PropertyContract` instances (verify by checking contract format differs from base).
- [x] **Debug**: `pytest tests/ -x` — fix implementation code until all tests pass (do NOT fix test code)
- [x] **Re-check contracts**: verify all contract obligations — facade availability, PropertyContract.contract format matches `"{{ name }} -> {{ signature }}"`, other contracts unchanged
- [x] **Lint**: `ruff check goga/contract/` — fix formatting if needed

---

### Task 2: python_contract integration tests (integration tests)

Интеграционные тесты для проверки корректности извлечения контракта через `python_contract` — что `cls` автоматически исключается для classmethod, `self` для обычных методов, staticmethod не фильтруется, и PropertyContract получает формат `"name -> type"`.

**Контрактные сущности**: `python_contract` (location: `python.py`)
**Файлы**: тестовый файл (вместе с тестами Task 1 или отдельный)

**Usages relevant to this task:**
- `contract_format`: JSON формат `[{"name": "...", "signature": "..."}]` — проверяем что извлечённые контракты соответствуют этому формату.
- `conventions` (из `.usages/development/conventions.md`):
  - Тесты зеркалируют структуру: `goga/contract/python.py` → `tests/goga/contract/test_python.py`
  - Функции: `test_<what>_<scenario>`, группировка: `class Test<Component>:`
  - Интеграционные тесты с внешними зависимостями используют `pytest.mark.skipif` при недоступности
  - Файловый I/O — фикстура `tmp_path`

**Annotations cascade:**
- Global: `Использовать формат contract_format`, `При разработке и тестировании использовать практику conventions`
- Entity (`python_contract`): `self, cls - исключается из сигнатуры`, `для свойств сигнатура - возвращаемый тип данных, если нет - пустая строка`

**Ключевой инсайт (из ревью)**: `inspect.signature(getattr(cls, name), eval_str=True)` на связанном classmethod **автоматически исключает `cls`** из параметров. Отдельный фильтр для classmethod не нужен.

**General setup:**
- Использовать `tmp_path` fixture для создания временных Python-пакетов
- Каждый тест создаёт `__init__.py` с `__all__` в `tmp_path`
- `sys.path.insert(0, str(tmp_path))` для импорта

**Тестовые сценарии из дизайн-документа:**

**test_classmethod_excludes_cls_from_signature**:
- Setup: `tmp_path` с `__init__.py` содержащим `class MyClass: @classmethod def create(cls, x: int) -> "MyClass": ...` и `__all__ = ["MyClass"]`
- Input: `python_contract("temp_module")`
- Trace: `import_module` → `__all__` → `isclass` → `_extract_methods` → `getattr(cls, "create")` → `inspect.signature` автоматически убирает `cls` → `(x: int) -> MyClass`
- Assertions: `method.signature == "(x: int) -> MyClass"`, `"cls" not in method.signature`

**test_regular_method_excludes_self**:
- Setup: класс с `def process(self, data: str) -> bool`
- Assertions: `"self" not in method.signature`, `method.signature == "(data: str) -> bool"`

**test_staticmethod_keeps_all_params**:
- Setup: класс с `@staticmethod def add(x: int, y: int) -> int`
- Assertions: `method.signature == "(x: int, y: int) -> int"`

**test_classmethod_with_self_named_param** (edge case):
- Setup: `@classmethod def method(cls, self: int) -> None` — self как имя обычного параметра
- Assertions: `"cls" not in method.signature`, `method.signature == "(self: int) -> None"`

**test_property_contract_format_through_python_contract**:
- Setup: класс с `@property def items(self) -> list[str]: ...`
- Assertions: `prop.contract == "items -> list[str]"`

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them.**

- [ ] Create integration test file with `tmp_path` fixture setup for temporary Python packages
- [ ] Test: `test_classmethod_excludes_cls_from_signature` — cls automatically removed by inspect.signature for classmethod
- [ ] Test: `test_regular_method_excludes_self` — self removed for regular methods
- [ ] Test: `test_staticmethod_keeps_all_params` — staticmethod params preserved
- [ ] Test: `test_classmethod_with_self_named_param` — edge case: self as regular param name in classmethod
- [ ] Test: `test_property_contract_format_through_python_contract` — PropertyContract gets `"name -> type"` format via _extract_properties
- [ ] Run validation: `pytest tests/ -x -v`

---

### Task 3: Create local usages file for python_contract (infrastructure)

Создать файл практики `.usages/python_contract.md` для функции `python_contract` — описывающий как использовать функцию для извлечения контракта с фасада Python-пакета.

**Файлы**: `goga/contract/.usages/python_contract.md`

**Usages relevant to this task:**
- Design document specifies: `.usages/python_contract.md` — практика использования функции python_contract для извлечения контракта

**Ожидаемое содержание файла:**
```markdown
Извлечение контракта с фасада Python-пакета

```python
from goga.contract import python_contract

result = python_contract("path/to/cell")
# result: list[EntityContract | RoutineContract]
```
```

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them.**

- [ ] Create directory `goga/contract/.usages/` if not exists
- [ ] Create file `goga/contract/.usages/python_contract.md` with usage practice for `python_contract` function
- [ ] Verify file exists: `ls goga/contract/.usages/python_contract.md`
- [ ] Lint: `ruff check goga/contract/` — no issues expected (markdown file)

---

## Validation Commands

- `pytest tests/ -x`: Run all tests
- `ruff check goga/contract/`: Lint check
- `python -c "from goga.contract import BaseContract, EntityContract, MethodContract, PropertyContract, RoutineContract, python_contract"`: Verify all facade entities are importable
- `python -c "from goga.contract import PropertyContract; pc = PropertyContract(name='test', signature='str'); assert pc.contract == 'test -> str', f'Got: {pc.contract}'"`: Verify PropertyContract contract format

---

## Done Criteria

- [ ] Every contract entity is implemented in the correct `location`
- [ ] Every contract entity is available from the package facade
- [ ] Properties and methods match the declared API
- [ ] Descriptions are reflected in behavior
- [ ] Contract dependencies are respected
- [ ] Re-exports are available from facade
- [ ] Every coding task followed the TDD workflow (contract tests → code → verify → logic tests → debug → re-check → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior within each coding task
- [ ] Integration tests exist where cross-entity scenarios require them
- [ ] No package boundary has been expanded
- [ ] No `CODEMANIFEST` files were modified (read-only contract)
- [ ] All validation commands pass
- [ ] Assumptions and open questions are explicitly documented
- [ ] Every Usages entry is referenced in at least one task (Phase 2 calibration)