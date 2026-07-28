# Project configuration — `.swax/config.yml`

## Предметная область

Шаблоны чтения и записи конфигурации проекта Swax. Целевая аудитория: cell-и `applications/init/` (записывает конфиг после интерактивного опроса) и `applications/discover/` (читает конфиг для путей к спецификациям).

Конфигурация хранится в YAML и описывает git-репозиторий со спецификациями и локальный путь для их сохранения.

---

## Модель

```python
from swax.config import Config, GitConfig, SpecsConfig

config = Config(
    git=GitConfig(url="https://github.com/org/api-specs.git", location="specs/"),
    specs=SpecsConfig(type="openapi", location="specs/"),
)
```

Поле `specs.type` — объявление формата (`"swagger"` или `"openapi"`); реальный парсер (Prance) определяет версию автоматически, поэтому значение носит информационный характер.

---

## Сохранение после инициализации

`run_init` создаёт конфигурацию из ответов пользователя и сохраняет её:

```python
from pathlib import Path

from swax.config import Config, GitConfig, SpecsConfig, save_config

def persist_config(repo_url: str, specs_location: str, download_path: Path, project_root: Path) -> None:
    config = Config(
        git=GitConfig(url=repo_url, location=specs_location),
        specs=SpecsConfig(type="openapi", location=str(download_path)),
    )
    save_config(config, project_root / ".swax" / "config.yml")
```

`save_config` создаёт родительские каталоги и пишет детерминированный YAML — diff между запусками стабилен.

---

## Чтение перед построением графа

`run_discover` читает конфигурацию, чтобы узнать, где лежат локальные спецификации:

```python
from swax.config import load_config

def locate_specs(project_root: Path) -> Path:
    config = load_config(project_root / ".swax" / "config.yml")
    return project_root / config.specs.location
```

Файл конфигурации обязан существовать к моменту `discover` — `init` должен быть запущен ранее.
