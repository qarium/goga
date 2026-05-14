# План: `rules-refactoring`

## Цель

Рефакторинг монолитного пакета `goga/ast/rules` — разделение на 7 подячеек с сохранением полной обратной совместимости фасада. Код перемещается из `document.py`, `ast.py`, `tools.py` в подкаталоги с соответствующими CODEMANIFEST. Фасадный `__init__.py` обновляется на реэкспорт из подмодулей. Старые файлы становятся deprecated-обёртками.

## Контекст

### Поверхность контракта

**Сущность: `DocumentRule`**
- Тип: Entity
- Объявленный `location`: `base/document.py`
- Обязанность фасада: должна быть импортируема из `goga/ast/rules`
- Свойства: `name -> str`
- Методы: `check(node: DocumentNode) -> errors:list[DocumentRuleError]`
- Семантические требования: базовый класс, `check` raises `NotImplementedError`
- Импортированные зависимости: `DocumentNode`, `DocumentRoot` (from `goga/ast/nodes`); `ASTRuleError`, `DocumentRuleError` (from `goga/ast/errors`)
- Контекст аннотаций: "При разработке и тестировании использовать практику `conventions`"

**Сущность: `ASTRule`**
- Тип: Entity
- Объявленный `location`: `base/ast.py`
- Обязанность фасада: должна быть импортируема из `goga/ast/rules`
- Свойства: `name -> str`, `tree -> list[DocumentRoot]`
- Методы: `check(document: DocumentRoot) -> errors:list[ASTRuleError]`
- Семантические требования: базовый класс, `check` raises `NotImplementedError`, дерево можно читать используя практику `nodes`
- Импортированные зависимости: `DocumentNode`, `DocumentRoot` (from `goga/ast/nodes`); `ASTRuleError`, `DocumentRuleError` (from `goga/ast/errors`)
- Контекст аннотаций: "При разработке и тестировании использовать практику `conventions`"

**Сущность: `signature_contains_type_name`**
- Тип: Routine
- Объявленный `location`: `document/imports/tools.py`
- Обязанность фасада: должна быть импортируема из `goga/ast/rules`
- Сигнатура: `(signature: str, type_name: str) -> result:bool`
- Семантические требования: поиск точного вхождения имени типа в сигнатуре с проверкой граничных символов {`:`, `>`, `(`, `)`, `[`, `]`, `,`, ` `}
- Контекст аннотаций: "При разработке и тестировании использовать практику `conventions`"

**Сущность: `DocumentRule::ImportsCanNotBeEmpty`**
- Тип: Entity (мутация DocumentRule)
- Объявленный `location`: `document/imports/document.py`
- Обязанность фасада: должна быть импортируема из `goga/ast/rules`
- Семантические требования: проверяет что блок Imports не пуст, если он декларирован; шаблон ошибки: `empty`
- Импортированные зависимости: `DocumentRule` (from `goga/ast/rules/base`); `ImportsNode`, `ImportTypeItemNode`, `ImportUsageItemNode` (from `goga/ast/nodes`)

**Сущность: `DocumentRule::ImportsHasOnlyValidKeys`**
- Тип: Entity (мутация DocumentRule)
- Объявленный `location`: `document/imports/document.py`
- Семантические требования: проверяет допустимые ключи в каждом item; шаблон ошибки: `unknown_keys`

**Сущность: `DocumentRule::ImportItemIsValid`**
- Тип: Entity (мутация DocumentRule)
- Объявленный `location`: `document/imports/document.py`
- Семантические требования: проверяет что каждый item содержит хотя бы один тип или практику; шаблон ошибки: `no_type`

**Сущность: `DocumentRule::ImportUsageExists`**
- Тип: Entity (мутация DocumentRule)
- Объявленный `location`: `document/imports/document.py`
- Семантические требования: проверяет что файл практики существует по пути `{from_path}/.usages/{name}.md`; шаблон ошибки: `not_found`

**Сущность: `DocumentRule::ImportHasValidFromPath`**
- Тип: Entity (мутация DocumentRule)
- Объявленный `location`: `document/imports/document.py`
- Семантические требования: проверяет корректность From-пути (не пустой, существует, не выходит за CWD); шаблоны ошибок: `empty`, `not_found`, `escapes`

**Сущность: `DocumentRule::ImportHasNotDuplicate`**
- Тип: Entity (мутация DocumentRule)
- Объявленный `location`: `document/imports/document.py`
- Семантические требования: проверяет уникальность имён типов и практик в импортах; шаблон ошибки: `duplicate`

**Сущность: `DocumentRule::ImportIsUsed`**
- Тип: Entity (мутация DocumentRule)
- Объявленный `location`: `document/imports/document.py`
- Семантические требования: проверяет что каждый импортированный тип/практика используется в документе (аннотации + сигнатуры); embedded считается использованным; usage не проверяется в сигнатурах; использует `signature_contains_type_name`; шаблон ошибки: `unused`

**Сущность: `DocumentRule::AllUsagesIsUsed`**
- Тип: Entity (мутация DocumentRule)
- Объявленный `location`: `document/usages/document.py`
- Семантические требования: проверяет что все декларированные usages используются в AnnotationsNode; шаблон ошибки: `unused`

**Сущность: `DocumentRule::UsageFilepathExists`**
- Тип: Entity (мутация DocumentRule)
- Объявленный `location`: `document/usages/document.py`
- Семантические требования: проверяет filepath: префикс `.goga/usages/`, не выходит за корень, файл существует; inline и URL usages пропускаются; шаблоны ошибок: `incorrect_path`, `outside_usages`, `not_found`

**Сущность: `DocumentRule::UsageUrlIsAccessible`**
- Тип: Entity (мутация DocumentRule)
- Объявленный `location`: `document/usages/document.py`
- Семантические требования: HEAD-запрос с fallback на GET, timeout 10s; inline и filepath usages пропускаются; шаблоны ошибок: `not_accessible`, `request_failed`

