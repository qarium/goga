from pathlib import Path, PurePath

import yaml

from .config import (
    AdditionalReviewConfig,
    BuildConfig,
    CodemanifestConfig,
    DepConfig,
    LintConfig,
    PipelineConfig,
    ProjectConfig,
    ReviewConfig,
    TopicsConfig,
    TopicsCreateConfig,
    TopicsPropagateConfig,
    TopicsUpdateConfig,
)


def _parse_optional_stripped_str(raw, key: str) -> str | None:
    """Parse an optional string field with the loader's emptiness rule.

    Args:
        raw: The raw field value from the mapping (a ``str``, or None when
            absent).
        key: The dotted field name for error messages (e.g.
            ``"build.agent"``).

    Returns:
        The stripped value, or ``None`` when unset/empty.

    Raises:
        ValueError: When ``raw`` is present but not a string.
    """
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError(f"{key} must be a string in .goga/config.yml")
    stripped = raw.strip()
    return stripped or None


def _parse_optional_plain_str(raw, key: str) -> str | None:
    """Parse an optional string field stored verbatim (no strip, no emptiness rule).

    Args:
        raw: The raw field value from the mapping (a ``str``, or None when
            absent).
        key: The dotted field name for error messages.

    Returns:
        The verbatim string, or ``None`` when absent/YAML-null.

    Raises:
        ValueError: When ``raw`` is present but not a string.
    """
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError(f"{key} must be a string in .goga/config.yml")
    return raw


def _parse_optional_agent(raw, section: str) -> str | None:
    """Parse an optional agent name from a config section.

    Args:
        raw: The raw ``agent`` value from the section mapping (a ``str``, or
            None when absent).
        section: The dotted section prefix for error messages
            (e.g. ``"build"``, ``"pipeline"``).

    Returns:
        The stripped agent name, or ``None`` when unset/empty.

    Raises:
        ValueError: When ``raw`` is present but not a string.
    """
    return _parse_optional_stripped_str(raw, f"{section}.agent")


def _parse_optional_int(raw, key: str) -> int | None:
    """Parse an optional int field; a YAML bool is rejected, not coerced.

    Args:
        raw: The raw field value from the mapping (an ``int``, or None when
            absent).
        key: The dotted field name for error messages.

    Returns:
        The verbatim int, or ``None`` when absent/YAML-null.

    Raises:
        ValueError: When ``raw`` is present but not an int (a bool included).
    """
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError(f"{key} must be an int in .goga/config.yml")
    return raw


def _parse_env_mapping(raw, key: str) -> dict[str, str]:
    """Parse an optional env layer — a string-keyed, string-valued mapping.

    Args:
        raw: The raw ``env`` value from the mapping.
        key: The dotted field name for error messages (e.g.
            ``"build.env"``).

    Returns:
        A plain dict copy of the mapping, or ``{}`` when absent/YAML-null.

    Raises:
        ValueError: When ``raw`` is present but not a mapping of strings to
            strings.
    """
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{key} must be a mapping in .goga/config.yml")
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in raw.items()):
        raise ValueError(f"{key} must have string keys and values")
    return dict(raw)


def _parse_proxy(proxy_data, section: str) -> str | None:
    """Validate an optional proxy field; None is a valid value."""
    if proxy_data is not None and not isinstance(proxy_data, str):
        raise ValueError(f"{section}.proxy must be a string in .goga/config.yml")
    return proxy_data


def _parse_hosts(hosts_data, section: str) -> dict[str, str]:
    """Validate an optional host→IP mapping; None/absent resolves to an empty dict."""
    if hosts_data is None:
        return {}
    if not isinstance(hosts_data, dict):
        raise ValueError(f"{section}.hosts must be a mapping in .goga/config.yml")
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in hosts_data.items()):
        raise ValueError(f"{section}.hosts must have string keys and values in .goga/config.yml")
    return dict(hosts_data)


