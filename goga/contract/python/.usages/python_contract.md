Extracting the contract from the Python package facade via tree-sitter

```python
from goga.contract.python import python_contract

result = python_contract("path/to/cell")
# result: list[goga.contract.EntityContract | goga.contract.RoutineContract]
```

Parsing is performed via tree-sitter without runtime import of the target project.
