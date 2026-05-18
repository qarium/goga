# План: `import-is-used-mutation-check`

## Цель

Расширить правило `ImportIsUsed` новым регионом поиска использования импортированных типов — мутациями сущностей (`body[*].mutations`). После реализации тип, использованный как базовый тип мутации сущности, не должен помечаться как неиспользованный импорт.

Основные разрывы между контрактом и кодом:
- отсутствует метод `_collect_mutation_names` в `ImportIsUsed`
- `_check_type_item` не проверяет вхождение типа в мутации
- `check()` не собирает и не передаёт `mutation_names`
- `.usages/import_rules.md` не упоминает мутации для `ImportIsUsed`

## Контекст

### Поверхность контракта

**Сущность: `DocumentRule::ImportIsUsed`**
- Тип: `class` (мутация `DocumentRule`)
- Объявленный `location`: `rules.py`
- Обязанность фасада: должна быть импортируема из `goga.ast.rules.document.imports` и `goga.ast.rules`
- Мутации: `DocumentRule::ImportIsUsed`
- Свойства: нет
- Методы:
  - `check(node: DocumentNode) -> list[DocumentRuleError]` — проверяет что каждый импортированный тип/практика используется в документе
- Семантические требования из описаний:
  - Тип считается использованным если он найден хотя бы в одном из: аннотации, сигнатуры, мутации (`body[*].mutations`), встраивания, типы свойств
  - Практики (usages) проверяются только в аннотациях, НЕ в сигнатурах и мутациях
  - Мутации включают embedded сущности
  - `entity.mutations` имеет тип `list[tuple[str, str]]` — первый элемент кортежа — имя базового типа мутации
- Импортированные зависимости: `DocumentRule` (из `goga/ast/rules/base`), `ImportsNode`, `ImportTypeItemNode`, `ImportUsageItemNode` (из `goga/ast/nodes`)
- Контекст аннотаций: `conventions` — Python 3.10+, dataclasses kw_only, относительные импорты, pytest

**Сущность: `signature_contains_type_name`**
- Тип: `function`
- Объявленный `location`: `tools.py`
- Без изменений — используется как есть для проверки вхождений в сигнатуры и типы свойств

### Реэкспорты

Нет новых реэкспортов. Все существующие реэкспорты фасада остаются без изменений.

### Контекст Usages

- `conventions`: `.goga/usages/development/conventions.md` — Python 3.10+, pytest, ruff, dataclasses kw_only, относительные импорты. Применяется глобально ко всем правилам ячейки.

### Импортированные Usages

Нет.

### Локальные Usages

- Путь к файлу: `.usages/import_rules.md`
- Функциональная категория: документация правил валидации импортов для потребителей
- Статус: расширяет существующий
- Связанные сущности: `ImportIsUsed`
- Описание: добавить мутации (`body[*].mutations`) в описание мест, где импортированный тип считается использованным
- Ссылка на задачу создания: Task 2

### Внешние зависимости

- pytest >= 8.0 — тестирование
- ruff >= 0.15.0 — линтинг и форматирование

## Факты

- `EntityTypeNode.mutations` имеет тип `list[tuple[str, str]]` (проверено в `goga/ast/nodes/body.py:35`)
- `_mutation_path` (второй элемент кортежа) игнорируется — для проверки использования достаточно имени базового типа
- Embedded сущности включаются в обход мутаций — `_collect_mutation_names` не фильтрует по `entity.embedded`
- Практики (usages) НЕ проверяются в мутациях — `_check_usage_item` остаётся без изменений
- Новый метод следует паттерну `_collect_property_types` — простой обход с возвратом `set[str]`
- Существующие тесты расположены в `tests/goga/ast/rules/document/imports/test_document.py`, класс `TestImportIsUsed`

## Анализ разрывов

- Отсутствующие методы контракта: `_collect_mutation_names` не существует — нужно создать
- Отсутствующие параметры: `_check_type_item` не принимает `mutation_names` — нужно добавить параметр
- Отсутствующая передача: `check()` не вызывает `_collect_mutation_names` и не передаёт `mutation_names` в `_check_type_item`
- Несоответствие документации: `.usages/import_rules.md` не упоминает мутации для `ImportIsUsed`
- Разрывы в тестовом покрытии: отсутствуют тесты для 6 сценариев использования мутаций

---

## Tasks

> **Правило упорядочивания по пакетам**: задачи кодирования каждого пакета завершаются перед началом следующего. Внутри каждой задачи кодирования контрактные тесты пишутся первыми (рабочий процесс TDD).

### Task 1: Добавить проверку использования типов в мутациях для `ImportIsUsed` (TDD кодирование)

Расширить правило `ImportIsUsed` новым регионом поиска: мутации сущностей (`body[*].mutations`). Необходимо добавить метод `_collect_mutation_names`, модифицировать `_check_type_item` и `check()`.

**Сущности контракта, покрываемые задачей:** `DocumentRule::ImportIsUsed`

**Целевые файлы:**
- `goga/ast/rules/document/imports/rules.py` — класс `ImportIsUsed`
- `tests/goga/ast/rules/document/imports/test_document.py` — класс `TestImportIsUsed`

