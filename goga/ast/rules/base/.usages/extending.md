# Создание собственных правил

Область: расширение системы правил через наследование базовых типов.
Аудитория: разработчики, которым нужно добавить новое правило валидации.

## DocumentRule — правило для одного документа

```python
from goga.ast.rules.base import DocumentRule
from goga.ast.errors import DocumentRuleError

class MyCustomRule(DocumentRule):
    def __init__(self, name: str = "my_custom_rule"):
        super().__init__(name)

    def check(self, node):
        errors = []
        # node — DocumentNode, обёртка над DocumentRoot
        # node.root — DocumentRoot документа
        document = node.root

        # Логика проверки...
        if some_violation:
            errors.append(DocumentRuleError(
                message="Description of error",
                rule=self.name,
                document=document,
                node=problematic_node,
            ))

        return errors
```

`check()` принимает `DocumentNode` (обёртка) и возвращает `list[DocumentRuleError]`.
Доступ к документу — через `node.root`.

## ASTRule — правило для всего дерева

```python
from goga.ast.rules.base import ASTRule
from goga.ast.errors import ASTRuleError

class MyGlobalRule(ASTRule):
    def __init__(self, tree, name: str = "my_global_rule"):
        super().__init__(tree, name)

    def check(self, document):
        errors = []
        # document — DocumentRoot, проверяемый в контексте всего дерева
        # self.tree — list[DocumentRoot], всё дерево документов

        # Логика проверки...
        if some_violation:
            errors.append(ASTRuleError(
                message="Description of error",
                rule=self.name,
                document=document,
                node=problematic_node,
            ))

        return errors
```

`check()` вызывается для каждого документа в дереве.
Правило имеет доступ ко всему дереву через `self.tree`.

## Когда выбирать базовый тип

- **DocumentRule** — если правило проверяет один документ изолированно (структура, ключи, локальные ссылки)
- **ASTRule** — если правило требует знания о других документах дерева (циклы, кросс-ссылки, иерархия)
