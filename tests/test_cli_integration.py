from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
from goga.cli import app

from tests.conftest import cwd as _cwd

SIMPLE_MANIFEST = """\
Usages: {}

Annotations: ""

---
"TestEntity()":
  location: entity.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Integration test cell
"""


class TestSchemaRegisteredInApp:
    def test_cli_schema_registered_in_app(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "schema" in result.output


class TestSchemaLinterCoexist:
    def test_cli_schema_linter_coexist(self) -> None:
        runner = CliRunner()

        with runner.isolated_filesystem() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "CODEMANIFEST").write_text(SIMPLE_MANIFEST, encoding="utf-8")

            with _cwd(tmp_path):
                schema_result = runner.invoke(app, ["schema"])

            assert schema_result.exit_code == 0
            schema_data = json.loads(schema_result.output)
            assert isinstance(schema_data, list)

            with _cwd(tmp_path):
                linter_result = runner.invoke(app, ["linter", "."])

            # Linter may exit 0 or 1 depending on whether it finds errors,
            # but it should not crash.
            assert linter_result.exit_code in (0, 1)
