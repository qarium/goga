from dataclasses import dataclass, field


@dataclass(kw_only=True, frozen=True)
class PipelineConfig:
    """Configuration for pipeline execution inside the container.

    `agent` drives the afm `client.command` inside the container, semantically
    distinct from `BuildConfig.agent`. Optional at the config level:
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
class AdditionalReviewConfig:
    """Value-object for the optional ``build.review.additional`` block of .goga/config.yml.

    The external-review settings source. Immutable verbatim container —
    structural typing only: no agent-name validation, no range checks. ``0`` is
    a meaningful value on both counters, never an unset marker (None is).

    ``agent``: external review agent name; None when unset — the consumer
    inherits ``review.agent``.

    ``patience``: external-review stop threshold (stop after N consecutive
    unchanged rounds; 0 = disabled); None when unset.

    ``max_iterations``: external review iteration cap (0 = ralphex auto);
    None when unset.
    """

    agent: str | None = None
    patience: int | None = None
    max_iterations: int | None = None


@dataclass(kw_only=True, frozen=True)
class ReviewConfig:
    """Value-object for the optional ``build.review`` section of .goga/config.yml.

    The review-pass settings source of the two-part build model. Immutable
    verbatim container — structural typing only. Every field is stored exactly
    as parsed: no empty-value normalization beyond the loader's strip rules, no
    role/strategy whitelists. An unset field is None (an empty dict for env)
    and means "inherit from the root" to the consumer — the inheritance itself
    belongs to the consumer, never here.

    ``roles=[]`` is NOT coerced to None (the "full default set" reading belongs
    to the consumer). The env-requires-agent rule also belongs to the consumer.

    ``env`` is the review-pass environment layer, stored verbatim from
    ``.goga/config.yml``: an empty dict when the field is absent, YAML-null, or
    an empty mapping. The review env never inherits the root env.

    ``strategy`` is a structural string only — the full|medium|short whitelist
    and the default medium belong to the consumer. ``finalize`` is the
    user-authored final review prompt, stored verbatim.
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


@dataclass(kw_only=True, frozen=True)
class BuildConfig:
    """Build execution settings in the two-part form.

    The ``build`` root of ``.goga/config.yml`` is the tasks-pass settings
    source; the optional ``review`` part carries the review-pass settings
    source. Constructed by ``load_project_config``; values verbatim, no
    inheritance applied here — root→review inheritance belongs to the
    consumer. All fields may be None; ``env``/``hosts`` default to empty
    dicts.

    ``agent``: tasks-pass executor agent name; None when unset — the
    consuming ``goga build`` command raises a clean ClickException when it
    actually needs an agent.

    ``env``: tasks-pass environment layer — the review pass never receives it.

    ``max_iterations``: maximum task iterations (root-only, tasks pass).

    ``session_timeout``/``idle_timeout``/``wait``: session knobs
    (Go duration strings).

    ``prompts_dir``/``agents_dir``: custom ralphex source directories.

    ``proxy``: optional HTTP/HTTPS proxy URL; ``hosts``: optional host→IP
    mapping for ``docker run --add-host``.

    ``review``: the review-pass settings part, or None when ``build.review``
    is absent.
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

    Stores `ignore` verbatim — including trailing separators and glob characters —
    with no normalization. Structural validation (mapping/list/element checks) belongs
    to the loader (`load_project_config` / `_parse_lint`), not here.
    """

    ignore: list[str]


@dataclass(kw_only=True, frozen=True)
class TopicsConfig:
    """Fast-creation configuration of the topics section of `.goga/config.yml`.

    Immutable verbatim value-object. Fields are stored exactly as parsed: no
    revision resolution, no template grammar checks, and no empty-to-None
    normalization (that rule belongs to the loader, which always passes both
    fields). Both fields may be `None` — a present-but-empty section means
    "everything unset" (explicit absence).

    `base_ref`: any revision string the base of a published branch resolves
                from — verbatim, None when unset
    `publish_commit`: the commit message template of the publication, with
                      or without the {slug} placeholder — verbatim, None when
                      unset

    Args:
        base_ref: The base revision of a published topic branch, verbatim
            from `.goga/config.yml`; None when absent/YAML-null/empty.
        publish_commit: The commit message template of the publication,
            verbatim from `.goga/config.yml`; None when absent/YAML-null/empty.
    """

    base_ref: str | None
    publish_commit: str | None


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
