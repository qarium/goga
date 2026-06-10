Extracting the contract from a JavaScript module facade

```python
from goga.contract.javascript import javascript_contract

result = javascript_contract("path/to/js/module")
# result: list[goga.contract.EntityContract | goga.contract.RoutineContract]
```