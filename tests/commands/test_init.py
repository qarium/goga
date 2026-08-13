from __future__ import annotations

import importlib
from unittest import mock

import click
from click.testing import CliRunner
from goga.onboarding.answers import GogaConfigAnswers, InitAnswers
from goga.onboarding.generator import FileGenerator
from goga.onboarding.logic import InitLogic
from goga.onboarding.questionnaire import Questionnaire

_cmd_init_module = importlib.import_module("goga.commands.init.init")


class TestContract:
    """Contract-level tests for init CLI command."""

    def test_init_importable_from_facade(self) -> None:
        from goga.commands.init import init

        assert callable(init)

    def test_init_is_click_command(self) -> None:
        from goga.commands.init import init

        assert isinstance(init, click.Command)

    def test_init_has_name_init(self) -> None:
        from goga.commands.init import init

        assert init.name == "init"

    def test_init_exposes_tpl_upgrade_ref_params(self) -> None:
        """The command surfaces the three declared click params."""
        from goga.commands.init import init

        arg_names = {p.name for p in init.params}
        arg_kinds = {p.name: p for p in init.params}

        assert "tpl" in arg_names
        assert "upgrade" in arg_names
        assert "ref" in arg_names
        # tpl is an (optional) argument; upgrade/ref are options
        assert isinstance(arg_kinds["tpl"], click.Argument)
        assert isinstance(arg_kinds["upgrade"], click.Option)
        assert isinstance(arg_kinds["ref"], click.Option)


