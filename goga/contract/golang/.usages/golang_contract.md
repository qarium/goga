Extracting the contract from the Go package facade

```python
from goga.contract.golang import golang_contract

result = golang_contract("path/to/go/package")
# result: list[goga.contract.EntityContract | goga.contract.RoutineContract]
```