**Сущность: `DocumentRule::UsageLinksHasNotConflicts`**
- Тип: Entity (мутация DocumentRule)
- Объявленный `location`: `document/usages/document.py`
- Семантические требования: проверяет отсутствие конфликтов имён usage с импортами и entity/routine; шаблоны ошибок: `import_conflict`, `entity_conflict`

**Сущность: `DocumentRule::EntitiesAndRoutinesHasNotConflicts`**
- Тип: Entity (мутация DocumentRule)
- Объявленный `location`: `document/structure/document.py`
- Семантические требования: проверяет отсутствие конфликтов имён entity/routine с импортами; embedded — исключение; шаблоны ошибок: `entity_conflict`, `routine_conflict`

**Сущность: `DocumentRule::EntityHasOnlyValidKeys`**
- Тип: Entity (мутация DocumentRule)
- Объявленный `location`: `document/structure/document.py`
- Семантические требования: проверяет что entity содержит только {location, annotations, properties, methods}; шаблон ошибки: `unknown_keys`

**Сущность: `DocumentRule::RoutineHasOnlyValidKeys`**
- Тип: Entity (мутация DocumentRule)
- Объявленный `location`: `document/structure/document.py`
- Семантические требования: проверяет что routine содержит только {location, annotations}; шаблон ошибки: `unknown_keys`

**Сущность: `DocumentRule::SignatureIsValid`**
- Тип: Entity (мутация DocumentRule)
- Объявленный `location`: `document/structure/document.py`
- Семантические требования: проверяет формат сигнатуры '(...) -> ...' или '(...)'; шаблоны ошибок: `format`, `empty`

**Сущность: `DocumentRule::ReturnTypeHasLink`**
- Тип: Entity (мутация DocumentRule)
- Объявленный `location`: `document/structure/document.py`
- Семантические требования: проверяет что возвращаемый тип имеет семантическую метку (label:Type); сигнатура без return — валидна; шаблон ошибки: `missing_link`

**Сущность: `DocumentRule::LocationIsRequired`**
- Тип: Entity (мутация DocumentRule)
- Объявленный `location`: `document/structure/document.py`
- Семантические требования: проверяет наличие и формат location; embedded пропускаются; шаблоны ошибок: `missing`, `no_extension`, `contains_path`

**Сущность: `DocumentRule::MutationExists`**
- Тип: Entity (мутация DocumentRule)
- Объявленный `location`: `document/mutation/document.py`
- Семантические требования: проверяет что базовый тип мутации существует (в imports, entities или routines); шаблон ошибки: `not_found`

**Сущность: `DocumentRule::MutationIsValid`**
- Тип: Entity (мутация DocumentRule)
- Объявленный `location`: `document/mutation/document.py`
- Семантические требования: проверяет что мутация не ссылается на себя; шаблон ошибки: `self_mutation`

**Сущность: `DocumentRule::EmbeddedEntityCanNotHasMutations`**
- Тип: Entity (мутация DocumentRule)
- Объявленный `location`: `document/mutation/document.py`
- Семантические требования: проверяет что embedded сущность не имеет мутаций; шаблон ошибки: `has_mutations`

**Сущность: `DocumentRule::AnnotationLinksExists`**
- Тип: Entity (мутация DocumentRule)
- Объявленный `location`: `document/annotations/document.py`
- Семантические требования: проверяет что все ссылки в аннотациях разрешимы (imports, usages, body, сигнатуры); использует `signature_contains_type_name` для поиска в сигнатурах; разделители: не `[\w-]`; шаблон ошибки: `not_found`
- Импортированные зависимости: `signature_contains_type_name` (from `goga/ast/rules/document/imports`)

**Сущность: `ASTRule::ImportsHasNotCyclicalDeps`**
- Тип: Entity (мутация ASTRule)
- Объявленный `location`: `ast/ast.py`
- Семантические требования: проверяет отсутствие циклических зависимостей; O(1) lookup через dict; шаблон ошибки: `cycle`

**Сущность: `ASTRule::ImportTypeExists`**
- Тип: Entity (мутация ASTRule)
- Объявленный `location`: `ast/ast.py`
- Семантические требования: проверяет что импортированный тип существует в целевом документе; skip при несуществующем пути; O(1) lookup; шаблон ошибки: `not_found`

**Сущность: `ASTRule::EmbeddedTypeHasLowLevel`**
- Тип: Entity (мутация ASTRule)
- Объявленный `location`: `ast/ast.py`
- Семантические требования: проверяет что embedded типы расположены ниже в иерархии; путь нормализован через `os.path.normpath`; шаблон ошибки: `wrong_level`

### Реэкспорты

Фасадный CODEMANIFEST (`goga/ast/rules/CODEMANIFEST`) реэкспортирует 27 сущностей из 7 подячеек:

- `DocumentRule`, `ASTRule` ← из `goga/ast/rules/base`
- `signature_contains_type_name`, `ImportsCanNotBeEmpty`, `ImportsHasOnlyValidKeys`, `ImportItemIsValid`, `ImportUsageExists`, `ImportHasValidFromPath`, `ImportHasNotDuplicate`, `ImportIsUsed` ← из `goga/ast/rules/document/imports`
- `AllUsagesIsUsed`, `UsageFilepathExists`, `UsageUrlIsAccessible`, `UsageLinksHasNotConflicts` ← из `goga/ast/rules/document/usages`
- `EntitiesAndRoutinesHasNotConflicts`, `EntityHasOnlyValidKeys`, `RoutineHasOnlyValidKeys`, `SignatureIsValid`, `ReturnTypeHasLink`, `LocationIsRequired` ← из `goga/ast/rules/document/structure`
- `MutationExists`, `MutationIsValid`, `EmbeddedEntityCanNotHasMutations` ← из `goga/ast/rules/document/mutation`
- `AnnotationLinksExists` ← из `goga/ast/rules/document/annotations`
- `ImportsHasNotCyclicalDeps`, `ImportTypeExists`, `EmbeddedTypeHasLowLevel` ← из `goga/ast/rules/ast`

