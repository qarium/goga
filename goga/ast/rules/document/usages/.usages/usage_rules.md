# Правила валидации практик (Usages)

Область: правила, проверяющие корректность секции Usages в CODEMANIFEST.
Аудитория: потребители системы правил, нуждающиеся в валидации практик.

## Доступные правила

### AllUsagesIsUsed

Каждая декларированная практика используется хотя бы в одной аннотации документа.

```python
from goga.ast.rules.document.usages import AllUsagesIsUsed
rule = AllUsagesIsUsed()
```

Поиск ведётся в аннотациях: HeaderNode, UsageItemNode, EntityTypeNode, RoutineTypeNode, MethodNode, PropertyNode.

### UsageFilepathExists

Путь к файлу практики:
- строится относительно корня проекта (CWD)
- содержит префикс `.goga/usages/`
- файл существует на файловой системе

```python
from goga.ast.rules.document.usages import UsageFilepathExists
rule = UsageFilepathExists()
```

Inline-практики (annotations.text) и URL-практики (annotations.url) пропускаются.

### UsageUrlIsAccessible

URL-практика отвечает HTTP 200.

```python
from goga.ast.rules.document.usages import UsageUrlIsAccessible
rule = UsageUrlIsAccessible()
```

- используется HEAD-запрос с fallback на GET
- таймаут — 10 секунд
- при сетевой ошибке — ошибка валидации
- Inline и filepath практики пропускаются
- результат проверки URL кэшируется в экземпляре правила: повторная проверка того же URL не выполняет сетевой запрос
- для максимальной эффективности переиспользуйте экземпляр правила между документами (как это делает линтер)

### UsageLinksHasNotConflicts

Имена практик не конфликтуют с:
- именами импортированных типов (конфликт решается через alias)
- именами entity и routine в теле документа

```python
from goga.ast.rules.document.usages import UsageLinksHasNotConflicts
rule = UsageLinksHasNotConflicts()
```

## Пример правильного использования практик

```yaml
Usages:
  conventions: .goga/usages/conventions.md
  pattern: |
    Inline pattern text

Annotations: |
  Use `conventions` for style.
  Use `pattern` for implementation.
```

Обе практики (`conventions`, `pattern`) использованы в аннотациях — правило `AllUsagesIsUsed` соблюдено.