def _parse_pipeline(pipeline_data: dict) -> PipelineConfig:
    """Parse and validate the pipeline section into a PipelineConfig instance."""
    agent = _parse_optional_agent(pipeline_data.get("agent"), "pipeline")

    env = pipeline_data.get("env", {})
    if not isinstance(env, dict):
        raise ValueError("pipeline.env must be a mapping in .goga/config.yml")
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
        raise ValueError("pipeline.env must have string keys and values")

    proxy = _parse_proxy(pipeline_data.get("proxy"), "pipeline")
    hosts = _parse_hosts(pipeline_data.get("hosts"), "pipeline")

    return PipelineConfig(agent=agent, env=dict(env), proxy=proxy, hosts=hosts)


def _parse_language(data: dict) -> str:
    """Extract and validate the language field from YAML data."""
    try:
        lang = data["language"]
    except KeyError as err:
        raise KeyError("language is required in .goga/config.yml") from err

    if not isinstance(lang, str) or not lang.strip():
        raise ValueError("language must be a non-empty string in .goga/config.yml")

    return lang.strip()


def _parse_image(data: dict) -> str | None:
    """Extract the optional top-level image field; None is a valid value."""
    image = data.get("image")
    if image is not None and not isinstance(image, str):
        raise ValueError("image must be a string in .goga/config.yml")
    return image


def _parse_dockerfile(data: dict) -> str | None:
    """Extract the optional top-level dockerfile field; None is a valid value.

    Raises:
        ValueError: When the value is present but not a string.
    """
    dockerfile = data.get("dockerfile")
    if dockerfile is not None and not isinstance(dockerfile, str):
        raise ValueError("dockerfile must be a string in .goga/config.yml")
    return dockerfile


def _parse_codemanifest(data: dict) -> CodemanifestConfig | None:
    """Parse optional codemanifest section from YAML data."""
    codemanifest_data = data.get("codemanifest")
    if codemanifest_data is None:
        return None
    if not isinstance(codemanifest_data, dict):
        raise ValueError("'codemanifest' must be a mapping in .goga/config.yml")

    usages = codemanifest_data.get("usages", {})
    if not isinstance(usages, dict):
        raise ValueError("codemanifest.usages must be a mapping")
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in usages.items()):
        raise ValueError("codemanifest.usages must have string keys and values")

    annotations = codemanifest_data.get("annotations")
    if annotations is not None and not isinstance(annotations, str):
        raise ValueError("codemanifest.annotations must be a string")

    return CodemanifestConfig(usages=dict(usages), annotations=annotations)


def _parse_lint(data: dict) -> LintConfig | None:
    """Parse the optional ``lint`` section into a ``LintConfig`` value-object.

    Args:
        data: The already-parsed ``.goga/config.yml`` document.

    Returns:
        A ``LintConfig`` storing ``ignore`` verbatim (``[]`` when ``lint.ignore``
        is absent or YAML-null), or ``None`` when the ``lint`` section is absent.

    Raises:
        ValueError: When ``lint`` is present but not a mapping, when
            ``lint.ignore`` is present but not a list, or when a ``lint.ignore``
            element is not a string.
    """
    lint_data = data.get("lint")
    if lint_data is None:
        return None
    if not isinstance(lint_data, dict):
        raise ValueError("'lint' must be a mapping in .goga/config.yml")

    ignore_raw = lint_data.get("ignore")
    if ignore_raw is None:
        ignore_list: list[str] = []
    elif not isinstance(ignore_raw, list):
        raise ValueError("lint.ignore must be a list of strings in .goga/config.yml")
    elif not all(isinstance(x, str) for x in ignore_raw):
        raise ValueError("lint.ignore must contain only strings in .goga/config.yml")
    else:
        ignore_list = list(ignore_raw)

    return LintConfig(ignore=ignore_list)


def _parse_topics_field(value, key: str) -> str | None:
    """Parse a single string field of the optional ``topics`` section.

    Args:
        value: The raw field value from the ``topics`` mapping (a ``str``, or
            None when absent).
        key: The dotted field name for error messages (e.g.
            ``"topics.base_ref"``).

    Returns:
        The stripped field value, or ``None`` when unset/empty.

    Raises:
        ValueError: When ``value`` is present but not a string.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string in .goga/config.yml")

    return value.strip() or None


def _parse_topics_section(raw, name: str, fields: tuple[str, ...]) -> dict[str, str | None] | None:
    """Parse one ``topics.<name>`` sub-mapping into its field values (loader step 9).

    Args:
        raw: The raw section value from the ``topics`` mapping (a ``dict``, or
            None when absent/YAML-null).
        name: The section name for error messages (``"create"``,
            ``"update"``, ``"propagate"``).
        fields: The known leaf field names of the section's model.

    Returns:
        A dict of parsed leaf values keyed by field name, or ``None`` when
        the section is absent or YAML-null.

    Raises:
        ValueError: When the section is present but not a mapping, or when a
            named leaf is present but not a string.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"'topics.{name}' must be a mapping in .goga/config.yml")

    return {field: _parse_topics_field(raw.get(field), f"topics.{name}.{field}") for field in fields}


