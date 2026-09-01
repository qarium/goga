"""Contract and logic tests for the entities declared in
``goga/topics/CODEMANIFEST`` with ``location: publishing.py``:

- ``publish_topic(branch_name, todo, base_ref, commit_message, year)`` —
  the fast creation-and-publication cycle

Every git touchpoint is mocked at the import point per the ``convention``
practice — no git binary and no repository are touched; ``normalize_topic_slug``
stays real because it is a pure string transformation, and so does
``resolve_topic_file`` (a pure path composer). The recording doubles assert
the decision-before-mutation order, the exact delegation arguments, and the
full rollback of a failed publication.
"""

from __future__ import annotations

import inspect
import subprocess
import sys
import typing
from pathlib import Path
from unittest import mock

import click
import pytest
from goga.topics import publish_topic, publishing

# --- Shared scenario helpers ---


def _non_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make stdin a non-terminal — the re-ask path must abort cleanly."""
    monkeypatch.setattr(sys, "stdin", mock.Mock(**{"isatty.return_value": False}))


def _interactive(
    monkeypatch: pytest.MonkeyPatch, answers: list[str]
) -> mock.Mock:
    """Make stdin a terminal and answer the re-ask prompts in order."""
    monkeypatch.setattr(sys, "stdin", mock.Mock(**{"isatty.return_value": True}))
    prompt = mock.Mock(side_effect=answers)
    monkeypatch.setattr(click, "prompt", prompt)
    return prompt


class _Cycle:
    """Recording doubles of every mocked touchpoint of the fast cycle.

    Every double is attached to one parent recorder, so a scenario can
    assert the real call order across touchpoints — not just per-touchpoint
    counts.
    """

    def __init__(self) -> None:
        self.recorder = mock.Mock(name="fast-cycle")
        self.resolve_current_branch_name = self._attach(
            "resolve_current_branch_name", return_value="main"
        )
        self.check_branch_occupancy = self._attach(
            "check_branch_occupancy", return_value=None
        )
        self.check_slug_occupancy = self._attach(
            "check_slug_occupancy", return_value=None
        )
        self.origin_configured = self._attach("origin_configured", return_value=True)
        self.resolve_ref_commit = self._attach("resolve_ref_commit", return_value="<base>")
        self.commit_file_on_base = self._attach(
            "commit_file_on_base", return_value="<commit>"
        )
        self.create_branch_at_commit = self._attach("create_branch_at_commit")
        self.push_branch = self._attach("push_branch")
        self.delete_local_branch = self._attach("delete_local_branch")
        self.current_year = self._attach("current_year", return_value="2026")

    def _attach(self, name: str, **kwargs: object) -> mock.Mock:
        double = mock.Mock(**kwargs)
        self.recorder.attach_mock(double, name)
        return double


def _wire_cycle(monkeypatch: pytest.MonkeyPatch) -> _Cycle:
    """Patch publishing's import points with the recording doubles."""
    cycle = _Cycle()
    for name, double in vars(cycle).items():
        if hasattr(publishing, name):
            monkeypatch.setattr(publishing, name, double)
    return cycle


def _assert_no_mutation(cycle: _Cycle) -> None:
    """Assert none of the three mutations of the cycle ran."""
    cycle.commit_file_on_base.assert_not_called()
    cycle.create_branch_at_commit.assert_not_called()
    cycle.push_branch.assert_not_called()
    cycle.delete_local_branch.assert_not_called()


# --- Contract tests ---


