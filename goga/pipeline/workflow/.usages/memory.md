# memory — авторинг памяти в workflow-файле

`memory` включает участие workflow в памяти проекта: один top-level блок
конфигурации и две per-stage инструкции участия. Документ адресован авторам
workflow-файлов: всё описанное проверяется структурно при парсинге — опечатки,
несоответствия типов и значений отвергаются с читаемой ошибкой.

## Top-level блок `memory:`

| Ключ | Тип | Умолчание | Примечание |
|------|-----|-----------|------------|
| `method` | `reflect` \| `alignment` | `reflect` | селектор словаря инструкций; селектор — сторона goga, в скомпилированный вывод не попадает |
| `path` | str | без суффикса | суффикс внутри фиксированного корня памяти проекта |
| `max_rules` | int >= 1 | `25` | материализуется — опустить нельзя молча |
| `commit` | bool | `false` | материализуется |
| `mode` | `r` \| `w` \| `rw` | `rw` (материализуется) | только при `method: alignment`; при `method: reflect` — структурная ошибка |

Неизвестный ключ — структурная ошибка. Workflow из одного блока `memory:`
валиден (не считается пустым).

## Инструкции блока `stages`

| Инструкция | Допустимый метод | Значение |
|------------|------------------|----------|
| `reflect: {file, mode?}` | `reflect` | `file` обязателен — файл рефлексии стадии (форма пути внутри корня памяти, без ведущего `/`, не абсолютный, без `..`); `mode` опционален (`r`/`w`/`rw`), умолчание `rw` материализуется |
| `memory: <bool>` | `alignment` | `true` — стадия участвует; `false` эквивалентен отсутствию ключа |

Несоответствие метода и инструкции — структурная ошибка: `reflect` допустим
только при reflect-методе, `memory` — только при alignment-методе. Метод
по умолчанию — `reflect`, поэтому инструкция `memory` без блока `memory:`
с явным `method: alignment` — ошибка.

В extend-записи обе инструкции запрещены: участие новой стадии авторится в
блоке `stages` по её имени.

## Минимальные примеры

Reflect-метод (умолчание) — стадии рефлексии в общий файл памяти:

```yaml
memory:
  max_rules: 40
stages:
  brainstorm:
    reflect:
      file: shared.md
  review:
    reflect:
      file: shared.md
      mode: r
```

Alignment-метод — избирательное участие стадий:

```yaml
memory:
  method: alignment
  path: goga-development
  mode: rw
stages:
  brainstorm:
    memory: true
  build:
    memory: true
```

Блок без инструкций — валидная конфигурация (тихий no-op при компиляции).

## Структурные ошибки (полный перечень)

| Авторинг | Ошибка |
|---|---|
| `memory:` не-отображение | non-mapping memory block in workflow |
| неизвестный ключ `memory:` | unknown key in workflow.memory: KEY; valid keys: method, path, max_rules, commit, mode |
| `method` вне {reflect, alignment} | структурная ошибка со списком допустимых |
| `max_rules` не int / < 1 | структурная ошибка |
| `commit`/`memory` не bool | структурная ошибка |
| `mode` вне {r, w, rw} | структурная ошибка со списком допустимых |
| `mode` при `method: reflect` | mode is forbidden in workflow.memory with method: reflect |
| `path`/`reflect.file` плохой формы | структурная ошибка (пустая строка, ведущий `/`, абсолютный путь, `..`) |
| `reflect` не-отображение | non-mapping reflect in workflow.stages.NAME |
| неизвестный ключ `reflect` | unknown key in workflow.stages.NAME.reflect: KEY; valid keys: file, mode |
| `reflect` без `file` | структурная ошибка |
| `reflect` при alignment | reflect is forbidden in workflow.stages.NAME with method: alignment |
| `memory` при reflect | memory is forbidden in workflow.stages.NAME with method: reflect |
| `reflect`/`memory` в extend-записи | reflect/memory is forbidden in workflow.extend.NAME |

## Anti-patterns

- Не авторить `reflect`/`memory` в теле стадии или в теле extend-записи —
  единственная точка авторинга инструкций — блок `stages` workflow-файла
  (ключи в телах стадий отвергаются при компиляции).
- Не рассчитывать на умолчания afm: материализация умолчаний (`mode`,
  `max_rules`, `commit`) — обязательное поведение парсера, а не стилистика.
- Не указывать `mode` в блоке `memory:` при методе по умолчанию — это
  структурная ошибка, а не молчаливое игнорирование.
