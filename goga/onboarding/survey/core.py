"""The core question tree of the onboarding session.

The entity declared in the cell CODEMANIFEST with ``location: core.py``:
the tree builder ``core_questions``. The builder composes the eight core
sections in survey order — the language choice, the base-convention gate,
the codemanifest entries, the build and pipeline executors, the docker
image decision, the tools collection, and the usages records — with the
image hints completed from the runtime minor tag, never a hardcoded one.
"""

from __future__ import annotations

from ..questions import Question, QuestionGroup

# Language → image-family mapping of the `image_defaults` practice. The
# names carry no tag: the builder completes each with the runtime minor tag
# (``{name}:{tag}``) — a hardcoded tag never appears here.
image_defaults: dict[str, list[str]] = {
    "python": [
        "qarium/goga-python-3.10",
        "qarium/goga-python-3.11",
        "qarium/goga-python-3.12",
        "qarium/goga-python-3.13",
        "qarium/goga-python-3.14",
    ],
    "golang": [
        "qarium/goga-golang-1.23",
        "qarium/goga-golang-1.24",
        "qarium/goga-golang-1.25",
        "qarium/goga-golang-1.26",
    ],
    "javascript": [
        "qarium/goga-node-22",
        "qarium/goga-node-24",
    ],
    "kotlin": [
        "qarium/goga-kotlin-2.0",
        "qarium/goga-kotlin-2.1",
        "qarium/goga-kotlin-2.2",
        "qarium/goga-kotlin-2.3",
    ],
    "swift": [
        "qarium/goga-swift-6.0",
        "qarium/goga-swift-6.1",
        "qarium/goga-swift-6.2",
    ],
}

# The languages offered for selection, in survey order.
_LANGUAGES = ["python", "golang", "kotlin", "swift", "javascript"]

# Agent → env-key mapping of the `agent_env_defaults` practice. The engine
# proposes the keys of the selected agent first, then collects arbitrary
# additions.
agent_env_defaults: dict[str, list[str]] = {
    "claude": [
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "ANTHROPIC_MODEL",
    ],
    "codex": [
        "CODEX_MODEL",
    ],
    "cursor": [
        "CURSOR_MODEL",
    ],
    "opencode": [
        "OPENCODE_MODEL",
        "OPENCODE_VARIANT",
    ],
    "qwen": [
        "OPENAI_BASE_URL",
        "OPENAI_MODEL",
    ],
}

# Agents offered for selection in the wizard. Derived from
# `agent_env_defaults` so the choice list can never drift from the set of
# agents the survey can actually configure env for — every selectable agent
# has env keys, and every agent with env keys is selectable. Order follows
# insertion order above (claude, codex first for backward-compatible UX).
_AGENTS = list(agent_env_defaults)


def _image_hints(image_tag: str) -> list[str]:
    """Complete every image name of ``image_defaults`` with ``image_tag``.

    Args:
        image_tag: The runtime minor tag appended to every image name.

    Returns:
        The completed hint list, in the ``image_defaults`` family order.
    """
    return [f"{name}:{image_tag}" for names in image_defaults.values() for name in names]


def _language_section() -> Question:
    """Build the language choice — the first section of every survey."""
    return Question(id="language", kind="choice", prompt="Language", choices=list(_LANGUAGES))


def _convention_section() -> QuestionGroup:
    """Build the base-convention gate — present only when no file exists."""
    return QuestionGroup(
        id="convention",
        prompt="--- Base Convention ---",
        children=[Question(id="adopt", kind="confirm", prompt="Download base convention", default=False)],
    )


def _codemanifest_section() -> QuestionGroup:
    """Build the codemanifest entries — usages pairs and annotations input.

    The records carry no defaults: the engine pre-fills both when the
    base-convention gate was accepted, not the tree.
    """
    return QuestionGroup(
        id="codemanifest",
        prompt="--- Codemanifest ---",
        children=[
            Question(id="usages", kind="pairs", prompt="Codemanifest usages (name → path)"),
            Question(id="annotations", kind="input", prompt="Codemanifest annotations"),
        ],
    )


