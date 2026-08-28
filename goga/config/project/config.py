from dataclasses import dataclass, field


@dataclass(kw_only=True, frozen=True)
class TaskExecutorConfig:
    """Configuration for the task execution agent and its environment.

    `agent` is optional at the config level: absent/empty in `.goga/config.yml`
    resolves to None, and the consuming `goga build` command raises a clean
    ClickException when it actually needs an agent.
    """

    agent: str | None = None
    env: dict = field(default_factory=dict)


@dataclass(kw_only=True, frozen=True)
class PipelineConfig:
    """Configuration for pipeline execution inside the container.

    `agent` drives the afm `client.command` inside the container, semantically
    distinct from `TaskExecutorConfig.agent`. Optional at the config level:
    absent/empty resolves to None, and `goga pipeline` raises a clean
    ClickException when it needs an agent.
    """

    agent: str | None = None
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
class ReviewExecutorConfig:
    """Value-object for the optional ``build.review_executor`` section of .goga/config.yml.

    Immutable verbatim container — structural typing only. Fields are stored exactly
    as parsed: no empty-value normalization, no role/agent whitelists. ``roles=[]``
    is NOT coerced to None (the "full default set" reading belongs to the consumer);
    semantic validation (role whitelist, agent existence) also belongs to consumers,
    not to this dataclass or the loader.

    ``env`` is the review-pass environment layer, stored verbatim from
    ``.goga/config.yml``: an empty dict when the field is absent, YAML-null, or an
    empty mapping. The env-requires-agent rule belongs to the consumer, not here.

    The section also carries the review diff base (``base_ref``) and the
    external-review stop threshold (``patience``). Both are stored verbatim —
    structural typing only: branch resolvability and threshold semantics belong to
    the consumer, never to this dataclass or the loader.
    """

    skip: bool | None = None
    agent: str | None = None
    roles: list[str] | None = None
    env: dict[str, str] = field(default_factory=dict)
    base_ref: str | None = None
    patience: int | None = None


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
    prompts_dir: str | None = None
    agents_dir: str | None = None
    codex_review: bool | None = None
    review_executor: ReviewExecutorConfig | None = None
    proxy: str | None = None
    hosts: dict[str, str] = field(default_factory=dict)


@dataclass(kw_only=True, frozen=True)
class LintConfig:
    """Immutable value-object for the optional `lint` section of `.goga/config.yml`.

    Stores `ignore` verbatim — including trailing separators and glob characters —
    with no normalization. Structural validation (mapping/list/element checks) belongs
    to the loader (`load_project_config` / `_parse_lint`), not here.
    """

    ignore: list[str]


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
    lint: LintConfig | None = None
