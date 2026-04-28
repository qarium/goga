# goga/config/config.py — Config, BuildConfig, TaskExecutor dataclasses

from dataclasses import dataclass, field


@dataclass(kw_only=True, frozen=True)
class TaskExecutor:
    agent: str
    env: dict = field(default_factory=dict)


@dataclass(kw_only=True, frozen=True)
class BuildConfig:
    task_executor: TaskExecutor
    worktree: bool | None = None
    skip_finalize: bool | None = None
    session_timeout: str | None = None
    idle_timeout: str | None = None
    wait: str | None = None
    max_iterations: int | None = None
    review_patience: int | None = None
    prompts_dir: str | None = None
    agents_dir: str | None = None
    codex_review: bool | None = None


@dataclass(kw_only=True, frozen=True)
class Config:
    lang: str
    build: BuildConfig
    commands: dict = field(default_factory=dict)