**Usages, релевантные для этой задачи:**
- `conventions`: Python 3.10+, dataclasses kw_only, относительные импорты, pytest для тестирования

**КРИТИЧЕСКИ: файлы `CODEMANIFEST` — определения контракта только для чтения. НЕ изменяйте их. Если реализация не соответствует контракту, исправляйте реализацию — никогда не исправляйте контракт.**

**Диаграмма взаимодействия (из дизайн-документа):**

```
                    ImportIsUsed.check(node)
                           |
          +----------------+----------------+
          |                |                |
  _collect_links()  _collect_signatures()  _collect_property_types()
          |                |                |
          |                |                |
          +----------------+----------------+
                           |
                  _collect_mutation_names()   <- НОВОЕ
                           |
                           v
                  _check_type_item() / _check_usage_item()
                           |
                    +------+------+
                    |             |
               Type items    Usage items
                    |             |
         Проверка по всем    Проверка только
         коллекциям:         по all_links:
         - all_links
         - embedded_names
         - all_signatures
         - property_types
         - mutation_names  <- НОВОЕ
```

**Алгоритм `_collect_mutation_names` (новый метод):**

```
1. types = empty set of str
2. FOR each entity IN node.root.body.entities:
   - FOR each (mutation_name, _) IN entity.mutations:
     - types.add(mutation_name)
3. RETURN types
```

**Алгоритм `_check_type_item` (изменённый метод):**

```
1. names = [alias] if alias else list(type_name)
2. FOR each name IN names:
   a. IF name IN all_links -> CONTINUE
   b. IF name IN embedded_names -> CONTINUE
   c. IF signature_contains_type_name(sig, name) for any sig -> CONTINUE
   d. IF signature_contains_type_name(pt, name) for any property_type -> CONTINUE
   e. IF name IN mutation_names -> CONTINUE  <- НОВОЕ
   f. ERROR: type unused
3. RETURN errors
```

- [x] **ШАГ 0 (ОБЪЯВЛЕНИЕ)**: Объявить работу над задачей — расширение `ImportIsUsed` проверкой мутаций
- [x] **ШАГ 1 (КОНТРАКТНЫЕ ТЕСТЫ)**: Написать контрактные тесты в классе `TestImportIsUsed` в файле `tests/goga/ast/rules/document/imports/test_document.py`:
  - `test_type_used_in_mutation_base` — тип, использованный как базовый тип мутации, не помечается как неиспользованный.
    Setup: `ImportTypeItemNode(type_name={"MyType"}, from_path="bar")`, `EntityTypeNode(name="MutatedEntity", signature="()", mutations=[("MyType", "bar")])`.
    Assert: `rule.check(node) == []`
  - `test_type_used_in_mutation_of_embedded_entity` — мутации embedded сущностей учитываются.
    Setup: `ImportTypeItemNode(type_name={"BaseType"}, from_path="bar")`, `EntityTypeNode(name="EmbeddedEntity", signature="()", embedded=True, mutations=[("BaseType", "bar")])`.
    Assert: `rule.check(node) == []`
  - `test_type_used_in_multi_level_mutation` — многоуровневые мутации `A::B::Cls`.
    Setup: `ImportTypeItemNode(type_name={"TypeA"}, from_path="bar")`, `EntityTypeNode(name="Cls", signature="()", mutations=[("TypeA", "bar"), ("TypeB", "baz")])`.
    Assert: `rule.check(node) == []`
  - `test_type_used_with_alias_in_mutation` — alias корректно работает для мутаций.
    Setup: `ImportTypeItemNode(type_name={"OriginalType"}, from_path="bar", alias="Alias")`, `EntityTypeNode(name="Cls", signature="()", mutations=[("Alias", "bar")])`.
    Assert: `rule.check(node) == []`
  - (Контрактные тесты ожидаемо падают на этом этапе)
- [x] **ШАГ 2 (РЕАЛИЗАЦИЯ)**: В файле `goga/ast/rules/document/imports/rules.py`:
  - Добавить метод `_collect_mutation_names(self, node: DocumentNode) -> set[str]`:
    - Инициализировать `types: set[str] = set()`
    - Обойти `node.root.body.entities`
    - Для каждой сущности обойти `entity.mutations` — извлечь `mutation_name` (первый элемент кортежа), добавить в `types`
    - Вернуть `types`
  - Добавить параметр `mutation_names: set[str] | None = None` в сигнатуру `_check_type_item` после `property_types`
  - Добавить проверку `if mutation_names and name in mutation_names: continue` после проверки `property_types` и перед генерацией ошибки
  - В методе `check()`:
    - После `embedded_names` добавить: `mutation_names = self._collect_mutation_names(node)`
    - Передать `mutation_names` в вызов `_check_type_item`
