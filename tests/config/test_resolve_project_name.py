from __future__ import annotations

import inspect
import subprocess

# The owning module of ``resolve_project_name`` is ``goga.config.git.identity``.
# Patch ``subprocess.run`` on that module directly so the call-time lookup hits
# the fake (the real lookup target at call time). Per ``convention`` (mock the
# subprocess call in tests by patching the owning module).
import goga.config.git.identity as _identity_module
import pytest
from goga.config.git.identity import resolve_project_name


def _patch_run(monkeypatch: pytest.MonkeyPatch, fake) -> None:
    monkeypatch.setattr(_identity_module.subprocess, "run", fake)


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


class _RaisingRun:
    """A fake ``subprocess.run`` that raises ``CalledProcessError`` (check=True).

    The moved routine uses ``check=True``: a non-zero exit / no ``origin``
    remote surfaces as a raised :class:`subprocess.CalledProcessError` (a
    subclass of :class:`subprocess.SubprocessError`), NOT a non-raising result
    with ``returncode=1``.
    """

    def __init__(self, stdout: str = "") -> None:
        self._stdout = stdout
        self.calls: list[list[str]] = []

    def __call__(self, argv, **_kwargs):
        self.calls.append(list(argv))
        raise subprocess.CalledProcessError(1, argv, output=self._stdout)


class TestResolveProjectNameContract:
    """Contract: resolve_project_name is importable and typed str | None."""

    def test_importable_from_identity_module(self) -> None:
        assert callable(resolve_project_name)

    def test_return_annotation_is_str_or_none(self) -> None:
        # ``identity.py`` uses ``from __future__ import annotations`` so the
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
        # check=True: a non-zero exit / no origin raises CalledProcessError,
        # which the routine swallows into None.
        _patch_run(monkeypatch, _RaisingRun())
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
