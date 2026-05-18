# Правила валидации аннотаций

Область: правила, проверяющие корректность ссылок в аннотациях CODEMANIFEST.
Аудитория: потребители системы правил, нуждающиеся в валидации аннотаций.

## AnnotationLinksExists

Проверяет, что все ссылки в обратных кавычках внутри аннотаций указывают на существующие сущности документа.

```python
from goga.ast.rules.document.annotations import AnnotationLinksExists

rule = AnnotationLinksExists()
```

Ссылка считается валидной, если она совпадает хотя бы с одним из:
- именем типа или алиасом из `Imports`
- именем практики из `Usages`
- именем entity или routine в теле документа
- параметром в сигнатуре (для EntityTypeNode, RoutineTypeNode, MethodNode)

Проверяются аннотации в:
- `HeaderNode` (глобальные аннотации)
- `UsageItemNode` (практики)
- `EntityTypeNode`, `RoutineTypeNode` (типы)
- `MethodNode`, `PropertyNode` (методы и свойства)

## Формат ошибок

При обнаружении несуществующей ссылки:
```
Link `{link}` in {context} annotation does not match any import, usage, entity, routine, or signature parameter
```
