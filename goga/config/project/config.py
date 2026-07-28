from dataclasses import dataclass, field


@dataclass(kw_only=True, frozen=True)
class TaskExecutorConfig:
    """Configuration for the task execution agent and its environment."""

    agent: str
    env: dict = field(default_factory=dict)


@dataclass(kw_only=True, frozen=True)
class PipelineConfig:
    """Configuration for pipeline execution inside the container.

    `agent` drives the afm `client.command` inside the container, semantically
    distinct from `TaskExecutorConfig.agent`.
    """

    agent: str
    env: dict = field(default_factory=dict)
    proxy: str | None = None
    hosts: dict[str, str] = field(default_factory=dict)


@dataclass(kw_only=True, frozen=True)
class CodemanifestConfig:
    """Configuration for codemanifest resolution and annotations."""

    usages: dict = field(default_factory=dict)
    annotations: str | None = None


@dataclass(kw_only=True, frozen=True)
class DepConfig:
    """Value of a single <dep> declaration inside the usages section of .goga/config.yml.

    Immutable value-object: structural validation (non-empty git, `root` normalization
    and path-safety) lives in the loader, NOT here. The dataclass stores `root`
    verbatim — normalization (`""` -> `None`) and `..`/absolute-path rejection are the
    loader's responsibility, so this field never stores an empty string.
    """

    git: str
    ref: str | None = None
    root: str | None = None


@dataclass(kw_only=True, frozen=True)
class BuildConfig:
    """Build pipeline settings including agent, worktree, and timeout options."""

    task_executor: TaskExecutorConfig
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
    proxy: str | None = None
    hosts: dict[str, str] = field(default_factory=dict)


@dataclass(kw_only=True, frozen=True)
class ProjectConfig:
    """Root project configuration loaded from .goga/config.yml."""

    lang: str
    image: str | None
    dockerfile: str | None
    build: BuildConfig | None
    pipeline: PipelineConfig | None
    commands: dict = field(default_factory=dict)
    codemanifest: CodemanifestConfig | None = None
    tools: dict[str, str] | None = None
    usages: dict[str, dict[str, DepConfig]] | None = None
