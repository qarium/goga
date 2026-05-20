# Форматирование YAML

Сделать из python объекта yaml строку с учетом форматирования.

```python
yaml.dump(data, sort_keys=False, default_flow_style=False, allow_unicode=True, indent=2)
```

indent: количество отступов
sort_keys: используется только для python 3.7 и выше, сохраняет порядок ключей
default_flow_style: заменяет компактный вид [...] на классические списки с дефисом
allow_unicode: позволяет выводить Unicode-символы (например, кириллицу) напрямую, а не кодами
