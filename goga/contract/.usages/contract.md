Диспетчер контрактных операций по языку реализации.

```python
from goga.contract import contract

result = contract("python", "path/to/cell")
# result: list[goga.contract.EntityContract | goga.contract.RoutineContract]
```

Язык передаётся строкой: "python", "golang". При неизвестном языке — ValueError.