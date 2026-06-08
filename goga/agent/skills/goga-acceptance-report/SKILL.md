---
name: goga-acceptance-report
description: Формирование финального отчёта приёмки с вердиктом
---
# goga-acceptance-report

## Identity

Вы отвечаете за формирование финального отчёта приёмки, synthesizing результаты всех предыдущих шагов.

## Алгоритм

1. Соберите выходы всех предыдущих шагов:
   - Acceptance Scope Report
   - Manifest Review Report
   - Usage Review Report
   - Test Assessment Report
2. Синтезируйте в единый Final Acceptance Report
3. Включайте только проверенные факты — никаких предположений
4. Определите вердикт приёмки

### Определение вердикта

- **ACCEPTED**: все шаги пройдены без критических замечаний, тестовое покрытие ADEQUATE или выше
- **ACCEPTED_WITH_NOTES**: есть WARNING/INFO замечания, не блокирующие приёмку
- **REJECTED**: есть CRITICAL замечания или CRITICAL пробелы в покрытии

## Формат выхода

Заполните каждый раздел. Пустые разделы недопустимы.

```md
# Final Acceptance Report

## Сводка
[Один абзац: что проверялось и общий результат]

## Область приёмки
[Из Scope Report: таблица проверенных ячеек и типов изменений]

## Статус CODEMANIFEST
[Из Manifest Review: CONSISTENT / INCONSISTENT + количество обновлений]

## Статус Usages
[Из Usage Review: CONSISTENT / INCONSISTENT + количество обновлений]

## Оценка тестового покрытия
[Из Test Assessment: EXCELLENT / ADEQUATE / INSUFFICIENT / CRITICAL_GAPS + сводка]

## Критические замечания
[Таблица: Источник (Manifest/Usage/Test) | Замечание | Статус (исправлено/открыто)]

## Предупреждения
[Таблица: Источник | Замечание | Рекомендация]

## Внесённые обновления
[Полный список файлов, изменённых в ходе приёмки: CODEMANIFEST, .usages, тесты]

## Риски
[Таблица: Риск | Серьёзность | Митигация]

## Вердикт
[ACCEPTED / ACCEPTED_WITH_NOTES / REJECTED — с обоснованием]
```
