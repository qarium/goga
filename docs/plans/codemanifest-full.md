# Plan: codemanifest-full

## Goal

Реализация всей иерархии пакета `goga/codemanifest` — системы для загрузки, парсинга, анализа и валидации `CODEMANIFEST` файлов.

После реализации пакет должен предоставлять:
- **nodes** — структуры данных (dataclass) для представления дерева документа манифеста
- **errors** — иерархия исключений для ошибок парсинга и нарушения правил
- **rules** — правила валидации на уровне документа и проекта
- **visitor** — посетитель для анализа отдельного документа
- **analyzer** — анализатор для глобального анализа дерева документов
- **factory** — фабрика для загрузки и парсинга CODEMANIFEST файлов в дерево нод
- **codemanifest (root)** — фасад пакета с сущностью `Project` для загрузки дерева документов

Стратегия: реализация от листьев к корню, каждый пакет (код + тесты) завершается полностью перед переходом к следующему.

## Context

### Contract Surface

#### Package: `goga/codemanifest/nodes`

**Entity: `Node()`**
- Kind: class
- Declared `location`: `base.py`
- Facade obligation: must be importable from `goga.codemanifest.nodes`
- Properties:
  - `parent -> DocumentNode | DocumentRoot` — Родительская нода или документ
  - `data -> dict[str, Any]` — Исходные данные из которых была сделана нода
- Annotations: python >=3.10, dataclasses, структуры создаются с пустыми данными по умолчанию

**Entity: `Node::DocumentRoot()`**
- Kind: class (mutation of Node)
- Declared `location`: `document.py`
- Facade obligation: must be importable from `goga.codemanifest.nodes`
- Properties:
  - `path -> str` — Относительный путь расположения документа
  - `links -> dict[str, list[Node]]` — Все ссылки в документе
  - `header -> HeaderNode` — Нода заголовка (default=HeaderNode())
  - `body -> BodyNode` — Нода тела (default=BodyNode())
  - `footer -> FooterNode` — Нижний колонтитул (default=FooterNode())
  - `types -> dict[str, list[Node]]` — Все типы в документе
  - `children -> list[DocumentRoot]` — Дочерние документы

**Entity: `Node::DocumentNode()`**
- Kind: class (mutation of Node)
- Declared `location`: `document.py`
- Facade obligation: must be importable from `goga.codemanifest.nodes`
- Properties:
  - `root -> DocumentRoot` — Основной объект документа

**Entity: `DocumentNode::AnnotationsNode()`**
- Kind: class (mutation of DocumentNode)
- Declared `location`: `common.py`
- Facade obligation: must be importable from `goga.codemanifest.nodes`
- Properties:
  - `url -> str | None` — URL для загрузки практики
  - `filepath -> str | None` — Путь до файла с аннотацией
  - `links -> list[str]` — Список ссылок в аннотациях
  - `text -> str` — Текст аннотации

**Entity: `DocumentNode::HeaderNode()`**
- Kind: class (mutation of DocumentNode)
- Declared `location`: `header.py`
- Facade obligation: must be importable from `goga.codemanifest.nodes`
- Properties:
  - `imports -> ImportsNode` — (default=ImportsNode())
  - `usages -> UsagesNode` — (default=UsagesNode())
  - `annotations -> AnnotationsNode`
  - `types -> list[str]` — Список имен типов подключенных через imports

**Entity: `DocumentNode::ImportsNode()`**
- Kind: class (mutation of DocumentNode)
- Declared `location`: `header.py`
- Properties:
  - `items -> list[ImportItemNode]`

**Entity: `DocumentNode::ImportItemNode()`**
- Kind: class (mutation of DocumentNode)
- Declared `location`: `header.py`
- Properties:
  - `type_name -> set[str]`
  - `from_path -> str`
  - `alias -> str`

**Entity: `DocumentNode::UsagesNode()`**
- Kind: class (mutation of DocumentNode)
- Declared `location`: `header.py`
- Properties:
  - `items -> list[UsageItemNode]`

**Entity: `DocumentNode::UsageItemNode()`**
- Kind: class (mutation of DocumentNode)
- Declared `location`: `header.py`
- Properties:
  - `name -> str`
  - `annotations -> AnnotationsNode`

**Entity: `DocumentNode::BodyNode()`**
- Kind: class (mutation of DocumentNode)
- Declared `location`: `body.py`
- Properties:
  - `types -> dict[str, list[Node]]`
  - `entities -> list[EntityTypeNode]`
  - `routines -> list[RoutineTypeNode]`

**Entity: `DocumentNode::RoutineTypeNode()`**
- Kind: class (mutation of DocumentNode)
- Declared `location`: `body.py`
- Properties:
  - `name -> str`
  - `signature -> str`
  - `location -> str`
  - `annotations -> AnnotationsNode`
  - `embedded -> bool`

**Entity: `DocumentNode::EntityTypeNode()`**
- Kind: class (mutation of DocumentNode)
- Declared `location`: `body.py`
- Properties:
  - `name -> str`
  - `signature -> str`
  - `location -> str`
  - `annotations -> AnnotationsNode`
  - `properties -> list[PropertyNode]`
  - `methods -> list[MethodNode]`
  - `embedded -> bool`
  - `mutations -> list[str]`

**Entity: `DocumentNode::MethodNode()`**
- Kind: class (mutation of DocumentNode)
- Declared `location`: `body.py`
- Properties:
  - `name -> str`
  - `signature -> str`
  - `annotations -> AnnotationsNode`

**Entity: `DocumentNode::PropertyNode()`**
- Kind: class (mutation of DocumentNode)
- Declared `location`: `body.py`
- Properties:
  - `name -> str`
  - `type -> str`
  - `annotations -> AnnotationsNode`

**Entity: `DocumentNode::FooterNode`**
- Kind: class (mutation of DocumentNode)
- Declared `location`: `footer.py`
- Properties:
  - `architector -> str`
  - `created_at -> str`
  - `description -> str`

---

#### Package: `goga/codemanifest/errors`

**Entity: `BaseCodemanifestError(message: str)`**
- Kind: class
- Declared `location`: `base.py`
- Facade obligation: must be importable from `goga.codemanifest.errors`
- Properties:
  - `message -> str`
- Annotations: Наследуется от Exception, message попадает в Exception.args

**Entity: `BaseCodemanifestException::ManifestParseError(message: str, filepath: str)`**
- Kind: class (mutation of BaseCodemanifestException)
- Declared `location`: `manifest.py`
- Properties:
  - `filepath -> str`

**Entity: `BaseCodemanifestException::ManifestRuleError(message: str, rule: str, document: DocumentRoot, node: DocumentNode)`**
- Kind: class (mutation of BaseCodemanifestException)
- Declared `location`: `manifest.py`
- Properties:
  - `rule -> str`
  - `document -> DocumentNode`
  - `node -> DocumentNode`
- Annotations: Строковое представление по формату с Rule, Path, Node

