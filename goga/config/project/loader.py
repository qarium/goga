from pathlib import Path, PurePath

import yaml

from .config import (
    BuildConfig,
    CodemanifestConfig,
    DepConfig,
    LintConfig,
    PipelineConfig,
    ProjectConfig,
    TaskExecutorConfig,
)


def _parse_optional_agent(raw, section: str) -> str | None:
    """Parse an optional agent name from a config section.

    Tolerant normalization for the optional-agent contract: an unset agent
    (absent, YAML-null, or empty/whitespace-only string) resolves to ``None`` so
    the consuming command owns the user-facing requirement. A present non-string
    value is a structural type error and raises ``ValueError``.

    Args:
        raw: The raw ``agent`` value from the section mapping (a ``str``, or
            None when absent).
        section: The dotted section prefix for error messages
            (e.g. ``"build.task_executor"``, ``"pipeline"``).

    Returns:
        The stripped agent name, or ``None`` when unset/empty.

    Raises:
        ValueError: When ``raw`` is present but not a string.
    """
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError(f"{section}.agent must be a string in .goga/config.yml")
    stripped = raw.strip()
    return stripped or None


def _parse_task_executor(task_executor_data: dict) -> TaskExecutorConfig:
    """Parse and validate task_executor section into a TaskExecutorConfig instance."""
    agent = _parse_optional_agent(task_executor_data.get("agent"), "build.task_executor")

    env = task_executor_data.get("env", {})
    if not isinstance(env, dict):
        raise ValueError("build.task_executor.env must be a mapping in .goga/config.yml")
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
        raise ValueError("build.task_executor.env must have string keys and values")

    return TaskExecutorConfig(agent=agent, env=dict(env))


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

    Mirrors `_parse_image`: a non-string value raises ValueError.
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

    Structural-only parse mirroring the style of ``_parse_codemanifest``.
    Returns ``None`` when the section is absent or YAML-null; raises
    ``ValueError`` when the section is present but not a mapping, when
    ``lint.ignore`` is present but not a list, or when any ``lint.ignore``
    element is not a string. Path semantics (normalization, globbing) are NOT
    validated here — that responsibility belongs to the AST consumer; the
    ``ignore`` list is stored verbatim.

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