def _parse_topics(data: dict) -> TopicsConfig | None:
    """Parse the optional ``topics`` section into a nested ``TopicsConfig`` (loader step 9).

    Args:
        data: The already-parsed ``.goga/config.yml`` document.

    Returns:
        A ``TopicsConfig`` with ``base_ref`` and the assembled operation sections stored verbatim,
        or ``None`` when the ``topics`` section is absent or YAML-null; a present-but-empty mapping
        yields a ``TopicsConfig`` with every field ``None``.

    Raises:
        ValueError: When ``topics`` is present but not a mapping; when a
            sub-section is present but not a mapping; or when any known leaf
            (``topics.base_ref``, ``topics.create.commit``,
            ``topics.update.{strategy,commit}``,
            ``topics.propagate.{strategy,commit}``) is present but not a
            string.
    """
    raw = data.get("topics")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("'topics' must be a mapping in .goga/config.yml")

    base_ref = _parse_topics_field(raw.get("base_ref"), "topics.base_ref")
    create_values = _parse_topics_section(raw.get("create"), "create", ("commit",))
    update_values = _parse_topics_section(raw.get("update"), "update", ("strategy", "commit"))
    propagate_values = _parse_topics_section(raw.get("propagate"), "propagate", ("strategy", "commit"))

    return TopicsConfig(
        base_ref=base_ref,
        create=TopicsCreateConfig(**create_values) if create_values is not None else None,
        update=TopicsUpdateConfig(**update_values) if update_values is not None else None,
        propagate=TopicsPropagateConfig(**propagate_values) if propagate_values is not None else None,
    )


def _parse_tools(data: dict) -> dict[str, str] | None:
    """Extract the optional top-level tools mapping.

    Returns:
        None when the key is absent or YAML-null; an empty dict when the section is present but
        empty; a plain dict copy otherwise — values pass through verbatim, no version-grammar
        validation.

    Raises:
        ValueError: When the section is present but not a mapping, or when a key or value is not a
            string (a YAML-null value is not coerced to ``latest``).
    """
    tools_data = data.get("tools")
    if tools_data is None:
        return None
    if not isinstance(tools_data, dict):
        raise ValueError("'tools' must be a mapping in .goga/config.yml")
    for k, v in tools_data.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise ValueError("'tools' must have string keys and values in .goga/config.yml")
    return dict(tools_data)


def _validate_usages_root(root: str) -> None:
    """Reject a ``root`` value unsafe as a walk-origin subpath — structural only, no filesystem access.

    Args:
        root: The already-stripped, backslash-normalized root string to validate — the
            slash-containing original. A leading ``/`` is caught here BEFORE the caller
            reconstructs the canonical form, which would silently drop it (design Remark 1).

    Raises:
        ValueError: When ``root`` is absolute (leading ``/`` or a UNC anchor) or
            contains a ``..`` segment.
    """
    path = PurePath(root)
    if path.is_absolute() or path.anchor != "":
        raise ValueError("usages root must be a relative path (no absolute paths) in .goga/config.yml")
    if ".." in path.parts:
        raise ValueError("usages root must not contain '..' segments (path escape) in .goga/config.yml")