def _executor_section(section_id: str, heading: str, agent_prompt: str, env_prompt: str) -> QuestionGroup:
    """Build one executor section — an agent choice plus its env pairs.

    Args:
        section_id: The section local name (build or pipeline).
        heading: The section heading prompt.
        agent_prompt: The agent choice prompt.
        env_prompt: The env pairs prompt.

    Returns:
        The executor section group.
    """
    return QuestionGroup(
        id=section_id,
        prompt=heading,
        children=[
            Question(id="agent", kind="choice", prompt=agent_prompt, choices=list(_AGENTS)),
            Question(id="env", kind="pairs", prompt=env_prompt),
        ],
    )


def _docker_image_section(image_tag: str, project_name: str | None) -> QuestionGroup:
    """Build the docker image section — the Dockerfile decision and names.

    The hints completed from ``image_tag`` are data of the tree — embedded
    in the ``base_image`` prompt with the last hint as its default; the
    engine renders them. The ``image`` default follows ``project_name``.

    Args:
        image_tag: The runtime minor tag completing the image hints.
        project_name: The git-derived project name; None offers no default.

    Returns:
        The docker image section group.
    """
    hints = _image_hints(image_tag)
    base_prompt = "\n".join(["Base image (FROM)", "Available images:", *[f"  - {hint}" for hint in hints]])
    image_default = f"{project_name}:latest" if project_name is not None else None

    return QuestionGroup(
        id="docker_image",
        prompt="--- Docker Image ---",
        children=[
            Question(id="dockerfile", kind="input", prompt="Dockerfile path", default=".goga/Dockerfile"),
            Question(id="base_image", kind="input", prompt=base_prompt, default=hints[-1]),
            Question(id="image", kind="input", prompt="Built image name", default=image_default),
        ],
    )


def _tools_section() -> Question:
    """Build the tools collection — name → version pairs in the version grammar.

    The prompt documents the four grammar forms of ``goga/version`` and the
    created files the collection drives (the config record and the
    ``.goga/tools/<tool>/`` configs of the invited tools).
    """
    prompt = "\n".join(
        [
            "Tools recorded in .goga/config.yml (name → version); "
            "invited tools contribute configs under .goga/tools/<tool>/",
            "Version forms: latest, N.x (newest within major N), N.M.x (newest patch within N.M), "
            "N.M or N.M.K (exact pin)",
            "An empty version reads as latest",
        ]
    )

    return Question(id="tools", kind="pairs", prompt=prompt)


def core_questions(image_tag: str, project_name: str | None, convention_exists: bool) -> QuestionGroup:
    """Build the core question tree of the onboarding session.

    Composes the eight core sections in survey order — language,
    convention, codemanifest, build, docker_image, pipeline, tools,
    usages. The convention section is omitted when the base conventions
    file already exists; the image hints are completed from ``image_tag``
    (never a hardcoded tag); the built-image name default follows
    ``project_name``.

    Args:
        image_tag: The current minor tag completing the image hints.
        project_name: The git-derived project name for the built-image name
            default; None offers no default.
        convention_exists: True when the base conventions file already
            exists (the convention section is omitted).

    Returns:
        The core tree — a group whose children are the core sections; the
        root id is never addressed in answers.
    """
    sections: list[Question | QuestionGroup] = [_language_section()]

    if not convention_exists:
        sections.append(_convention_section())

    sections.append(_codemanifest_section())
    sections.append(_executor_section("build", "--- Build ---", "Build agent", "Build environment variables"))
    sections.append(_docker_image_section(image_tag, project_name))
    sections.append(
        _executor_section("pipeline", "--- Pipeline ---", "Pipeline agent", "Pipeline environment variables")
    )
    sections.append(_tools_section())
    sections.append(QuestionGroup(id="usages", prompt="--- Usages ---"))

    return QuestionGroup(id="core", children=sections)