**Entity: `BaseCodemanifestException::ProjectRuleError(message: str, rule: str, document: DocumentRoot | None, node: DocumentNode | None)`**
- Kind: class (mutation of BaseCodemanifestException)
- Declared `location`: `project.py`
- Properties:
  - `rule -> str`
  - `document -> DocumentNode | None`
  - `node -> DocumentNode | None`
- Annotations: Строковое представление по формату (document/node может быть None)

---

#### Package: `goga/codemanifest/rules`

**Entity: `DocumentRule(name: str)`**
- Kind: class
- Declared `location`: `document.py`
- Facade obligation: must be importable from `goga.codemanifest.rules`
- Properties:
  - `name -> str`
- Methods:
  - `check(node: DocumentNode) -> errors:list[CodemanifestRuleError]` — Проверяет ноду на соответствие правилу

**Entity: `DocumentRule::ImportsCanNotBeEmptyRule(name: str = 'imports_can_not_be_empty')`**
- Kind: class (mutation of DocumentRule)
- Declared `location`: `document.py`
- Annotations: Проверяет что список импортов не пустой

**Entity: `DocumentRule::ImportHasTypeRule(name: str = 'import_has_type')`**
- Kind: class (mutation of DocumentRule)
- Declared `location`: `document.py`
- Annotations: Проверяет что импорт содержит подключаемый тип

**Entity: `DocumentRule::ImportHasValidFromPathRule(name: str = 'import_has_valid_from_path')`**
- Kind: class (mutation of DocumentRule)
- Declared `location`: `document.py`
- Annotations: Проверяет: путь существует, не выходит за пределы CWD

**Entity: `ProjectRule(tree: list[DocumentRoot], name: str)`**
- Kind: class
- Declared `location`: `project.py`
- Properties:
  - `name -> str`
  - `tree -> list[DocumentRoot]`
- Methods:
  - `check(document: DocumentRoot) -> errors:list[CodemanifestRuleError]` — Проверяет документ

**Entity: `ProjectRule::ImportsHasNotCyclicalDepsRule(tree: list[DocumentRoot], name: str = 'imports_has_not_cyclical_deps')`**
- Kind: class (mutation of ProjectRule)
- Declared `location`: `project.py`
- Annotations: Проверяет отсутствие циклических зависимостей в импортах

**Entity: `ProjectRule::AllUsagesIsUsed(tree: list[DocumentRoot], name: str = 'all_usages_is_used')`**
- Kind: class (mutation of ProjectRule)
- Declared `location`: `project.py`
- Annotations: Проверяет что все usages используются в аннотациях

---

#### Package: `goga/codemanifest/visitor`

**Entity: `Visitor(document: DocumentRoot)`**
- Kind: class
- Declared `location`: `visitor.py`
- Facade obligation: must be importable from `goga.codemanifest.visitor`
- Properties:
  - `document -> DocumentRoot`
- Methods:
  - `analyze(rules: list[DocumentRule]) -> errors:list[ManifestRuleError]` — Анализирует документ по правилам

---

#### Package: `goga/codemanifest/analyzer`

**Entity: `Analyzer(tree: list[DocumentRoot])`**
- Kind: class
- Declared `location`: `analyzer.py`
- Facade obligation: must be importable from `goga.codemanifest.analyzer`
- Properties:
  - `tree -> list[DocumentRoot]`
- Methods:
  - `analyze(rules: list[ProjectRule]) -> errors:list[ProjectRuleError]` — Анализирует все документы

---

#### Package: `goga/codemanifest/factory`

**Entity: `Factory(path: str)`**
- Kind: class
- Declared `location`: `factory.py`
- Facade obligation: must be importable from `goga.codemanifest.factory`
- Methods:
  - `create(parent: Node = None) -> document:DocumentRoot` — Создает дерево документа
- Usages: `dsl` (.usages/codemanifest/dsl.md), `yaml` (pyyaml)
- Annotations: Подробные правила парсинга YAML → дерево нод

---

#### Package: `goga/codemanifest` (root)

**Entity: `Project(path: str)`**
- Kind: class
- Declared `location`: `project.py`
- Facade obligation: must be importable from `goga.codemanifest`
- Properties:
  - `tree -> list[DocumentRoot]`
  - `errors -> list[ProjectRuleError | ManifestRuleError]`
- Methods:
  - `load()` — Загружает дерево по указанному пути (рекурсивный обход, factory, visitor, analyzer)

---

### Re-exports

Нет явных re-export блоков (`->Name: {}`) ни в одном CODEMANIFEST.

### Usages Context

- **dsl** (`goga/codemanifest/factory`): `.usages/codemanifest/dsl.md` — спецификация DSL формата CODEMANIFEST, определяет структуру документа (заголовок, тело, колонтитул), типы (entity, routine), мутации, аннотации, регистр ключей
- **yaml** (`goga/codemanifest/factory`): Библиотека pyyaml для парсинга YAML документов. Уже в зависимостях pyproject.toml
- **nodes** (`goga/codemanifest/factory`, `goga/codemanifest/rules`): API пакета goga/codemanifest/nodes для работы со структурой документа
- **factory** (`goga/codemanifest`): API пакета goga/codemanifest/factory для создания документа
- **visitor** (`goga/codemanifest`): API пакета goga/codemanifest/visitor для анализа одного документа
- **analyzer** (`goga/codemanifest`): API пакета goga/codemanifest/analyzer для анализа дерева документов

### External Dependencies

- `pyyaml` — для парсинга YAML документов (уже в зависимостях)
- `dataclasses` — стандартная библиотека Python для структур данных
- `typing.Any` — для поля `data` в `Node`

## Facts

- Все пакеты пустые — существуют только `__init__.py` файлы без содержимого
- Python >=3.10 (из pyproject.toml `requires-python = ">=3.10"`, подтверждено аннотациями CODEMANIFEST)
- Используется `dataclasses` для структур данных (указано в аннотациях nodes)
- Структуры создаются с пустыми данными по умолчанию (пустая строка, ноль и т.д.) если не указано None
- `pyyaml` уже в зависимостях проекта
- Тесты используют pytest (pytest >=8.0 в зависимостях)
- Линтер — ruff (target-version py310)
- Порядок обработки пакетов определяется зависимостями: nodes → errors → rules → visitor → analyzer → factory → codemanifest
- CODEMANIFEST файлы — read-only контракт, не подлежат модификации
- `FooterNode` объявлен без конструктора `()` — это тоже dataclass
- В `ManifestRuleError` свойство `document` имеет тип `DocumentNode` в аннотациях, но параметр конструктора `document: DocumentRoot` — фактически хранит DocumentRoot
- `BaseCodemanifestError` vs `BaseCodemanifestException` — в base.py имя Error, в mutations используется Exception

## Assumptions

- Assumption: `BaseCodemanifestError` в base.py и `BaseCodemanifestException` в mutations — это одно и то же базовое исключение. Имя `BaseCodemanifestException` в mutations (ManifestParseError, ManifestRuleError, ProjectRuleError) — это каноническое имя, `BaseCodemanifestError` в base.py описывает тот же класс.
  - Basis: mutations наследуются от BaseCodemanifestException, а base.py определяет BaseCodemanifestError — вероятнее всего опечатка в DSL, сущность одна
  - Criticality: high — определяет иерархию исключений
  - Safe to proceed without confirmation: yes (имплементация будет использовать BaseCodemanifestError как базовый класс)

