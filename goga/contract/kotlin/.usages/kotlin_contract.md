Извлечение контракта с фасада Kotlin-пакета

```python
from goga.contract.kotlin import kotlin_contract

result = kotlin_contract("path/to/kotlin/package")
# result: list[goga.contract.EntityContract | goga.contract.RoutineContract]
```