- [x] **ШАГ 3 (ВЕРИФИКАЦИЯ ИНТЕРФЕЙСОВ)**: Запустить контрактные тесты: `python -m pytest tests/goga/ast/rules/document/imports/test_document.py::TestImportIsUsed -v` — все 4 контрактных теста должны пройти
- [x] **ШАГ 4 (ЛОГИЧЕСКИЕ ТЕСТЫ)**: Написать логические тесты в классе `TestImportIsUsed`:
  - `test_type_unused_despite_other_mutations` — наличие мутаций с другими типами не маскирует неиспользованный импорт.
    Setup: `ImportTypeItemNode(type_name={"UnusedType"}, from_path="bar")`, `EntityTypeNode(name="Cls", signature="()", mutations=[("OtherType", "baz")])`.
    Assert: `len(errors) == 1`, `"not used" in errors[0].message.lower()`
  - `test_entity_with_empty_mutations` — пустой список мутаций не маскирует неиспользованные импорты.
    Setup: `ImportTypeItemNode(type_name={"UnusedType"}, from_path="bar")`, `EntityTypeNode(name="Entity", signature="()", mutations=[])`.
    Assert: `len(errors) == 1`
  - `test_no_entities_no_errors_from_mutations` — отсутствие сущностей (только routines) не влияет на работу.
    Setup: `ImportTypeItemNode(type_name={"UnusedType"}, from_path="bar")`, body без entities.
    Assert: `len(errors) == 1`
- [x] **ШАГ 5 (ОТЛАДКА)**: Запустить все тесты: `python -m pytest tests/goga/ast/rules/document/imports/test_document.py -v` — исправлять код реализации, пока все тесты не пройдут (НЕ исправлять тестовый код)
- [x] **ШАГ 6 (ПЕРЕПРОВЕРКА КОНТРАКТА)**: Проверить что:
  - `_collect_mutation_names` возвращает `set[str]` имён базовых типов мутаций
  - `_check_type_item` принимает `mutation_names` и проверяет `name in mutation_names`
  - `check()` вызывает `_collect_mutation_names` и передаёт результат в `_check_type_item`
  - `_check_usage_item` не изменён — практики не проверяются в мутациях
  - Embedded сущности включены в обход мутаций
- [x] **ШАГ 7 (ЛИНТ)**: `python -m ruff check goga/ast/rules/document/imports/rules.py tests/goga/ast/rules/document/imports/test_document.py --fix` — исправить форматирование при необходимости
- [x] **ШАГ 8 (ЗАВЕРШЕНИЕ)**: Отметить чекбоксы как выполненные

### Task 2: Обновить `.usages/import_rules.md` — добавить мутации в описание `ImportIsUsed` (инфраструктура)

Обновить документацию практики `import_rules`, добавив мутации (`body[*].mutations`) в список мест, где импортированный тип считается использованным.

**Usages, релевантные для этой задачи:**
- `conventions`: структура документации практик

**КРИТИЧЕСКИ: файлы `CODEMANIFEST` — определения контракта только для чтения. НЕ изменяйте их. Если реализация не соответствует контракту, исправляйте реализацию — никогда не исправляйте контракт.**

- [x] В файле `goga/ast/rules/document/imports/.usages/import_rules.md` обновить секцию `### ImportIsUsed`:
  - Добавить пункт "в мутациях сущностей (`body[*].mutations`)" в список мест использования типа
  - Обновить описание: "Каждый импортированный тип или практика используется хотя бы в одном месте документа: в аннотациях (заголовок, практики, типы, методы, свойства), в сигнатурах (entities, routines, methods) — только для типов, в мутациях сущностей (body[*].mutations) — только для типов"
- [x] Проверить что файл корректно отображается: `cat goga/ast/rules/document/imports/.usages/import_rules.md`

---

## Команды валидации

- `python -m pytest tests/goga/ast/rules/document/imports/test_document.py -v`: Запустить все тесты ячейки imports
- `python -m pytest tests/goga/ast/rules/document/imports/test_document.py::TestImportIsUsed -v`: Запустить тесты ImportIsUsed
- `python -m ruff check goga/ast/rules/document/imports/ --fix`: Линтинг кода реализации
- `python -m ruff check tests/goga/ast/rules/document/imports/ --fix`: Линтинг тестов
- `python -c "from goga.ast.rules.document.imports import ImportIsUsed; print('facade ok')"`: Проверить доступность фасада

---

## Критерии завершения

- [x] Метод `_collect_mutation_names` реализован и возвращает `set[str]` имён базовых типов мутаций
- [x] Метод `_check_type_item` принимает `mutation_names` и проверяет `name in mutation_names`
- [x] Метод `check()` вызывает `_collect_mutation_names` и передаёт `mutation_names` в `_check_type_item`
- [x] `_check_usage_item` не изменён — практики не проверяются в мутациях
- [x] Embedded сущности включены в обход мутаций
- [x] 7 новых тестов (4 позитивных + 3 негативных/краевых) добавлены в `TestImportIsUsed`
- [x] `.usages/import_rules.md` обновлён — мутации добавлены в описание `ImportIsUsed`
- [x] Все существующие тесты продолжают проходить
- [x] Файлы `CODEMANIFEST` не были изменены (контракт только для чтения)
- [x] Все команды валидации проходят