def _parse_tools(data: dict) -> dict[str, str] | None:
    """Extract the optional top-level tools mapping.

    Structural-only extraction — performs NO semantic validation of value
    contents (operator-prefixed forms, malformed numerics, pre-release forms
    all pass through verbatim). The loader is not the validation authority for
    the version grammar; that responsibility belongs to the consumer.

    Returns None when the key is absent or YAML-null; an empty dict when the
    section is present but empty; a plain dict copy otherwise. YAML-null
    individual values ('viewer:') are a structural type error and raise
    ValueError — they are NOT coerced to 'latest'.
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
    """Reject a ``root`` value that is unsafe as a walk-origin subpath of the clone.

    Structural path-safety only — this NEVER ``stat``/``exists``/``resolve`` the path
    against the filesystem (the cloned repository is owned by the usages-sync deploy
    consumer). A leading ``/`` or a UNC root (``//host/share``) is rejected as absolute
    (an escape vector out of the clone root); a ``..`` segment is rejected as traversal.
    On POSIX, a Windows drive-letter form (``C:/x``) normalizes to a relative path and
    is NOT rejected — it is not an escape vector (design Remark 2).

    Distinct from ``_validate_usages_segment`` (single-segment ``<group>``/``<dep>``
    keys that reject any ``/``): ``root`` is a multi-segment subpath where ``/`` is the
    segment separator, so the segment helper MUST NOT be reused here.

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

    Deliberate divergence from ``ref``: an empty/separator/whitespace-only ``root``
    normalizes to None (≡ "no root" — walk from the clone root), NOT a ValueError,
    whereas an empty ``ref`` raises. Backslashes are normalized to forward slashes so a
    Windows-style ``root`` (``docs\\sub``) is treated as ``docs/sub``.

    Validation runs on the slash-containing original BEFORE the canonical form is
    reconstructed, so a leading ``/`` is caught as absolute rather than silently coerced
    to a relative path (design Remark 1). The filesystem is never touched here — only
    structural path safety is enforced at the config boundary; resolving a non-None
    ``root`` against the cloned repository is the deploy consumer's responsibility.

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

    Dynamic ``usages`` keys are used verbatim as path segments in ``sync``
    (``.goga/usages/<group>/<dep>/``). A name that is empty, a traversal segment
    (``.``/``..``), or contains a path separator (``/`` or ``\\``) could otherwise
    direct deploys outside the target root (``shutil.copytree(..., dirs_exist_ok=True)``
    overwrites colliding files), so such names are rejected at the config boundary.

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

    Mirrors the structural style of `_parse_tools`. Raises ValueError when the
    section, or any group/dep value, is present but not a mapping, when a
    group/dep key is not a string, or when a dep's `git`/`ref` has an invalid
    type. Raises KeyError when a dep's `git` is missing (or YAML-null). Dynamic
    <group>/<dep> names are preserved as dict keys — NOT dataclass fields — so
    dot-notation `usages.<group>.<dep>` works downstream.

    Args:
        raw: The already-parsed `usages` node from the config document (a
            mapping, or None).

    Returns:
        None when the section is absent or YAML-null; an empty dict when the
        section is present but empty; otherwise a dict[group][dep] -> DepConfig.
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

    Returns None when the key is absent (or explicitly null); raises ValueError
    when the key is present but not a mapping. The loader does not enforce
    presence of optional sections — that is the consuming command's responsibility.
    """
    section = data.get(key)
    if section is None:
        return None
    if not isinstance(section, dict):
        raise ValueError(f"'{key}' must be a mapping in .goga/config.yml")
    return section


def _parse_build(build_data: dict) -> BuildConfig:
    """Parse and validate the build section into a BuildConfig instance.

    Hard-rejects the deprecated `build.image` field (schema break).
    """
    if "image" in build_data:
        raise ValueError("build.image is no longer supported — set top-level 'image' in .goga/config.yml")

    try:
        task_executor_data = build_data["task_executor"]
    except KeyError as err:
        raise KeyError("build.task_executor is required in .goga/config.yml") from err

    if not isinstance(task_executor_data, dict):
        raise ValueError("build.task_executor must be a mapping in .goga/config.yml")

    task_executor = _parse_task_executor(task_executor_data)

    proxy = _parse_proxy(build_data.get("proxy"), "build")
    hosts = _parse_hosts(build_data.get("hosts"), "build")

    return BuildConfig(
        task_executor=task_executor,
        worktree=build_data.get("worktree"),
        skip_finalize=build_data.get("skip_finalize"),
        session_timeout=build_data.get("session_timeout"),
        idle_timeout=build_data.get("idle_timeout"),
        wait=build_data.get("wait"),
        max_iterations=build_data.get("max_iterations"),
        review_patience=build_data.get("review_patience"),
        prompts_dir=build_data.get("prompts_dir"),
        agents_dir=build_data.get("agents_dir"),
        codex_review=build_data.get("codex_review"),
        proxy=proxy,
        hosts=hosts,
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
        ValueError: if .goga/config.yml is not a YAML mapping or invalid field values,
            or when the deprecated build.image field is present.
        KeyError: if required sections are missing (language, or build.task_executor
            when build is present).
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

    lang = _parse_language(data)
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

    return ProjectConfig(
        lang=lang,
        image=image,
        dockerfile=dockerfile,
        build=build,
        pipeline=pipeline,
        commands=commands,
        codemanifest=_parse_codemanifest(data),
        tools=tools,
        usages=usages,
        lint=lint,
    )
