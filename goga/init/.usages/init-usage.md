# Инициализация проекта — goga/init

## Обзор

Пакет `goga.init` предоставляет интерактивную инициализацию проекта goga —
опрос пользователя и создание файлов конфигурации.

## Фасад

Все типы импортируются напрямую из `goga.init`:

```python
from goga.init import InitLogic, Questionnaire, FileGenerator, InitAnswers, GogaConfigAnswers
```

## Использование

### InitLogic — оркестратор

```python
from goga.init import InitLogic, Questionnaire, FileGenerator

questionnaire = Questionnaire()
generator = FileGenerator()
logic = InitLogic(questionnaire=questionnaire, generator=generator)

exit_code = logic.run()
```

### InitLogic.run()

Проводит интерактивный опрос пользователя и создаёт файлы проекта.

**Возвращает:** exit_code (0 — успех, 1 — ошибка)

**Поведение:**
- Создаёт директорию .goga/ если не существует
- Создаёт .goga/config.yml с минимальной конфигурацией
- Если пользователь согласился на скачивание конвенции — скачивает .goga/usages/conventions.md

### Данные

InitAnswers — контейнер ответов, содержит GogaConfigAnswers с полями:
language, agent, image, env, codemanifest_usages, codemanifest_annotations

## Опрос — flow

Опрос Questionnaire.ask_goga_config() проходит в следующем порядке:

1. **language** — выбор языка (python, golang, kotlin, swift, javascript, cpp)
2. **convention** — предложение скачать базовую конвенцию для выбранного языка
   - URL: `https://raw.githubusercontent.com/qarium/goga-lang-conventions/refs/heads/0.0.x/{language}/project.md`
   - Идентификатор языка используется напрямую как URL-сегмент (без маппинга)
   - При согласии добавляется `{"conventions": ".goga/usages/conventions.md"}` в codemanifest_usages
3. **agent** — выбор AI-executor
4. **image** — Docker-образ: показываются подсказки для языка, дефолт — последний, ввод свободный
   - python: qarium/goga-python-3.10:1.0 .. qarium/goga-python-3.14:1.0
   - golang: qarium/goga-golang-1.23:1.0 .. qarium/goga-golang-1.26:1.0
5. **env** — опционально, пары ключ-значение
6. **codemanifest_usages** — опционально, дополнительные практики
7. **codemanifest_annotations** — опционально
