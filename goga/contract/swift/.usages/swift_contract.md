Извлечение контракта с фасада Swift-модуля

```python
from goga.contract.swift import swift_contract

result = swift_contract("path/to/swift/module")
# result: list[goga.contract.EntityContract | goga.contract.RoutineContract]
```