Все должны быть импортируемы из `goga/ast/rules`.

### Контекст Usages

- **`conventions`**: `.goga/usages/development/conventions.md` — соглашения по разработке и тестированию Python (3.10+, dataclasses kw_only, pytest, ruff, относительные импорты, зеркальная структура тестов). Используется во всех ячейках.

- **`nodes`** (только в `base`): inline практика — инструкция использовать манифест `goga/ast/nodes` и его API для работы со структурой документа. Используется в аннотации `ASTRule`.

### Внешние зависимости

- `goga/ast/nodes` — типы узлов документа (`DocumentNode`, `DocumentRoot`, `ImportsNode`, `ImportTypeItemNode`, `ImportUsageItemNode`, `EntityTypeNode`, `RoutineTypeNode`, `MethodNode`, `PropertyNode`, `UsagesNode`, `UsageItemNode`, `AnnotationsNode`, `HeaderNode`, `BodyNode`)
- `goga/ast/errors` — типы ошибок (`DocumentRuleError`, `ASTRuleError`)
- `pytest` — тестовый фреймворк
- `ruff` — линтер/форматтер
- `unittest.mock` — мокирование для тестов

## Факты

- Подкаталоги с CODEMANIFEST уже созданы, но не содержат Python-файлов (только `__pycache__`)
- Исходный код существует в монолитных файлах: `goga/ast/rules/document.py`, `goga/ast/rules/ast.py`, `goga/ast/rules/tools.py`
- Существующие тесты в `tests/goga/ast/rules/` должны быть реорганизованы зеркально новой структуре
- Внешние потребители (`goga/ast/visitor`, `goga/ast/analyzer`, `goga/ast`) импортируют из фасада — обратная совместимость обязательна
- Внутренняя зависимость: `document/annotations` → `document/imports` (через `signature_contains_type_name`)
- Все правила stateless и потокобезопасны
- `python -m pytest` — запуск тестов; `ruff check` / `ruff format` — линт/форматирование

## Анализ разрывов

- **Отсутствующие сущности контракта**: все 27 сущностей должны быть перемещены из монолита в подячейки
- **Отсутствующее раскрытие фасада**: фасадный `__init__.py` должен обновить импорты на подмодули
- **Неверное размещение в `location`**: код находится в монолите, должен быть в подкаталогах по `location` из CODEMANIFEST
- **Обратная совместимость**: `goga/ast/rules/document.py`, `ast.py`, `tools.py` должны стать deprecated реэкспортами
- **Разрывы в тестовом покрытии**: тесты должны быть реорганизованы в зеркальную структуру
- **Отсутствующие `__init__.py`**: ни в одной подячейке нет `__init__.py`

---

## Tasks

> **Правило упорядочивания по пакетам**: задачи кодирования каждого пакета завершаются перед началом следующего. Листовые ячейки первыми. Внутри каждой задачи кодирования контрактные тесты пишутся первыми (рабочий процесс TDD).

### Task 1: Инфраструктура — базовая ячейка `base` (инфраструктура)

Создать структуру подячейки `goga/ast/rules/base/`: `__init__.py` с реэкспортом, `document.py` с классом `DocumentRule`, `ast.py` с классом `ASTRule`. Код извлекается из существующего монолита `goga/ast/rules/document.py` и `goga/ast/rules/ast.py`.

**Usages, релевантные для этой задачи:**
- `conventions`: python 3.10+, dataclasses с kw_only=True, относительные импорты, pytest + ruff
- `nodes`: инструкция использовать манифест goga/ast/nodes и его API для работы с структурой документа

**КРИТИЧЕСКИ: файлы `CODEMANIFEST` — определения контракта только для чтения. НЕ изменяйте их. Если реализация не соответствует контракту, исправляйте реализацию — никогда не исправляйте контракт.**

- [x] Создать файл `goga/ast/rules/base/__init__.py` с реэкспортом `DocumentRule` из `.document` и `ASTRule` из `.ast`
- [x] Создать файл `goga/ast/rules/base/document.py` — извлечь класс `DocumentRule` из `goga/ast/rules/document.py`: `__init__(name: str)`, property `name -> str`, метод `check(node: DocumentNode) -> list[DocumentRuleError]` (raises NotImplementedError). Импорты: `from ...errors import DocumentRuleError`, `from ...nodes import DocumentNode`
- [x] Создать файл `goga/ast/rules/base/ast.py` — извлечь класс `ASTRule` из `goga/ast/rules/ast.py`: `__init__(tree: list[DocumentRoot], name: str)`, properties `name -> str` и `tree -> list[DocumentRoot]`, метод `check(document: DocumentRoot) -> list[ASTRuleError]` (raises NotImplementedError). Импорты: `from ...errors import ASTRuleError`, `from ...nodes import DocumentRoot`
- [x] Проверить доступность фасада: `python -c "from goga.ast.rules.base import DocumentRule, ASTRule; print('OK')"`
- [x] Линт: `ruff check goga/ast/rules/base/ && ruff format goga/ast/rules/base/` — исправить форматирование при необходимости

### Task 2: Ячейка `document/imports` — Routine `signature_contains_type_name` (TDD кодирование)

Реализовать функцию `signature_contains_type_name` в `goga/ast/rules/document/imports/tools.py`. Код извлекается из существующего `goga/ast/rules/tools.py`. Функция проверяет вхождение имени типа в сигнатуру с учётом граничных символов.

