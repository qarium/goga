Dispatcher of contract operations by implementation language.

```python
from goga.contract import contract

result = contract("python", "path/to/cell")
# result: list[goga.contract.EntityContract | goga.contract.RoutineContract]
```

The language is passed as a string: "python", "golang", "javascript", "kotlin", "swift". For an unknown language — ValueError.