def _parse_depcfg_root(group: str, dep: str, root) -> str | None:
    """Normalize and structurally validate the optional usages dep ``root`` field.

    Args:
        group: The owning group name (for error messages).
        dep: The dep name (for error messages).
        root: The raw ``root`` value from the dep mapping (a ``str``, or None when absent).

    Returns:
        None when ``root`` is absent or empty/separator/whitespace-only; otherwise the
        canonical forward-slash form with empty/trailing segments dropped.

    Raises:
        ValueError: When ``root`` is present but not a string, or is absolute / contains
            a ``..`` segment.
    """
    if root is None:
        return None
    if not isinstance(root, str):
        raise ValueError(f"usages.{group}.{dep}.root must be a string in .goga/config.yml")
    stripped = root.strip().replace("\\", "/")
    if stripped.strip("/") == "":
        return None
    _validate_usages_root(stripped)
    return "/".join(segment for segment in stripped.split("/") if segment)


def _parse_depcfg(group: str, dep: str, dep_data: dict) -> DepConfig:
    """Parse a single ``<dep>`` mapping into a ``DepConfig`` (structural validation).

    Args:
        group: The owning group name (for error messages).
        dep: The dep name (for error messages).
        dep_data: The already-parsed ``<dep>`` mapping.

    Returns:
        The validated ``DepConfig``.

    Raises:
        KeyError: When ``git`` is missing or YAML-null.
        ValueError: When ``git`` is not a non-empty string; when ``ref`` is present
            but not a (non-empty) string; or when ``root`` is present but not a string
            or is structurally unsafe (absolute / contains a ``..`` segment). An empty
            or separator/whitespace-only ``root`` is NOT an error — it normalizes to None.
    """
    git = dep_data.get("git")
    if git is None:
        raise KeyError(f"usages.{group}.{dep}.git is required in .goga/config.yml")
    if not isinstance(git, str) or not git.strip():
        raise ValueError(f"usages.{group}.{dep}.git must be a non-empty string in .goga/config.yml")
    ref = dep_data.get("ref")
    if ref is not None and not isinstance(ref, str):
        raise ValueError(f"usages.{group}.{dep}.ref must be a string in .goga/config.yml")
    if isinstance(ref, str):
        # Mirror ``git``: strip whitespace and reject empty so a stray ``ref: ""``
        # fails loudly here instead of producing a cryptic ``git checkout ""`` error.
        ref = ref.strip()
        if ref == "":
            raise ValueError(f"usages.{group}.{dep}.ref must be a non-empty string in .goga/config.yml")
    # Note: empty/separator/whitespace-only ``root`` normalizes to None here (NOT a
    # ValueError) — the deliberate divergence from ``ref`` above.
    root = _parse_depcfg_root(group, dep, dep_data.get("root"))
    return DepConfig(git=git.strip(), ref=ref, root=root)


def _validate_usages_segment(name: str, *, group: str, is_dep: bool) -> None:
    """Reject a ``<group>``/``<dep>`` key that is unsafe as a filesystem path segment.

    Args:
        name: The group or dep key string to validate.
        group: The owning group name (for error context).
        is_dep: True when ``name`` is a dep key, False when it is a group key.

    Raises:
        ValueError: When ``name`` is empty, a traversal segment, or contains a
            path separator.
    """
    if name == "" or name in (".", "..") or "/" in name or "\\" in name:
        kind = f"usages.{group} dep" if is_dep else "'usages' group"
        raise ValueError(f"{kind} name must be a plain name without '/' or '..' (got {name!r}) in .goga/config.yml")


