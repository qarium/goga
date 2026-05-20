Извлечение контракта с фасада Python-пакета

```python
from goga.contract.python import python_contract

result = python_contract("path/to/cell")
# result: list[goga.contract.EntityContract | goga.contract.RoutineContract]
```