- Assumption: Мутации реализуются через наследование Python (class Child(Parent)) — это наиболее естественный механизм для dataclass и Exception иерархий.
  - Basis: Python идиома, dataclass/exception требуют наследования для корректной работы
  - Criticality: medium
  - Safe to proceed without confirmation: yes

- Assumption: Свойство `data -> dict[str, Any]` в `Node` инициализируется как `field(default_factory=dict)`.
  - Basis: annotations говорят "пустые данные по умолчанию", dict — mutable, нужен default_factory
  - Criticality: low
  - Safe to proceed without confirmation: yes

- Assumption: `parent -> DocumentNode | DocumentRoot` в Node — это `Optional[Union[DocumentNode, DocumentRoot]]` с default=None, но annotations говорят "пустые данные по умолчанию", не None. Вероятно None для корня дерева.
  - Basis: у корневого документа нет родителя
  - Criticality: medium
  - Safe to proceed without confirmation: yes

- Assumption: `ManifestRuleError.document` хранит `DocumentRoot` (а не `DocumentNode`), т.к. параметр конструктора `document: DocumentRoot`, а свойство описано как `document -> DocumentNode` — но это свойство для узла в котором произошла ошибка.
  - Basis: сигнатура конструктора приоритетнее описания свойства
  - Criticality: medium
  - Safe to proceed without confirmation: yes

- Assumption: `location` в `EntityTypeNode` и `RoutineTypeNode` — это файл относительно CWD. Аннотации factory говорят "просто имя файла на одном уровне с CODEMANIFEST, нужно преобразовать в относительный путь от CWD".
  - Basis:annotations factory
  - Criticality: medium
  - Safe to proceed without confirmation: yes

## Open Questions

- (none in default mode)

## Gap Analysis

- **Missing contract entities**: ALL — ни один пакет не имеет реализации (только пустые `__init__.py`)
- **Missing facade exposure**: ALL — все `__init__.py` пустые
- **Wrong `location` placement**: N/A — файлов реализации не существует
- **API mismatches**: N/A — нет кода для сравнения
- **Behavioral mismatches**: N/A — нет кода для сравнения
- **Existing code that can be reused**: None
- **Test coverage gaps**: 100% — нет тестов для контракта
- **Missing workspace or git visibility**: Git показывает только untracked директории `.usages/` и `goga/codemanifest/` — файлы CODEMANIFEST не отслеживаются

---

## Tasks

> **Per-package ordering rule**: Каждый пакет завершается полностью (код + тесты) перед переходом к следующему. Порядок: nodes → errors → rules → visitor → analyzer → factory → codemanifest(root).

---

### Package: `goga/codemanifest/nodes`

### Task 1: Nodes — Infrastructure and facade setup

Создать структуру файлов пакета `goga/codemanifest/nodes` и настроить `__init__.py` для экспорта всех контрактных сущностей.

Контрактные сущности пакета: `Node`, `DocumentRoot`, `DocumentNode`, `AnnotationsNode`, `HeaderNode`, `ImportsNode`, `ImportItemNode`, `UsagesNode`, `UsageItemNode`, `BodyNode`, `RoutineTypeNode`, `EntityTypeNode`, `MethodNode`, `PropertyNode`, `FooterNode`.

Файлы: `base.py`, `document.py`, `common.py`, `header.py`, `body.py`, `footer.py`.

Annotations: python >=3.10, dataclasses, структуры создаются с пустыми данными по умолчанию.

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them. If the implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Create `goga/codemanifest/nodes/base.py` with `Node` dataclass skeleton
- [ ] Create `goga/codemanifest/nodes/document.py` with `DocumentRoot` and `DocumentNode` dataclass skeletons (extending Node)
- [ ] Create `goga/codemanifest/nodes/common.py` with `AnnotationsNode` dataclass skeleton (extending DocumentNode)
- [ ] Create `goga/codemanifest/nodes/header.py` with `HeaderNode`, `ImportsNode`, `ImportItemNode`, `UsagesNode`, `UsageItemNode` dataclass skeletons
- [ ] Create `goga/codemanifest/nodes/body.py` with `BodyNode`, `RoutineTypeNode`, `EntityTypeNode`, `MethodNode`, `PropertyNode` dataclass skeletons
- [ ] Create `goga/codemanifest/nodes/footer.py` with `FooterNode` dataclass skeleton (extending DocumentNode)
- [ ] Update `goga/codemanifest/nodes/__init__.py` to export all 14 entities: `Node`, `DocumentRoot`, `DocumentNode`, `AnnotationsNode`, `HeaderNode`, `ImportsNode`, `ImportItemNode`, `UsagesNode`, `UsageItemNode`, `BodyNode`, `RoutineTypeNode`, `EntityTypeNode`, `MethodNode`, `PropertyNode`, `FooterNode`
- [ ] Verify facade availability: `python -c "from goga.codemanifest.nodes import Node, DocumentRoot, DocumentNode, AnnotationsNode, HeaderNode, ImportsNode, ImportItemNode, UsagesNode, UsageItemNode, BodyNode, RoutineTypeNode, EntityTypeNode, MethodNode, PropertyNode, FooterNode"`
- [ ] Run existing tests to verify no regressions: `pytest tests/ -x` (skip this step if no test files exist yet)
- [ ] If any tests fail, fix the code written in this task (not test code) and re-run tests until they pass

### Task 2: Nodes — Implement base.py (Node dataclass)

Реализовать `Node` в `goga/codemanifest/nodes/base.py` — базовая нода дерева документа. Это корень иерархии всех нод.

Контракт:
- `parent -> DocumentNode | DocumentRoot` — Родительская нода или документ. По умолчанию None (у корня нет родителя).
- `data -> dict[str, Any]` — Исходные данные. По умолчанию пустой dict (использовать `field(default_factory=dict)`).

Annotations: python >=3.10, dataclasses, структуры создаются с пустыми данными по умолчанию (пустая строка, ноль и т.д.) если явно не указано None.

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them.**

- [ ] Implement `Node` as `@dataclass` in `base.py`
- [ ] Property `parent` with type `Optional[Union['DocumentNode', 'DocumentRoot']]`, default `None`
- [ ] Property `data` with type `dict[str, Any]`, default `field(default_factory=dict)`
- [ ] Ensure `from __future__ import annotations` for forward references (Python 3.10 compatibility)
- [ ] Verify import: `python -c "from goga.codemanifest.nodes.base import Node; n = Node(); print(n)"`
- [ ] Run existing tests to verify no regressions: `pytest tests/ -x` (skip this step if no test files exist yet)
- [ ] If any tests fail, fix the code written in this task (not test code) and re-run tests until they pass

### Task 3: Nodes — Implement document.py (DocumentRoot, DocumentNode)

