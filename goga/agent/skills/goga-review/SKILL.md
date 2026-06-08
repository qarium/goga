---
name: goga-review
description: Диспетчер специализированных review skills
---
Вы — dispatcher-команда для запуска специализированных review skills. Вы определяете тип ревью и вызываете соответствующий скилл.

## Диспетчеризация

Аргументы: $ARGUMENTS

### Определение типа ревью

1. **Аргументы содержат путь** — извлеките тип из пути:
   - Путь содержит `docs/arch/` → **architecture**
   - Путь содержит `docs/design/` → **design**
   - Путь содержит `docs/plans/` → **plan**
   - Путь содержит `docs/tasks/` → **task**
   - Путь не содержит `docs/` (или содержит другое расположение) → **cell**

   Извлеките `<target>` из пути:
   - Для `docs/arch/javascript-contract.md` → `<target>` = `javascript-contract`
   - Для `src/cell/my-cell` → `<target>` = `src/cell/my-cell`
   - Для `my-cell` → `<target>` = `my-cell`

2. **Аргументы пусты** — спросите пользователя через AskUserQuestion:
   - **question**: "Что вы хотите проверить?"
   - **header**: "Тип ревью"
   - **multiSelect**: false
   - **options**:
     - **label**: "architecture", **description**: "Ревью плана архитектуры из docs/arch/"
     - **label**: "design", **description**: "Ревью дизайн-документа из docs/design/"
     - **label**: "plan", **description**: "Ревью плана реализации из docs/plans/"
     - **label**: "cell", **description**: "Ревью ячейки (CODEMANIFEST и файловой структуры)"
     - **label**: "task", **description**: "Ревью задачи из docs/tasks/"

### Маршрутизация по типу

#### architecture
Проверьте, существует ли `docs/arch/<target>.md`.
1. **Не существует** — остановитесь и сообщите об этом пользователю.
2. **Существует** — используйте **Skill tool** для вызова скилла `goga-review-arch` с `<target>` в качестве аргумента.

#### design
Проверьте, существует ли `docs/design/<target>.md`.
1. **Не существует** — остановитесь и сообщите об этом пользователю.
2. **Существует** — используйте **Skill tool** для вызова скилла `goga-review-design` с `<target>` в качестве аргумента.

#### plan
Проверьте, существует ли `docs/plans/<target>.md`.
1. **Не существует** — остановитесь и сообщите об этом пользователю.
2. **Существует** — используйте **Skill tool** для вызова скилла `goga-review-plan` с `<target>` в качестве аргумента.

#### cell
Проверьте, существует ли директория `<target>` и файл `<target>/CODEMANIFEST`.
1. **Не существует** — остановитесь и сообщите об этом пользователю.
2. **Существует** — используйте **Skill tool** для вызова скилла `goga-review-cell` с `<target>` в качестве аргумента.

#### task
Проверьте, существует ли `docs/tasks/<target>.md`.
1. **Не существует** — остановитесь и сообщите об этом пользователю.
2. **Существует** — используйте **Skill tool** для вызова скилла `goga-review-task` с `<target>` в качестве аргумента.
