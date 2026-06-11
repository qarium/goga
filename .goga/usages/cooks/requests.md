# HTTP-запросы с requests

## Library

**requests** — HTTP-библиотека для Python.

Installation: `pip install requests`

**IMPORTANT** — библиотека должна быть добавлена в зависимости проекта.

## Базовые запросы

### GET — скачивание содержимого

```python
import requests

response = requests.get(url, timeout=30)
response.raise_for_status()
content = response.text
```

### HEAD — проверка доступности URL

```python
response = requests.head(url, timeout=5)
response.raise_for_status()
```

### GET с fallback (если HEAD не поддерживается)

```python
try:
    response = requests.head(url, timeout=5)
except requests.exceptions.HTTPError:
    response = requests.get(url, timeout=5)
response.raise_for_status()
```

## Обработка ошибок

```python
import requests

try:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
except requests.exceptions.HTTPError as e:
    # Сервер вернул 4xx/5xx
except requests.exceptions.ConnectionError as e:
    # Ошибка сети (DNS, отказ соединения)
except requests.exceptions.Timeout as e:
    # Таймаут запроса
except requests.exceptions.RequestException as e:
    # Общий catch-all для всех ошибок requests
```

## Ключевые свойства Response

| Свойство | Описание |
|----------|----------|
| `response.status_code` | HTTP-статус (int) |
| `response.text` | Тело ответа как строка (UTF-8 auto-decode) |
| `response.headers` | Заголовки ответа (dict-like) |
| `response.ok` | `True` если статус < 400 |
| `response.raise_for_status()` | Бросает HTTPError если статус >= 400 |

## Anti-patterns

- Не использовать `urllib.request` вместе с `requests` в одном проекте
- Не читать тело ответа через `response.content.decode()` — использовать `response.text`
- Не проверять статус через `if response.status_code == 200` — использовать `response.raise_for_status()`