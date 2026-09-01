"""The switch resolution and orchestration of the topics domain.

The entities declared in the cell CODEMANIFEST with
``location: switching.py``: one candidate of a switch-identifier
resolution, the read-only resolver walking the same ref trees as the
board, and the orchestrator that brings the repository onto the chosen
host branch by purely switching — the shared switch tail also serves the
ensure orchestration of ``ensuring.py``. Topic identity and statuses belong to the
history facade; the bounded git mutations belong to the nested git cell.
Git infrastructure failures and the fatal scale-assembly ``ImportError``
surface as ``click.ClickException`` — the clean-error boundary of the
domain; the interactive moments follow the ``click`` practice.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass

import click

from ..history import (
    StatusScale,
    assemble_status_scale,
    current_year,
    normalize_topic_slug,
    resolve_current_branch_name,
)
from .board import _current_branch_topic, _short_name, _year_topics_by_ref
from .git import (
    BranchRef,
    checkout_local_branch,
    create_branch_from_remote_tracking,
    is_working_tree_clean,
    list_branch_refs,
)


@dataclass(frozen=True, kw_only=True)
class SwitchCandidate:
    """One candidate of a switch-identifier resolution — a branch that may
    host the requested work.

    Attributes:
        branch: The display name of the candidate branch.
        topic: The topic slug the branch hosts, or ``None`` for a branch
            without a topic.
        statuses: The qualified names of the maximal present statuses, in
            scale order — empty for a branch without a topic.
        current: ``True`` for the current branch.
        remote: ``True`` when the candidate ref is remote-tracking.
    """

    branch: str
    topic: str | None
    statuses: list[str]
    current: bool
    remote: bool


def resolve_switch_candidates(
    identifier: str, year: str | None = None
) -> list[SwitchCandidate]:
    """Resolve a switch identifier into its candidate branches.

    Args:
        identifier: The user input — a branch name, a topic slug, or their
            prefix.
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        The matching candidates, exact matches first, then prefix matches —
        locals before remote-tracking refs, then by branch, then by topic.
        Every branch appears once: a remote-tracking candidate whose local
        twin hosts the same topic is collapsed — the local branch wins —
        and a branch hosting several topics of the year contributes its
        first entry only. A branch without a topic is a valid candidate
        with ``topic=None`` and empty ``statuses``.

    Algorithm:
        1. Normalize ``identifier`` into a slug via ``normalize_topic_slug``
        2. Collect the branch inventory and the topics of the resolved year
           — the same ref-tree walk as the board, with the current branch
           read from the working copy
        3. Exact branch name match -> the candidates hosting that name
        4. Exact slug match otherwise -> the branches hosting the slug,
           local branches first
        5. Prefix matches otherwise -> the branches whose name or hosted
           slug starts with the input
        6. Collapse the tier to one entry per branch and return the
           candidates with their statuses

    Requirements:
        Exact matches always precede prefix matches — the first non-empty
        tier wins and excludes every other tier.
        A branch appears in the result once — a local branch beats its
        remote twin, so an unambiguous identifier never reaches a prompt.
        A branch without a topic is a valid candidate.
        Read-only — no mutation before a choice.

    Constraints:
        Do not choose among multiple candidates — selection belongs to the
        caller.

    Raises:
        click.ClickException: a git infrastructure failure (its stderr when
            git reports one, or a missing git binary), or the fatal
            ``ImportError`` of the scale assembly — the broken tool package
            is named in the message.
    """
    try:
        return _resolve_switch_candidates(identifier, year)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        raise click.ClickException(f"git failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(f"git is not available: {exc}") from exc
    except ImportError as exc:
        raise click.ClickException(str(exc)) from exc


def switch_topic(identifier: str, year: str | None = None) -> str:
    """Bring the repository onto the branch hosting the requested work.

    Args:
        identifier: The user input — a branch name, a topic slug, or their
            prefix.
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        One line describing the outcome — the idempotent success, the
        checkout, or the branch creation.

    Algorithm:
        1. Resolve the candidates via ``resolve_switch_candidates``
        2. No candidate -> clean error with a hint to the board
        3. One candidate -> take it; several -> print the numbered list with
           statuses and prompt for a number, or fail with the list when no
           interactive input is available
        4. Already on the hosting branch -> idempotent success, no mutation,
           no cleanliness probe
        5. A mutation is needed -> probe the working tree cleanliness first
           via ``is_working_tree_clean``; a dirty tree is a clean error
           naming the reason and the next step — commit or stash the
           working copy before switching
        6. Local host -> check out the branch via ``checkout_local_branch``;
           remote-only host -> create the local branch from the
           remote-tracking ref via ``create_branch_from_remote_tracking``
        7. Return the single result line

    Requirements:
        Every mutation is local — no network, no fetch, no push.
        Nothing is mutated before the candidate choice is complete.
        The result is exactly one line.

    Constraints:
        Do not manage the stages of the hosting pipeline — continuation
        belongs to the pipeline itself.
        Do not return to the previous branch — the switch is the outcome.

    Raises:
        click.ClickException: no branch hosts the identifier, several
            candidates without an interactive terminal, a dirty working
            tree, a git infrastructure failure (its stderr when git reports
            one, or a missing git binary), or the fatal ``ImportError`` of
            the scale assembly.
        click.Abort: Ctrl-C or EOF at the selection prompt — the repository
            is left untouched.
    """
    try:
        return _switch_topic(identifier, year)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        raise click.ClickException(f"git failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(f"git is not available: {exc}") from exc
    except ImportError as exc:
        raise click.ClickException(str(exc)) from exc


def _resolve_switch_candidates(
    identifier: str, year: str | None
) -> list[SwitchCandidate]:
    """Build the candidate inventory and take the first non-empty tier.

    Args:
        identifier: The user input as entered.
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        The candidates of the first non-empty resolution tier — exact
        branch, exact slug, prefix — collapsed to one entry per branch.
    """
    resolved_year = year or current_year()
    scale = assemble_status_scale()
    inventory = list_branch_refs()
    current = resolve_current_branch_name()
    candidates = _hosted_candidates(inventory, current, resolved_year, scale)

    slug = normalize_topic_slug(identifier)
    tiers = (
        [candidate for candidate in candidates if candidate.branch == identifier],
        [candidate for candidate in candidates if candidate.topic == slug],
        [
            candidate
            for candidate in candidates
            if candidate.branch.startswith(identifier)
            or (slug != "" and candidate.topic is not None and candidate.topic.startswith(slug))
        ],
    )

    for tier in tiers:
        if tier:
            return _unique_candidates(tier)

    return []


def _hosted_candidates(
    refs: list[BranchRef], current: str | None, year: str, scale: StatusScale
) -> list[SwitchCandidate]:
    """List every hosted-work candidate of the branch inventory.

    One candidate per ``(branch, hosted slug)`` pair — a branch hosting
    several topics of the year yields several candidates, a branch hosting
    none yields one ``topic=None`` candidate. The current branch is read
    from the working copy exactly like the board row: the shared helper
    guards the empty-slug branch name before the path oracles, which raise
    on it before their existence check.

    Args:
        refs: The full branch inventory.
        current: The current branch name, or ``None`` when there is none.
        year: The resolved year as four digits.
        scale: The assembled status scale.

    Returns:
        The candidates ordered local-first, then by branch, then by topic.
    """
    topics_by_ref = _year_topics_by_ref(refs, year)
    hosted: list[tuple[BranchRef, str | None, list[str]]] = []

    for ref in refs:
        if current is not None and not ref.remote and ref.name == current:
            working_copy = _current_branch_topic(current, year, scale)
            if working_copy is None:
                hosted.append((ref, None, []))
            else:
                slug, statuses, _todo = working_copy
                hosted.append((ref, slug, statuses))
            continue

        topics = topics_by_ref[ref.name]
        if not topics:
            hosted.append((ref, None, []))
            continue
        for slug, artifacts in topics.items():
            hosted.append((ref, slug, scale.maximal_present(artifacts)))

    hosted.sort(key=lambda entry: (entry[0].remote, entry[0].name, entry[1] or ""))

    return [
        SwitchCandidate(
            branch=ref.name,
            topic=slug,
            statuses=statuses,
            current=current is not None and not ref.remote and ref.name == current,
            remote=ref.remote,
        )
        for ref, slug, statuses in hosted
    ]


def _unique_candidates(candidates: list[SwitchCandidate]) -> list[SwitchCandidate]:
    """Collapse the redundant candidates of one resolution tier.

    A remote-tracking candidate whose local twin hosts the same topic is
    dropped — the local branch wins, mirroring the board's twin collapse —
    and every branch is kept once: the first entry of the tier order
    (locals first, then branch, then topic) carries it, so a branch
    hosting several topics of the year never repeats in the list and an
    unambiguous identifier stays unambiguous.

    Args:
        candidates: The candidates of one resolution tier, in tier order.

    Returns:
        The candidates without remote twins and branch repetitions.
    """
    local_topics = {
        (candidate.topic, candidate.branch)
        for candidate in candidates
        if not candidate.remote
    }
    unique: list[SwitchCandidate] = []
    branches: set[str] = set()

    for candidate in candidates:
        hosted_twin = (candidate.topic, _short_name(candidate.branch)) in local_topics
        if candidate.remote and hosted_twin:
            continue
        if candidate.branch in branches:
            continue
        branches.add(candidate.branch)
        unique.append(candidate)

    return unique


def _switch_topic(identifier: str, year: str | None) -> str:
    """Run the traced switch procedure — the unwrapped orchestration.

    Args:
        identifier: The user input as entered.
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        The single result line of the outcome.
    """
    candidates = resolve_switch_candidates(identifier, year)

    if not candidates:
        raise click.ClickException(
            f"no branch hosts {identifier!r} — run 'goga topics board' to see the board"
        )

    return _switch_to_candidate(candidates)


def _switch_to_candidate(candidates: list[SwitchCandidate]) -> str:
    """Take the resolved candidates onto the working copy — the shared switch
    tail of ``switch_topic`` and the ensure orchestration of
    ``ensuring.py``.

    Args:
        candidates: The non-empty candidate list of the resolution.

    Returns:
        The single result line of the outcome.

    Raises:
        click.ClickException: several candidates without a terminal, or a
            dirty working tree when a mutation is needed.
        click.Abort: Ctrl-C or EOF at the selection prompt.
    """
    chosen = candidates[0] if len(candidates) == 1 else _choose_candidate(candidates)

    if chosen.current:
        return f"Already on branch {chosen.branch}"
    if not is_working_tree_clean():
        raise click.ClickException("working tree is dirty — commit or stash before switching")
    if not chosen.remote:
        checkout_local_branch(chosen.branch)
        return f"Switched to branch {chosen.branch}"

    create_branch_from_remote_tracking(BranchRef(name=chosen.branch, remote=True))
    short = chosen.branch.partition("/")[2]

    return f"Created branch {short} from {chosen.branch}"


def _choose_candidate(candidates: list[SwitchCandidate]) -> SwitchCandidate:
    """Narrow several candidates to one — the numbered selection.

    Args:
        candidates: The candidate list of the resolution — two or more.

    Returns:
        The chosen candidate.

    Raises:
        click.ClickException: without a terminal — the numbered list goes to
            the user as a non-interactive abort.
        click.Abort: Ctrl-C or EOF at the prompt.
    """
    lines = _numbered_lines(candidates)

    if not sys.stdin.isatty():
        raise click.ClickException("\n".join(lines))

    for line in lines:
        click.echo(line)

    number = click.prompt(
        "Select a branch by number", type=click.IntRange(1, len(candidates))
    )

    return candidates[number - 1]


def _numbered_lines(candidates: list[SwitchCandidate]) -> list[str]:
    """Render the numbered candidate list with the status segments.

    Args:
        candidates: The candidate list of the resolution.

    Returns:
        One line per candidate — ``N) <branch> (<topic>) [status] ...`` with
        the topic and the status segments present only when hosted.
    """
    lines = []

    for index, candidate in enumerate(candidates, start=1):
        line = f"{index}) {candidate.branch}"
        if candidate.topic is not None:
            line += f" ({candidate.topic})"
        if candidate.statuses:
            line += " " + " ".join(f"[{status}]" for status in candidate.statuses)

        lines.append(line)

    return lines