**Контракт**: `signature_contains_type_name(signature: str, type_name: str) -> result:bool`

**Алгоритм:**
```
1. IF type_name is empty → return False
2. allowed = {":", ">", "(", ")", "[", "]", ",", " "}
3. start = 0
4. LOOP:
   a. idx = signature.find(type_name, start)
   b. IF idx == -1 → return False
   c. end = idx + len(type_name)
   d. left_ok = (idx == 0) OR (signature[idx-1] in allowed)
   e. right_ok = (end == len(signature)) OR (signature[end] in allowed)
   f. IF left_ok AND right_ok → return True
   g. start = idx + 1
```

**Usages, релевантные для этой задачи:**
- `conventions`: python 3.10+, pytest, относительные импорты

**КРИТИЧЕСКИ: файлы `CODEMANIFEST` — определения контракта только для чтения. НЕ изменяйте их.**

- [x] **ШАГ 0 (ОБЪЯВЛЕНИЕ)**: Объявить работу над Task 2 — `signature_contains_type_name`
- [x] **Контрактные тесты**: создать файл `tests/goga/ast/rules/document/imports/__init__.py` и `tests/goga/ast/rules/document/imports/test_tools.py` — проверить доступность функции из `goga.ast.rules.document.imports.tools`, сигнатуру `(signature: str, type_name: str) -> bool` (ожидаемо падают)
- [x] **Код**: создать файл `goga/ast/rules/document/imports/__init__.py` (пустой или с реэкспортом)
- [x] **Код**: создать файл `goga/ast/rules/document/imports/tools.py` — извлечь функцию `signature_contains_type_name` из `goga/ast/rules/tools.py`
- [x] **Верификация интерфейсов**: `python -m pytest tests/goga/ast/rules/document/imports/test_tools.py -v` — контрактные тесты должны пройти
- [x] **Логические тесты**: в `test_tools.py` добавить тесты:
  - позитивные: тип как значение параметра `(param: TypeName)`, тип в return `(param: Type) -> rv:TypeName`, тип в середине `(param: TypeName, param_2: Type)`, тип в начале `TypeName(param)`
  - негативные: тип как префикс `(param: TypeNameOne)`, тип как суффикс `(param: TwoTypeName)`, тип в строковом литерале `(param: Type: = "TypeName")`
  - краевые: пустой `type_name` → False, `type_name` в начале сигнатуры → True
- [x] **Отладка**: `python -m pytest tests/goga/ast/rules/document/imports/test_tools.py -v` — исправлять код реализации, пока все тесты не пройдут
- [x] **Перепроверка контрактов**: проверить сигнатуру `(signature: str, type_name: str) -> result:bool`, доступность из фасада `goga.ast.rules.document.imports`
- [x] **Линт**: `ruff check goga/ast/rules/document/imports/ && ruff format goga/ast/rules/document/imports/` — исправить форматирование

### Task 3: Ячейка `document/imports` — 7 правил проверки импортов (TDD кодирование)

Реализовать 7 классов-мутаций DocumentRule в `goga/ast/rules/document/imports/document.py`. Код извлекается из существующего `goga/ast/rules/document.py`. Все классы наследуют от `DocumentRule`.

**Сущности контракта:**
- `ImportsCanNotBeEmpty` — проверяет что Imports блок не пуст (только если декларирован)
- `ImportsHasOnlyValidKeys` — проверяет допустимые ключи {Types, Usages, From}
- `ImportItemIsValid` — проверяет что item содержит хотя бы один тип или практику
- `ImportUsageExists` — проверяет что файл практики существует по пути
- `ImportHasValidFromPath` — проверяет корректность From-пути
- `ImportHasNotDuplicate` — проверяет уникальность имён
- `ImportIsUsed` — проверяет что импортированные типы/практики используются (вызывает `signature_contains_type_name`)

**Импортированные зависимости**: `DocumentRule` (from `goga/ast/rules/base`); `ImportsNode`, `ImportTypeItemNode`, `ImportUsageItemNode` (from `goga/ast/nodes`)

**Внутренняя зависимость**: `ImportIsUsed` → `signature_contains_type_name` (из `tools.py` этой же ячейки)

**Usages, релевантные для этой задачи:**
- `conventions`: python 3.10+, dataclasses kw_only=True, pytest, относительные импорты

**КРИТИЧЕСКИ: файлы `CODEMANIFEST` — определения контракта только для чтения.**

- [x] **ШАГ 0 (ОБЪЯВЛЕНИЕ)**: Объявить работу над Task 3 — 7 правил проверки импортов
- [x] **Контрактные тесты**: создать файл `tests/goga/ast/rules/document/imports/test_document.py` — проверить доступность всех 7 классов из `goga.ast.rules.document.imports.document`, наследование от DocumentRule, сигнатуру `check(node) -> list[DocumentRuleError]` (ожидаемо падают)
- [x] **Код**: создать файл `goga/ast/rules/document/imports/document.py` — извлечь 7 классов из `goga/ast/rules/document.py`, обновить импорты на относительные: `from ...base.document import DocumentRule`, `from ....nodes import ImportsNode, ImportTypeItemNode, ImportUsageItemNode`, `from .tools import signature_contains_type_name`
- [x] **Код**: обновить `goga/ast/rules/document/imports/__init__.py` — добавить реэкспорт всех 7 классов + `signature_contains_type_name`
- [x] **Верификация интерфейсов**: `python -m pytest tests/goga/ast/rules/document/imports/test_document.py -v` — контрактные тесты должны пройти
- [x] **Логические тесты**: в `test_document.py` добавить тесты для каждого правила:
  - `ImportsCanNotBeEmpty`: пустой imports → ошибка "empty"; нет блока Imports → []; непустой imports → []
  - `ImportsHasOnlyValidKeys`: неизвестный ключ → ошибка "unknown_keys"; только допустимые → []
  - `ImportItemIsValid`: пустой Types/Usages → ошибка "no_type"; непустой → []
  - `ImportUsageExists`: файл не существует → ошибка "not_found"; существует → []
  - `ImportHasValidFromPath`: пустой путь → "empty"; путь не существует → "not_found"; путь выходит за CWD → "escapes"; валидный → []
  - `ImportHasNotDuplicate`: дубликат → "duplicate"; уникальные → []
  - `ImportIsUsed`: неиспользуемый тип → "unused"; используемый в аннотации → []; embedded → []; usage не проверяется в сигнатурах
