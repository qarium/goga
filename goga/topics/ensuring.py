"""The ensure orchestration of the topics domain.

The entity declared in the cell CODEMANIFEST with
``location: ensuring.py``: the combined orchestrator that brings the
repository onto the requested work — by switching when a branch hosts the
identifier, by creating the fresh work when nothing does. The resolution
and the switch tail belong to the switching module; the creation fallback
belongs to the creation module. Topic identity and statuses belong to the
history facade; the bounded git mutations belong to the nested git cell.
Git infrastructure failures and the fatal scale-assembly ``ImportError``
surface as ``click.ClickException`` — the clean-error boundary of the
domain; the interactive moments follow the ``click`` practice.
"""

from __future__ import annotations

import subprocess

import click

from .creation import create_topic
from .switching import _switch_to_candidate, resolve_switch_candidates


def ensure_topic(identifier: str, year: str | None = None) -> str:
    """Bring the repository onto the requested work, creating it when nothing
    hosts the identifier.

    Args:
        identifier: The user input — a branch name, a topic slug, or their
            prefix.
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        One line describing the outcome — the idempotent success, the
        checkout, the branch creation from a remote-tracking ref, or the
        fresh-work creation.

    Algorithm:
        1. Resolve the candidates via ``resolve_switch_candidates``
        2. No candidate -> create fresh work via ``create_topic`` with the
           identifier as the branch name — the occupancy oracles, the re-ask
           cycle, and the idempotent current-branch success belong to it
        3. Otherwise -> the switch procedure — the candidate choice, the
           idempotent confirmation, the cleanliness probe, and the checkout

    Requirements:
        Creation happens only at zero candidates — a resolvable identifier
        never creates anything.
        The result is exactly one line.
        Every mutation is local — no network, no fetch, no push.

    Constraints:
        Do not alter the switch-only contract of ``switch_topic`` — the
        topics switch command keeps its stricter behavior.
        Do not manage the stages of the hosting pipeline — continuation
        belongs to the pipeline itself.

    Raises:
        click.ClickException: several candidates without an interactive
            terminal, a dirty working tree on a switch mutation, an unusable
            (empty-slug) or occupied name without a terminal, a git
            infrastructure failure (its stderr when git reports one, or a
            missing git binary), or the fatal ``ImportError`` of the scale
            assembly.
        click.Abort: Ctrl-C or EOF at a selection or re-ask prompt — the
            repository is left untouched.
    """
    try:
        return _ensure_topic(identifier, year)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        raise click.ClickException(f"git failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(f"git is not available: {exc}") from exc
    except ImportError as exc:
        raise click.ClickException(str(exc)) from exc


def _ensure_topic(identifier: str, year: str | None) -> str:
    """Run the traced ensure procedure — the unwrapped orchestration.

    Args:
        identifier: The user input as entered.
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        The single result line of the outcome.
    """
    candidates = resolve_switch_candidates(identifier, year)

    if not candidates:
        return create_topic(identifier, year)

    return _switch_to_candidate(candidates)
