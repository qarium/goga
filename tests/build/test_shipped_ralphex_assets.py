"""Shipped-ralphex-defaults guard — the vendored assets must carry the real templates.

`sync_ralphex_defaults` reads `goga/assets/ralphex/{prompts,agents}` on every
build run without custom `prompts_dir`/`agents_dir`. The vendored files were
extracted with `ralphex --dump-defaults` (v1.6.1) and `_filter_review_prompt`'s
counter rewrites are pinned to this template generation's literal fragments — a
missing or renamed file turns every default `goga build` into exit 1, and a
reworded template silently breaks the counter adaptation. This guard catches a
vendoring mistake here rather than at runtime in the container.
"""

from __future__ import annotations

from pathlib import Path

import goga

# The assets live inside the `goga` package directory, so resolve them from the
# package `__file__` regardless of the current working directory / test root.
_ASSETS_DIR = Path(goga.__file__).resolve().parent / "assets" / "ralphex"

_PROMPTS_DIR = _ASSETS_DIR / "prompts"
_AGENTS_DIR = _ASSETS_DIR / "agents"

_AGENT_ROLES = ("quality", "implementation", "testing", "simplification", "documentation")

# Literal counter fragments of the ralphex v1.6.1 review templates that
# `_filter_review_prompt` rewrites; they must survive any re-vendoring.
_FIRST_PASS_FRAGMENTS = (
    "Launch ALL 5 Review Agents",
    "All 5 agent invocations",
    "until ALL 5 agents",
    "launches 5 parallel reviewer agents",
)
_SECOND_PASS_FRAGMENTS = (
    "uses 2 agents",
    "until BOTH agents",
    "Both agent invocations",
    "until both complete",
    "emit them both in one response",
)


def test_shipped_ralphex_prompt_assets_exist() -> None:
    """The vendored prompts directory carries the four canonical templates."""
    assert _PROMPTS_DIR.is_dir(), f"vendored ralphex prompts missing at {_PROMPTS_DIR}"
    for name in ("task.txt", "review_first.txt", "review_second.txt", "codex.txt"):
        assert (_PROMPTS_DIR / name).is_file(), f"vendored prompt {name} missing"


def test_shipped_ralphex_agent_assets_exist() -> None:
    """The vendored agents directory carries all five review-agent definitions."""
    assert _AGENTS_DIR.is_dir(), f"vendored ralphex agents missing at {_AGENTS_DIR}"
    for role in _AGENT_ROLES:
        assert (_AGENTS_DIR / f"{role}.txt").is_file(), f"vendored agent {role} missing"


def test_shipped_review_prompts_carry_agent_lines() -> None:
    """Both review templates keep their `{{agent:X}}` lines for every declared role.

    `_filter_review_prompt` derives the composition solely from these lines, and
    `ROLE_WHITELIST` accepts every role they declare — a dropped line would
    silently remove that reviewer from every role-filtered run.
    """
    first = (_PROMPTS_DIR / "review_first.txt").read_text()
    second = (_PROMPTS_DIR / "review_second.txt").read_text()

    for role in _AGENT_ROLES:
        assert f"{{{{agent:{role}}}}}" in first

    for role in ("quality", "implementation"):
        assert f"{{{{agent:{role}}}}}" in second


def test_shipped_review_prompts_carry_counter_fragments() -> None:
    """The templates keep the exact fragments the counter rewrites are pinned to.

    A re-vendoring from a reworded ralphex release makes each rewrite a silent
    no-op; this pins the fragments so the mismatch surfaces here instead.
    """
    first = (_PROMPTS_DIR / "review_first.txt").read_text()
    second = (_PROMPTS_DIR / "review_second.txt").read_text()

    for fragment in _FIRST_PASS_FRAGMENTS:
        assert fragment in first, f"review_first.txt lost the fragment {fragment!r}"

    for fragment in _SECOND_PASS_FRAGMENTS:
        assert fragment in second, f"review_second.txt lost the fragment {fragment!r}"


def test_shipped_assets_sync_byte_identical_without_roles(tmp_path, monkeypatch) -> None:
    """A no-roles sync copies the real vendored assets byte-identically end to end."""
    from goga.build.ralphex_runtime import sync_ralphex_defaults
    from goga.build.review_options import ReviewOptions
    from goga.config import BuildConfig, TaskExecutorConfig

    monkeypatch.chdir(tmp_path)
    config = BuildConfig(task_executor=TaskExecutorConfig(agent="claude", env={}))

    sync_ralphex_defaults(
        config, ReviewOptions(skip=False, review_agent=None, roles=None, two_pass=False, review_env={})
    )

    assert (_PROMPTS_DIR / "task.txt").read_bytes() == (tmp_path / ".ralphex" / "prompts" / "task.txt").read_bytes()
    assert (_PROMPTS_DIR / "review_first.txt").read_bytes() == (
        tmp_path / ".ralphex" / "prompts" / "review_first.txt"
    ).read_bytes()
    assert (_AGENTS_DIR / "quality.txt").read_bytes() == (tmp_path / ".ralphex" / "agents" / "quality.txt").read_bytes()
