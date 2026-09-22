"""Contract and logic tests for the entity declared in
``goga/config/hooks/CODEMANIFEST`` with ``location: events.py``:

- ``ConfigHooks()`` — the checkpoint surface of the config domain: the
  staged per-tool delivery of the hard ``config/amend_config`` action over
  the platform facade

The delivery runs for real over the platform boundary fixtures of
``tests/hooks/conftest.py`` (re-exported by the zone test package) — the
registry, the registrars, and the delivery execute the actual platform
code; only the installed-packages mapping and the ``sys.modules`` entry of
a fake ``goga_tool_*`` package are pinned.
"""

from __future__ import annotations

import inspect

import pytest
from goga.config.hooks.events import ConfigHooks
from goga.config.hooks.overlay import AppliedAmendment
from goga.config.project import BuildConfig, LintConfig, ProjectConfig, load_project_config


def _authored(**overrides: object) -> ProjectConfig:
    """A minimal authored configuration — every optional branch absent.

    Args:
        overrides: field values layered over the silent base.

    Returns:
        The authored configuration of the run.
    """
    fields: dict[str, object] = {
        "language": "python",
        "image": None,
        "dockerfile": None,
        "build": None,
        "pipeline": None,
    }
    fields.update(overrides)
    return ProjectConfig(**fields)  # type: ignore[arg-type]


# --- Contract tests ---


class TestCheckpointContract:
    def test_surface_is_importable_from_the_declared_module(self) -> None:
        """The entity lives on the module the CODEMANIFEST declares."""
        from goga.config.hooks import events

        assert events.ConfigHooks is ConfigHooks

    def test_surface_carries_the_declared_method_signature(self) -> None:
        """The checkpoint takes exactly the declared parameter."""
        assert list(inspect.signature(ConfigHooks.amend_config).parameters) == ["self", "config"]

    def test_construction_enumerates_nothing(self, pin_package_environment) -> None:
        """Cheap construction — the package environment stays unread."""
        boundary = pin_package_environment({"goga_tool_demo": ["demo-dist"]})

        ConfigHooks()

        assert boundary.call_count == 0


# --- Logic tests: the checkpoint delivery (real platform) ---


