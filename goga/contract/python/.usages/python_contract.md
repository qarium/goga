Извлечение контракта с фасада Python-пакета через tree-sitter

```python
from goga.contract.python import python_contract

result = python_contract("path/to/cell")
# result: list[goga.contract.EntityContract | goga.contract.RoutineContract]
```

Парсинг выполняется через tree-sitter без runtime-импорта целевого проекта.
