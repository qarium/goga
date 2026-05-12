# Загрузка конфигурации проекта

## Назначение

Загружает базовые usages и annotations проекта из конфигурационного файла `.goga.yml` с помощью CLI-команд `goga config`.
Эти настройки задают проектные практики и инструкции, доступные всем CODEMANIFEST файлам.

---

## Поведение

Не пересказывайте содержимое — применяйте загруженные usages и annotations в контексте вызвавшего скилла.

---

## Инструкция

### Шаг 1: Получите базовые usages проекта

Выполните команду `docker run --rm -v .:/project -w /project qarium/goga:latest config codemanifest.usages` чтобы получить базовые usages проекта из секции `codemanifest.usages` в `.goga.yml`.
Это проектные практики, доступные всем CODEMANIFEST файлам.

### Шаг 2: Получите базовые annotations проекта

Выполните команду `docker run --rm -v .:/project -w /project qarium/goga:latest config codemanifest.annotations` чтобы получить базовые annotations проекта — текстовые инструкции
для AI-агента из секции `codemanifest.annotations` в `.goga.yml`.

### Шаг 3: Обработка результата

Если команды вернули ошибку «Option not found» — значит секция `codemanifest` отсутствует в `.goga.yml`, базовые
annotations и usages не заданы, зафиксируйте это как факт.

Если секция `codemanifest` существует:

1. **Прочитайте файлы практик** — для каждого usage из `codemanifest.usages` прочитайте соответствующий md файл.
   Эти практики обязательны для учёта при проектировании всех CODEMANIFEST файлов.

2. **Проанализируйте базовые annotations** — если annotations содержат инструкции влияющие на формирование
   CODEMANIFEST (например требования к структуре, конвенции, ограничения), зафиксируйте их как обязательные
   условия проектирования.

---
