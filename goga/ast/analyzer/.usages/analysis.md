# Анализ дерева документов

Область: глобальный анализ всех документов AST-дерева.
Аудитория: потребители, которым нужно применить правила уровня проекта к загруженному дереву.

## Минимальный пример

```python
from goga.ast.analyzer import Analyzer
from goga.ast.nodes import DocumentRoot

# tree — список DocumentRoot, полученный из Factory или AST
analyzer = Analyzer(tree)
errors = analyzer.analyze(ast_rules)
```

Analyzer принимает:
- `tree` — плоский список всех документов дерева (включая вложенные)
- `rules` — список правил типа `ASTRule`

Для каждого правила вызывается `rule.check(document)` по каждому документу.
Результат — плоский список `ASTRuleError`.

## Использование вместе с Visitor

Analyzer не заменяет Visitor — они работают на разных уровнях:
- `Visitor` — правила одного документа (`DocumentRule`)
- `Analyzer` — правила, требующие доступа ко всему дереву (`ASTRule`)

Типичный порядок: сначала Visitor для каждого документа, затем Analyzer для дерева целиком.
