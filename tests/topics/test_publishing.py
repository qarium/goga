"""Contract and logic tests for the entities declared in
``goga/topics/CODEMANIFEST`` with ``location: publishing.py``:

- ``publish_topic(branch_name, title, base_ref, commit_message, year)`` —
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
    """Recording doubles of every mocked touchpoint of the fast cycle."""

    def __init__(self) -> None:
        self.resolve_current_branch_name = mock.Mock(return_value="main")
        self.check_branch_occupancy = mock.Mock(return_value=None)
        self.check_slug_occupancy = mock.Mock(return_value=None)
        self.origin_configured = mock.Mock(return_value=True)
        self.resolve_ref_commit = mock.Mock(return_value="<base>")
        self.commit_file_on_base = mock.Mock(return_value="<commit>")
        self.create_branch_at_commit = mock.Mock()
        self.push_branch = mock.Mock()
        self.delete_local_branch = mock.Mock()
        self.current_year = mock.Mock(return_value="2026")


def _wire_cycle(monkeypatch: pytest.MonkeyPatch) -> _Cycle:
    """Patch publishing's import points with the recording doubles."""
    cycle = _Cycle()
    for name, double in vars(cycle).items():
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
        """``publish_topic(branch_name, title, base_ref, commit_message, year=None)``.

        ``commit_message`` carries no default — the design-review pin: the
        template is always an explicit argument.
        """
        signature = inspect.signature(publish_topic)
        assert list(signature.parameters) == [
            "branch_name",
            "title",
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
            "title": str,
            "base_ref": str,
            "commit_message": str,
            "year": str | None,
            "return": str,
        }

    def test_no_working_copy_write_in_publishing(self) -> None:
        """The quarantined cycle writes nothing to the working copy."""
        assert not hasattr(publishing, "ensure_topic_dir")
        source = inspect.getsource(publishing)
        assert "write_text" not in source
        assert "mkdir" not in source

    def test_publishing_never_switches(self) -> None:
        """No switch, checkout, or reset primitive reaches the fast cycle."""
        for forbidden in (
            "create_and_switch_branch",
            "checkout_local_branch",
            "create_branch_from_remote_tracking",
        ):
            assert not hasattr(publishing, forbidden)


# --- Logic tests: the fast creation-and-publication cycle ---


class TestPublishTopic:
    def test_publish_topic_happy_path_builds_plants_and_pushes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A free name: resolve, build, plant, push — in that exact order."""
        monkeypatch.chdir(tmp_path)
        cycle = _wire_cycle(monkeypatch)

        result = publish_topic(
            "Feature/Foo_Bar", "Payment retry", "origin/main", "goga: create topic {slug}"
        )

        cycle.resolve_current_branch_name.assert_called_once_with()
        cycle.check_branch_occupancy.assert_called_once_with(
            "Feature/Foo_Bar", "feature-foo-bar", "2026"
        )
        cycle.check_slug_occupancy.assert_called_once_with("feature-foo-bar", "2026")
        cycle.origin_configured.assert_called_once_with()
        cycle.resolve_ref_commit.assert_called_once_with("origin/main")
        cycle.commit_file_on_base.assert_called_once_with(
            "<base>",
            ".goga/history/2026/feature-foo-bar/title.txt",
            "Payment retry\n",
            "goga: create topic feature-foo-bar",
        )
        cycle.create_branch_at_commit.assert_called_once_with(
            "Feature/Foo_Bar", "<commit>"
        )
        cycle.push_branch.assert_called_once_with("Feature/Foo_Bar")
        cycle.delete_local_branch.assert_not_called()
        assert result == (
            "Created branch Feature/Foo_Bar and published topic 2026/feature-foo-bar"
        )
        assert "\n" not in result

    @pytest.mark.parametrize(
        ("template", "expected"),
        [
            ("chore: new topic", "chore: new topic"),
            ("chore: new topic {slug}", "chore: new topic feature-foo-bar"),
        ],
    )
    def test_publish_topic_template_without_placeholder_used_as_is(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        template: str,
        expected: str,
    ) -> None:
        """The template applies via plain ``str.replace`` — no format grammar."""
        monkeypatch.chdir(tmp_path)
        cycle = _wire_cycle(monkeypatch)

        publish_topic("Feature/Foo_Bar", "T", "origin/main", template)

        assert cycle.commit_file_on_base.call_args.args[3] == expected

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
            " — run 'goga topics status' to see the board"
        )
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
            == ".goga/history/2026/feature-baz/title.txt"
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
            == ".goga/history/2026/feature-baz/title.txt"
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