def _parse_usages(raw) -> dict[str, dict[str, DepConfig]] | None:
    """Parse the optional usages section into a dict[group][dep] -> DepConfig.

    Args:
        raw: The already-parsed `usages` node from the config document (a
            mapping, or None).

    Returns:
        None when the section is absent or YAML-null; an empty dict when the section is present
        but empty; otherwise a dict[group][dep] -> DepConfig — dynamic <group>/<dep> names are
        preserved as dict keys, not dataclass fields.

    Raises:
        ValueError: When the section or any group/dep value is present but not a mapping, when a
            group/dep key is not a string, or when a dep's ``git``/``ref`` has an invalid type.
        KeyError: When a dep's ``git`` is missing or YAML-null.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("'usages' must be a mapping in .goga/config.yml")

    usages: dict[str, dict[str, DepConfig]] = {}

    for group, group_data in raw.items():
        if not isinstance(group, str):
            raise ValueError("'usages' must have string group names in .goga/config.yml")
        _validate_usages_segment(group, group=group, is_dep=False)
        if not isinstance(group_data, dict):
            raise ValueError(f"usages.{group} must be a mapping in .goga/config.yml")
        deps: dict[str, DepConfig] = {}
        for dep, dep_data in group_data.items():
            if not isinstance(dep, str):
                raise ValueError(f"usages.{group} must have string dep names in .goga/config.yml")
            _validate_usages_segment(dep, group=group, is_dep=True)
            if not isinstance(dep_data, dict):
                raise ValueError(f"usages.{group}.{dep} must be a mapping in .goga/config.yml")
            deps[dep] = _parse_depcfg(group, dep, dep_data)
        usages[group] = deps

    return usages


def _optional_mapping(data: dict, key: str) -> dict | None:
    """Extract an optional mapping section.

    Returns:
        The mapping when present, or None when the key is absent or explicitly null.

    Raises:
        ValueError: When the key is present but not a mapping.
    """
    section = data.get(key)
    if section is None:
        return None
    if not isinstance(section, dict):
        raise ValueError(f"'{key}' must be a mapping in .goga/config.yml")

    return section


def _parse_review(build_data: dict) -> ReviewConfig | None:
    """Parse the optional ``build.review`` sub-mapping (loader step 7).

    Args:
        build_data: The already-parsed ``build`` mapping.

    Returns:
        A ``ReviewConfig`` storing every field verbatim (``env`` as a fresh
        dict, ``{}`` when absent/YAML-null/empty), or None when the section is
        absent or YAML-null.

    Raises:
        ValueError: When the section is present but not a mapping, or when any
            known field is present with an invalid type.
    """
    raw = build_data.get("review")

    if raw is None:
        return None

    if not isinstance(raw, dict):
        raise ValueError("build.review must be a mapping in .goga/config.yml")

    skip = raw.get("skip")

    if skip is not None and not isinstance(skip, bool):
        raise ValueError("build.review.skip must be a bool in .goga/config.yml")

    agent = _parse_optional_agent(raw.get("agent"), "build.review")
    env = _parse_env_mapping(raw.get("env"), "build.review.env")

    roles_raw = raw.get("roles")

    if roles_raw is None:
        roles = None
    elif not isinstance(roles_raw, list) or not all(isinstance(x, str) for x in roles_raw):
        raise ValueError("build.review.roles must be a list of strings in .goga/config.yml")
    else:
        roles = list(roles_raw)

    base_ref = _parse_optional_stripped_str(raw.get("base_ref"), "build.review.base_ref")
    strategy = _parse_optional_stripped_str(raw.get("strategy"), "build.review.strategy")
    finalize = _parse_optional_stripped_str(raw.get("finalize"), "build.review.finalize")

    session_timeout = _parse_optional_stripped_str(raw.get("session_timeout"), "build.review.session_timeout")
    idle_timeout = _parse_optional_stripped_str(raw.get("idle_timeout"), "build.review.idle_timeout")
    wait = _parse_optional_stripped_str(raw.get("wait"), "build.review.wait")
    max_iterations = _parse_optional_int(raw.get("max_iterations"), "build.review.max_iterations")

    additional = _parse_additional_review(raw.get("additional"))

    return ReviewConfig(
        skip=skip,
        agent=agent,
        env=env,
        roles=roles,
        base_ref=base_ref,
        strategy=strategy,
        finalize=finalize,
        additional=additional,
        session_timeout=session_timeout,
        idle_timeout=idle_timeout,
        wait=wait,
        max_iterations=max_iterations,
    )


def _parse_additional_review(raw) -> AdditionalReviewConfig | None:
    """Parse the optional ``build.review.additional`` external-review block.

    Args:
        raw: The raw ``additional`` value from the ``build.review`` mapping.

    Returns:
        An ``AdditionalReviewConfig`` storing the block verbatim, or None when
        absent/YAML-null.

    Raises:
        ValueError: When the block is present but not a mapping, or when
            ``agent``/``patience``/``max_iterations`` is present with an
            invalid type.
    """
    if raw is None:
        return None

    if not isinstance(raw, dict):
        raise ValueError("build.review.additional must be a mapping in .goga/config.yml")

    agent = _parse_optional_agent(raw.get("agent"), "build.review.additional")
    patience = _parse_optional_int(raw.get("patience"), "build.review.additional.patience")
    max_iterations = _parse_optional_int(raw.get("max_iterations"), "build.review.additional.max_iterations")

    return AdditionalReviewConfig(agent=agent, patience=patience, max_iterations=max_iterations)


def _parse_build(build_data: dict) -> BuildConfig:
    """Parse and validate the build section into a two-part BuildConfig (loader step 6).

    Args:
        build_data: The already-parsed ``build`` mapping.

    Returns:
        A ``BuildConfig`` with the root fields verbatim (``env``/``hosts`` as fresh dicts, ``{}``
        when absent) and the parsed ``review`` part; unknown keys are silently ignored, never stored.

    Raises:
        ValueError: When a known root or review field is present with an
            invalid type.
    """
    agent = _parse_optional_agent(build_data.get("agent"), "build")
    env = _parse_env_mapping(build_data.get("env"), "build.env")
    max_iterations = _parse_optional_int(build_data.get("max_iterations"), "build.max_iterations")
    session_timeout = _parse_optional_stripped_str(build_data.get("session_timeout"), "build.session_timeout")
    idle_timeout = _parse_optional_stripped_str(build_data.get("idle_timeout"), "build.idle_timeout")
    wait = _parse_optional_stripped_str(build_data.get("wait"), "build.wait")

    prompts_dir = _parse_optional_plain_str(build_data.get("prompts_dir"), "build.prompts_dir")
    agents_dir = _parse_optional_plain_str(build_data.get("agents_dir"), "build.agents_dir")

    proxy = _parse_proxy(build_data.get("proxy"), "build")
    hosts = _parse_hosts(build_data.get("hosts"), "build")
    review = _parse_review(build_data)

    return BuildConfig(
        agent=agent,
        env=env,
        max_iterations=max_iterations,
        session_timeout=session_timeout,
        idle_timeout=idle_timeout,
        wait=wait,
        prompts_dir=prompts_dir,
        agents_dir=agents_dir,
        proxy=proxy,
        hosts=hosts,
        review=review,
    )


def load_project_config() -> ProjectConfig:
    """Load project configuration from .goga/config.yml in the current working directory.

    Returns:
        ProjectConfig instance. Top-level image and dockerfile are None-able; build and
        pipeline are None when their sections are absent in .goga/config.yml.

    Raises:
        FileNotFoundError: if .goga/config.yml does not exist or is empty.
        OSError: if .goga/config.yml exists but cannot be read (e.g. it is a
            directory, or the file is unreadable due to permissions). These are
            raised by ``config_path.open()``.
        ValueError: if .goga/config.yml is not a YAML mapping or invalid field values.
        KeyError: if required sections are missing (language).
        yaml.YAMLError: if YAML parsing fails.
    """
    config_path = Path("./.goga/config.yml")

    if not config_path.exists():
        raise FileNotFoundError(".goga/config.yml not found in project root")

    with config_path.open() as f:
        data = yaml.safe_load(f)

    if data is None:
        raise FileNotFoundError(".goga/config.yml not found in project root")

    if not isinstance(data, dict):
        raise ValueError(".goga/config.yml must be a YAML mapping")

    language = _parse_language(data)
    image = _parse_image(data)
    dockerfile = _parse_dockerfile(data)
    pipeline_data = _optional_mapping(data, "pipeline")
    pipeline = _parse_pipeline(pipeline_data) if pipeline_data is not None else None
    build_data = _optional_mapping(data, "build")
    build = _parse_build(build_data) if build_data is not None else None

    commands = data.get("commands", {})
    if not isinstance(commands, dict):
        raise ValueError("'commands' must be a mapping in .goga/config.yml")
    commands = dict(commands)

    tools = _parse_tools(data)
    usages = _parse_usages(data.get("usages"))
    lint = _parse_lint(data)
    topics = _parse_topics(data)

    return ProjectConfig(
        language=language,
        image=image,
        dockerfile=dockerfile,
        build=build,
        pipeline=pipeline,
        commands=commands,
        codemanifest=_parse_codemanifest(data),
        tools=tools,
        usages=usages,
        lint=lint,
        topics=topics,
    )
