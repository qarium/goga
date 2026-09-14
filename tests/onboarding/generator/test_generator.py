from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import requests
import yaml
from goga.config import load_project_config
from goga.onboarding.generator import CreatedFile, FileGenerator
from goga.onboarding.participation import ToolContribution, ToolParticipation
from goga.onboarding.questions import SessionAnswers

pytestmark = pytest.mark.usefixtures("_clean_cwd")


class TestContract:
    """Contract-level tests for the generator cell facade."""

    def test_file_generator_and_created_file_importable_from_facade(self) -> None:
        import goga.onboarding.generator as cell

        assert cell.FileGenerator is FileGenerator
        assert cell.CreatedFile is CreatedFile

    def test_facade_all_lists_both_names(self) -> None:
        import goga.onboarding.generator as facade

        assert facade.__all__ == ["CreatedFile", "FileGenerator"]

    def test_file_generator_constructs_with_no_arguments(self) -> None:
        assert isinstance(FileGenerator(), FileGenerator)

    def test_created_file_exposes_both_fields(self) -> None:
        record = CreatedFile(path="p", tool=None)

        assert record.path == "p"
        assert record.tool is None

    def test_created_file_carries_the_tool_identity(self) -> None:
        record = CreatedFile(path=".goga/tools/my-tool/service.yml", tool="my-tool")

        assert record.tool == "my-tool"

    def test_generator_methods_callable_on_the_instance(self) -> None:
        generator = FileGenerator()

        for name in ("generate", "generate_goga_config", "generate_tool_configs"):
            assert callable(getattr(generator, name))


