from dataclasses import dataclass, field


@dataclass(kw_only=True, frozen=True)
class PipelineConfig:
    """Configuration for pipeline execution inside the container.

    Attributes:
        agent: The afm client command inside the container, semantically distinct from
            :attr:`BuildConfig.agent`; None when absent/empty — resolved by the in-container consumer.
        env: The in-container afm launch env layer, above the inherited launch environment.
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

    Attributes:
        root: Stored verbatim — never an empty string; the loader normalizes ``""`` to ``None``.
    """

    git: str
    ref: str | None = None
    root: str | None = None


@dataclass(kw_only=True, frozen=True)
class AdditionalReviewConfig:
    """Value-object for the optional ``build.review.additional`` block of .goga/config.yml.

    Attributes:
        agent: External review agent name; None when unset — the consumer inherits ``review.agent``.
        patience: External-review stop threshold (stop after N consecutive unchanged rounds;
            0 = disabled); None when unset.
        max_iterations: External review iteration cap (0 = ralphex auto); None when unset.
    """

    agent: str | None = None
    patience: int | None = None
    max_iterations: int | None = None


@dataclass(kw_only=True, frozen=True)
class ReviewConfig:
    """Value-object for the optional ``build.review`` section of .goga/config.yml.

    Attributes:
        env: The review-pass environment layer, verbatim — an empty dict when absent, YAML-null, or
            an empty mapping; it never inherits the root env.
        roles: Stored verbatim — ``[]`` is not coerced to None.
        strategy: Structural string only — the whitelist and the default belong to the consumer.
        finalize: The user-authored final review prompt, verbatim.
        max_iterations: Review-pass iteration cap; None when unset — it never inherits the root
            ``build.max_iterations``.
    """

    skip: bool | None = None
    agent: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    roles: list[str] | None = None
    base_ref: str | None = None
    strategy: str | None = None
    finalize: str | None = None
    additional: AdditionalReviewConfig | None = None
    session_timeout: str | None = None
    idle_timeout: str | None = None
    wait: str | None = None
    max_iterations: int | None = None


@dataclass(kw_only=True, frozen=True)
class BuildConfig:
    """Build execution settings in the two-part form.

    Attributes:
        agent: Tasks-pass executor agent name; None when unset — guarded by the in-container consumer.
        env: Tasks-pass environment layer — the review pass never receives it.
        max_iterations: Maximum task iterations (root-only, tasks pass).
        session_timeout: Session knob (Go duration string).
        idle_timeout: Session knob (Go duration string).
        wait: Session knob (Go duration string).
        prompts_dir: Custom ralphex source directory.
        agents_dir: Custom ralphex source directory.
        proxy: Optional HTTP/HTTPS proxy URL.
        hosts: Optional host-to-IP mapping for ``docker run --add-host``.
        review: The review-pass settings part, or None when ``build.review`` is absent.
    """

    agent: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    max_iterations: int | None = None
    session_timeout: str | None = None
    idle_timeout: str | None = None
    wait: str | None = None
    prompts_dir: str | None = None
    agents_dir: str | None = None
    proxy: str | None = None
    hosts: dict[str, str] = field(default_factory=dict)
    review: ReviewConfig | None = None


@dataclass(kw_only=True, frozen=True)
class LintConfig:
    """Immutable value-object for the optional `lint` section of `.goga/config.yml`.

    Attributes:
        ignore: Stored verbatim — trailing separators and glob characters included, no normalization.
    """

    ignore: list[str]


@dataclass(kw_only=True, frozen=True)
class TopicsCreateConfig:
    """The ``topics.create`` section of ``.goga/config.yml``.

    Attributes:
        commit: The creation todo commit message template, verbatim; None when unset.
    """

    commit: str | None = None


@dataclass(kw_only=True, frozen=True)
class TopicsUpdateConfig:
    """The ``topics.update`` section of ``.goga/config.yml``.

    Attributes:
        strategy: The strategy name, verbatim; None when unset — the consumer applies the default.
        commit: The message template, verbatim; None when unset.
    """

    strategy: str | None = None
    commit: str | None = None


@dataclass(kw_only=True, frozen=True)
class TopicsPropagateConfig:
    """The ``topics.propagate`` section of ``.goga/config.yml``.

    Attributes:
        strategy: The strategy name, verbatim; None when unset — the consumer applies the default.
        commit: The message template, verbatim; None when unset.
    """

    strategy: str | None = None
    commit: str | None = None


@dataclass(kw_only=True, frozen=True)
class TopicsConfig:
    """The topics section of `.goga/config.yml` — the shared base and the operation sections, fields verbatim.

    Args:
        base_ref: The base revision of the topic exchange, verbatim from
            `.goga/config.yml`; None when absent/YAML-null/empty.
        create: The `TopicsCreateConfig` of the creation defaults, or None
            when the `topics.create` section is absent.
        update: The `TopicsUpdateConfig` of the update defaults, or None
            when the `topics.update` section is absent.
        propagate: The `TopicsPropagateConfig` of the propagation defaults,
            or None when the `topics.propagate` section is absent.
    """

    base_ref: str | None = None
    create: TopicsCreateConfig | None = None
    update: TopicsUpdateConfig | None = None
    propagate: TopicsPropagateConfig | None = None


@dataclass(kw_only=True, frozen=True)
class ProjectConfig:
    """Root project configuration loaded from .goga/config.yml."""

    language: str
    image: str | None
    dockerfile: str | None
    build: BuildConfig | None
    pipeline: PipelineConfig | None
    commands: dict = field(default_factory=dict)
    codemanifest: CodemanifestConfig | None = None
    tools: dict[str, str] | None = None
    usages: dict[str, dict[str, DepConfig]] | None = None
    lint: LintConfig | None = None
    topics: TopicsConfig | None = None
