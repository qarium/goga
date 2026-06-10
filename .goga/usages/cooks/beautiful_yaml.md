# YAML Formatting

Convert a Python object to a YAML string with formatting.

```python
yaml.dump(data, sort_keys=False, default_flow_style=False, allow_unicode=True, indent=2)
```

indent: number of indentation spaces
sort_keys: only used for Python 3.7+, preserves key order
default_flow_style: replaces compact notation `[...]` with classic dash-prefixed lists
allow_unicode: allows outputting Unicode characters (e.g., Cyrillic) directly instead of escape codes
