# Форматирование JSON

Сделать из python объекта json строку с учетом форматирования.

```python
json.dumps(data, indent=4, sort_keys=True, ensure_ascii=False)
```

indent: количество отступов
sort_keys: упорядочить ключи словаря по алфавиту
ensure_ascii: отобразить корректно кириллицу или другие спецсимволы