- [x] **Отладка**: `python -m pytest tests/goga/ast/rules/document/imports/ -v` — исправлять код, пока все тесты не пройдут
- [x] **Перепроверка контрактов**: проверить что все 7 классов доступны из `goga.ast.rules.document.imports`, наследуют DocumentRule, имеют корректные default имена
- [x] **Линт**: `ruff check goga/ast/rules/document/imports/ && ruff format goga/ast/rules/document/imports/`

### Task 4: Ячейка `document/usages` — 4 правила проверки практик (TDD кодирование)

Реализовать 4 класса-мутации DocumentRule в `goga/ast/rules/document/usages/document.py`. Код извлекается из существующего `goga/ast/rules/document.py`.

**Сущности контракта:**
- `AllUsagesIsUsed` — все декларированные usages используются в AnnotationsNode
- `UsageFilepathExists` — filepath: префикс `.goga/usages/`, файл существует; inline/URL пропускаются
- `UsageUrlIsAccessible` — HEAD → fallback GET, timeout 10s; inline/filepath пропускаются
- `UsageLinksHasNotConflicts` — отсутствие конфликтов имён с импортами и entity/routine

**Импортированные зависимости**: `DocumentRule` (from `goga/ast/rules/base`); `UsagesNode`, `UsageItemNode`, `AnnotationsNode`, `HeaderNode`, `RoutineTypeNode`, `EntityTypeNode`, `MethodNode`, `PropertyNode` (from `goga/ast/nodes`)

**Usages, релевантные для этой задачи:**
- `conventions`: python 3.10+, dataclasses kw_only=True, pytest + ruff, `mock.patch` для HTTP-запросов, `tmp_path` для файловых операций

**КРИТИЧЕСКИ: файлы `CODEMANIFEST` — определения контракта только для чтения.**

- [x] **ШАГ 0 (ОБЪЯВЛЕНИЕ)**: Объявить работу над Task 4 — 4 правила проверки usages
- [x] **Контрактные тесты**: создать `tests/goga/ast/rules/document/usages/__init__.py` и `tests/goga/ast/rules/document/usages/test_document.py` — проверить доступность 4 классов, наследование от DocumentRule, сигнатуру check (ожидаемо падают)
- [x] **Код**: создать `goga/ast/rules/document/usages/__init__.py` с реэкспортом
- [x] **Код**: создать `goga/ast/rules/document/usages/document.py` — извлечь 4 класса, обновить импорты на относительные
- [x] **Верификация интерфейсов**: `python -m pytest tests/goga/ast/rules/document/usages/test_document.py -v`
- [x] **Логические тесты**: в `test_document.py` добавить:
  - `AllUsagesIsUsed`: неиспользуемая практика → "unused"; используемая в аннотации → []
  - `UsageFilepathExists`: путь без `.goga/usages/` → "incorrect_path"; путь выходит за корень → "outside_usages"; файл не существует → "not_found"; существует → []; inline usage → пропуск; URL usage → пропуск
  - `UsageUrlIsAccessible`: HTTP 200 → []; HTTP 404 → "not_accessible"; network error → "request_failed"; inline/filepath → пропуск; использовать `mock.patch` для HTTP-запросов
  - `UsageLinksHasNotConflicts`: конфликт с импортом → "import_conflict"; конфликт с entity → "entity_conflict"; нет конфликтов → []
- [x] **Отладка**: `python -m pytest tests/goga/ast/rules/document/usages/ -v` — исправлять код
- [x] **Перепроверка контрактов**: проверить доступность 4 классов из `goga.ast.rules.document.usages`
- [x] **Линт**: `ruff check goga/ast/rules/document/usages/ && ruff format goga/ast/rules/document/usages/`

### Task 5: Ячейка `document/structure` — 6 правил структуры entity/routine (TDD кодирование)

Реализовать 6 классов-мутаций DocumentRule в `goga/ast/rules/document/structure/document.py`. Код извлекается из существующего `goga/ast/rules/document.py`.

**Сущности контракта:**
- `EntitiesAndRoutinesHasNotConflicts` — имена не конфликтуют с импортами; embedded — исключение
- `EntityHasOnlyValidKeys` — допустимые ключи {location, annotations, properties, methods}
- `RoutineHasOnlyValidKeys` — допустимые ключи {location, annotations}
- `SignatureIsValid` — формат '(...) -> ...' или '(...)'
- `ReturnTypeHasLink` — возвращаемый тип имеет метку label:Type; без return — валидно
- `LocationIsRequired` — location обязателен, с расширением, без '/'; embedded пропускаются

**Импортированные зависимости**: `DocumentRule` (from `goga/ast/rules/base`); `EntityTypeNode`, `RoutineTypeNode`, `MethodNode`, `ImportsNode` (from `goga/ast/nodes`)

**Usages, релевантные для этой задачи:**
- `conventions`: python 3.10+, pytest + ruff

**КРИТИЧЕСКИ: файлы `CODEMANIFEST` — определения контракта только для чтения.**

