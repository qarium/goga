from __future__ import annotations

import inspect
import sys

import pytest
from goga.pipeline.run_pipeline import resolve_project_name

# ``goga.pipeline.run_pipeline`` is shadowed in the package ``__init__`` by the
# ``run_pipeline`` function, so a dotted-string ``monkeypatch.setattr`` path
# walking through ``goga.pipeline.run_pipeline`` resolves to the function (not
# the module) and fails to find ``subprocess``. Resolve the real module via
# ``sys.modules`` and patch its ``subprocess.run`` attribute directly (the real
# lookup target at call time). Per [[feedback_mock_patch_module_shadowing]].
_run_pipeline_module = sys.modules["goga.pipeline.run_pipeline"]


def _patch_run(monkeypatch: pytest.MonkeyPatch, fake) -> None:
    monkeypatch.setattr(_run_pipeline_module.subprocess, "run", fake)


class _Result:
    """A fake :class:`subprocess.CompletedProcess` (returncode + stdout)."""

    def __init__(self, returncode: int, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout


class _RecordingRun:
    """A fake ``subprocess.run`` recording every argv it is handed."""

    def __init__(self, returncode: int = 0, stdout: str = "") -> None:
        self._returncode = returncode
        self._stdout = stdout
        self.calls: list[list[str]] = []

    def __call__(self, argv, **_kwargs) -> _Result:
        self.calls.append(list(argv))
        return _Result(self._returncode, self._stdout)


class TestResolveProjectNameContract:
    """Contract: resolve_project_name is importable and typed str | None."""

    def test_importable_from_run_pipeline_module(self) -> None:
        assert callable(resolve_project_name)

    def test_return_annotation_is_str_or_none(self) -> None:
        # ``run_pipeline.py`` uses ``from __future__ import annotations`` so the
        # return annotation is the string ``"str | None"`` at runtime.
        annotation = inspect.signature(resolve_project_name).return_annotation
        assert annotation == "str | None"

    def test_invokes_git_config_for_origin_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = _RecordingRun(0, "https://github.com/acme/widget.git\n")
        _patch_run(monkeypatch, fake)
        resolve_project_name()
        assert len(fake.calls) == 1
        assert fake.calls[0] == ["git", "config", "--get", "remote.origin.url"]


class TestResolveProjectNameLogic:
    """Logic: name derivation + never-raise failure modes."""

    def test_strips_git_suffix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_run(monkeypatch, _RecordingRun(0, "https://github.com/acme/widget.git\n"))
        assert resolve_project_name() == "widget"

    def test_ssh_url_strips_git_suffix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_run(monkeypatch, _RecordingRun(0, "git@github.com:acme/widget.git\n"))
        assert resolve_project_name() == "widget"

    def test_url_without_git_suffix_is_used_verbatim(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_run(monkeypatch, _RecordingRun(0, "https://github.com/acme/widget\n"))
        assert resolve_project_name() == "widget"

    def test_returns_none_when_no_remote(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_run(monkeypatch, _RecordingRun(1, ""))
        assert resolve_project_name() is None

    def test_trailing_slash_url_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # basename("https://github.com/acme/") == "" → None (graceful, no prefix).
        _patch_run(monkeypatch, _RecordingRun(0, "https://github.com/acme/\n"))
        assert resolve_project_name() is None

    def test_empty_result_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_run(monkeypatch, _RecordingRun(0, "\n"))
        assert resolve_project_name() is None

    def test_missing_git_binary_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def raise_filenotfound(_argv, **_kwargs) -> _Result:
            raise FileNotFoundError(2, "No such file or directory: 'git'")

        _patch_run(monkeypatch, raise_filenotfound)
        assert resolve_project_name() is None