class TestLogic:
    """Logic-level tests for init CLI command."""

    def test_init_cli_command(self, tmp_path, monkeypatch) -> None:
        """Successful init: exit_code == 0."""
        from goga.commands.init import init

        config = GogaConfigAnswers(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:0.1",
            pipeline_agent="claude",
            env={},
        )
        answers = InitAnswers(goga_config=config)

        mock_q = mock.MagicMock(spec=Questionnaire)
        mock_q.ask.return_value = answers

        gen = FileGenerator()
        gen._base_dir = tmp_path

        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(_cmd_init_module, "Questionnaire", return_value=mock_q),
            mock.patch.object(_cmd_init_module, "FileGenerator", return_value=gen),
        ):
            runner = CliRunner()
            result = runner.invoke(init, [])

        assert result.exit_code == 0

    def test_init_cli_returns_nonzero_on_failure(self, tmp_path, monkeypatch) -> None:
        """InitLogic.run() returns 1 → non-zero exit."""
        from goga.commands.init import init

        mock_logic = mock.MagicMock(spec=InitLogic)
        mock_logic.run.return_value = 1

        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(_cmd_init_module, "Questionnaire"),
            mock.patch.object(_cmd_init_module, "FileGenerator"),
            mock.patch.object(_cmd_init_module, "InitLogic", return_value=mock_logic),
        ):
            runner = CliRunner()
            result = runner.invoke(init, [])

        assert result.exit_code != 0

    def test_init_bare_onboarding_runs_full_flow(self, tmp_path, monkeypatch) -> None:
        """BARE_ONBOARDING (no args, clean cwd) runs InitLogic.run() → 0."""
        from goga.commands.init import init

        mock_logic = mock.MagicMock(spec=InitLogic)
        mock_logic.run.return_value = 0

        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(_cmd_init_module, "Questionnaire"),
            mock.patch.object(_cmd_init_module, "FileGenerator"),
            mock.patch.object(_cmd_init_module, "InitLogic", return_value=mock_logic),
        ):
            runner = CliRunner()
            result = runner.invoke(init, [])

        assert result.exit_code == 0
        mock_logic.run.assert_called_once()

    def test_init_scaffold_then_onboarding_runs_scaffold_first(
        self, tmp_path, monkeypatch
    ) -> None:
        """SCAFFOLD_THEN_ONBOARDING: Scaffold.generate runs before InitLogic.run."""
        from goga.commands.init import init

        mock_scaffold = mock.MagicMock()
        mock_scaffold.generate.return_value = 0

        mock_logic = mock.MagicMock(spec=InitLogic)
        mock_logic.run.return_value = 0

        order: list[str] = []

        def _gen(*args, **kwargs):
            order.append("generate")
            return 0

        def _run(*args, **kwargs):
            order.append("run")
            return 0

        mock_scaffold.generate.side_effect = _gen
        mock_logic.run.side_effect = _run

        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(_cmd_init_module, "Scaffold", return_value=mock_scaffold),
            mock.patch.object(_cmd_init_module, "InitLogic", return_value=mock_logic),
        ):
            runner = CliRunner()
            result = runner.invoke(init, ["https://example.com/tpl.git"])

        assert result.exit_code == 0
        mock_scaffold.generate.assert_called_once_with(
            "https://example.com/tpl.git", None
        )
        mock_logic.run.assert_called_once()
        assert order == ["generate", "run"]

    def test_init_scaffold_passes_ref_override_to_generate(
        self, tmp_path, monkeypatch
    ) -> None:
        """--ref is wired end-to-end to Scaffold.generate as ref_override."""
        from goga.commands.init import init

        mock_scaffold = mock.MagicMock()
        mock_scaffold.generate.return_value = 0
        mock_logic = mock.MagicMock(spec=InitLogic)
        mock_logic.run.return_value = 0

        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(_cmd_init_module, "Scaffold", return_value=mock_scaffold),
            mock.patch.object(_cmd_init_module, "InitLogic", return_value=mock_logic),
        ):
            runner = CliRunner()
            result = runner.invoke(
                init,
                ["https://example.com/tpl.git#v1.0", "--ref", "main"],
            )

        assert result.exit_code == 0
        mock_scaffold.generate.assert_called_once_with(
            "https://example.com/tpl.git#v1.0", "main"
        )

    def test_init_upgrade_passes_ref_to_scaffold_upgrade(
        self, tmp_path, monkeypatch
    ) -> None:
        """UPGRADE + --ref passes ref to Scaffold.upgrade; no onboarding."""
        from goga.commands.init import init

        mock_scaffold = mock.MagicMock()
        mock_scaffold.upgrade.return_value = 0
        mock_logic = mock.MagicMock(spec=InitLogic)

        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(_cmd_init_module, "Scaffold", return_value=mock_scaffold),
            mock.patch.object(_cmd_init_module, "InitLogic", return_value=mock_logic),
        ):
            runner = CliRunner()
            result = runner.invoke(init, ["--upgrade", "--ref", "v2.0"])

        assert result.exit_code == 0
        mock_scaffold.upgrade.assert_called_once_with("v2.0")
        mock_logic.run.assert_not_called()

    def test_init_rejects_tpl_and_upgrade_mutually_exclusive(self, tmp_path, monkeypatch) -> None:
        """tpl + --upgrade → nonzero, mutually exclusive message, no delegate."""
        from goga.commands.init import init

        mock_scaffold = mock.MagicMock()
        mock_logic = mock.MagicMock(spec=InitLogic)

        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(_cmd_init_module, "Scaffold", return_value=mock_scaffold),
            mock.patch.object(_cmd_init_module, "InitLogic", return_value=mock_logic),
        ):
            runner = CliRunner()
            result = runner.invoke(init, ["https://example.com/tpl.git", "--upgrade"])

        assert result.exit_code != 0
        assert "mutually exclusive" in result.output
        mock_scaffold.generate.assert_not_called()
        mock_logic.run.assert_not_called()

    def test_init_rejects_bare_ref(self, tmp_path, monkeypatch) -> None:
        """--ref with no <tpl> and no --upgrade → nonzero, --ref requires message."""
        from goga.commands.init import init

        mock_scaffold = mock.MagicMock()
        mock_logic = mock.MagicMock(spec=InitLogic)

        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(_cmd_init_module, "Scaffold", return_value=mock_scaffold),
            mock.patch.object(_cmd_init_module, "InitLogic", return_value=mock_logic),
        ):
            runner = CliRunner()
            result = runner.invoke(init, ["--ref", "main"])

        assert result.exit_code != 0
        assert "--ref requires" in result.output
        mock_scaffold.generate.assert_not_called()
        mock_scaffold.upgrade.assert_not_called()
        mock_logic.run.assert_not_called()

    def test_init_bare_in_existing_project_is_nonzero(self, tmp_path, monkeypatch) -> None:
        """BARE_ONBOARDING with .goga/ existing → nonzero, already initialized."""
        from goga.commands.init import init

        (tmp_path / ".goga").mkdir()

        mock_scaffold = mock.MagicMock()
        mock_logic = mock.MagicMock(spec=InitLogic)

        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(_cmd_init_module, "Scaffold", return_value=mock_scaffold),
            mock.patch.object(_cmd_init_module, "InitLogic", return_value=mock_logic),
        ):
            runner = CliRunner()
            result = runner.invoke(init, [])

        assert result.exit_code != 0
        assert "already initialized" in result.output
        mock_logic.run.assert_not_called()

    def test_init_upgrade_propagates_scaffold_nonzero(self, tmp_path, monkeypatch) -> None:
        """UPGRADE: Scaffold.upgrade returns 1 → exit 1, no onboarding."""
        from goga.commands.init import init

        mock_scaffold = mock.MagicMock()
        mock_scaffold.upgrade.return_value = 1
        mock_logic = mock.MagicMock(spec=InitLogic)

        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(_cmd_init_module, "Scaffold", return_value=mock_scaffold),
            mock.patch.object(_cmd_init_module, "InitLogic", return_value=mock_logic),
        ):
            runner = CliRunner()
            result = runner.invoke(init, ["--upgrade"])

        assert result.exit_code == 1
        mock_logic.run.assert_not_called()

    def test_init_tpl_skips_already_init_guard_in_existing_project(
        self, tmp_path, monkeypatch
    ) -> None:
        """SCAFFOLD_THEN_ONBOARDING: the already-init guard does NOT fire."""
        from goga.commands.init import init

        (tmp_path / ".goga").mkdir()

        mock_scaffold = mock.MagicMock()
        mock_scaffold.generate.return_value = 0
        mock_logic = mock.MagicMock(spec=InitLogic)
        mock_logic.run.return_value = 0

        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(_cmd_init_module, "Scaffold", return_value=mock_scaffold),
            mock.patch.object(_cmd_init_module, "InitLogic", return_value=mock_logic),
        ):
            runner = CliRunner()
            result = runner.invoke(init, ["https://example.com/tpl.git"])

        assert result.exit_code == 0
        assert "already initialized" not in result.output

    def test_init_upgrade_does_not_run_onboarding(self, tmp_path, monkeypatch) -> None:
        """UPGRADE (no ref): no onboarding, Scaffold.upgrade → 0."""
        from goga.commands.init import init

        mock_scaffold = mock.MagicMock()
        mock_scaffold.upgrade.return_value = 0
        mock_logic = mock.MagicMock(spec=InitLogic)

        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(_cmd_init_module, "Scaffold", return_value=mock_scaffold),
            mock.patch.object(_cmd_init_module, "InitLogic", return_value=mock_logic),
        ):
            runner = CliRunner()
            result = runner.invoke(init, ["--upgrade"])

        assert result.exit_code == 0
        mock_logic.run.assert_not_called()