- [x] **ШАГ 0 (ОБЪЯВЛЕНИЕ)**: Объявить работу над Task 5 — 6 правил структуры
- [x] **Контрактные тесты**: создать `tests/goga/ast/rules/document/structure/__init__.py` и `tests/goga/ast/rules/document/structure/test_document.py` — проверить доступность 6 классов, наследование, сигнатуру check (ожидаемо падают)
- [x] **Код**: создать `goga/ast/rules/document/structure/__init__.py` с реэкспортом
- [x] **Код**: создать `goga/ast/rules/document/structure/document.py` — извлечь 6 классов, обновить импорты
- [x] **Верификация интерфейсов**: `python -m pytest tests/goga/ast/rules/document/structure/test_document.py -v`
- [x] **Логические тесты**: в `test_document.py` добавить:
  - `EntitiesAndRoutinesHasNotConflicts`: конфликт entity с импортом → "entity_conflict"; конфликт routine → "routine_conflict"; embedded → пропуск; нет конфликтов → []
  - `EntityHasOnlyValidKeys`: неизвестный ключ → "unknown_keys"; только допустимые → []
  - `RoutineHasOnlyValidKeys`: неизвестный ключ → "unknown_keys"; только допустимые → []
  - `SignatureIsValid`: некорректный формат → "format"; пустая сигнатура → "empty"; валидная → []
  - `ReturnTypeHasLink`: тип без метки → "missing_link"; с меткой → []; без return → []
  - `LocationIsRequired`: нет location → "missing"; без расширения → "no_extension"; содержит '/' → "contains_path"; embedded → пропуск; валидный → []
- [x] **Отладка**: `python -m pytest tests/goga/ast/rules/document/structure/ -v` — исправлять код
- [x] **Перепроверка контрактов**: проверить доступность 6 классов из `goga.ast.rules.document.structure`
- [x] **Линт**: `ruff check goga/ast/rules/document/structure/ && ruff format goga/ast/rules/document/structure/`

### Task 6: Ячейка `document/mutation` — 3 правила мутаций (TDD кодирование)

Реализовать 3 класса-мутации DocumentRule в `goga/ast/rules/document/mutation/document.py`. Код извлекается из существующего `goga/ast/rules/document.py`.

**Сущности контракта:**
- `MutationExists` — базовый тип мутации существует (в imports, entities, routines)
- `MutationIsValid` — мутация не ссылается на себя
- `EmbeddedEntityCanNotHasMutations` — embedded сущность не имеет мутаций

**Импортированные зависимости**: `DocumentRule` (from `goga/ast/rules/base`); `EntityTypeNode`, `ImportsNode` (from `goga/ast/nodes`)

**Usages, релевантные для этой задачи:**
- `conventions`: python 3.10+, pytest + ruff

**КРИТИЧЕСКИ: файлы `CODEMANIFEST` — определения контракта только для чтения.**

- [ ] **ШАГ 0 (ОБЪЯВЛЕНИЕ)**: Объявить работу над Task 6 — 3 правила мутаций
- [ ] **Контрактные тесты**: создать `tests/goga/ast/rules/document/mutation/__init__.py` и `tests/goga/ast/rules/document/mutation/test_document.py` — проверить доступность 3 классов, наследование, сигнатуру check (ожидаемо падают)
- [ ] **Код**: создать `goga/ast/rules/document/mutation/__init__.py` с реэкспортом
- [ ] **Код**: создать `goga/ast/rules/document/mutation/document.py` — извлечь 3 класса, обновить импорты
- [ ] **Верификация интерфейсов**: `python -m pytest tests/goga/ast/rules/document/mutation/test_document.py -v`
- [ ] **Логические тесты**: в `test_document.py` добавить:
  - `MutationExists`: тип не найден → "not_found"; найден в entities → []; найден в routines → []; найден в imports → []
  - `MutationIsValid`: мутация ссылается на себя → "self_mutation"; ссылается на другой → []
  - `EmbeddedEntityCanNotHasMutations`: embedded с мутациями → "has_mutations"; без мутаций → []
- [ ] **Отладка**: `python -m pytest tests/goga/ast/rules/document/mutation/ -v` — исправлять код
- [ ] **Перепроверка контрактов**: проверить доступность 3 классов из `goga.ast.rules.document.mutation`
- [ ] **Линт**: `ruff check goga/ast/rules/document/mutation/ && ruff format goga/ast/rules/document/mutation/`

### Task 7: Ячейка `document/annotations` — правило проверки аннотаций (TDD кодирование)

Реализовать класс `AnnotationLinksExists` в `goga/ast/rules/document/annotations/document.py`. Код извлекается из существующего `goga/ast/rules/document.py`.

**Сущность контракта: `DocumentRule::AnnotationLinksExists`** — проверяет что все ссылки в аннотациях (backtick references) разрешимы в контексте документа: imports (type или alias), usages (name), body (entity/routine name), сигнатуры. Для поиска в сигнатурах использует `signature_contains_type_name`.

**Импортированные зависимости**: `DocumentRule` (from `goga/ast/rules/base`); `signature_contains_type_name` (from `goga/ast/rules/document/imports`); `AnnotationsNode`, `HeaderNode`, `UsageItemNode`, `RoutineTypeNode`, `EntityTypeNode`, `MethodNode`, `PropertyNode`, `BodyNode` (from `goga/ast/nodes`)

**Внутренняя зависимость**: вызывает `signature_contains_type_name` из ячейки `document/imports`

**Usages, релевантные для этой задачи:**
- `conventions`: python 3.10+, pytest + ruff

**КРИТИЧЕСКИ: файлы `CODEMANIFEST` — определения контракта только для чтения.**

