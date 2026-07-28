# Project layout — `.swax/` directory and spec copying

## Предметная область

Шаблоны управления файловой структурой проекта Swax. Целевая аудитория: cell `applications/init/` (создаёт структуру и копирует спецификации после клонирования).

Структура проекта Swax на файловой системе:
```
<project_root>/
├── .swax/
│   ├── config.yml          # создастся через save_config
│   └── traceability.yml    # создастся позже через save_traceability
└── <specs.location>/       # сюда попадут спецификации через copy_specs
    └── *.yaml | *.json
```

---

## Гарантия каталога `.swax/`

Вызывать перед каждой записью в `.swax/` — idempotent:

```python
from pathlib import Path

from swax.fs import ensure_swax_dir

def write_config(project_root: Path) -> Path:
    swax_dir = ensure_swax_dir(project_root)
    config_path = swax_dir / "config.yml"
    # save_config(config, config_path) — делегируется cell `config/`
    return config_path
```

`ensure_swax_dir` создаёт `.swax/` с parents=True, exist_ok=True — безопасно вызывать повторно.

---

## Копирование спецификаций

После клонирования репозитория через `clone_specs` (cell `git/`) спецификации нужно перенести в локальный путь проекта. Путь назначения берётся из `SpecsConfig.location`:

```python
from pathlib import Path

from swax.fs import copy_specs

def install_specs(specs_in_clone: Path, download_path: Path) -> None:
    copy_specs(source=specs_in_clone, destination=download_path)
```

Соглашения потребителя:
- `source` — путь, yields из `clone_specs` (временный каталог клонирования).
- `destination` — локальный путь из `SpecsConfig.location`. Cell `fs/` создаёт родительские каталоги при необходимости.
- Повторный запуск `init` перезаписывает существующие файлы (обновление локальных спецификаций).
