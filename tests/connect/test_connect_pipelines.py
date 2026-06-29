"""Contract and logic tests for wiring ``install_pipelines`` into ``connect``.

These cover the changed step 3 (install shared pipelines once after the agent loop)
and step 4 (propagate ``install_pipelines`` exit code into ``connect``'s return
value) without altering the ``connect`` signature.
"""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from unittest import mock

from goga.connect import connect

_install_mod = importlib.import_module("goga.connect.connect")
_install_pipelines_mod = importlib.import_module("goga.connect.install_pipelines")


def _create_agent_resources(target: Path) -> Path:
    """Create a minimal ``goga/assets/`` source tree so the agent loop succeeds."""
    source = target / "goga" / "assets"
    (source / "commands").mkdir(parents=True)
    (source / "commands" / "build.md").write_text("# build command")
    (source / "skills" / "goga-cell").mkdir(parents=True)
    (source / "skills" / "goga-cell" / "SKILL.md").write_text("# cell skill")
    (source / "skills" / "goga-cell" / "dsl.md").parent.mkdir(parents=True, exist_ok=True)
    return source


class TestConnectPipelinesContract:
    def test_connect_importable_from_facade(self) -> None:
        """connect remains importable from the goga.connect facade."""
        assert connect is not None

    def test_connect_signature_unchanged(self) -> None:
        """connect signature stays (agents, force_overwrite=False)."""
        signature = inspect.signature(connect)
        parameters = list(signature.parameters)

        assert parameters == ["agents", "force_overwrite"]
        assert signature.parameters["force_overwrite"].default is False

    def test_connect_returns_int(self, tmp_path: Path, monkeypatch) -> None:
        """connect returns 0 on a successful single-agent install."""
        _create_agent_resources(tmp_path)
        mock_source = tmp_path / "goga" / "assets"
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setattr(_install_pipelines_mod, "_get_internal_pipelines_dir", lambda: tmp_path / "none")

        with (
            mock.patch.object(_install_mod, "_get_source_dir", return_value=mock_source),
            mock.patch.object(_install_mod, "_download_dsl_spec"),
        ):
            exit_code = connect(["claude"])

        assert exit_code == 0


class TestConnectPipelinesLogic:
    def test_connect_installs_pipelines_into_user_goga_dir(self, tmp_path: Path, monkeypatch) -> None:
        """connect recreates ~/.goga/pipelines/ and copies at least one pipeline."""
        _create_agent_resources(tmp_path)
        mock_source = tmp_path / "goga" / "assets"

        # Redirect install_pipelines' internal source to a dir with a pipeline.
        internal_pipelines = tmp_path / "internal_pipelines"
        internal_pipelines.mkdir()
        (internal_pipelines / "deploy.yml").write_text("deploy")
        monkeypatch.setattr(_install_pipelines_mod, "_get_internal_pipelines_dir", lambda: internal_pipelines)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with (
            mock.patch.object(_install_mod, "_get_source_dir", return_value=mock_source),
            mock.patch.object(_install_mod, "_download_dsl_spec"),
        ):
            exit_code = connect(["claude"])

        assert exit_code == 0
        pipelines_dir = tmp_path / ".goga" / "pipelines"
        assert pipelines_dir.is_dir()
        assert (pipelines_dir / "deploy.yml").read_text() == "deploy"

    def test_connect_propagates_force_overwrite_to_install_pipelines(self, tmp_path: Path, monkeypatch) -> None:
        """connect forwards force_overwrite to install_pipelines."""
        _create_agent_resources(tmp_path)
        mock_source = tmp_path / "goga" / "assets"
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with (
            mock.patch.object(_install_mod, "_get_source_dir", return_value=mock_source),
            mock.patch.object(_install_mod, "_download_dsl_spec"),
            mock.patch.object(_install_mod, "install_pipelines", return_value=0) as mock_pipelines,
        ):
            connect(["claude"], force_overwrite=True)

        mock_pipelines.assert_called_once()
        assert mock_pipelines.call_args.kwargs["force_overwrite"] is True

    def test_connect_returns_nonzero_when_install_pipelines_fails(self, tmp_path: Path, monkeypatch) -> None:
        """A failing install_pipelines makes connect return 1 even if agents succeeded."""
        _create_agent_resources(tmp_path)
        mock_source = tmp_path / "goga" / "assets"
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with (
            mock.patch.object(_install_mod, "_get_source_dir", return_value=mock_source),
            mock.patch.object(_install_mod, "_download_dsl_spec"),
            mock.patch.object(_install_mod, "install_pipelines", return_value=1),
        ):
            exit_code = connect(["claude"])

        assert exit_code == 1

    def test_connect_runs_install_pipelines_once_for_multiple_agents(self, tmp_path: Path, monkeypatch) -> None:
        """install_pipelines is invoked exactly once regardless of agent count."""
        _create_agent_resources(tmp_path)
        mock_source = tmp_path / "goga" / "assets"
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with (
            mock.patch.object(_install_mod, "_get_source_dir", return_value=mock_source),
            mock.patch.object(_install_mod, "_download_dsl_spec"),
            mock.patch.object(_install_mod, "install_pipelines", return_value=0) as mock_pipelines,
        ):
            connect(["claude", "codex"])

        assert mock_pipelines.call_count == 1