- [ ] **ШАГ 0 (ОБЪЯВЛЕНИЕ)**: Объявить работу над Task 7 — правило проверки аннотаций
- [ ] **Контрактные тесты**: создать `tests/goga/ast/rules/document/annotations/__init__.py` и `tests/goga/ast/rules/document/annotations/test_document.py` — проверить доступность `AnnotationLinksExists`, наследование от DocumentRule, сигнатуру check (ожидаемо падает)
- [ ] **Код**: создать `goga/ast/rules/document/annotations/__init__.py` с реэкспортом
- [ ] **Код**: создать `goga/ast/rules/document/annotations/document.py` — извлечь класс, обновить импорты: `from ...base.document import DocumentRule`, `from ..imports.tools import signature_contains_type_name`, `from ....nodes import ...`
- [ ] **Верификация интерфейсов**: `python -m pytest tests/goga/ast/rules/document/annotations/test_document.py -v`
- [ ] **Логические тесты**: в `test_document.py` добавить:
  - ссылка найдена в imports (type) → []
  - ссылка найдена в imports (alias) → []
  - ссылка найдена в usages → []
  - ссылка найдена в entity/routine name → []
  - ссылка найдена в сигнатуре через `signature_contains_type_name` → []
  - ссылка не найдена → "not_found"
  - проверка разделителей: `param_` и `param-` не являются разделителями (ссылка не найдена); `param:` — разделитель (ссылка найдена)
- [ ] **Отладка**: `python -m pytest tests/goga/ast/rules/document/annotations/ -v` — исправлять код
- [ ] **Перепроверка контрактов**: проверить доступность `AnnotationLinksExists` из `goga.ast.rules.document.annotations`
- [ ] **Линт**: `ruff check goga/ast/rules/document/annotations/ && ruff format goga/ast/rules/document/annotations/`

### Task 8: Ячейка `ast` — 3 AST правила (TDD кодирование)

Реализовать 3 класса-мутации ASTRule в `goga/ast/rules/ast/ast.py`. Код извлекается из существующего `goga/ast/rules/ast.py`.

**Сущности контракта:**
- `ImportsHasNotCyclicalDeps` — проверяет отсутствие циклических зависимостей; O(1) lookup через `dict[str, set[str]]`
- `ImportTypeExists` — проверяет что импортированный тип существует в целевом документе; skip при несуществующем пути; O(1) lookup
- `EmbeddedTypeHasLowLevel` — проверяет что embedded типы расположены ниже в иерархии; `os.path.normpath`

**Импортированные зависимости**: `ASTRule` (from `goga/ast/rules/base`); `DocumentRoot` (from `goga/ast/nodes`)

**Usages, релевантные для этой задачи:**
- `conventions`: python 3.10+, pytest + ruff

**КРИТИЧЕСКИ: файлы `CODEMANIFEST` — определения контракта только для чтения.**

- [ ] **ШАГ 0 (ОБЪЯВЛЕНИЕ)**: Объявить работу над Task 8 — 3 AST правила
- [ ] **Контрактные тесты**: создать `tests/goga/ast/rules/ast/__init__.py` и `tests/goga/ast/rules/ast/test_ast.py` — проверить доступность 3 классов, наследование от ASTRule, сигнатуру check(document) (ожидаемо падают)
- [ ] **Код**: создать `goga/ast/rules/ast/__init__.py` с реэкспортом
- [ ] **Код**: создать `goga/ast/rules/ast/ast.py` — извлечь 3 класса, обновить импорты: `from ..base.ast import ASTRule`, `from ...nodes import DocumentRoot`
- [ ] **Верификация интерфейсов**: `python -m pytest tests/goga/ast/rules/ast/test_ast.py -v`
- [ ] **Логические тесты**: в `test_ast.py` добавить:
  - `ImportsHasNotCyclicalDeps`: без цикла → []; с циклом (взаимный импорт) → "cycle"
  - `ImportTypeExists`: тип найден → []; тип не найден → "not_found"; путь не существует → пропуск []
  - `EmbeddedTypeHasLowLevel`: уровень ниже → []; уровень выше → "wrong_level"; `os.path.normpath` нормализация
- [ ] **Отладка**: `python -m pytest tests/goga/ast/rules/ast/ -v` — исправлять код
- [ ] **Перепроверка контрактов**: проверить доступность 3 классов из `goga.ast.rules.ast`
- [ ] **Линт**: `ruff check goga/ast/rules/ast/ && ruff format goga/ast/rules/ast/`

### Task 9: Фасад и обратная совместимость (инфраструктура)

Обновить фасадный `goga/ast/rules/__init__.py` для реэкспорта из подмодулей. Превратить `goga/ast/rules/document.py`, `ast.py`, `tools.py` в deprecated-обёртки, реэкспортирующие из подкаталогов. Это гарантирует обратную совместимость для внешних потребителей (`goga/ast/visitor`, `goga/ast/analyzer`, `goga/ast`).

**Usages, релевантные для этой задачи:**
- `conventions`: относительные импорты, ruff

**КРИТИЧЕСКИ: файлы `CODEMANIFEST` — определения контракта только для чтения.**

- [ ] Обновить `goga/ast/rules/__init__.py` — заменить импорты из монолитных файлов на импорты из подмодулей. Реэкспортировать все 27 сущностей: `from .base import DocumentRule, ASTRule`, `from .document.imports import ...`, `from .document.usages import ...`, `from .document.structure import ...`, `from .document.mutation import ...`, `from .document.annotations import AnnotationLinksExists`, `from .ast import ImportsHasNotCyclicalDeps, ImportTypeExists, EmbeddedTypeHasLowLevel`
- [ ] Обновить `goga/ast/rules/document.py` — заменить реализацию на реэкспорт из подмодулей (deprecated): `from .document.imports.document import ...`, `from .document.usages.document import ...`, `from .document.structure.document import ...`, `from .document.mutation.document import ...`, `from .document.annotations.document import ...`
- [ ] Обновить `goga/ast/rules/ast.py` — заменить реализацию на реэкспорт: `from .ast.ast import ...`
- [ ] Обновить `goga/ast/rules/tools.py` — заменить реализацию на реэкспорт: `from .document.imports.tools import signature_contains_type_name`
- [ ] Проверить доступность фасада: `python -c "from goga.ast.rules import DocumentRule, ASTRule, signature_contains_type_name, ImportsCanNotBeEmpty, ImportsHasNotCyclicalDeps; print('OK')"` — все 27 сущностей должны быть доступны
- [ ] Проверить обратную совместимость: `python -c "from goga.ast.rules.document import ImportsCanNotBeEmpty; from goga.ast.rules.ast import ImportsHasNotCyclicalDeps; from goga.ast.rules.tools import signature_contains_type_name; print('OK')"`
- [ ] Запустить все существующие тесты: `python -m pytest tests/ -v` — все тесты должны пройти (1032 теста)
- [ ] Линт: `ruff check goga/ast/rules/ && ruff format goga/ast/rules/`

