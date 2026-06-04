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
- Если пользователь запросил кастомный Dockerfile — создаёт его с `FROM {image}`

### Данные

InitAnswers — контейнер ответов, содержит GogaConfigAnswers с полями:
language, agent, image, env, codemanifest_usages, codemanifest_annotations, dockerfile_path

## Опрос — flow

Опрос Questionnaire.ask_goga_config() проходит в следующем порядке:

1. **language** — выбор языка (python, golang, kotlin, swift, javascript)
2. **convention** — предложение скачать базовую конвенцию для выбранного языка
   - URL: `https://raw.githubusercontent.com/qarium/goga-lang-conventions/refs/heads/0.0.x/{language}/project.md`
   - Идентификатор языка используется напрямую как URL-сегмент (без маппинга)
   - При согласии добавляется `{"conventions": ".goga/usages/conventions.md"}` в codemanifest_usages
3. **codemanifest_usages** — опционально, дополнительные практики
4. **codemanifest_annotations** — опционально
5. **agent** — выбор AI-executor (claude)
6. **image** — Docker-образ: показываются подсказки для языка, дефолт — последний, ввод свободный
   - python: qarium/goga-python-3.10:1.0 .. qarium/goga-python-3.14:1.0
   - golang: qarium/goga-golang-1.23:1.0 .. qarium/goga-golang-1.26:1.0
7. **dockerfile** — опционально, создание кастомного Dockerfile
   - При согласии запрашивается путь (дефолт: "Dockerfile")
   - Dockerfile содержит `FROM {image}`
8. **env** — сначала предлагаются env-ключи по выбранному агенту (из `agent_env_defaults`):
   - claude: ANTHROPIC_DEFAULT_HAIKU_MODEL, ANTHROPIC_DEFAULT_SONNET_MODEL, ANTHROPIC_DEFAULT_OPUS_MODEL, ANTHROPIC_BASE_URL
   - Пользователь вводит значения для предложенных ключей
   - Затем опционально — произвольные пары ключ-значение
