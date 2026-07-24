Working with Contract Data Classes

```python
from goga.contract.data import EntityContract, RoutineContract

# EntityContract — entity contract (class, struct, interface)
entity = EntityContract(name="TypeName", signature="(param: str)", properties=[...], methods=[...])

# RoutineContract — routine contract (function)
routine = RoutineContract(name="function_name", signature="(param: str) -> str")
```