class TestLogic:
    """Logic tests for the snapshot-driven generator — `_clean_cwd` filesystem."""

    def test_generate_writes_dockerfile_then_config(self) -> None:
        answers = SessionAnswers()
        answers.record("language", "python")
        answers.record(
            "docker_image",
            {
                "dockerfile": ".goga/Dockerfile",
                "base_image": "qarium/goga-python-3.13:1.3",
                "image": "my-app:latest",
            },
        )

        files = FileGenerator().generate(answers, [])

        assert Path(".goga/Dockerfile").read_text(encoding="utf-8") == "FROM qarium/goga-python-3.13:1.3\n"

        cfg = yaml.safe_load(Path(".goga/config.yml").read_text(encoding="utf-8"))
        assert cfg["language"] == "python"
        assert cfg["image"] == "my-app:latest"
        assert cfg["dockerfile"] == ".goga/Dockerfile"
        assert "base_image" not in cfg

        assert [f.path for f in files] == [".goga/Dockerfile", ".goga/config.yml"]
        assert all(f.tool is None for f in files)

    def test_generate_empty_language_is_clean_error(self) -> None:
        answers = SessionAnswers()
        answers.record("docker_image", {"image": "my-app:latest"})

        with pytest.raises(ValueError, match="language"):
            FileGenerator().generate(answers, [])

        assert not Path(".goga/config.yml").exists()

    def test_conventions_download_failure_names_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        answers = SessionAnswers()
        answers.record("language", "python")
        answers.record("codemanifest", {"usages": {"conventions": ".goga/usages/conventions.md"}})

        def _raise(url: str, timeout: int) -> None:
            raise requests.ConnectionError("down")

        monkeypatch.setattr(requests, "get", _raise)

        with pytest.raises(RuntimeError, match=r"https://raw\.githubusercontent\.com/.*/python/project\.md"):
            FileGenerator().generate(answers, [])

        assert not Path(".goga/config.yml").exists()

    def test_existing_config_skips_generation_returns_tool_files_only(self) -> None:
        Path(".goga").mkdir()
        Path(".goga/config.yml").write_text("language: python\n")

        answers = SessionAnswers()
        answers.record("language", "python")
        contribution = ToolContribution(tool="my-tool", invited=True, answers={})
        contribution.write_config("service.yml", {"token_source": "env"})

        files = FileGenerator().generate(answers, [contribution])

        assert [f.path for f in files] == [".goga/tools/my-tool/service.yml"]
        assert files[0].tool == "my-tool"
        assert Path(".goga/tools/my-tool/service.yml").exists()
        assert not Path(".goga/Dockerfile").exists()

    def test_skipped_base_image_collapses_dockerfile_branch(self) -> None:
        answers = SessionAnswers()
        answers.record("language", "python")
        answers.record(
            "docker_image",
            {"dockerfile": ".goga/Dockerfile", "image": "my-app:latest"},
        )

        FileGenerator().generate(answers, [])

        assert not Path(".goga/Dockerfile").exists()

        cfg = yaml.safe_load(Path(".goga/config.yml").read_text(encoding="utf-8"))
        assert "dockerfile" not in cfg
        assert cfg["image"] == "my-app:latest"

    def test_generate_maps_the_whole_snapshot_in_field_order(self) -> None:
        answers = SessionAnswers()
        answers.record("language", "python")
        answers.record(
            "docker_image",
            {"dockerfile": ".goga/Dockerfile", "base_image": "qarium/goga-python-3.13:1.3", "image": "my-app:latest"},
        )
        answers.record("build", {"agent": "claude", "env": {"API_KEY": "secret"}})
        answers.record("pipeline", {"agent": "codex", "env": {"CODEX_MODEL": "x"}})
        answers.record(
            "codemanifest",
            {
                "usages": {"custom": ".goga/usages/custom.md"},
                "annotations": "Use conventions for code writing rules.",
            },
        )
        answers.record("tools", {"my-tool": "latest"})
        answers.record("usages", {"cell": {"dep": {"git": "https://example.com/repo.git", "ref": "main"}}})

        FileGenerator().generate(answers, [])

        text = Path(".goga/config.yml").read_text(encoding="utf-8")
        cfg = yaml.safe_load(text)

        assert list(cfg.keys()) == [
            "language",
            "image",
            "dockerfile",
            "build",
            "pipeline",
            "codemanifest",
            "tools",
            "usages",
        ]
        assert cfg["build"] == {"task_executor": {"agent": "claude", "env": {"API_KEY": "secret"}}}
        assert cfg["pipeline"] == {"agent": "codex", "env": {"CODEX_MODEL": "x"}}
        assert cfg["codemanifest"]["usages"] == {"custom": ".goga/usages/custom.md"}
        assert cfg["codemanifest"]["annotations"] == "Use conventions for code writing rules.\n"
        assert "annotations: |" in text
        assert cfg["tools"] == {"my-tool": "latest"}
        assert cfg["usages"] == {"cell": {"dep": {"git": "https://example.com/repo.git", "ref": "main"}}}

    def test_annotations_without_usages_still_emit_the_codemanifest_block(self) -> None:
        """An annotations-only codemanifest section is emitted — no usages needed."""
        answers = SessionAnswers()
        answers.record("language", "python")
        answers.record("codemanifest", {"annotations": "Keep it small."})

        FileGenerator().generate(answers, [])

        text = Path(".goga/config.yml").read_text(encoding="utf-8")
        cfg = yaml.safe_load(text)

        assert list(cfg.keys()) == ["language", "codemanifest"]
        assert cfg["codemanifest"] == {"annotations": "Keep it small.\n"}
        assert "annotations: |" in text

    def test_conventions_download_writes_conventions_md_between_dockerfile_and_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        answers = SessionAnswers()
        answers.record("language", "python")
        answers.record(
            "docker_image",
            {
                "dockerfile": ".goga/Dockerfile",
                "base_image": "qarium/goga-python-3.13:1.3",
                "image": "my-app:latest",
            },
        )
        answers.record("codemanifest", {"usages": {"conventions": ".goga/usages/conventions.md"}})

        response = MagicMock()
        response.text = "# Python conventions"
        response.raise_for_status = MagicMock()
        monkeypatch.setattr(requests, "get", MagicMock(return_value=response))

        files = FileGenerator().generate(answers, [])

        assert Path(".goga/usages/conventions.md").read_text(encoding="utf-8") == "# Python conventions"
        assert [f.path for f in files] == [".goga/Dockerfile", ".goga/usages/conventions.md", ".goga/config.yml"]

    def test_written_config_passes_the_project_config_loader(self) -> None:
        answers = SessionAnswers()
        answers.record("language", "python")
        answers.record("docker_image", {"image": "my-app:latest"})
        answers.record("build", {"agent": "claude", "env": {"API_KEY": "secret"}})
        answers.record("tools", {"my-tool": "latest"})
        answers.record("usages", {"cell": {"dep": {"git": "https://example.com/repo.git"}}})

        FileGenerator().generate(answers, [])

        config = load_project_config()

        assert config.lang == "python"
        assert config.image == "my-app:latest"
        assert config.build is not None
        assert config.build.task_executor.agent == "claude"
        assert config.tools == {"my-tool": "latest"}
        assert config.usages is not None
        assert config.usages["cell"]["dep"].git == "https://example.com/repo.git"

    def test_generate_tool_configs_noop_on_empty_list(self) -> None:
        assert FileGenerator().generate_tool_configs([]) is None
        assert not Path(".goga").exists()

    def test_generate_tool_configs_with_attribution(self) -> None:
        answers = SessionAnswers()
        answers.record("language", "python")

        contribution = ToolContribution(tool="my-tool", invited=True, answers={})
        contribution.write_config("service.yml", {"token_source": "env"})
        contribution.write_config("service.yml", {"interval": 60})

        files = FileGenerator().generate(answers, [contribution])

        assert yaml.safe_load(Path(".goga/tools/my-tool/service.yml").read_text(encoding="utf-8")) == {"interval": 60}
        assert files[-1].tool == "my-tool"
        assert files[-1].path == ".goga/tools/my-tool/service.yml"


