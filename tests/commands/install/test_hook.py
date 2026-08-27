"""Contract and logic tests for the hook routines declared in
``goga/commands/install/CODEMANIFEST`` with ``location: hook.py``:

- ``resolve_initiating_user() -> str`` — the actual person behind a possibly
  sudo-ed install (``SUDO_USER`` when set and non-empty, else the OS user)
- ``call_install_hook(tool: str, user: str) -> bool`` — dynamic
  ``goga_tool_<tool>`` facade import with signature-projected ``user``
  injection
- ``run_install_hooks(tools: list[str]) -> None`` — sequential runner with
  one initiating user per run and tool-context failure wrapping

The facade boundary is mocked at the import boundary per the
hook-fake construction rule: every fake ``install`` is a REAL function
declaring its parameters (a recorder appending to a list), never a bare
MagicMock — ``inspect.signature(MagicMock())`` is ``(*args, **kwargs)`` and
the signature projection would bare-call it.
"""

from __future__ import annotations

import inspect
import logging
import sys
import types
import typing
from unittest import mock

import pytest
from goga.commands.install import hook as hook_module

# --- Contract tests ---


class TestHookContract:
    def test_three_routines_exist_and_are_callable(self) -> None:
        """The three routines are defined on the hook module and callable."""
        assert callable(hook_module.resolve_initiating_user)
        assert callable(hook_module.run_install_hooks)
        assert callable(hook_module.call_install_hook)

    def test_module_carries_the_convention_logger(self) -> None:
        """``logger = logging.getLogger(__name__)`` — the module's own logger."""
        assert hook_module.logger.name == "goga.commands.install.hook"

    def test_resolve_initiating_user_signature(self) -> None:
        """``resolve_initiating_user() -> str``."""
        signature = inspect.signature(hook_module.resolve_initiating_user)
        assert list(signature.parameters) == []
        hints = typing.get_type_hints(hook_module.resolve_initiating_user)
        assert hints == {"return": str}

    def test_run_install_hooks_signature(self) -> None:
        """``run_install_hooks(tools: list[str]) -> None``."""
        signature = inspect.signature(hook_module.run_install_hooks)
        assert list(signature.parameters) == ["tools"]
        assert signature.parameters["tools"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        hints = typing.get_type_hints(hook_module.run_install_hooks)
        assert hints == {"tools": list[str], "return": type(None)}

    def test_call_install_hook_signature(self) -> None:
        """``call_install_hook(tool: str, user: str) -> bool``."""
        signature = inspect.signature(hook_module.call_install_hook)
        assert list(signature.parameters) == ["tool", "user"]
        for parameter in signature.parameters.values():
            assert parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        hints = typing.get_type_hints(hook_module.call_install_hook)
        assert hints == {"tool": str, "user": str, "return": bool}


# --- Logic tests — resolve_initiating_user ---


class TestResolveInitiatingUser:
    def test_resolve_initiating_user_prefers_sudo_user(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A set, non-empty ``SUDO_USER`` short-circuits before ``getpass``."""
        monkeypatch.setenv("SUDO_USER", "alice")

        def _raise_unresolvable() -> str:
            raise KeyError("no resolvable identity")

        with mock.patch.object(hook_module.getpass, "getuser", side_effect=_raise_unresolvable):
            assert hook_module.resolve_initiating_user() == "alice"

    def test_resolve_initiating_user_falls_back_to_os_user(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No (or set-but-empty) ``SUDO_USER`` → the OS user name."""
        monkeypatch.delenv("SUDO_USER", raising=False)
        with mock.patch.object(hook_module.getpass, "getuser", return_value="bob"):
            assert hook_module.resolve_initiating_user() == "bob"
        # Set but EMPTY is treated as unset — the OS user is the answer too.
        monkeypatch.setenv("SUDO_USER", "")
        with mock.patch.object(hook_module.getpass, "getuser", return_value="bob"):
            assert hook_module.resolve_initiating_user() == "bob"

    def test_resolve_initiating_user_identity_failure_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No fallback name is invented when identity resolution fails."""
        monkeypatch.delenv("SUDO_USER", raising=False)
        with (
            mock.patch.object(hook_module.getpass, "getuser", side_effect=KeyError("uid not found")),
            pytest.raises(KeyError),
        ):
            hook_module.resolve_initiating_user()


# --- Logic tests — call_install_hook ---


class TestCallInstallHook:
    def test_call_install_hook_injects_declared_user_keyword(self) -> None:
        """A declared keyword-capable ``user`` parameter receives the value."""
        calls: list[dict[str, str | None]] = []

        def _fake_install(user: str | None = None) -> None:
            calls.append({"user": user})

        fake_module = types.SimpleNamespace(install=_fake_install)
        with mock.patch.object(hook_module.importlib, "import_module", return_value=fake_module) as mock_import:
            invoked = hook_module.call_install_hook("fake", "alice")
        assert invoked is True
        assert calls == [{"user": "alice"}]
        mock_import.assert_called_once_with("goga_tool_fake")

    def test_call_install_hook_bare_call_when_no_user_parameter(self) -> None:
        """A hook without a ``user`` parameter is called with NO arguments."""
        calls: list[tuple[()]] = []

        def _fake_install() -> None:
            calls.append(())

        fake_module = types.SimpleNamespace(install=_fake_install)
        with mock.patch.object(hook_module.importlib, "import_module", return_value=fake_module):
            invoked = hook_module.call_install_hook("fake", "alice")
        assert invoked is True
        # The zero-parameter recorder proves the call carried no arguments —
        # any argument would have raised TypeError and propagated.
        assert calls == [()]

    def test_call_install_hook_positional_only_user_not_injected(self) -> None:
        """``def install(user, /)`` — positional-only is NOT keyword-capable."""
        calls: list[dict[str, str | None]] = []

        def _fake_install(user: str | None = None, /) -> None:
            calls.append({"user": user})

        fake_module = types.SimpleNamespace(install=_fake_install)
        with mock.patch.object(hook_module.importlib, "import_module", return_value=fake_module):
            invoked = hook_module.call_install_hook("fake", "alice")
        assert invoked is True
        # The bare call leaves the declared default — "alice" never arrives.
        assert calls == [{"user": None}]

    def test_call_install_hook_var_keyword_only_not_injected(self) -> None:
        """``def install(**kwargs)`` — ``**kwargs`` is NOT a declared opt-in."""
        calls: list[dict[str, object]] = []

        def _fake_install(**kwargs: object) -> None:
            calls.append(dict(kwargs))

        fake_module = types.SimpleNamespace(install=_fake_install)
        with mock.patch.object(hook_module.importlib, "import_module", return_value=fake_module):
            invoked = hook_module.call_install_hook("fake", "alice")
        assert invoked is True
        assert calls == [{}]

    def test_call_install_hook_missing_facade_module_skips_quietly(self) -> None:
        """A truly missing ``goga_tool_<tool>`` facade is a skip, not a failure."""
        error = ModuleNotFoundError("No module named 'goga_tool_ghost'", name="goga_tool_ghost")
        with mock.patch.object(hook_module.importlib, "import_module", side_effect=error):
            assert hook_module.call_install_hook("ghost", "alice") is False

    def test_call_install_hook_broken_facade_import_is_failure_not_skip(self) -> None:
        """A DIFFERENT missing module (the facade's own import broke) propagates."""
        error = ModuleNotFoundError("No module named 'dep'", name="dep")
        with (
            mock.patch.object(hook_module.importlib, "import_module", side_effect=error),
            pytest.raises(ModuleNotFoundError),
        ):
            hook_module.call_install_hook("fake", "alice")

    def test_call_install_hook_absent_or_non_callable_install_skips(self) -> None:
        """A facade without ``install``, or with a non-callable one, skips."""
        with mock.patch.object(hook_module.importlib, "import_module", return_value=types.SimpleNamespace()):
            assert hook_module.call_install_hook("fake", "alice") is False
        with mock.patch.object(
            hook_module.importlib,
            "import_module",
            return_value=types.SimpleNamespace(install="not-callable"),
        ):
            assert hook_module.call_install_hook("fake", "alice") is False

    def test_call_install_hook_hook_exception_propagates_unchanged(self) -> None:
        """Whatever the hook itself raises escapes untouched (no wrap here)."""

        def _fake_install(user: str | None = None) -> None:
            raise ValueError("boom")

        fake_module = types.SimpleNamespace(install=_fake_install)
        with (
            mock.patch.object(hook_module.importlib, "import_module", return_value=fake_module),
            pytest.raises(ValueError, match=r"^boom$"),
        ):
            hook_module.call_install_hook("fake", "alice")


# --- Logic tests — run_install_hooks ---


class TestRunInstallHooks:
    def test_run_install_hooks_order_and_shared_user(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Hooks run in order, every one seeing the SAME initiating user."""
        log: list[tuple[str, str | None]] = []

        def _install_a(user: str | None = None) -> None:
            log.append(("a", user))

        def _install_b(user: str | None = None) -> None:
            log.append(("b", user))

        # Real throwaway facades in sys.modules — the real importlib path
        # resolves them without touching the filesystem.
        monkeypatch.setitem(sys.modules, "goga_tool_a", types.SimpleNamespace(install=_install_a))
        monkeypatch.setitem(sys.modules, "goga_tool_b", types.SimpleNamespace(install=_install_b))
        monkeypatch.delenv("SUDO_USER", raising=False)
        with mock.patch.object(hook_module.getpass, "getuser", return_value="alice"):
            hook_module.run_install_hooks(["a", "b"])
        assert log == [("a", "alice"), ("b", "alice")]

    def test_run_install_hooks_stops_at_first_failure_with_tool_context(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The failing hook's exception is wrapped with its tool name; the rest never run."""
        log: list[str] = []

        def _boom(user: str | None = None) -> None:
            raise ValueError("boom")

        def _install_b(user: str | None = None) -> None:
            log.append("b")

        monkeypatch.setitem(sys.modules, "goga_tool_a", types.SimpleNamespace(install=_boom))
        monkeypatch.setitem(sys.modules, "goga_tool_b", types.SimpleNamespace(install=_install_b))
        monkeypatch.delenv("SUDO_USER", raising=False)
        with (
            mock.patch.object(hook_module.getpass, "getuser", return_value="alice"),
            pytest.raises(RuntimeError) as excinfo,
        ):
            hook_module.run_install_hooks(["a", "b"])
        assert str(excinfo.value) == "install hook for tool 'a' failed: boom"
        assert isinstance(excinfo.value.__cause__, ValueError)
        assert log == []

    def test_run_install_hooks_user_resolution_failure_not_wrapped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An identity-resolution failure is not a hook failure — no tool context."""
        monkeypatch.delenv("SUDO_USER", raising=False)
        with (
            mock.patch.object(hook_module.getpass, "getuser", side_effect=KeyError("uid not found")),
            pytest.raises(KeyError),
        ):
            hook_module.run_install_hooks(["a"])

    def test_run_install_hooks_empty_list_is_quiet_noop(self, caplog: pytest.LogCaptureFixture) -> None:
        """``[]`` — no user resolution, no import calls, no log lines."""
        with (
            mock.patch.object(hook_module, "resolve_initiating_user") as mock_resolve,
            mock.patch.object(hook_module.importlib, "import_module") as mock_import,
        ):
            hook_module.run_install_hooks([])
        mock_resolve.assert_not_called()
        mock_import.assert_not_called()
        assert caplog.records == []

    def test_run_install_hooks_log_levels_invoked_and_skipped(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """An invoked hook logs INFO; a quiet skip logs DEBUG only."""
        calls: list[str | None] = []

        def _fake_install(user: str | None = None) -> None:
            calls.append(user)

        def _fake_import(name: str) -> types.SimpleNamespace:
            if name == "goga_tool_present":
                return types.SimpleNamespace(install=_fake_install)
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)

        monkeypatch.delenv("SUDO_USER", raising=False)
        with (
            mock.patch.object(hook_module.importlib, "import_module", side_effect=_fake_import),
            mock.patch.object(hook_module.getpass, "getuser", return_value="alice"),
            caplog.at_level(logging.DEBUG, logger="goga.commands.install.hook"),
        ):
            hook_module.run_install_hooks(["present", "ghost"])
        assert calls == ["alice"]
        invoked = [r for r in caplog.records if r.message == "install hook invoked"]
        skipped = [r for r in caplog.records if r.message == "install hook skipped"]
        assert len(invoked) == 1
        assert invoked[0].levelno == logging.INFO
        assert invoked[0].tool == "present"
        assert len(skipped) == 1
        assert skipped[0].levelno == logging.DEBUG
        assert skipped[0].tool == "ghost"