Реализовать `DocumentRoot` и `DocumentNode` в `goga/codemanifest/nodes/document.py`. Обе мутации (наследуются) от `Node`.

Контракт `DocumentRoot`:
- `path -> str` — Относительный путь расположения документа (default: `""`)
- `links -> dict[str, list[Node]]` — Все ссылки (default: `field(default_factory=dict)`)
- `header -> HeaderNode` — Нода заголовка (default: `HeaderNode()`)
- `body -> BodyNode` — Нода тела (default: `BodyNode()`)
- `footer -> FooterNode` — Колонтитул (default: `FooterNode()`)
- `types -> dict[str, list[Node]]` — Все типы (default: `field(default_factory=dict)`)
- `children -> list[DocumentRoot]` — Дочерние документы (default: `field(default_factory=list)`)

Контракт `DocumentNode`:
- `root -> DocumentRoot` — Основной объект документа

Import: `Node` from `goga.codemanifest.nodes.base`. Forward references to `HeaderNode`, `BodyNode`, `FooterNode`.

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them.**

- [ ] Implement `DocumentRoot` as `@dataclass` extending `Node` in `document.py`
- [ ] All properties with defaults as specified in contract (empty strings, empty dicts/lists, default HeaderNode/BodyNode/FooterNode instances)
- [ ] Implement `DocumentNode` as `@dataclass` extending `Node` with property `root -> DocumentRoot`
- [ ] Use `from __future__ import annotations` for forward references
- [ ] Verify import: `python -c "from goga.codemanifest.nodes.document import DocumentRoot, DocumentNode; dr = DocumentRoot(); dn = DocumentNode(root=dr); print(dr, dn)"`
- [ ] Run existing tests to verify no regressions: `pytest tests/ -x` (skip this step if no test files exist yet)
- [ ] If any tests fail, fix the code written in this task (not test code) and re-run tests until they pass

### Task 4: Nodes — Implement common.py (AnnotationsNode)

Реализовать `AnnotationsNode` в `goga/codemanifest/nodes/common.py`. Мутация (наследуется) от `DocumentNode`.

Контракт:
- `url -> str | None` — URL для загрузки практики (default: `None`)
- `filepath -> str | None` — Путь до файла с аннотацией (default: `None`)
- `links -> list[str]` — Список ссылок (default: `field(default_factory=list)`)
- `text -> str` — Текст аннотации (default: `""`)

Import: `DocumentNode` from `goga.codemanifest.nodes.document`.

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them.**

- [ ] Implement `AnnotationsNode` as `@dataclass` extending `DocumentNode`
- [ ] Properties with defaults: `url=None`, `filepath=None`, `links=field(default_factory=list)`, `text=""`
- [ ] Verify import: `python -c "from goga.codemanifest.nodes.common import AnnotationsNode; a = AnnotationsNode(root=None); print(a)"`
- [ ] Run existing tests to verify no regressions: `pytest tests/ -x` (skip this step if no test files exist yet)
- [ ] If any tests fail, fix the code written in this task (not test code) and re-run tests until they pass

### Task 5: Nodes — Implement header.py (HeaderNode, ImportsNode, ImportItemNode, UsagesNode, UsageItemNode)

Реализовать 5 dataclass-ов в `goga/codemanifest/nodes/header.py`. Все мутации (наследуются) от `DocumentNode`.

Контракт:

**HeaderNode**:
- `imports -> ImportsNode` — (default=ImportsNode())
- `usages -> UsagesNode` — (default=UsagesNode())
- `annotations -> AnnotationsNode` — (default: AnnotationsNode с root=None)
- `types -> list[str]` — (default: `field(default_factory=list)`)

**ImportsNode**:
- `items -> list[ImportItemNode]` — (default: `field(default_factory=list)`)

**ImportItemNode**:
- `type_name -> set[str]` — (default: `field(default_factory=set)`)
- `from_path -> str` — (default: `""`)
- `alias -> str` — (default: `""`)

**UsagesNode**:
- `items -> list[UsageItemNode]` — (default: `field(default_factory=list)`)

**UsageItemNode**:
- `name -> str` — (default: `""`)
- `annotations -> AnnotationsNode` — (default: AnnotationsNode с root=None)

Import: `DocumentNode` from `goga.codemanifest.nodes.document`, `AnnotationsNode` from `goga.codemanifest.nodes.common`.

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them.**

- [ ] Implement all 5 dataclasses in `header.py`, each extending `DocumentNode`
- [ ] HeaderNode has default values: `imports=ImportsNode()`, `usages=UsagesNode()`, `annotations=AnnotationsNode(root=None)`
- [ ] ImportItemNode: `type_name` uses `field(default_factory=set)`
- [ ] UsageItemNode: `annotations` has default `AnnotationsNode(root=None)`
- [ ] Use `from __future__ import annotations` for forward references
- [ ] Verify import: `python -c "from goga.codemanifest.nodes.header import HeaderNode, ImportsNode, ImportItemNode, UsagesNode, UsageItemNode; h = HeaderNode(root=None); print(h)"`
- [ ] Run existing tests to verify no regressions: `pytest tests/ -x` (skip this step if no test files exist yet)
- [ ] If any tests fail, fix the code written in this task (not test code) and re-run tests until they pass

### Task 6: Nodes — Implement body.py (BodyNode, RoutineTypeNode, EntityTypeNode, MethodNode, PropertyNode)

Реализовать 5 dataclass-ов в `goga/codemanifest/nodes/body.py`. Все мутации (наследуются) от `DocumentNode`.

Контракт:

**BodyNode**:
- `types -> dict[str, list[Node]]` — (default: `field(default_factory=dict)`)
- `entities -> list[EntityTypeNode]` — (default: `field(default_factory=list)`)
- `routines -> list[RoutineTypeNode]` — (default: `field(default_factory=list)`)

**RoutineTypeNode**:
- `name -> str` (default: `""`)
- `signature -> str` (default: `""`)
- `location -> str` (default: `""`)
- `annotations -> AnnotationsNode` (default: AnnotationsNode с root=None)
- `embedded -> bool` (default: `False`)

**EntityTypeNode**:
- `name -> str` (default: `""`)
- `signature -> str` (default: `""`)
- `location -> str` (default: `""`)
- `annotations -> AnnotationsNode` (default: AnnotationsNode с root=None)
- `properties -> list[PropertyNode]` (default: `field(default_factory=list)`)
- `methods -> list[MethodNode]` (default: `field(default_factory=list)`)
- `embedded -> bool` (default: `False`)
- `mutations -> list[str]` (default: `field(default_factory=list)`)

**MethodNode**:
- `name -> str` (default: `""`)
- `signature -> str` (default: `""`)
- `annotations -> AnnotationsNode` (default: AnnotationsNode с root=None)

**PropertyNode**:
- `name -> str` (default: `""`)
- `type -> str` (default: `""`)
- `annotations -> AnnotationsNode` (default: AnnotationsNode с root=None)

Import: `DocumentNode` from `goga.codemanifest.nodes.document`, `Node` from `goga.codemanifest.nodes.base`, `AnnotationsNode` from `goga.codemanifest.nodes.common`.

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them.**