class TestToolFileSoftness:
    """The tool config write path never fails the session — drops with a warning."""

    def test_escaping_file_names_rejected_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Absolute and ``..`` names never leave the tool directory; the valid file still lands."""
        answers = SessionAnswers()
        answers.record("language", "python")

        contribution = ToolContribution(tool="my-tool", invited=True, answers={})
        contribution.write_config("/etc/cron.d/escape.yml", {"a": 1})
        contribution.write_config("../../escape.yml", {"b": 2})
        contribution.write_config("service.yml", {"c": 3})

        with caplog.at_level(logging.WARNING):
            files = FileGenerator().generate(answers, [contribution])

        assert [f.path for f in files] == [".goga/config.yml", ".goga/tools/my-tool/service.yml"]
        assert not Path("/etc/cron.d/escape.yml").exists()
        assert not (Path.cwd().parent.parent / "escape.yml").exists()

        rejected = [record.message for record in caplog.records if "rejected the config file" in record.message]
        assert len(rejected) == 2
        assert all("my-tool" in message for message in rejected)

    def test_unserializable_payload_dropped_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """A payload yaml cannot serialize drops its file only — the session output stands."""
        deep: dict = {}
        current = deep
        for _ in range(50_000):
            current["n"] = {}
            current = current["n"]

        answers = SessionAnswers()
        answers.record("language", "python")

        contribution = ToolContribution(tool="my-tool", invited=True, answers={})
        contribution.write_config("bad.yml", deep)
        contribution.write_config("service.yml", {"a": 1})

        with caplog.at_level(logging.WARNING):
            files = FileGenerator().generate(answers, [contribution])

        assert [f.path for f in files] == [".goga/config.yml", ".goga/tools/my-tool/service.yml"]
        assert not Path(".goga/tools/my-tool/bad.yml").exists()
        assert any(
            "my-tool" in record.message and "bad.yml" in record.message for record in caplog.records
        )

    def test_unwritable_target_dropped_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """A tool directory path occupied by a regular file fails softly — nothing crashes."""
        Path(".goga/tools").mkdir(parents=True)
        Path(".goga/tools/my-tool").write_text("not a directory\n", encoding="utf-8")

        answers = SessionAnswers()
        answers.record("language", "python")

        contribution = ToolContribution(tool="my-tool", invited=True, answers={})
        contribution.write_config("service.yml", {"a": 1})

        with caplog.at_level(logging.WARNING):
            files = FileGenerator().generate(answers, [contribution])

        assert [f.path for f in files] == [".goga/config.yml"]
        assert Path(".goga/tools/my-tool").read_text(encoding="utf-8") == "not a directory\n"
        assert any("my-tool" in record.message for record in caplog.records)


class TestStagedCommit:
    """The staged-commit story end to end — the cross-entity negative trace."""

    def test_failing_hook_discards_files_with_amendments(
        self,
        pin_package_environment,
        install_tool_package,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A hook that buffers then raises leaves nothing behind — the core config still stands."""

        def amend_boom(context: Any) -> None:
            context.answer("tools", {"my-tool": "latest"})
            context.write_config("x.yml", {"a": 1})
            raise RuntimeError("crash")

        def register_hooks(hooks: Any) -> None:
            hooks.subscribe("onboarding", "amend_config", "a1", amend_boom)

        pin_package_environment({"goga_tool_my_tool": ["goga-tool-my-tool"]})
        install_tool_package("goga_tool_my_tool", register_hooks=register_hooks)

        answers = SessionAnswers()
        answers.record("language", "python")

        with caplog.at_level(logging.WARNING):
            contributions = ToolParticipation(invited=["my-tool"]).collect_contributions(answers)

        FileGenerator().generate(answers, [])

        assert contributions == []
        assert "tools" not in answers.snapshot()
        assert not Path(".goga/tools").exists()

        cfg = yaml.safe_load(Path(".goga/config.yml").read_text(encoding="utf-8"))
        assert cfg == {"language": "python"}
        assert any("my-tool" in record.message for record in caplog.records)