class TestAmendConfigDelivery:
    def test_config_hooks_passthrough_without_subscriptions(
        self,
        pin_package_environment,
        tmp_path,
        monkeypatch,
    ) -> None:
        """No subscriptions — the passed configuration itself, nothing applied.

        The authored base is built by the real loader from a real
        ``.goga/config.yml`` in ``tmp_path``: the checkpoint observes the
        load moment exactly as a host-side command produces it.
        """
        pin_package_environment({})

        goga_dir = tmp_path / ".goga"
        goga_dir.mkdir()
        (goga_dir / "config.yml").write_text("language: python\n")
        monkeypatch.chdir(tmp_path)

        authored = load_project_config()
        overlay = ConfigHooks().amend_config(config=authored)

        assert overlay.config is authored  # the passed object itself
        assert overlay.applied == []
        assert overlay.summary_lines == []

    def test_subscribed_tool_with_empty_buffer_commits_nothing(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A subscribed hook that buffers nothing — silent, no warning, no empty contribution."""
        pin_package_environment({"goga_tool_silent": ["silent-dist"]})

        def register(hooks: object) -> None:
            def observe(context: object) -> None:
                _ = context.config.image  # the read surface delivers the authored values

            hooks.subscribe("config", "amend_config", "observe", observe)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_silent", register_hooks=register)

        authored = _authored()
        overlay = ConfigHooks().amend_config(config=authored)

        assert overlay.config is authored  # the passthrough — nothing committed
        assert overlay.applied == []
        assert overlay.summary_lines == []

    def test_per_tool_delivery_commits_buffered_amendments(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """One tool, two buffered amendments — both commit and merge in buffer order."""
        pin_package_environment({"goga_tool_hardener": ["goga-tool-hardener"]})

        def register(hooks: object) -> None:
            def harden(context: object) -> None:
                _ = context.config.build  # mutual blindness: the read is authored-only
                context.set("build.agent", "claude")
                context.force("lint.ignore", ["a/", "b/"])

            hooks.subscribe("config", "amend_config", "hardening", harden)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_hardener", register_hooks=register)

        overlay = ConfigHooks().amend_config(config=_authored())

        # The platform derives goga_tool_hardener -> hardener.
        assert overlay.config.build is not None
        assert overlay.config.build.agent == "claude"
        assert overlay.config.lint is not None
        assert overlay.config.lint.ignore == ["a/", "b/"]
        assert [(a.tool, a.path, a.intent) for a in overlay.applied] == [
            ("hardener", "build.agent", "set"),
            ("hardener", "lint.ignore", "forced"),
        ]
        assert overlay.summary_lines == [
            "config amendments: 2 applied",
            "- hardener set build.agent",
            "- hardener forced lint.ignore",
        ]

    def test_raising_hook_stops_command_names_tool_and_action(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The first failing tool stops the walk — later tools never run."""
        pin_package_environment({"goga_tool_boomer": ["boomer-dist"], "goga_tool_second": ["second-dist"]})
        calls: list[str] = []

        def register_boom(hooks: object) -> None:
            def boom(context: object) -> None:
                context.set("build.agent", "claude")
                raise RuntimeError("boom")

            hooks.subscribe("config", "amend_config", "hardening", boom)  # type: ignore[attr-defined]

        def register_second(hooks: object) -> None:
            def witness(context: object) -> None:
                calls.append("second-called")

            hooks.subscribe("config", "amend_config", "witness", witness)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_boomer", register_hooks=register_boom)
        install_tool_package("goga_tool_second", register_hooks=register_second)

        with pytest.raises(ValueError, match=r"hook hardening of tool boomer failed on config\.amend_config: boom"):
            ConfigHooks().amend_config(config=_authored())

        assert calls == []  # tool #2 never called; nothing committed, nothing merged

    def test_two_hooks_of_one_tool_commit_as_one_contribution(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The commit granularity is the tool — both hooks' buffers commit together, in buffer order."""
        pin_package_environment({"goga_tool_hardener": ["goga-tool-hardener"]})

        def register(hooks: object) -> None:
            def buffers_agent(context: object) -> None:
                context.set("build.agent", "claude")

            def buffers_ignore(context: object) -> None:
                context.force("lint.ignore", ["a/"])

            hooks.subscribe("config", "amend_config", "agent", buffers_agent)  # type: ignore[attr-defined]
            hooks.subscribe("config", "amend_config", "ignore", buffers_ignore)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_hardener", register_hooks=register)

        overlay = ConfigHooks().amend_config(config=_authored())

        assert [(a.tool, a.path, a.intent) for a in overlay.applied] == [
            ("hardener", "build.agent", "set"),
            ("hardener", "lint.ignore", "forced"),
        ]

    def test_failing_second_hook_discards_the_whole_tool_contribution(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A tool commits only after every hook — the first hook's buffer dies with the view.

        The buffered path is deliberately one the merge would reject loudly:
        had the contribution been committed and reached the merge, the error
        would carry ``amendment rejected``; the hook-failure message instead
        proves the failure preempts the merge entirely.
        """
        pin_package_environment({"goga_tool_flaky": ["flaky-dist"]})

        def register(hooks: object) -> None:
            def buffers(context: object) -> None:
                context.force("build.nonexistent", "claude")

            def explodes(context: object) -> None:
                raise RuntimeError("boom")

            hooks.subscribe("config", "amend_config", "buffers", buffers)  # type: ignore[attr-defined]
            hooks.subscribe("config", "amend_config", "explodes", explodes)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_flaky", register_hooks=register)

        with pytest.raises(ValueError, match=r"hook explodes of tool flaky failed on config\.amend_config: boom"):
            ConfigHooks().amend_config(config=_authored())

    def test_one_registry_per_surface_across_checkpoints(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Two checkpoints on one surface — the package enumeration runs exactly once."""
        boundary = pin_package_environment({"goga_tool_hardener": ["goga-tool-hardener"]})

        def register(hooks: object) -> None:
            def harden(context: object) -> None:
                context.set("build.agent", "claude")

            hooks.subscribe("config", "amend_config", "hardening", harden)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_hardener", register_hooks=register)

        surface = ConfigHooks()
        first = surface.amend_config(config=_authored())
        second = surface.amend_config(config=_authored())

        assert boundary.call_count == 1
        assert [(a.tool, a.path, a.intent) for a in first.applied] == [("hardener", "build.agent", "set")]
        assert first.applied == second.applied

    def test_delivered_configuration_is_deeply_read_only(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """No write channel into the authored tree — reads only, everywhere."""
        pin_package_environment({"goga_tool_mutator": ["mutator-dist"]})
        observed: dict[str, object] = {}

        def register(hooks: object) -> None:
            def mutate(context: object) -> None:
                try:
                    context.config.build.env["INJECTED"] = "1"
                    observed["mapping_write"] = "mutated"
                except TypeError:
                    observed["mapping_write"] = "blocked"
                try:
                    context.config.image = "x"
                    observed["attribute_write"] = "assigned"
                except Exception:
                    observed["attribute_write"] = "blocked"
                # A list write stays local to the view's fresh copy — the
                # authored list and the effective list are both untouched.
                context.config.lint.ignore.append("evil/")
                observed["reads"] = (
                    context.config.language,
                    context.config.build.env["A"],
                    context.config.lint.ignore == ["x/", "evil/"],
                )

            hooks.subscribe("config", "amend_config", "mutating", mutate)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_mutator", register_hooks=register)

        authored = _authored(build=BuildConfig(env={"A": "1"}), lint=LintConfig(ignore=["x/"]))
        overlay = ConfigHooks().amend_config(config=authored)

        assert observed["mapping_write"] == "blocked"
        assert observed["attribute_write"] == "blocked"
        assert observed["reads"] == ("python", "1", True)
        assert authored.build.env == {"A": "1"}
        assert authored.lint.ignore == ["x/"]
        assert overlay.config.build is not None
        assert overlay.config.build.env == {"A": "1"}
        assert overlay.config.lint is not None
        assert overlay.config.lint.ignore == ["x/"]
        assert overlay.applied == []  # nothing entered the effective config unrecorded

    def test_list_write_never_reaches_a_later_tool_view(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Mutual blindness across tools — a list write in one view dies with it.

        Enumeration is alphabetical (``goga_tool_a`` before ``goga_tool_b``),
        so the reading tool observes the state left by the mutating tool's
        in-place list write — which must be nothing: every tool reads its own
        fresh snapshot of the authored values.
        """
        pin_package_environment({"goga_tool_a": ["a-dist"], "goga_tool_b": ["b-dist"]})
        observed: dict[str, object] = {}

        def register_a(hooks: object) -> None:
            def mutate(context: object) -> None:
                context.config.lint.ignore.append("injected-by-a")

            hooks.subscribe("config", "amend_config", "mutating", mutate)  # type: ignore[attr-defined]

        def register_b(hooks: object) -> None:
            def read(context: object) -> None:
                observed["ignore"] = list(context.config.lint.ignore)

            hooks.subscribe("config", "amend_config", "reading", read)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_a", register_hooks=register_a)
        install_tool_package("goga_tool_b", register_hooks=register_b)

        authored = _authored(lint=LintConfig(ignore=["x/"]))
        overlay = ConfigHooks().amend_config(config=authored)

        assert observed["ignore"] == ["x/"]  # the authored values only, never tool a's write
        assert authored.lint.ignore == ["x/"]
        assert overlay.config.lint is not None
        assert overlay.config.lint.ignore == ["x/"]
        assert overlay.applied == []

    def test_within_tool_later_same_path_replaces_earlier(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The buffer keeps one entry per path — the later call replaces the earlier."""
        pin_package_environment({"goga_tool_hardener": ["goga-tool-hardener"]})

        def register(hooks: object) -> None:
            def harden(context: object) -> None:
                context.set("build.agent", "a")
                context.force("build.agent", "b")

            hooks.subscribe("config", "amend_config", "hardening", harden)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_hardener", register_hooks=register)

        overlay = ConfigHooks().amend_config(config=_authored())

        assert overlay.config.build is not None
        assert overlay.config.build.agent == "b"
        assert overlay.applied == [AppliedAmendment(tool="hardener", path="build.agent", intent="forced")]

    def test_structurally_malformed_contribution_wrapped_with_action(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A malformed contribution fails the merge — the wrapper adds the action, no duplication."""
        pin_package_environment({"goga_tool_hardener": ["goga-tool-hardener"]})

        def register(hooks: object) -> None:
            def harden(context: object) -> None:
                context.force("build.nonexistent", "claude")

            hooks.subscribe("config", "amend_config", "hardening", harden)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_hardener", register_hooks=register)

        with pytest.raises(
            ValueError,
            match=r"amendment rejected on config\.amend_config: tool hardener: amendment at 'build.nonexistent'",
        ):
            ConfigHooks().amend_config(config=_authored())
