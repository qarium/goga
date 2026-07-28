# Specs repository — клонирование для чтения спецификаций

## Предметная область

Шаблоны доступа к удалённому git-репозиторию со спецификациями OpenAPI/Swagger. Целевая аудитория: cell `applications/init/` (клонирует репозиторий, чтобы скопировать спецификации в локальный путь проекта).

Swax обращается с репозиторием как с read-only: клонирует, читает, удаляет временный клон. Никаких commit-ов и push-ей.

---

## Клонирование как context manager

`clone_specs` — это context manager: yields путь к спецификациям внутри временного клона и автоматически очищает временный каталог при выходе (нормальном или с исключением):

```python
from pathlib import Path

from swax.git import clone_specs

def install_specs(repo_url: str, specs_location: str) -> Path:
    with clone_specs(repo_url, specs_location) as specs_path:
        # specs_path валиден только внутри with — после выхода каталог удалён
        # copy_specs(source=specs_path, destination=local_path) — делегируется cell `fs/`
        return list(specs_path.rglob("*.yaml"))
```

Соглашения потребителя:
- `repo_url` — clone URL. Для приватных репозиториев полагаться на git credential helpers; не встраивать токены в URL.
- `specs_location` — подкаталог в репозитории, где лежат спецификации (из `GitConfig.location`).
- Использовать `with` обязательно — path за пределами блока невалиден.

---

## Обработка доменных исключений

`clone_specs` выбрасывает два доменных исключения. Потребитель (CLI-handler команды `init`) маппит их в `click.ClickException` для единообразного выхода:

```python
from swax.git import clone_specs, RepositoryCloneError, SpecsNotFoundError

def safe_clone(repo_url: str, specs_location: str):
    try:
        with clone_specs(repo_url, specs_location) as specs_path:
            yield specs_path
    except RepositoryCloneError as exc:
        # click.ClickException(f"Не удалось клонировать {exc.url}: {exc.reason}")
        ...
    except SpecsNotFoundError as exc:
        # click.ClickException(f"Спецификации не найдены в {exc.path}")
        ...
```

`RepositoryCloneError` несёт `url` и `reason` — для понятного сообщения пользователю.
`SpecsNotFoundError` несёт `path` — указывает, какой подкаталог отсутствует в репозитории.

---

## Тестирование

В тестах `mock.patch` вызова `Repo.clone_from` в точке импорта (conventions — Моки). Не выполнять реальное клонирование в тестах.