- [ ] Implement all 5 dataclasses in `body.py`, each extending `DocumentNode`
- [ ] BodyNode defaults: empty dict for types, empty lists for entities/routines
- [ ] RoutineTypeNode: `embedded=False` by default
- [ ] EntityTypeNode: `embedded=False`, empty lists for properties/methods/mutations
- [ ] Use `from __future__ import annotations` for forward references
- [ ] Verify import: `python -c "from goga.codemanifest.nodes.body import BodyNode, RoutineTypeNode, EntityTypeNode, MethodNode, PropertyNode; b = BodyNode(root=None); print(b)"`
- [ ] Run existing tests to verify no regressions: `pytest tests/ -x` (skip this step if no test files exist yet)
- [ ] If any tests fail, fix the code written in this task (not test code) and re-run tests until they pass

### Task 7: Nodes — Implement footer.py (FooterNode)

Реализовать `FooterNode` в `goga/codemanifest/nodes/footer.py`. Мутация (наследуется) от `DocumentNode`.

Контракт:
- `architector -> str` — (default: `""`)
- `created_at -> str` — (default: `""`)
- `description -> str` — (default: `""`)

Import: `DocumentNode` from `goga.codemanifest.nodes.document`.

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them.**

- [ ] Implement `FooterNode` as `@dataclass` extending `DocumentNode`
- [ ] All properties default to empty strings
- [ ] Verify import: `python -c "from goga.codemanifest.nodes.footer import FooterNode; f = FooterNode(root=None); print(f)"`
- [ ] Run existing tests to verify no regressions: `pytest tests/ -x` (skip this step if no test files exist yet)
- [ ] If any tests fail, fix the code written in this task (not test code) and re-run tests until they pass

### Task 8: Contract tests for nodes package

Создать контрактные тесты для пакета `goga/codemanifest/nodes`. Проверить фасад, API shape, defaults, иерархию наследования.

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them.**

- [ ] Create test file `tests/test_nodes.py`
- [ ] Test facade availability: `from goga.codemanifest.nodes import Node, DocumentRoot, DocumentNode, AnnotationsNode, HeaderNode, ImportsNode, ImportItemNode, UsagesNode, UsageItemNode, BodyNode, RoutineTypeNode, EntityTypeNode, MethodNode, PropertyNode, FooterNode`
- [ ] Test Node: default parent=None, data={}
- [ ] Test DocumentRoot: extends Node, all defaults (path="", links={}, header=HeaderNode(), body=BodyNode(), footer=FooterNode(), types={}, children=[])
- [ ] Test DocumentNode: extends Node, property root
- [ ] Test AnnotationsNode: extends DocumentNode, defaults (url=None, filepath=None, links=[], text="")
- [ ] Test HeaderNode: extends DocumentNode, defaults (imports=ImportsNode(), usages=UsagesNode(), types=[])
- [ ] Test ImportsNode/ImportItemNode: defaults, set for type_name
- [ ] Test UsagesNode/UsageItemNode: defaults
- [ ] Test BodyNode: defaults (types={}, entities=[], routines=[])
- [ ] Test RoutineTypeNode: defaults (embedded=False)
- [ ] Test EntityTypeNode: defaults (embedded=False, properties=[], methods=[], mutations=[])
- [ ] Test MethodNode/PropertyNode: defaults
- [ ] Test FooterNode: defaults (architector="", created_at="", description="")
- [ ] Run validation: `pytest tests/test_nodes.py -v`

---

### Package: `goga/codemanifest/errors`

### Task 9: Errors — Infrastructure and base exception

Создать базовое исключение `BaseCodemanifestError` в `goga/codemanifest/errors/base.py`.

Контракт:
- Наследуется от `Exception`
- Конструктор принимает `message: str`
- `message` попадает в `Exception.args`
- Свойство `message -> str`

Annotations: python >=3.10.

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them.**

- [ ] Implement `BaseCodemanifestError` in `goga/codemanifest/errors/base.py` extending `Exception`
- [ ] Constructor accepts `message: str`, passes it to `super().__init__(message)`
- [ ] Property `message` returns the error message
- [ ] Update `goga/codemanifest/errors/__init__.py` to export `BaseCodemanifestError`
- [ ] Verify facade: `python -c "from goga.codemanifest.errors import BaseCodemanifestError; e = BaseCodemanifestError('test'); print(e.message)"`
- [ ] Run existing tests to verify no regressions: `pytest tests/ -x`
- [ ] If any tests fail, fix the code written in this task (not test code) and re-run tests until they pass

### Task 10: Errors — Implement ManifestParseError and ManifestRuleError

Реализовать `ManifestParseError` и `ManifestRuleError` в `goga/codemanifest/errors/manifest.py`. Оба наследуются от `BaseCodemanifestError`.

**ManifestParseError(message: str, filepath: str)**:
- Свойство `filepath -> str`

**ManifestRuleError(message: str, rule: str, document: DocumentRoot, node: DocumentNode)**:
- Свойства: `rule -> str`, `document -> DocumentRoot`, `node -> DocumentNode`
- Строковое представление по формату:
  ```
  Error: <message>
    * Rule: <rule>
    * Path: <document path without filename>
    * Node:
      <beautiful node data>
  ```

Imports: `DocumentRoot`, `DocumentNode` from `goga.codemanifest.nodes`, `BaseCodemanifestError` from `goga.codemanifest.errors.base`.

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them.**

- [ ] Implement `ManifestParseError` extending `BaseCodemanifestError` with `filepath` property
- [ ] Implement `ManifestRuleError` extending `BaseCodemanifestError` with `rule`, `document`, `node` properties
- [ ] `ManifestRuleError.__str__` follows the required format with Rule, Path (document.path without filename), Node data
- [ ] Update `goga/codemanifest/errors/__init__.py` to export both classes
- [ ] Verify facade: `python -c "from goga.codemanifest.errors import ManifestParseError, ManifestRuleError"`
- [ ] Run existing tests to verify no regressions: `pytest tests/ -x`
- [ ] If any tests fail, fix the code written in this task (not test code) and re-run tests until they pass

### Task 11: Errors — Implement ProjectRuleError

Реализовать `ProjectRuleError` в `goga/codemanifest/errors/project.py`. Наследуется от `BaseCodemanifestError`.

**ProjectRuleError(message: str, rule: str, document: DocumentRoot | None, node: DocumentNode | None)**:
- Свойства: `rule -> str`, `document -> DocumentRoot | None`, `node -> DocumentNode | None`
- Строковое представление по формату (document/node может быть None):
  ```
  Error: <message>
    * Rule: <rule>
    * Path: <document path without filename if document exists>
    * Node:
      <beautiful node data if node exists>
  ```

Imports: `DocumentRoot`, `DocumentNode` from `goga.codemanifest.nodes`, `BaseCodemanifestError` from `goga.codemanifest.errors.base`.

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them.**

