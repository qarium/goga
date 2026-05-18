# Реестр правил валидации CODEMANIFEST

Область: обзор всех доступных правил и их分类икация.
Аудитория: потребители, которым нужно подобрать правила для валидации манифеста.

## Два уровня правил

Правила разделены на две категории по области применения:

### DocumentRule — правила одного документа

Применяются через `Visitor` к каждому документу отдельно.

**Импорты:**
- `ImportsCanNotBeEmpty` — блок импортов не может быть пустым
- `ImportsHasOnlyValidKeys` — только ключи Types, Usages, From
- `ImportItemIsValid` — каждый импорт содержит тип или практику
- `ImportUsageExists` — импортируемая практика существует на файловой системе
- `ImportHasValidFromPath` — путь From существует и не выходит за CWD
- `ImportHasNotDuplicate` — нет дубликатов в импортах
- `ImportIsUsed` — каждый импорт используется в документе

**Практики (Usages):**
- `AllUsagesIsUsed` — каждая практика используется в аннотациях
- `UsageFilepathExists` — файл практики существует
- `UsageUrlIsAccessible` — URL практики доступен (HTTP 200)
- `UsageLinksHasNotConflicts` — имена практик не конфликтуют с типами

**Аннотации:**
- `AnnotationLinksExists` — ссылки в аннотациях указывают на существующие сущности

**Структуры:**
- `EntitiesAndRoutinesHasNotConflicts` — имена не конфликтуют с импортами
- `EntityHasOnlyValidKeys` — entity содержит только допустимые ключи
- `RoutineHasOnlyValidKeys` — routine содержит только допустимые ключи
- `SignatureIsValid` — формат сигнатуры `(...) -> ...` или `(...)`
- `ReturnTypeHasLink` — возвращаемый тип имеет семантическую метку
- `LocationIsRequired` — тип содержит location — имя файла с расширением

**Мутации:**
- `MutationExists` — базовый тип мутации существует
- `MutationIsValid` — мутация не ссылается на себя
- `EmbeddedEntityCanNotHasMutations` — встроенная сущность не имеет мутаций

### ASTRule — правила всего дерева

Применяются через `Analyzer` ко всем документам.

- `ImportsHasNotCyclicalDeps` — нет циклических импортов между документами
- `ImportTypeExists` — импортируемый тип существует в указанном документе
- `EmbeddedTypeHasLowLevel` — встроенный тип находится ниже в иерархии

## Вспомогательные типы

- `signature_contains_type_name(signature, type_name) -> bool` — проверяет вхождение имени типа в сигнатуру