class TestPublishingContract:
    def test_publish_topic_is_importable_from_the_cell_facade(self) -> None:
        """``publish_topic`` lives on the cell facade and in ``__all__``."""
        import goga.topics as cell

        assert cell.publish_topic is publish_topic
        expected = {
            "BoardRecord",
            "SwitchCandidate",
            "check_branch_occupancy",
            "check_slug_occupancy",
            "collect_topic_board",
            "create_topic",
            "ensure_topic",
            "publish_topic",
            "resolve_switch_candidates",
            "switch_topic",
        }
        assert set(cell.__all__) == expected
        assert "publish_topic" in cell.__all__

    def test_publish_topic_signature(self) -> None:
        """``publish_topic(branch_name, todo, base_ref, commit_message, year=None)``.

        ``commit_message`` carries no default — the design-review pin: the
        template is always an explicit argument. ``todo`` is required and
        non-empty at the call site; an empty todo is a clean error asking
        for it.
        """
        signature = inspect.signature(publish_topic)
        assert list(signature.parameters) == [
            "branch_name",
            "todo",
            "base_ref",
            "commit_message",
            "year",
        ]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
            for parameter in signature.parameters.values()
        )
        assert (
            signature.parameters["commit_message"].default is inspect.Parameter.empty
        )
        assert signature.parameters["year"].default is None
        hints = typing.get_type_hints(publish_topic)
        assert hints == {
            "branch_name": str,
            "todo": str,
            "base_ref": str,
            "commit_message": str,
            "year": str | None,
            "return": str,
        }

    def test_no_working_copy_write_in_publishing(self) -> None:
        """A shallow source guardrail against working-copy writes.

        This greps the module source for the write primitives and checks the
        write helper is not imported — it cannot catch every spelling
        (``os.makedirs``, ``Path.write_bytes``, a function-local import).
        The real invariant is pinned end-to-end by the dirty-tree snapshot
        of ``tests/integration/test_topic_workflows.py``; this guardrail only
        makes the obvious regressions fail fast.
        """
        assert not hasattr(publishing, "ensure_topic_dir")
        source = inspect.getsource(publishing)
        assert "write_text" not in source
        assert "mkdir" not in source

    def test_publishing_never_switches(self) -> None:
        """The switch primitives of the sibling paths stay unimported.

        An attribute check on the module — it fails when a switch helper is
        imported at module level, but a function-local import would evade it.
        The end-to-end guarantee lives in the integration snapshot.
        """
        for forbidden in (
            "create_and_switch_branch",
            "checkout_local_branch",
            "create_branch_from_remote_tracking",
        ):
            assert not hasattr(publishing, forbidden)


# --- Logic tests: the fast creation-and-publication cycle ---


