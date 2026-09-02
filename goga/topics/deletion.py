"""The identified-topic deletion of the topics domain.

The entities declared in the cell CODEMANIFEST with
``location: deletion.py``: one identified deletion target — a topic with
its hosting refs and its directory —, the read-only resolution that
maps deletion identifiers to targets, and the confirmed removal of the
resolved targets — every decision is made before the first mutation.
The resolution mirrors the switch tiers, keeps merged work out of
scope, and collapses a local branch and its origin twin into one target
assembled from the full inventory; the removal deletes the local branch,
the origin twin, and the topic directory, restoring the local branch at
its captured commit when the remote deletion fails. Topic identity and
addressing belong to the history facade; the ref inventory, the
ref-tree reading, and the branch removals belong to the nested git
cell. Git infrastructure failures surface as
``click.ClickException`` — the clean-error boundary of the domain.
"""

from __future__ import annotations

import contextlib
import subprocess
from dataclasses import dataclass

import click

from ..history import (
    collect_history_tree,
    current_year,
    normalize_topic_slug,
    remove_topic_dir,
    resolve_current_branch_name,
    resolve_history_root,
)
from .board import _short_name
from .git import (
    BranchRef,
    create_branch_at_commit,
    delete_local_branch,
    delete_remote_branch,
    list_branch_refs,
    read_ref_tree_paths,
    resolve_ref_commit,
)


@dataclass(frozen=True, kw_only=True)
class DeleteTarget:
    """One identified deletion target — a topic with its hosting refs and
    directory.

    Attributes:
        topic: The topic slug.
        branch: The hosting local branch name, or ``None``.
        remote: The hosting origin twin name — the short name the remote
            deletion consumes — or ``None``.
        has_dir: ``True`` when the topic directory of the year exists on
            disk.
    """

    topic: str
    branch: str | None
    remote: str | None
    has_dir: bool