- [ ] Implement `ProjectRuleError` extending `BaseCodemanifestError`
- [ ] `document` and `node` parameters accept `None`
- [ ] `__str__` follows required format, omitting Path/Node sections when None
- [ ] Update `goga/codemanifest/errors/__init__.py` to export `ProjectRuleError`
- [ ] Verify facade: `python -c "from goga.codemanifest.errors import ProjectRuleError"`
- [ ] Run existing tests to verify no regressions: `pytest tests/ -x`
- [ ] If any tests fail, fix the code written in this task (not test code) and re-run tests until they pass

### Task 12: Contract tests for errors package

Создать контрактные тесты для пакета `goga/codemanifest/errors`.

- [ ] Create test file `tests/test_errors.py`
- [ ] Test facade availability: `from goga.codemanifest.errors import BaseCodemanifestError, ManifestParseError, ManifestRuleError, ProjectRuleError`
- [ ] Test BaseCodemanifestError: inherits Exception, message in args, message property
- [ ] Test ManifestParseError: inherits BaseCodemanifestError, filepath property
- [ ] Test ManifestRuleError: inherits BaseCodemanifestError, rule/document/node properties, __str__ format with Rule, Path, Node
- [ ] Test ProjectRuleError: inherits BaseCodemanifestError, rule property, document/node accept None, __str__ format with None handling
- [ ] Run validation: `pytest tests/test_errors.py -v`

---

### Package: `goga/codemanifest/rules`

### Task 13: Rules — Infrastructure and DocumentRule base class

Создать базовый класс `DocumentRule` в `goga/codemanifest/rules/document.py`.

Контракт:
- Конструктор `DocumentRule(name: str)`
- Свойство `name -> str`
- Метод `check(node: DocumentNode) -> errors:list[CodemanifestRuleError]`

Imports: `DocumentNode` from `goga.codemanifest.nodes`, `CodemanifestRuleError` from `goga.codemanifest.errors`.

Annotations: python >=3.10.

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them.**

- [ ] Implement `DocumentRule` class in `goga/codemanifest/rules/document.py`
- [ ] Constructor stores `name`, method `check` raises NotImplementedError (abstract base)
- [ ] Update `goga/codemanifest/rules/__init__.py` to export `DocumentRule`
- [ ] Verify facade: `python -c "from goga.codemanifest.rules import DocumentRule"`
- [ ] Run existing tests to verify no regressions: `pytest tests/ -x`
- [ ] If any tests fail, fix the code written in this task (not test code) and re-run tests until they pass

### Task 14: Rules — Implement DocumentRule mutations (ImportsCanNotBeEmptyRule, ImportHasTypeRule, ImportHasValidFromPathRule)

Реализовать 3 правила в `goga/codemanifest/rules/document.py`. Все наследуются от `DocumentRule`.

**ImportsCanNotBeEmptyRule(name: str = 'imports_can_not_be_empty')**:
- Проверяет что `ImportsNode.items` не пустой список

**ImportHasTypeRule(name: str = 'import_has_type')**:
- Проверяет что каждый `ImportItemNode.type_name` не пустой set

**ImportHasValidFromPathRule(name: str = 'import_has_valid_from_path')**:
- Проверяет: from_path не пустой, путь существует на ФС, путь не выходит за пределы CWD

Imports: `DocumentNode`, `DocumentRoot` from nodes, `CodemanifestRuleError` from errors.

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them.**

- [ ] Implement `ImportsCanNotBeEmptyRule` — check that `node.root.header.imports.items` is not empty
- [ ] Implement `ImportHasTypeRule` — check each `ImportItemNode.type_name` is not empty
- [ ] Implement `ImportHasValidFromPathRule` — check from_path is non-empty, exists on filesystem, does not escape CWD (use `os.path` or `pathlib`)
- [ ] Each rule returns list of `CodemanifestRuleError` (empty if no violations)
- [ ] Update `__init__.py` to export all 3 rules
- [ ] Verify facade: `python -c "from goga.codemanifest.rules import ImportsCanNotBeEmptyRule, ImportHasTypeRule, ImportHasValidFromPathRule"`
- [ ] Run existing tests to verify no regressions: `pytest tests/ -x`
- [ ] If any tests fail, fix the code written in this task (not test code) and re-run tests until they pass

### Task 15: Rules — Implement ProjectRule base and mutations

Создать `ProjectRule` в `goga/codemanifest/rules/project.py` и его 2 мутации.

**ProjectRule(tree: list[DocumentRoot], name: str)**:
- Свойства: `name -> str`, `tree -> list[DocumentRoot]`
- Метод `check(document: DocumentRoot) -> errors:list[CodemanifestRuleError]`

**ImportsHasNotCyclicalDepsRule(tree: list[DocumentRoot], name: str = 'imports_has_not_cyclical_deps')**:
- Проверяет отсутствие циклических зависимостей: если A импортирует из B и B импортирует из A — ошибка

**AllUsagesIsUsed(tree: list[DocumentRoot], name: str = 'all_usages_is_used')**:
- Проверяет что все usages из header используются хотя бы в одной аннотации (header, entity, method, property)

Imports: `DocumentRoot`, `DocumentNode` from nodes, `CodemanifestRuleError` from errors.

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them.**

- [ ] Implement `ProjectRule` base class with `check` method (raises NotImplementedError)
- [ ] Implement `ImportsHasNotCyclicalDepsRule` — detect circular imports between documents using document tree
- [ ] Implement `AllUsagesIsUsed` — verify each usage name appears in at least one annotation text across the document
- [ ] Update `__init__.py` to export `ProjectRule`, `ImportsHasNotCyclicalDepsRule`, `AllUsagesIsUsed`
- [ ] Verify facade: `python -c "from goga.codemanifest.rules import ProjectRule, ImportsHasNotCyclicalDepsRule, AllUsagesIsUsed"`
- [ ] Run existing tests to verify no regressions: `pytest tests/ -x`
- [ ] If any tests fail, fix the code written in this task (not test code) and re-run tests until they pass

### Task 16: Contract tests for rules package

Создать контрактные тесты для пакета `goga/codemanifest/rules`.

- [ ] Create test file `tests/test_rules.py`
- [ ] Test facade availability for all rule classes
- [ ] Test DocumentRule: name property, check raises NotImplementedError
- [ ] Test ImportsCanNotBeEmptyRule: positive (non-empty imports), negative (empty imports)
- [ ] Test ImportHasTypeRule: positive (has type_name), negative (empty type_name)
- [ ] Test ImportHasValidFromPathRule: positive (valid path), negative (empty/invalid/escaping path)
- [ ] Test ProjectRule: name and tree properties, check raises NotImplementedError
- [ ] Test ImportsHasNotCyclicalDepsRule: positive (no cycles), negative (circular imports between 2 documents)
- [ ] Test AllUsagesIsUsed: positive (all usages referenced), negative (unused usage name)
- [ ] Run validation: `pytest tests/test_rules.py -v`

---

### Package: `goga/codemanifest/visitor`

### Task 17: Visitor — Implement Visitor class

Реализовать `Visitor` в `goga/codemanifest/visitor/visitor.py`.

