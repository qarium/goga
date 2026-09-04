# Contract — API

The facade of the domain package **`goga.contract`** — the comparison of CODEMANIFEST declarations with the implementation. The per-language extractors live in the nested cells (`goga.contract.python`, `.golang`, `.kotlin`, `.swift`, `.javascript`); the shared contract model in `goga.contract.data`.

The signatures below are the CODEMANIFEST contract of the cell.

```python
contract(lang: str, cell_path: str) -> list[EntityContract | RoutineContract]
```

Parse the cell's `CODEMANIFEST`, extract the implementation surface of `cell_path`'s source files with the `lang` extractor, and return the contract view — one `EntityContract` or `RoutineContract` per declared type, carrying the match between the declaration and the implementation.

```python
BaseContract()
EntityContract(...)   # a declared entity: methods and properties matched against the code
RoutineContract(...)  # a declared routine: the callable signature matched against the code
MethodContract(...)
PropertyContract(...)
```

The contract result types. The per-language entry points are re-exported on the facade:

```python
python_contract(...)      # goga.contract.python
golang_contract(...)      # goga.contract.golang
kotlin_contract(...)      # goga.contract.kotlin
swift_contract(...)       # goga.contract.swift
javascript_contract(...)  # goga.contract.javascript
```

## Example

```python
from goga.contract import contract

for entry in contract("python", "goga/topics"):
    print(entry)
```