class TestPublishTopic:
    @pytest.mark.parametrize(
        ("todo", "template", "expected_content", "expected_message"),
        [
            pytest.param(
                "Fix retries.",
                "goga: create topic {slug}",
                "Fix retries.\n",
                "goga: create topic feature-foo-bar",
                id="basic",
            ),
            pytest.param(
                "Fix retries.\n\nRetries ignore the cap.",
                "goga: create topic {slug}",
                "Fix retries.\n\nRetries ignore the cap.\n",
                "goga: create topic feature-foo-bar",
                id="multiline",
            ),
            pytest.param(
                "Fix retries.",
                "chore: fresh topic",
                "Fix retries.\n",
                "chore: fresh topic",
                id="no-placeholder",
            ),
        ],
    )
    def test_publish_topic_commits_todo_file(  # noqa: PLR0913, PLR0917 — the parametrized scenario columns
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        todo: str,
        template: str,
        expected_content: str,
        expected_message: str,
    ) -> None:
        """The cycle commits exactly one todo.md artifact — verbatim content.

        A multi-line todo reaches the commit verbatim plus one trailing
        newline; a template without the ``{slug}`` placeholder is used as
        is (plain ``str.replace`` — no format grammar).
        """
        monkeypatch.chdir(tmp_path)
        cycle = _wire_cycle(monkeypatch)
        cycle.resolve_ref_commit.return_value = "abc123"

        result = publish_topic(
            "Feature/Foo_Bar", todo, "origin/main", template, year="2026"
        )

        assert (
            cycle.commit_file_on_base.call_args.args[1]
            == ".goga/history/2026/feature-foo-bar/todo.md"
        )
        assert cycle.commit_file_on_base.call_args.args[2] == expected_content
        assert cycle.commit_file_on_base.call_args.args[3] == expected_message
        assert cycle.create_branch_at_commit.call_args.args[0] == "Feature/Foo_Bar"
        cycle.resolve_current_branch_name.assert_called_once_with()
        cycle.check_branch_occupancy.assert_called_once_with(
            "Feature/Foo_Bar", "feature-foo-bar", "2026"
        )
        cycle.check_slug_occupancy.assert_called_once_with("feature-foo-bar", "2026")
        cycle.origin_configured.assert_called_once_with()
        cycle.resolve_ref_commit.assert_called_once_with("origin/main")
        cycle.push_branch.assert_called_once_with("Feature/Foo_Bar")
        cycle.delete_local_branch.assert_not_called()
        # The parent recorder pins the cross-touchpoint order: every
        # decision precedes the first mutation, and the mutations run
        # build -> plant -> push.
        assert cycle.recorder.mock_calls == [
            mock.call.resolve_current_branch_name(),
            mock.call.check_branch_occupancy(
                "Feature/Foo_Bar", "feature-foo-bar", "2026"
            ),
            mock.call.check_slug_occupancy("feature-foo-bar", "2026"),
            mock.call.origin_configured(),
            mock.call.resolve_ref_commit("origin/main"),
            mock.call.commit_file_on_base(
                "abc123",
                ".goga/history/2026/feature-foo-bar/todo.md",
                expected_content,
                expected_message,
            ),
            mock.call.create_branch_at_commit("Feature/Foo_Bar", "<commit>"),
            mock.call.push_branch("Feature/Foo_Bar"),
        ]
        assert result == (
            "Created branch Feature/Foo_Bar and published topic 2026/feature-foo-bar"
        )
        assert "\n" not in result

    def test_publish_topic_empty_todo_clean_error_before_mutations(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An empty todo is one clean error — before every decision and mutation.

        The gate sits between the slug normalization and the current-branch
        check, so not a single git mutation and not even the origin probe
        of the decision chain runs — an empty todo means the caller never
        meant to publish anything.
        """
        monkeypatch.chdir(tmp_path)
        _non_interactive(monkeypatch)
        cycle = _wire_cycle(monkeypatch)

        with pytest.raises(click.ClickException) as raised:
            publish_topic("X", "", "origin/main", "tmpl")

        assert raised.value.message == (
            "the fast path needs a non-empty todo"
            " — pass the text or enter it interactively"
        )
        cycle.commit_file_on_base.assert_not_called()
        cycle.origin_configured.assert_not_called()
        _assert_no_mutation(cycle)

    def test_publish_topic_current_branch_hosting_slug_is_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The current branch hosting the slug: one clean error, no mutation."""
        monkeypatch.chdir(tmp_path)
        cycle = _wire_cycle(monkeypatch)
        cycle.resolve_current_branch_name.return_value = "Feature/Foo_Bar"

        with pytest.raises(click.ClickException) as raised:
            publish_topic("Feature/Foo_Bar", "T", "origin/main", "m")

        assert raised.value.message == (
            "branch Feature/Foo_Bar already hosts topic 2026/feature-foo-bar"
            " — the fast path is only for fresh work"
        )
        _assert_no_mutation(cycle)

    def test_publish_topic_conflict_without_terminal_fails_with_board_hint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An occupancy conflict without a terminal: the reason and the hint."""
        monkeypatch.chdir(tmp_path)
        _non_interactive(monkeypatch)
        cycle = _wire_cycle(monkeypatch)
        cycle.check_slug_occupancy.return_value = (
            "topic 'feature-foo-bar' of 2026 is already hosted by branch 'alpha'"
        )

        with pytest.raises(click.ClickException) as raised:
            publish_topic("Feature/Foo_Bar", "T", "origin/main", "m", "2026")

        assert raised.value.message == (
            "topic 'feature-foo-bar' of 2026 is already hosted by branch 'alpha'"
            " — run 'goga topics board' to see the board"
        )
        _assert_no_mutation(cycle)

    def test_publish_topic_branch_occupancy_conflict_skips_the_slug_oracle(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The oracle order: branch occupancy first — its conflict wins alone.

        The CODEMANIFEST pins the step: ``check_branch_occupancy`` runs
        before ``check_slug_occupancy`` and the first conflict wins, so a
        branch-occupancy conflict must leave the slug oracle unprobed —
        probing both would double the git invocations and blur the reason.
        """
        monkeypatch.chdir(tmp_path)
        _non_interactive(monkeypatch)
        cycle = _wire_cycle(monkeypatch)
        cycle.check_branch_occupancy.return_value = "branch 'Feature/Foo_Bar' already exists"

        with pytest.raises(click.ClickException) as raised:
            publish_topic("Feature/Foo_Bar", "T", "origin/main", "m", "2026")

        assert raised.value.message == (
            "branch 'Feature/Foo_Bar' already exists"
            " — run 'goga topics board' to see the board"
        )
        cycle.check_slug_occupancy.assert_not_called()
        _assert_no_mutation(cycle)

    def test_publish_topic_failed_push_rolls_back_and_surfaces_reason(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed push deletes the planted branch and keeps its reason."""
        monkeypatch.chdir(tmp_path)
        cycle = _wire_cycle(monkeypatch)
        cycle.push_branch.side_effect = subprocess.CalledProcessError(
            1, ["git", "push"], stderr="error: failed to push some refs"
        )

        with pytest.raises(click.ClickException) as raised:
            publish_topic("Feature/Foo_Bar", "T", "origin/main", "m", "2026")

        assert raised.value.message == "git failed: error: failed to push some refs"
        cycle.delete_local_branch.assert_called_once_with("Feature/Foo_Bar")

    def test_publish_topic_rollback_failure_still_surfaces_push_reason(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A rollback failure of its own is suppressed — the push reason wins."""
        monkeypatch.chdir(tmp_path)
        cycle = _wire_cycle(monkeypatch)
        cycle.push_branch.side_effect = subprocess.CalledProcessError(
            1, ["git", "push"], stderr="error: failed to push some refs"
        )
        cycle.delete_local_branch.side_effect = subprocess.CalledProcessError(
            128, ["git", "update-ref"], stderr="fatal: unable to delete"
        )

        with pytest.raises(click.ClickException) as raised:
            publish_topic("Feature/Foo_Bar", "T", "origin/main", "m", "2026")

        assert raised.value.message == "git failed: error: failed to push some refs"
        cycle.delete_local_branch.assert_called_once_with("Feature/Foo_Bar")

    def test_publish_topic_rollback_oserror_still_surfaces_push_reason(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An OS-level rollback failure is suppressed like a git one.

        The push guard catches every ``OSError``, so the rollback suppresses
        every ``OSError`` too — a ``PermissionError`` of the deletion (an
        ``OSError`` that is not a ``FileNotFoundError``) must not replace the
        in-flight push reason with its own message.
        """
        monkeypatch.chdir(tmp_path)
        cycle = _wire_cycle(monkeypatch)
        cycle.push_branch.side_effect = subprocess.CalledProcessError(
            1, ["git", "push"], stderr="error: failed to push some refs"
        )
        cycle.delete_local_branch.side_effect = PermissionError(
            "no more process handles"
        )

        with pytest.raises(click.ClickException) as raised:
            publish_topic("Feature/Foo_Bar", "T", "origin/main", "m", "2026")

        assert raised.value.message == "git failed: error: failed to push some refs"
        cycle.delete_local_branch.assert_called_once_with("Feature/Foo_Bar")

    def test_publish_topic_unresolvable_base_is_clean_error_before_mutations(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unresolvable base fails before any mutation was made."""
        monkeypatch.chdir(tmp_path)
        cycle = _wire_cycle(monkeypatch)
        cycle.resolve_ref_commit.side_effect = subprocess.CalledProcessError(
            128, ["git", "rev-parse"], stderr="fatal: Needed a single revision"
        )

        with pytest.raises(click.ClickException) as raised:
            publish_topic("Feature/Foo_Bar", "T", "no-such-ref", "m")

        assert raised.value.message == "git failed: fatal: Needed a single revision"
        _assert_no_mutation(cycle)

    def test_publish_topic_without_origin_is_clean_error_before_mutations(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No origin remote: one clean error, nothing mutated."""
        monkeypatch.chdir(tmp_path)
        cycle = _wire_cycle(monkeypatch)
        cycle.origin_configured.return_value = False

        with pytest.raises(click.ClickException) as raised:
            publish_topic("Feature/Foo_Bar", "T", "origin/main", "m")

        assert (
            raised.value.message
            == "origin is not configured — the fast mode publishes to origin"
        )
        _assert_no_mutation(cycle)

    def test_publish_topic_detached_head_does_not_interfere(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A detached HEAD reads ``None`` and stays out of the way."""
        monkeypatch.chdir(tmp_path)
        cycle = _wire_cycle(monkeypatch)
        cycle.resolve_current_branch_name.return_value = None

        result = publish_topic("Feature/Foo_Bar", "T", "origin/main", "m")

        assert result == (
            "Created branch Feature/Foo_Bar and published topic 2026/feature-foo-bar"
        )
        cycle.resolve_current_branch_name.assert_called_once_with()
        cycle.push_branch.assert_called_once_with("Feature/Foo_Bar")

    def test_publish_topic_reask_restarts_the_fast_cycle(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A re-asked name restarts the whole cycle — new branch, new slug."""
        monkeypatch.chdir(tmp_path)
        prompt = _interactive(monkeypatch, ["Feature/Baz"])
        cycle = _wire_cycle(monkeypatch)
        cycle.check_slug_occupancy.side_effect = [
            "topic 'feature-foo-bar' of 2026 is already hosted by branch 'alpha'",
            None,
        ]

        result = publish_topic("Feature/Foo_Bar", "T", "origin/main", "m", "2026")

        assert result == "Created branch Feature/Baz and published topic 2026/feature-baz"
        assert prompt.call_count == 1
        assert prompt.call_args.args[0] == "New branch name"
        cycle.create_branch_at_commit.assert_called_once_with("Feature/Baz", "<commit>")
        assert (
            cycle.commit_file_on_base.call_args.args[1]
            == ".goga/history/2026/feature-baz/todo.md"
        )
        assert cycle.commit_file_on_base.call_args.args[3] == "m"
        cycle.push_branch.assert_called_once_with("Feature/Baz")

    def test_publish_topic_empty_slug_reasks(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A name that normalizes to nothing re-asks — no board hint, no mutation."""
        monkeypatch.chdir(tmp_path)
        prompt = _interactive(monkeypatch, ["Feature/Baz"])
        cycle = _wire_cycle(monkeypatch)

        result = publish_topic("///", "T", "origin/main", "m")

        assert prompt.call_count == 1
        assert prompt.call_args.args[0] == "New branch name"
        cycle.create_branch_at_commit.assert_called_once_with("Feature/Baz", "<commit>")
        assert (
            cycle.commit_file_on_base.call_args.args[1]
            == ".goga/history/2026/feature-baz/todo.md"
        )
        assert cycle.commit_file_on_base.call_args.args[2] == "T\n"
        cycle.push_branch.assert_called_once_with("Feature/Baz")
        assert result == "Created branch Feature/Baz and published topic 2026/feature-baz"


# --- Infrastructure boundary ---


class TestPublishingInfrastructureBoundary:
    def test_missing_git_binary_surfaces_as_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing git binary during the cycle is a clean error."""
        monkeypatch.chdir(tmp_path)
        cycle = _wire_cycle(monkeypatch)
        cycle.resolve_ref_commit.side_effect = FileNotFoundError("git")

        with pytest.raises(click.ClickException) as raised:
            publish_topic("Feature/Foo_Bar", "T", "origin/main", "m")

        assert "git" in raised.value.message
        _assert_no_mutation(cycle)

    def test_unwritable_repository_surfaces_as_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An OS failure of the quarantined chain is a clean error.

        The temporary index of ``commit_file_on_base`` lives under ``.git`` —
        an unwritable repository directory raises ``PermissionError`` (an
        ``OSError``), which the boundary must fold into one clean error the
        way ``create_topic`` folds its ``mkdir`` failures, not a traceback.
        """
        monkeypatch.chdir(tmp_path)
        cycle = _wire_cycle(monkeypatch)
        cycle.commit_file_on_base.side_effect = PermissionError(13, "Permission denied")

        with pytest.raises(click.ClickException) as raised:
            publish_topic("Feature/Foo_Bar", "T", "origin/main", "m")

        assert raised.value.message.startswith("cannot complete the publication:")
        cycle.create_branch_at_commit.assert_not_called()
        cycle.push_branch.assert_not_called()

    def test_publish_topic_oserror_push_rolls_back_too(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An OS failure of the push rolls the planted branch back as well.

        ``push_branch`` can fail at spawn level (``PermissionError`` and kin
        are ``OSError`` subclasses) — the full-rollback guarantee covers
        every failed publication, not only git's own non-zero exits, or a
        branch nobody asked for would survive the error.
        """
        monkeypatch.chdir(tmp_path)
        cycle = _wire_cycle(monkeypatch)
        cycle.push_branch.side_effect = PermissionError(13, "Permission denied")

        with pytest.raises(click.ClickException) as raised:
            publish_topic("Feature/Foo_Bar", "T", "origin/main", "m", "2026")

        assert raised.value.message.startswith("cannot complete the publication:")
        cycle.delete_local_branch.assert_called_once_with("Feature/Foo_Bar")