Контракт:
- Конструктор `Visitor(document: DocumentRoot)`
- Свойство `document -> DocumentRoot`
- Метод `analyze(rules: list[DocumentRule]) -> errors:list[ManifestRuleError]`
  - Применяет все правила к документу
  - Собирает все ошибки из всех правил в один список

Imports: `DocumentRoot` from nodes, `CodemanifestParseError`, `ManifestRuleError` from errors, `DocumentRule` from rules.

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them.**

- [ ] Implement `Visitor` class in `goga/codemanifest/visitor/visitor.py`
- [ ] Constructor stores `document`
- [ ] `analyze` iterates over rules, calls each rule's `check` on the document's root node, collects all errors
- [ ] Update `goga/codemanifest/visitor/__init__.py` to export `Visitor`
- [ ] Verify facade: `python -c "from goga.codemanifest.visitor import Visitor"`
- [ ] Run existing tests to verify no regressions: `pytest tests/ -x`
- [ ] If any tests fail, fix the code written in this task (not test code) and re-run tests until they pass

### Task 18: Contract tests for visitor package

Создать контрактные тесты для пакета `goga/codemanifest/visitor`.

- [ ] Create test file `tests/test_visitor.py`
- [ ] Test facade availability: `from goga.codemanifest.visitor import Visitor`
- [ ] Test Visitor: document property stores the provided DocumentRoot
- [ ] Test analyze: with no rules returns empty errors list
- [ ] Test analyze: with passing rules returns empty errors list
- [ ] Test analyze: with failing rules returns ManifestRuleError instances
- [ ] Test analyze: multiple rules aggregate all errors
- [ ] Run validation: `pytest tests/test_visitor.py -v`

---

### Package: `goga/codemanifest/analyzer`

### Task 19: Analyzer — Implement Analyzer class

Реализовать `Analyzer` в `goga/codemanifest/analyzer/analyzer.py`.

Контракт:
- Конструктор `Analyzer(tree: list[DocumentRoot])`
- Свойство `tree -> list[DocumentRoot]`
- Метод `analyze(rules: list[ProjectRule]) -> errors:list[ProjectRuleError]`
  - Применяет все project-level правила ко всем документам в дереве

Imports: `DocumentRoot` from nodes, `ProjectRuleError`, `ManifestParseError` from errors, `ProjectRule` from rules.

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them.**

- [ ] Implement `Analyzer` class in `goga/codemanifest/analyzer/analyzer.py`
- [ ] Constructor stores `tree`
- [ ] `analyze` iterates over rules and documents, calls each rule's `check` for each document, collects all errors
- [ ] Update `goga/codemanifest/analyzer/__init__.py` to export `Analyzer`
- [ ] Verify facade: `python -c "from goga.codemanifest.analyzer import Analyzer"`
- [ ] Run existing tests to verify no regressions: `pytest tests/ -x`
- [ ] If any tests fail, fix the code written in this task (not test code) and re-run tests until they pass

### Task 20: Contract tests for analyzer package

Создать контрактные тесты для пакета `goga/codemanifest/analyzer`.

- [ ] Create test file `tests/test_analyzer.py`
- [ ] Test facade availability: `from goga.codemanifest.analyzer import Analyzer`
- [ ] Test Analyzer: tree property stores the provided list
- [ ] Test analyze: with no rules returns empty errors list
- [ ] Test analyze: with passing rules returns empty errors list
- [ ] Test analyze: with failing rules returns ProjectRuleError instances
- [ ] Test analyze: multiple rules on multiple documents aggregate all errors
- [ ] Run validation: `pytest tests/test_analyzer.py -v`

---

### Package: `goga/codemanifest/factory`

### Task 21: Factory — Implement Factory class with YAML parsing

Реализовать `Factory` в `goga/codemanifest/factory/factory.py`. Это самый сложный пакет — парсинг YAML CODEMANIFEST в дерево нод.

Контракт:
- Конструктор `Factory(path: str)` — путь до папки с файлом CODEMANIFEST относительно CWD
- Метод `create(parent: Node = None) -> document:DocumentRoot` — создает дерево документа

Usages:
- `dsl` — спецификация DSL (.usages/codemanifest/dsl.md): структура документа, типы, мутации, регистр ключей
- `yaml` — библиотека pyyaml для парсинга

Правила парсинга (из annotations):
- Корень документа → `DocumentRoot`
- Заголовок → `HeaderNode` (imports, usages, annotations)
- Импорты → `ImportsNode` с `ImportItemNode` (парсинг alias через AS)
- Usages → `UsagesNode` с `UsageItemNode` (сборка аннотаций, определение file vs URL)
- Аннотации → `AnnotationsNode` (только строковые представления)
- Тело → `BodyNode` (рутины без properties/methods → `RoutineTypeNode`, сущности → `EntityTypeNode`)
- Колонтитул → `FooterNode`
- Неизвестные ключи в header/footer → `ManifestParseError` (показать все неизвестные ключи сразу)
- Типы значений должны соответствовать DSL спецификации
- Путь в location сущностей — имя файла, преобразуется в относительный путь от CWD

Imports: все типы из `goga.codemanifest.nodes`, `ManifestParseError` из `goga.codemanifest.errors`.

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them.**

- [ ] Implement `Factory` class in `goga/codemanifest/factory/factory.py`
- [ ] Constructor stores `path`
- [ ] Implement `create(parent=None) -> DocumentRoot`:
  - Load and parse YAML from `path/CODEMANIFEST` using pyyaml
  - Parse header section: Imports, Usages, Annotations → build `HeaderNode`
  - Parse import items: handle `AS` alias syntax, create `ImportItemNode` per type
  - Parse usage items: detect file path (`.md` suffix) vs URL (`http://`/`https://` prefix) vs inline text
  - Build `AnnotationsNode` from annotations text
  - Parse body section: identify routines (no properties/methods/mutations but may have annotations) vs entities (has properties/methods or mutations)
  - Build `RoutineTypeNode` and `EntityTypeNode` with correct signatures
  - Transform location filenames to relative paths from CWD
  - Parse footer section → `FooterNode`
  - Validate unknown keys in header/footer → raise `ManifestParseError` with all unknown keys
  - Set parent reference, populate DocumentRoot with all parsed data
- [ ] Update `goga/codemanifest/factory/__init__.py` to export `Factory`
- [ ] Verify facade: `python -c "from goga.codemanifest.factory import Factory"`
- [ ] Run existing tests to verify no regressions: `pytest tests/ -x`
- [ ] If any tests fail, fix the code written in this task (not test code) and re-run tests until they pass

### Task 22: Contract tests for factory package

Создать контрактные тесты для пакета `goga/codemanifest/factory`. Тесты должны проверять парсинг с разной глубиной и содержимым.

Annotations требования к тестированию:
- Деревья не меньше 3 уровней в глубину
- Разное содержимое манифест файлов (с/без необязательных ключей)
- Парсинг алиасов во всех негативных кейсах (нет пробела, маленькие буквы)
- Регистр ключей
- Все виды нод в полной цепочке
- Рутины vs сущности по признакам (properties/methods/mutations) — если нет свойств и методов но есть мутации — это сущность
- Наполнение каждого свойства ноды

