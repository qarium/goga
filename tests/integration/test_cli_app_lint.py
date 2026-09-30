"""Integration: the config -> ast -> lint chain through the full ``goga`` CLI app.

Drives the real CLI entrypoint (``CliRunner().invoke(app, ["lint", ...])``)
rather than the ``lint`` command function directly, to verify the chain is
wired correctly through Click's group dispatch and the ``app`` facade. The
shared lint scaffolding (the manifest constants and writers) stays with the
command suite and is imported from it.
"""

from __future__ import annotations

from click.testing import CliRunner
from goga.cli import app

from tests.commands.conftest import write_codemanifest as _write_codemanifest
from tests.commands.lint.test_lint import (
    INVALID_CODEMANIFEST,
    MINIMAL_VALID_CODEMANIFEST,
    _write_goga_config,
)


class TestCliAppIntegration:
    """The config -> ast -> lint chain wired end-to-end through the ``goga`` CLI app."""

    def test_lint_app_end_to_end_ignores_directory(self, tmp_path) -> None:
        _write_goga_config(tmp_path, "language: python\nlint:\n  ignore:\n    - .venv/\n")
        _write_codemanifest(tmp_path, MINIMAL_VALID_CODEMANIFEST)
        venv_dir = tmp_path / ".venv"
        venv_dir.mkdir()
        _write_codemanifest(venv_dir, INVALID_CODEMANIFEST)

        runner = CliRunner()
        result = runner.invoke(app, ["lint", str(tmp_path)])

        assert result.exit_code == 0
        assert ".venv" not in result.output