def resolve_delete_targets(
    identifiers: list[str], year: str | None = None
) -> list[DeleteTarget]:
    """Resolve deletion identifiers into targets — every check before any
    removal.

    Args:
        identifiers: The user inputs — branch names, topic slugs, or their
            prefixes.
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        One ``DeleteTarget`` per identified topic, in identifier order.
        A local branch and its origin twin form one target; repeated
        identifiers naming one topic collapse into it.

    Algorithm:
        1. Resolve the year and collect the read-only inventory once: the
           branch refs via ``list_branch_refs``, the topics of the year
           hosted by every ref via ``read_ref_tree_paths`` under the
           history root, and the topics of the year on disk via
           ``collect_history_tree``
        2. Each identifier resolves through the tiers — the exact branch
           name (a local ref by its name, a remote-tracking ref by its
           short name), the exact topic slug (a ref hosting it in its
           tree, or a disk topic), the prefixes of both — the first
           non-empty tier wins
        3. Within the tier the distinct hosted topics decide: none or a
           single tier without topics -> clean error naming the
           identifier; more than one -> clean error listing the
           candidates — no interactive choice
        4. Merged-work guard: a hosting ref is part of the target only
           when its normalized name equals the topic slug; a topic whose
           every hosting ref carries it as merged work is a clean error
           naming the topic and the hosting branch — a disk topic no
           branch hosts stays targetable (no refs, directory only)
        5. Assemble every identified target from the full inventory — the
           local ref and the remote-tracking twin whose normalized names
           equal the slug, and the disk presence — never from the tier
           that matched, so the result cannot depend on identifier order
        6. The current branch naming any target's branch, or its slug
           naming any target's topic -> clean error asking to switch away
           first

    Requirements:
        Read-only — nothing is removed, created, or switched.
        All-or-nothing — any unresolved or ambiguous identifier cancels
        the whole call.

    Constraints:
        Do not resolve remote state over the network — the local
        inventory only.
        Do not offer an interactive selection.

    Raises:
        click.ClickException: an identifier nothing hosts, an ambiguous
            identifier, merged work, the current branch hosting a target,
            a git infrastructure failure (its stderr when git reports
            one, or a missing git binary), or an OS failure of the
            history-tree read.
    """
    try:
        return _resolve_delete_targets(identifiers, year)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        raise click.ClickException(f"git failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(f"git is not available: {exc}") from exc
    except OSError as exc:
        raise click.ClickException(f"reading the history tree failed: {exc}") from exc


def _resolve_delete_targets(identifiers: list[str], year: str | None) -> list[DeleteTarget]:
    """Run the traced resolution — the unwrapped orchestration.

    Args:
        identifiers: The user inputs as entered.
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        The targets in identifier order, deduplicated by topic slug.
    """
    resolved_year = year or current_year()
    refs = list_branch_refs()
    hosted = _hosted_slugs(refs, resolved_year)
    disk = _disk_slugs(resolved_year)

    topics: list[str] = []
    for identifier in identifiers:
        topic = _identify(identifier, refs, hosted, disk)
        if topic not in topics:
            topics.append(topic)

    targets = [_assemble_target(topic, refs, hosted, disk) for topic in topics]
    _guard_current_branch(targets)

    return targets


def _hosted_slugs(refs: list[BranchRef], year: str) -> dict[str, set[str]]:
    """Read the topics of one year hosted by every given ref.

    One ``read_ref_tree_paths`` invocation per ref under the year prefix
    of the history root — the same tree-reading pattern as the board and
    the switch resolution, without checkout and without statuses: the
    deletion inventory carries names only.

    Args:
        refs: The refs whose trees are read.
        year: The resolved year as four digits.

    Returns:
        The hosted topic slugs per ref display name — an empty set for a
        ref hosting nothing of the year.
    """
    prefix = f"{resolve_history_root().as_posix()}/{year}/"
    return {ref.name: _slugs_under(read_ref_tree_paths(ref.name, prefix), prefix) for ref in refs}


def _slugs_under(paths: list[str], prefix: str) -> set[str]:
    """Take the topic slugs of the ref-tree paths under the year prefix.

    Args:
        paths: The file paths of one ref tree, relative to the repository
            root, already filtered under ``prefix`` by the reader.
        prefix: The year prefix the paths sit under.

    Returns:
        The distinct topic slugs — the first path segment after the
        prefix.
    """
    return {path.removeprefix(prefix).split("/", 1)[0] for path in paths}


def _disk_slugs(year: str) -> set[str]:
    """Read the topics of one year found in the on-disk history tree.

    The scale-free provider of the deletion flow — statuses are never
    computed, so the status registry is never touched.

    Args:
        year: The resolved year as four digits.

    Returns:
        The topic slugs of the year present on disk — a topic directory
        no branch hosts is a targetable topic.
    """
    for record in collect_history_tree():
        if record.year == year:
            return set(record.topics)
    return set()


def _identify(
    identifier: str, refs: list[BranchRef], hosted: dict[str, set[str]], disk: set[str]
) -> str:
    """Resolve one identifier into its single topic through the tiers.

    Args:
        identifier: The user input as entered.
        refs: The full branch inventory.
        hosted: The hosted topic slugs per ref display name.
        disk: The on-disk topic slugs of the year.

    Returns:
        The one identified topic slug.

    Raises:
        click.ClickException: nothing matches the identifier, or several
            topics match it — no interactive choice.
    """
    slug = normalize_topic_slug(identifier)
    tiers = (
        _tier_exact_branch(identifier, refs, hosted),
        _tier_exact_slug(slug, refs, hosted, disk),
        _tier_prefix(identifier, slug, refs, hosted, disk),
    )

    for topics in tiers:
        if topics is None:
            continue
        if len(topics) > 1:
            raise click.ClickException(
                f"several topics match {identifier!r}: {', '.join(sorted(topics))}"
            )
        if topics:
            return next(iter(topics))
        break

    raise click.ClickException(f"no topic matches {identifier!r}")


def _tier_exact_branch(
    identifier: str, refs: list[BranchRef], hosted: dict[str, set[str]]
) -> set[str] | None:
    """Take the first tier — the exact branch name.

    Args:
        identifier: The user input as entered.
        refs: The full branch inventory.
        hosted: The hosted topic slugs per ref display name.

    Returns:
        The distinct hosted topics of the matched refs — ``None`` when no
        ref carries the name (the tier is skipped), an empty set when a
        matched branch hosts nothing (deletion deletes topics, not bare
        branches).
    """
    matched = [
        ref
        for ref in refs
        if (not ref.remote and ref.name == identifier)
        or (ref.remote and _short_name(ref.name) == identifier)
    ]
    if not matched:
        return None
    return set().union(*(hosted[ref.name] for ref in matched))


def _tier_exact_slug(
    slug: str, refs: list[BranchRef], hosted: dict[str, set[str]], disk: set[str]
) -> set[str] | None:
    """Take the second tier — the exact topic slug.

    Args:
        slug: The normalized identifier.
        refs: The full branch inventory.
        hosted: The hosted topic slugs per ref display name.
        disk: The on-disk topic slugs of the year.

    Returns:
        The hosted topics of the refs carrying the slug, plus the slug
        itself when it sits on disk — ``None`` when neither matches (the
        tier is skipped).
    """
    matched = [ref for ref in refs if slug != "" and slug in hosted[ref.name]]
    on_disk = slug != "" and slug in disk
    if not matched and not on_disk:
        return None
    topics = set().union(*(hosted[ref.name] for ref in matched)) if matched else set()
    if on_disk:
        topics.add(slug)
    return topics


def _tier_prefix(
    identifier: str, slug: str, refs: list[BranchRef], hosted: dict[str, set[str]], disk: set[str]
) -> set[str] | None:
    """Take the third tier — the prefixes of both.

    Args:
        identifier: The user input as entered.
        slug: The normalized identifier.
        refs: The full branch inventory.
        hosted: The hosted topic slugs per ref display name.
        disk: The on-disk topic slugs of the year.

    Returns:
        The hosted topics of the refs whose name starts with the
        identifier, plus the hosted and disk slugs starting with the
        normalized slug — ``None`` when nothing matches (the tier is
        skipped). A non-ASCII identifier normalizes to the empty slug,
        which every slug starts with, so the slug-prefix arms stay
        disabled for it.
    """
    topics: set[str] = set()
    matched = [
        ref
        for ref in refs
        if ref.name.startswith(identifier) or _short_name(ref.name).startswith(identifier)
    ]
    for ref in matched:
        topics |= hosted[ref.name]
    if slug != "":
        topics |= {
            hosted_slug for slugs in hosted.values() for hosted_slug in slugs if hosted_slug.startswith(slug)
        }
        topics |= {disk_slug for disk_slug in disk if disk_slug.startswith(slug)}
    if not matched and not topics:
        return None
    return topics


def _assemble_target(
    topic: str, refs: list[BranchRef], hosted: dict[str, set[str]], disk: set[str]
) -> DeleteTarget:
    """Assemble one topic's target from the full inventory.

    The hosting refs decide eligibility — a ref is part of the target
    only when its normalized name equals the topic slug, so a branch
    carrying the topic as merged work never turns into a deletion of the
    integration branch. The lookup walks the full inventory, never the
    tier that matched, so repeated identifiers of one topic in any order
    assemble the identical target.

    Args:
        topic: The identified topic slug.
        refs: The full branch inventory.
        hosted: The hosted topic slugs per ref display name.
        disk: The on-disk topic slugs of the year.

    Returns:
        The assembled target — the local branch and the origin twin short
        name of the eligible refs, and the disk presence.

    Raises:
        click.ClickException: the topic is hosted only by refs that carry
            it as merged work — the hosting branch is named in the error.
    """
    hosts = [ref for ref in refs if topic in hosted[ref.name]]
    eligible = [ref for ref in hosts if _normalized_name(ref) == topic]
    if hosts and not eligible:
        names = ", ".join(ref.name for ref in hosts)
        raise click.ClickException(
            f"topic {topic!r} is hosted by {names} as merged work — "
            "remove it from the hosting branch's tree instead of deleting"
        )

    branch = next((ref.name for ref in eligible if not ref.remote), None)
    # The twin is the *origin* twin — the one remote the deletion push of
    # the git cell addresses. A tracking ref of another remote stays an
    # eligible host (never merged work), but it contributes no deletable
    # twin: its short name would otherwise be pushed at origin — a wrong
    # remote's branch deleted or a phantom "remote ref does not exist"
    # after the local branch is already gone.
    remote = next(
        (
            _short_name(ref.name)
            for ref in eligible
            if ref.remote and ref.name.partition("/")[0] == "origin"
        ),
        None,
    )
    return DeleteTarget(topic=topic, branch=branch, remote=remote, has_dir=topic in disk)


def _normalized_name(ref: BranchRef) -> str:
    """Normalize one ref's name into the topic-slug grammar.

    Args:
        ref: The ref whose name is normalized.

    Returns:
        The normalized name — the short name for a remote-tracking ref
        (the local twin's name), the display name for a local branch.
    """
    return normalize_topic_slug(_short_name(ref.name) if ref.remote else ref.name)


def _guard_current_branch(targets: list[DeleteTarget]) -> None:
    """Reject a deletion that would remove the current branch's topic.

    Args:
        targets: The assembled targets.

    Raises:
        click.ClickException: the current branch names a target's branch,
            or its slug names a target's topic — the deletion needs a
            switch away first.
    """
    current = resolve_current_branch_name()
    if current is None:
        return
    slug = normalize_topic_slug(current)
    for target in targets:
        if target.branch == current or slug == target.topic:
            raise click.ClickException(
                f"the current branch hosts topic {target.topic!r} — switch away before deleting"
            )


def delete_topics(targets: list[DeleteTarget], year: str | None = None) -> str:
    """Delete confirmed targets — the local branch, the origin twin, and
    the topic directory of each.

    Args:
        targets: The confirmed targets, as resolved by
            ``resolve_delete_targets``.
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        One line reporting the removal.

    Algorithm:
        1. Resolve the year once
        2. Per target, in order: capture the hosting local branch's
           commit, delete the local branch, delete the origin twin, then
           remove the topic directory — on a remote failure restore the
           local branch at the captured commit before the error surfaces
        3. Return the single outcome line

    Requirements:
        The commit is captured before the local deletion — after it the
        name no longer resolves.

        Targets removed before a failure stay removed; a failed remote
        deletion restores the failing target's local branch at the
        captured commit, and a failure of the restore itself is
        suppressed so the original remote reason surfaces.

        The directory removal is idempotent on absence — a missing
        directory is not an error.

    Constraints:
        Do not confirm, check merges, or re-resolve — the caller resolved
        the targets and owns the confirmation.

    Raises:
        click.ClickException: a git infrastructure failure (its stderr
            when git reports one, or a missing git binary), or an OS
            failure of the removal.
    """
    try:
        return _delete_topics(targets, year)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        raise click.ClickException(f"git failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(f"git is not available: {exc}") from exc
    except OSError as exc:
        raise click.ClickException(f"cannot complete the deletion: {exc}") from exc


def _delete_topics(targets: list[DeleteTarget], year: str | None) -> str:
    """Run the traced removal — the unwrapped orchestration.

    Args:
        targets: The confirmed targets, in deletion order.
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        The single result line of the outcome.
    """
    resolved_year = year or current_year()

    for target in targets:
        commit: str | None = None
        if target.branch is not None:
            commit = resolve_ref_commit(target.branch)
            delete_local_branch(target.branch)
        if target.remote is not None:
            try:
                delete_remote_branch(target.remote)
            except (subprocess.CalledProcessError, OSError):
                # Restore the local branch at the captured commit before the
                # error propagates — a failure of the restore itself is
                # suppressed so the original remote reason surfaces (the
                # ``publish_topic`` precedent). A remote-only target has
                # nothing to restore; targets removed before this one stay
                # removed.
                if target.branch is not None:
                    with contextlib.suppress(subprocess.CalledProcessError, OSError):
                        create_branch_at_commit(target.branch, commit)
                raise
        if target.has_dir:
            remove_topic_dir(target.topic, resolved_year)

    slugs = ", ".join(target.topic for target in targets)
    return f"Deleted {len(targets)} topic(s) of {resolved_year}: {slugs}"
