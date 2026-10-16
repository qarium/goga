"""End-to-end integration tests for the resolved wrapper path flow.

These stitch together the cross-cell path of the ``unified-agent-wrappers-
resolution`` migration on the two-part build model. A single leaf routine —
``resolve_wrapper_path`` in ``goga/agents/wrapper`` — is re-exported through
the ``goga.agents`` facade and consumed by the in-container build domain:

    goga/agents/wrapper/resolve.py  (leaf)
        -> goga/agents/__init__.py  (facade re-export)
            -> goga/build/role_env_wrappers.py (exec targets of the generated
               per-role closures, one per pass executor)

The integration boundary is the facade import
``from goga.agents import resolve_wrapper_path``: the build consumer embeds
one resolved wrapper per pass executor of the always-two-pass cycle — the
tasks pass under the root agent, the review pass under the review agent, or
under the additional agent when the strategy is short — inside the generated
role closures, so the per-pass closure sequence and the final
``.ralphex/config`` are verified together. The former pipeline-side
consumer (the host afm-config tmpfile ``client.command``) was retired with the
tmpfile flow: the afm configuration file is authored in-container by
``goga/pipeline`` (covered by ``tests/pipeline/test_afm_config.py``), and the
host launcher resolves no agent.

The docker/subprocess boundary is mocked per
``[[feedback_mock_patch_module_shadowing]]``: the package ``__init__`` re-exports
submodule functions, which shadows string-based ``mock.patch`` paths, so the
real modules are resolved via ``sys.modules`` and patched by attribute.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple
from unittest import mock

import pytest
from goga.agents import resolve_wrapper_path
from goga.build import build
from goga.build.build_pass import write_ralphex_config as _real_write_ralphex_config
from goga.config import load_project_config
from goga.ralphex.run_ralphex import _build_command


def _load_config(tmp_path: Path, monkeypatch) -> object:
    """Chdir into tmp_path and load the .goga/config.yml written there."""
    monkeypatch.chdir(tmp_path)
    return load_project_config()


# --- build consumer: per-pass executor wrappers and .ralphex/config ---


class _PassCase(NamedTuple):
    """One per-pass closure scenario: the review section, the pass sequence's
    role closures, and the exec target embedded in each."""

    review_section: dict
    expected_roles: list[str]
    expected_execs: list[str]


class TestBuildResolvedPathFlow:
    @pytest.mark.parametrize("agent", ["claude", "codex", "opencode"])
    def test_build_resolved_path_matches_resolve_wrapper_path(  # noqa: PLR0913, PLR0917
        self,
        tmp_path: Path,
        monkeypatch,
        write_goga_config,
        mock_vendored_sources,
        relocated_wrapper_base: Path,
        agent: str,
    ) -> None:
        """build() embeds the resolve_wrapper_path(agent) value as the exec target
        of the generated role closures."""
        write_goga_config(agent=agent, image="goga:latest")
        config = _load_config(tmp_path, monkeypatch)
        cli_options = {"dry_run": True, "skip_manifest_check": True}

        wrapper = tmp_path / f"{agent}-as-claude.sh"
        wrapper.write_text("#!/bin/sh\n")

        with (
            mock_vendored_sources(),
            mock.patch("goga.build.review_config.resolve_wrapper_path", return_value=str(wrapper)),
            mock.patch("goga.build.build_pass.run_ralphex", return_value=0),
        ):
            result = build("plan.md", config, cli_options)

        assert result == 0

        # The facade is the single source of truth: the exec target inside the
        # tasks closure must equal exactly what resolve_wrapper_path returns
        # for this agent (the review agent inherits it here).
        tasks_closure = (relocated_wrapper_base / "tasks.sh").read_text()
        assert f'exec {resolve_wrapper_path(agent)} "$@"' in tasks_closure

        # The claude_command of the final (review) pass is that pass's
        # generated closure — the wrapper resolution rides inside it.
        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert f"claude_command = {relocated_wrapper_base / 'review.sh'}" in config_text

    @pytest.mark.parametrize(
        "case",
        [
            # medium (the default strategy): tasks pass under the root agent,
            # review pass under the review agent.
            _PassCase(
                review_section={"agent": "codex"},
                expected_roles=["tasks", "review"],
                expected_execs=[
                    "/home/goga/bin/claude-as-claude.sh",
                    "/home/goga/bin/codex-as-claude.sh",
                ],
            ),
            # short: the review pass is the external-only pass carried by the
            # additional agent's closure.
            _PassCase(
                review_section={
                    "agent": "codex",
                    "strategy": "short",
                    "additional": {"agent": "cursor", "patience": 2},
                },
                expected_roles=["tasks", "additional"],
                expected_execs=[
                    "/home/goga/bin/claude-as-claude.sh",
                    "/home/goga/bin/cursor-as-claude.sh",
                ],
            ),
        ],
        ids=["medium-review-agent", "short-additional-agent"],
    )
    def test_wrapper_resolved_per_pass(  # noqa: PLR0913, PLR0917
        self,
        tmp_path: Path,
        monkeypatch,
        write_goga_config,
        mock_vendored_sources,
        relocated_wrapper_base: Path,
        case: _PassCase,
    ) -> None:
        """Each pass launches through its own role closure; the final
        .ralphex/config carries the last pass's closure."""
        write_goga_config(agent="claude", image="goga:latest", review=case.review_section)
        config = _load_config(tmp_path, monkeypatch)
        Path("plan.md").write_text("# plan\n")

        review_wrapper = tmp_path / "codex-as-claude.sh"
        review_wrapper.write_text("#!/bin/sh\n")
        wrappers: list[str] = []
        additional_paths: list[str | None] = []

        def _record(settings, wrapper_path, additional_wrapper_path=None):
            wrappers.append(wrapper_path)
            additional_paths.append(additional_wrapper_path)
            return _real_write_ralphex_config(settings, wrapper_path, additional_wrapper_path)

        with (
            mock_vendored_sources(),
            mock.patch("goga.build.review_config.resolve_wrapper_path", return_value=str(review_wrapper)),
            mock.patch("goga.build.build_pass.write_ralphex_config", side_effect=_record),
            mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run,
        ):
            result = build("plan.md", config, {"skip_manifest_check": True})

        assert result == 0

        # The always-two-pass cycle writes one config per pass, closure of that
        # pass; the sequence follows the per-stage role resolution.
        assert mock_run.call_count == 2
        assert wrappers == [str(relocated_wrapper_base / f"{role}.sh") for role in case.expected_roles]

        # Every pass-config write carries the additional closure alongside the
        # pass executor — the surviving write is the one ralphex reads.
        additional_closure = str(relocated_wrapper_base / "additional.sh")
        assert additional_paths == [additional_closure, additional_closure]

        # Each pass's closure execs its own agent's resolved wrapper.
        for role, resolved in zip(case.expected_roles, case.expected_execs, strict=True):
            closure = (relocated_wrapper_base / f"{role}.sh").read_text()
            assert f'exec {resolved} "$@"' in closure

        # The mode flags follow the strategy: --review for medium, -e for short.
        second_options = mock_run.call_args_list[1].args[1]
        if case.review_section.get("strategy") == "short":
            assert second_options["external_only"] is True
            assert "review" not in second_options
            assert _build_command("plan.md", second_options)[4:6] == ["-e", "--review-patience"]
        else:
            assert second_options["review"] is True

        # The final pass config carries the last pass's executor closure.
        config_text = (tmp_path / ".ralphex" / "config").read_text()
        last_closure = relocated_wrapper_base / f"{case.expected_roles[-1]}.sh"
        assert f"claude_command = {last_closure}" in config_text
