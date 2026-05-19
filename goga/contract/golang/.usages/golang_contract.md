Извлечение контракта с фасада Go-пакета

```python
from goga.contract.golang import golang_contract

result = golang_contract("path/to/go/package")
# result: list[goga.contract.EntityContract | goga.contract.RoutineContract]
```