### Task 10: Реорганизация тестов (инфраструктура)

Переместить существующие тесты из `tests/goga/ast/rules/` в зеркальную структуру подкаталогов. Новые тесты уже созданы в задачах 2–8. Старые тестовые файлы должны быть удалены или превращены в deprecated-обёртки.

**КРИТИЧЕСКИ: файлы `CODEMANIFEST` — определения контракта только для чтения.**

- [ ] Переместить `tests/goga/ast/rules/test_document.py` → соответствующие файлы в подкаталогах (содержимое уже покрыто задачами 2–8, дублирование недопустимо — убедиться что новые тесты покрывают все кейсы из старого файла)
- [ ] Переместить `tests/goga/ast/rules/test_import_item_is_valid.py` → `tests/goga/ast/rules/document/imports/test_document.py` (объединить с тестами из Task 3)
- [ ] Переместить `tests/goga/ast/rules/test_import_usage_exists.py` → `tests/goga/ast/rules/document/imports/test_document.py` (объединить с тестами из Task 3)
- [ ] Переместить `tests/goga/ast/rules/test_location_is_required.py` → `tests/goga/ast/rules/document/structure/test_document.py` (объединить с тестами из Task 5)
- [ ] Удалить или обновить старые тестовые файлы, убедившись что покрытие не уменьшилось
- [ ] Запустить все тесты: `python -m pytest tests/ -v` — все должны пройти
- [ ] Линт: `ruff check tests/goga/ast/rules/ && ruff format tests/goga/ast/rules/`

### Task 11: Интеграционные тесты для `rules` (интеграционные тесты)

Проверить межсущностные сценарии: корректность фасадного реэкспорта всех 27 сущностей, обратная совместимость старых путей импорта, взаимодействие `AnnotationLinksExists` → `signature_contains_type_name` через границу ячеек.

**Usages, релевантные для этой задачи:**
- `conventions`: pytest, относительные импорты

- [ ] Создать файл `tests/goga/ast/rules/test_integration.py`
- [ ] Протестировать фасад: все 27 сущностей импортируемы из `goga.ast.rules` одним `import`
- [ ] Протестировать обратную совместимость: импорт из `goga.ast.rules.document`, `goga.ast.rules.ast`, `goga.ast.rules.tools` возвращает те же объекты что и из подмодулей
- [ ] Протестировать межсущностное взаимодействие: `AnnotationLinksExists` корректно вызывает `signature_contains_type_name` через границу ячеек (`document/annotations` → `document/imports`)
- [ ] Протестировать граничный случай: создание экземпляров всех классов и вызов `check` с валидными/невалидными данными
- [ ] Запустить валидацию: `python -m pytest tests/goga/ast/rules/test_integration.py -v`

---

## Команды валидации

- `python -m pytest tests/ -v`: Запустить все тесты
- `ruff check goga/ast/rules/`: Проверка линта
- `ruff format goga/ast/rules/ --check`: Проверка форматирования
- `python -c "from goga.ast.rules import DocumentRule, ASTRule, signature_contains_type_name, ImportsCanNotBeEmpty, ImportsHasOnlyValidKeys, ImportItemIsValid, ImportUsageExists, ImportHasValidFromPath, ImportHasNotDuplicate, ImportIsUsed, AllUsagesIsUsed, UsageFilepathExists, UsageUrlIsAccessible, UsageLinksHasNotConflicts, EntitiesAndRoutinesHasNotConflicts, EntityHasOnlyValidKeys, RoutineHasOnlyValidKeys, SignatureIsValid, ReturnTypeHasLink, LocationIsRequired, MutationExists, MutationIsValid, EmbeddedEntityCanNotHasMutations, AnnotationLinksExists, ImportsHasNotCyclicalDeps, ImportTypeExists, EmbeddedTypeHasLowLevel; print('All 27 entities OK')"`: Проверить доступность всех сущностей фасада

---

## Критерии завершения

- [ ] Каждая сущность контракта реализована в правильном `location`
- [ ] Каждая сущность контракта доступна из фасада `goga.ast.rules`
- [ ] Свойства и методы соответствуют объявленному API
- [ ] Описания отражены в поведении
- [ ] Зависимости контракта соблюдены (относительные импорты)
- [ ] Реэкспорты доступны из фасада (27 сущностей)
- [ ] Обратная совместимость: импорт из старых путей (`document.py`, `ast.py`, `tools.py`) работает
- [ ] Каждая задача кодирования следовала рабочему процессу TDD
- [ ] Контрактные тесты и логические тесты покрывают фасад, API и поведение
- [ ] Интеграционные тесты проверяют фасад и межсущностные взаимодействия
- [ ] Ни одна граница пакета не была расширена
- [ ] Файлы `CODEMANIFEST` не были изменены (контракт только для чтения)
- [ ] Все команды валидации проходят
- [ ] Все 1032+ тестов проходят
