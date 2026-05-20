Работа с data-классами контрактов

```python
from goga.contract.data import EntityContract, RoutineContract

# EntityContract — контракт сущности (класс, struct, interface)
entity = EntityContract(
    name="TypeName",
    signature="(param: str)",
    properties=[...],
    methods=[...]
)

# RoutineContract — контракт рутины (функция)
routine = RoutineContract(
    name="function_name",
    signature="(param: str) -> str"
)
```
