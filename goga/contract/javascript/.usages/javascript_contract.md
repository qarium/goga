Извлечение контракта с фасада JavaScript-модуля

```python
from goga.contract.javascript import javascript_contract

result = javascript_contract("path/to/js/module")
# result: list[goga.contract.EntityContract | goga.contract.RoutineContract]
```