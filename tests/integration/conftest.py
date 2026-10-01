"""Shared fixtures of the integration suites — the hooks platform boundary.

Re-exports the two boundary fixtures of the hooks platform tests
(``pin_package_environment`` / ``install_tool_package``) so the integration
suites pin the same two outside-world points — the ``packages_distributions``
read and the ``sys.modules`` entry of a fake ``goga_tool_*`` package — with
the platform delivery under test running for real.

Also carries the scaffolding shared by the end-to-end suites of this zone: the
synthetic vendored ralphex sources, the minimal ``.goga/config.yml`` and home
config writers, and the minimal ``ProjectConfig`` factory.
"""

import sys
from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from unittest import mock

import pytest
import yaml
from goga.config import BuildConfig, PipelineConfig, ProjectConfig

from tests.hooks.conftest import install_tool_package, pin_package_environment  # noqa: F401

# --- shared vendored-ralphex scaffolding of the end-to-end build suites ---

_ROLES = ("quality", "implementation", "testing", "simplification", "documentation")

# Synthetic stand-ins for the vendored ralphex v1.6.1 review prompts, carrying
# the literal counter fragments the role filter adapts (see .goga/usages/cooks/
# ralphex.md § Review prompt composition). The real assets are a maintainers'
# artifact; tests never depend on it.
_REVIEW_FIRST_TEMPLATE = (
    "# first review prompt\n"
    "launches 5 parallel reviewer agents\n"
    "Launch ALL 5 Review Agents\n"
    "All 5 agent invocations\n" + "".join(f"{{{{agent:{role}}}}}\n" for role in _ROLES) + "until ALL 5 agents\n"
)

_REVIEW_SECOND_TEMPLATE = (
    "# second review prompt\n"
    "uses 2 agents\n"
    "Both agent invocations\n"
    "{{agent:quality}}\n"
    "{{agent:implementation}}\n"
    "until both complete\n"
    "until BOTH agents\n"
    "emit them both in one response\n"
)


@pytest.fixture
def mock_vendored_sources(tmp_path: Path) -> Callable[[], AbstractContextManager[None]]:
    """Factory: context manager pointing the vendored ralphex defaults at tmp sources.

    ``build()`` fully rewrites ``.ralphex/prompts|agents/`` from the vendored
    defaults, so the two constants are patched at this external boundary with
    synthetic sources under ``tmp_path`` (the real assets are a maintainers'
    artifact outside the tests).
    """

    @contextmanager
    def _mock_vendored_sources() -> AbstractContextManager[None]:
        from goga.build import ralphex_runtime

        prompts_dir = tmp_path / "vendored-prompts"
        agents_dir = tmp_path / "vendored-agents"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        agents_dir.mkdir(parents=True, exist_ok=True)
        (prompts_dir / "task.txt").write_text("# task prompt\n")
        (prompts_dir / "codex.txt").write_text("# codex review prompt\n")
        (prompts_dir / "review_first.txt").write_text(_REVIEW_FIRST_TEMPLATE)
        (prompts_dir / "review_second.txt").write_text(_REVIEW_SECOND_TEMPLATE)

        for role in _ROLES:
            (agents_dir / f"{role}.txt").write_text(f"# {role} agent definition\n")

        with (
            mock.patch.object(ralphex_runtime, "_VENDORED_PROMPTS", prompts_dir),
            mock.patch.object(ralphex_runtime, "_VENDORED_AGENTS", agents_dir),
        ):
            yield

    return _mock_vendored_sources


# --- shared config writers of the integration suites ---


@pytest.fixture
def write_goga_config(tmp_path: Path) -> Callable[..., Path]:
    """Factory: write the minimal two-part ``.goga/config.yml`` into ``tmp_path``.

    The shared shape of the integration suites: ``language`` with a top-level
    ``image``, a ``build`` block carrying its ``agent`` plus the optional
    ``review`` / ``env`` sub-blocks, a ``pipeline`` block on the same agent,
    and the optional top-level ``dockerfile``. Returns ``tmp_path`` (the
    project root tests chdir into).
    """

    def _write(
        *,
        agent: str = "claude",
        image: str = "qarium/goga:latest",
        review: dict | None = None,
        build_env: dict[str, str] | None = None,
        dockerfile: str | None = None,
    ) -> Path:
        build_block: dict = {"agent": agent}

        if review is not None:
            build_block["review"] = review
        if build_env is not None:
            build_block["env"] = build_env

        data: dict = {
            "language": "python",
            "image": image,
            "build": build_block,
            "pipeline": {"agent": agent},
        }
        if dockerfile is not None:
            data["dockerfile"] = dockerfile

        goga_dir = tmp_path / ".goga"
        goga_dir.mkdir(parents=True, exist_ok=True)
        (goga_dir / "config.yml").write_text(yaml.dump(data))
        return tmp_path

    return _write


@pytest.fixture
def write_home_config() -> Callable[[dict], None]:
    """Factory: write ``~/.goga/config.yml`` with the given data.

    The home root is ``Path.home()`` resolved at write time — the isolated
    HOME of the shared ``_isolate_home`` autouse fixture.
    """

    def _write(data: dict) -> None:
        goga = Path.home() / ".goga"
        goga.mkdir(parents=True, exist_ok=True)
        (goga / "config.yml").write_text(yaml.dump(data))

    return _write


# --- shared in-container run context of the pipeline run-path suites ---


@pytest.fixture
def in_container_pipeline_run_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pin_package_environment,  # noqa: F811 — the factory fixture, shadowing the re-export above
) -> Path:
    """Provide the authored project configuration of the in-container run path.

    ``run_pipeline`` opens with the ``./.goga/config.yml`` load and the
    config-amendment delivery, and writes the afm configuration file at the
    fixed in-container home path. The in-container-half scenarios that drive
    the real chain (``pipeline_cli run`` → ``run_pipeline`` → ``run_flow``,
    only afm mocked) opt into this context: a minimal authored configuration
    (``language`` plus an empty ``pipeline`` section — the section the host
    structural guard guarantees) lands in the isolated process CWD, the
    package environment pins empty (the delivery is the passthrough), and the
    fixed home-path constant redirects into the tmp tree so no test writes
    the real home.

    Returns:
        The project root (the isolated CWD) carrying the written configuration.
    """
    goga_dir = tmp_path / ".goga"
    goga_dir.mkdir(parents=True, exist_ok=True)
    (goga_dir / "config.yml").write_text("language: python\npipeline: {}\n")
    pin_package_environment({})

    afm_config_module = sys.modules["goga.pipeline.afm_config"]
    monkeypatch.setattr(afm_config_module, "_AFM_CONFIG_PATH", tmp_path / ".afm-home" / "config.yaml")
    return tmp_path


# --- shared ProjectConfig factory of the integration suites ---


@pytest.fixture
def make_project_config() -> Callable[..., ProjectConfig]:
    """Factory: a minimal valid ``ProjectConfig`` for the build/pipeline flows."""

    def _make(
        *,
        image: str | None = "qarium/goga:latest",
        dockerfile: str | None = None,
        pipeline_agent: str = "claude",
        pipeline_env: dict[str, str] | None = None,
    ) -> ProjectConfig:
        return ProjectConfig(
            language="python",
            image=image,
            dockerfile=dockerfile,
            build=BuildConfig(agent="claude"),
            pipeline=PipelineConfig(agent=pipeline_agent, env=pipeline_env or {}),
        )

    return _make