- [ ] Create test file `tests/test_factory.py`
- [ ] Create test fixtures: sample CODEMANIFEST YAML files at different depths (1, 2, 3 levels)
- [ ] Test facade availability: `from goga.codemanifest.factory import Factory`
- [ ] Test basic parsing: Factory creates DocumentRoot with correct header, body, footer
- [ ] Test imports parsing: ImportItemNode with alias (AS syntax), without alias
- [ ] Test alias edge cases: missing space, lowercase "as", "As" — all should parse or raise appropriate error
- [ ] Test usages parsing: file path (.md suffix), URL (http/https prefix), inline text
- [ ] Test annotations: string-only annotations, filepath vs URL detection
- [ ] Test body parsing: routines (no properties/methods) vs entities (has properties/methods)
- [ ] Test entity with mutations but no properties/methods — should be EntityTypeNode not RoutineTypeNode
- [ ] Test footer parsing: architector, created_at, description
- [ ] Test key case sensitivity: wrong case should raise ManifestParseError
- [ ] Test unknown keys in header/footer → ManifestParseError with all unknown keys listed
- [ ] Test deep hierarchy (3+ levels): nested CODEMANIFEST files with parent-child relationships
- [ ] Test location transformation: filename converted to relative path from CWD
- [ ] Test all node properties are populated correctly
- [ ] Run validation: `pytest tests/test_factory.py -v`

---

### Package: `goga/codemanifest` (root)

### Task 23: Codemanifest root — Implement Project class

Реализовать `Project` в `goga/codemanifest/project.py`. Это фасадный класс, объединяющий factory, visitor, analyzer.

Контракт:
- Конструктор `Project(path: str)` — путь для загрузки дерева манифестов
- Свойство `tree -> list[DocumentRoot]` — Дерево документов (вершины графа)
- Свойство `errors -> list[ProjectRuleError | ManifestRuleError]` — Список ошибок после анализа
- Метод `load()` — Загружает дерево по указанному пути

Алгоритм load():
1. Рекурсивно обойти каждую директорию
2. Обнаружить CODEMANIFEST → создать документ через factory
3. Добавить вершину в tree (верхний уровень) или ребенка к родителю
4. Анализ документа через visitor (правила: ImportsCanNotBeEmptyRule, ImportHasTypeRule, ImportHasValidFromPathRule)
5. Применить глобальный анализ через analyzer (правила: ImportsHasNotCyclicalDepsRule, AllUsagesIsUsed)

Imports:
- `DocumentRoot` from nodes
- `ImportsCanNotBeEmptyRule`, `ImportHasTypeRule`, `ImportHasValidFromPathRule`, `ImportsHasNotCyclicalDepsRule`, `AllUsagesIsUsed` from rules
- `ProjectRuleError`, `ManifestRuleError` from errors
- `Factory` from factory
- `Visitor` from visitor
- `Analyzer` from analyzer

Usages: nodes API, factory API, visitor API, analyzer API.

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them.**

- [ ] Implement `Project` class in `goga/codemanifest/project.py`
- [ ] Constructor stores `path`, initializes `tree=[]`, `errors=[]`
- [ ] Implement `load()`:
  - Recursively walk directories from `path`
  - For each CODEMANIFEST found: use Factory to create DocumentRoot
  - Top-level documents → append to `self.tree`
  - Nested documents → add as children to parent DocumentRoot
  - For each document: create Visitor, apply document rules (ImportsCanNotBeEmptyRule, ImportHasTypeRule, ImportHasValidFromPathRule), collect errors
  - After all documents loaded: create Analyzer with tree, apply project rules (ImportsHasNotCyclicalDepsRule, AllUsagesIsUsed), collect errors
  - Store all errors in `self.errors`
- [ ] Update `goga/codemanifest/__init__.py` to export `Project`
- [ ] Verify facade: `python -c "from goga.codemanifest import Project"`
- [ ] Run existing tests to verify no regressions: `pytest tests/ -x`
- [ ] If any tests fail, fix the code written in this task (not test code) and re-run tests until they pass

### Task 24: Contract tests for codemanifest root package

Создать контрактные тесты для корневого пакета `goga.codemanifest`.

- [ ] Create test file `tests/test_codemanifest_project.py`
- [ ] Test facade availability: `from goga.codemanifest import Project`
- [ ] Test Project: path property, tree=[], errors=[] initially
- [ ] Test load() with empty directory: tree=[], errors=[]
- [ ] Test load() with single CODEMANIFEST: tree has 1 root, no errors if valid
- [ ] Test load() with nested CODEMANIFEST files (3+ levels): tree with parent-child hierarchy
- [ ] Test load() detects document-level rule violations: errors contain ManifestRuleError
- [ ] Test load() detects project-level rule violations: errors contain ProjectRuleError
- [ ] Test load() accumulates errors from both visitor and analyzer
- [ ] Run validation: `pytest tests/test_codemanifest_project.py -v`

---

## Validation Commands

- `python -c "from goga.codemanifest.nodes import Node, DocumentRoot, DocumentNode, AnnotationsNode, HeaderNode, ImportsNode, ImportItemNode, UsagesNode, UsageItemNode, BodyNode, RoutineTypeNode, EntityTypeNode, MethodNode, PropertyNode, FooterNode"`: Nodes facade availability
- `python -c "from goga.codemanifest.errors import BaseCodemanifestError, ManifestParseError, ManifestRuleError, ProjectRuleError"`: Errors facade availability
- `python -c "from goga.codemanifest.rules import DocumentRule, ImportsCanNotBeEmptyRule, ImportHasTypeRule, ImportHasValidFromPathRule, ProjectRule, ImportsHasNotCyclicalDepsRule, AllUsagesIsUsed"`: Rules facade availability
- `python -c "from goga.codemanifest.visitor import Visitor"`: Visitor facade availability
- `python -c "from goga.codemanifest.analyzer import Analyzer"`: Analyzer facade availability
- `python -c "from goga.codemanifest.factory import Factory"`: Factory facade availability
- `python -c "from goga.codemanifest import Project"`: Root facade availability
- `pytest tests/ -x`: Run all tests
- `ruff check goga/`: Lint check
- `pytest tests/ -v --tb=short`: Run all tests with verbose output

---

## Done Criteria

- [ ] Every contract entity is implemented in the correct `location`
- [ ] Every contract entity is available from the package facade
- [ ] Properties and methods match the declared API
- [ ] Descriptions are reflected in behavior
- [ ] Contract dependencies are respected
- [ ] Contract tests cover facade, API, and behavior for all 7 packages
- [ ] No package boundary has been expanded
- [ ] No `CODEMANIFEST` files were modified (read-only contract)
- [ ] All validation commands pass
- [ ] Assumptions and open questions are explicitly documented
- [ ] Python >=3.10 compatibility maintained
- [ ] All mutations implemented through Python inheritance
- [ ] All default values match contract specifications
- [ ] ManifestRuleError and ProjectRuleError string formats match specifications