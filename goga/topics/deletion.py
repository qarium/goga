"""The identified-topic deletion of the topics domain.

The entities declared in the cell CODEMANIFEST with
``location: deletion.py``: one identified deletion target — a topic with
its own branch, its origin twin, and its directory —, the read-only
resolution that maps deletion identifiers to targets, the read-only
resolution of the merged-topic clear scope of one year against a base
ref's tree, and the confirmed removal of the resolved targets — every
decision is made before the first mutation. The pointer model governs
both resolutions: a topic exists exactly as long as its own branch
exists — found by name over the full inventory, never by tree carriage
— so a topic without its own branch is history, a clean error under
an explicit identifier and silently out of the clear scope; each
resolution mirrors the switch tiers or the base tree, collapses a local
branch and its origin twin into one target assembled from the full
inventory, and gates the directory on the surviving branches. The
removal deletes the local branch, the origin twin, and the topic
directory, restoring the local branch at its captured commit when the
remote deletion fails. Every fully removed
target emits the deletion notification over the nested hooks zone — the
branch-less identity with the removal composition; a target whose
removal fails midway fires nothing (the restore path raises before the
emission). Topic identity and
addressing belong to the history facade; the ref inventory, the
ref-tree reading, and the branch removals belong to the nested git
cell; the lifecycle checkpoints belong to the nested hooks zone.
Git infrastructure failures surface as
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
from .hooks import TopicHooks, TopicIdentity


@dataclass(frozen=True, kw_only=True)
class DeleteTarget:
    """One identified deletion target — a topic with its hosting refs and directory.

    Attributes:
        topic: The topic slug.
        branch: The own local branch name, or ``None``.
        remote: The own origin twin name — the short name the remote
            deletion consumes — or ``None``.
        has_dir: ``True`` exactly when the topic directory of the year
            exists on disk and no branch surviving the deletion carries
            the topic in its tree — the survivors are the inventory
            minus the own local branch and its origin twin.
    """

    topic: str
    branch: str | None
    remote: str | None
    has_dir: bool


def resolve_delete_targets(identifiers: list[str], year: str | None = None) -> list[DeleteTarget]:
    """Resolve deletion identifiers into targets — every check before any removal.

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
           tree, or a disk topic — the slug names one topic, never the
           hosting ref's other topics), the prefixes of both — the first
           non-empty tier wins
        3. Within the tier the distinct hosted topics decide: more than
           one -> clean error listing the candidates — no interactive
           choice; an empty tier names no topic and the resolution falls
           through to the next — no topic in any tier -> clean error
           naming the identifier (a branch nothing hosts never resolves)
        4. Pointer-model assembly: a topic without its own branch — no
           ref of the inventory whose branch part normalizes into the
           topic slug — is a clean error naming the topic only (the
           topic has no branch, there is nothing to delete — it is
           history); a topic with its own refs and other carriers loses
           its own refs only — its directory flag is survivor-gated; a
           topic directory no branch hosts stays targetable (no refs,
           directory only)
        5. Assemble every identified target from the full inventory — the
           own local branch and the origin twin found by name, and the
           survivor-gated disk presence — never from the tier
           that matched, so the result cannot depend on identifier order;
           several local refs normalizing into the slug are a clean error
           naming them
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
            identifier, a topic without its own branch, several branches
            hosting one topic, the current branch hosting a target,
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


def resolve_clear_targets(base_ref: str, year: str | None = None) -> list[DeleteTarget]:
    """Resolve the clear scope of one year against the base ref's tree.

    Every own-branched topic of the year whose topic directory the base
    ref's tree carries — the merged topics the base already integrated —
    becomes one deletion target; nothing is removed here.

    Args:
        base_ref: Any revision string git resolves — resolved once and
            read at the resolved commit; read-only, being on it is not
            an error.
        year: Optional year as four digits; ``None`` means the current
            year.

    Returns:
        One ``DeleteTarget`` per topic in scope, alphabetical by topic.
        A topic without its own branch is out of scope silently — it is
        history; an empty scope yields the empty list — not an error.

    Algorithm:
        1. Resolve the year and collect the branch inventory once — the
           own-branched set is the normalized names of every ref of the
           inventory, local and remote-tracking alike
        2. Resolve the base ref to one commit — the snapshot is pinned, a
           moving ref is not resolved twice — and read its tree under
           the year prefix of the history root: the topics whose
           directory the base tree carries; the base resolution precedes
           the per-ref reads, and an empty scope skips them entirely
        3. The scope is the intersection of the two, alphabetical; an
           empty scope returns ``[]`` before any per-ref read runs
        4. Assemble every scope topic through the shared assembly — the
           own local branch, the origin twin, the survivor-gated
           directory flag
        5. The current branch naming any target's branch, or its slug
           naming any target's topic -> clean error asking to switch
           away first; the whole call cancels

    Requirements:
        Read-only — nothing is removed, created, or switched; the base is
        never moved or pushed.

        All-or-nothing — the current-branch guard cancels the whole
        call.

    Constraints:
        Do not resolve remote state over the network — the local
        inventory only.

        Do not confirm or execute — the confirmation and the deletion
        belong to the caller.

    Raises:
        click.ClickException: the current branch hosts a target, an
            unresolvable base ref (git's own reason via the wrapper), a
            git infrastructure failure (its stderr when git reports one,
            or a missing git binary), or an OS failure of the
            history-tree read.
    """
    try:
        return _resolve_clear_targets(base_ref, year)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        raise click.ClickException(f"git failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(f"git is not available: {exc}") from exc
    except OSError as exc:
        raise click.ClickException(f"reading the history tree failed: {exc}") from exc


def _resolve_clear_targets(base_ref: str, year: str | None) -> list[DeleteTarget]:
    """Run the traced clear resolution — the unwrapped orchestration.

    Args:
        base_ref: The base revision string as given.
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        The targets of the clear scope, alphabetical by topic.
    """
    resolved_year = year or current_year()
    refs = list_branch_refs()
    own_branched = {_normalized_name(ref) for ref in refs} - {""}

    # Resolve the base ONCE, before any per-ref read — the read set of
    # an empty scope is one rev-parse plus one base tree read.
    commit = resolve_ref_commit(base_ref)
    prefix = f"{resolve_history_root().as_posix()}/{resolved_year}/"
    base_topics = _slugs_under(read_ref_tree_paths(commit, prefix), prefix)

    scope = sorted(base_topics & own_branched)
    if not scope:
        return []

    hosted = _hosted_slugs(refs, resolved_year)
    disk = _disk_slugs(resolved_year)
    targets = [_assemble_target(topic, refs, hosted, disk) for topic in scope]
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


def _identify(identifier: str, refs: list[BranchRef], hosted: dict[str, set[str]], disk: set[str]) -> str:
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
        _tier_exact_slug(slug, hosted, disk),
        _tier_prefix(identifier, slug, refs, hosted, disk),
    )

    for topics in tiers:
        if topics is None:
            continue
        if len(topics) > 1:
            raise click.ClickException(f"several topics match {identifier!r}: {', '.join(sorted(topics))}")
        if topics:
            return next(iter(topics))
        # An empty tier names no topic — fall through to the next tier. The
        # exact name of a bare branch must not shadow the slug tier: right
        # after a creation the branch exists while its todo.md is still
        # uncommitted, so the topic lives on disk only and the exact-name
        # identifier reaches it there (a branch nothing hosts never
        # resolves — deletion deletes topics, not bare branches).

    raise click.ClickException(f"no topic matches {identifier!r}")


def _tier_exact_branch(identifier: str, refs: list[BranchRef], hosted: dict[str, set[str]]) -> set[str] | None:
    """Take the first tier — the exact branch name.

    Args:
        identifier: The user input as entered.
        refs: The full branch inventory.
        hosted: The hosted topic slugs per ref display name.

    Returns:
        The distinct hosted topics of the matched refs — ``None`` when no
        ref carries the name (the tier is skipped), an empty set when a
        matched branch hosts nothing: the empty tier names no topic, so
        the resolution falls through to the slug tier — the exact name of
        a bare branch must not shadow the disk topic of the same slug
        (deletion deletes topics, not bare branches: a branch nothing
        hosts never resolves).
    """
    matched = [
        ref
        for ref in refs
        if (not ref.remote and ref.name == identifier) or (ref.remote and _short_name(ref.name) == identifier)
    ]
    if not matched:
        return None

    return set().union(*(hosted[ref.name] for ref in matched))


def _tier_exact_slug(slug: str, hosted: dict[str, set[str]], disk: set[str]) -> set[str] | None:
    """Take the second tier — the exact topic slug.

    Args:
        slug: The normalized identifier.
        hosted: The hosted topic slugs per ref display name.
        disk: The on-disk topic slugs of the year.

    Returns:
        The slug itself when a ref hosts it or it sits on disk — the
        slug names exactly one topic, and a hosting ref's other topics
        are not matches of it (the per-pair tiering of the switch
        resolver) — ``None`` when neither matches (the tier is skipped).
    """
    if slug == "":
        return None
    if any(slug in slugs for slugs in hosted.values()) or slug in disk:
        return {slug}

    return None


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
        skipped). The short-name arm carries the exact tier's remote
        rule: a remote-tracking ref is read by its short name, a local
        branch by its full name alone — a slashed local branch's tail
        never widens the prefix. A non-ASCII identifier normalizes to
        the empty slug, which every slug starts with, so the
        slug-prefix arms stay disabled for it.
    """
    topics: set[str] = set()
    matched = [
        ref
        for ref in refs
        if ref.name.startswith(identifier) or (ref.remote and _short_name(ref.name).startswith(identifier))
    ]

    for ref in matched:
        topics |= hosted[ref.name]

    if slug != "":
        topics |= {hosted_slug for slugs in hosted.values() for hosted_slug in slugs if hosted_slug.startswith(slug)}
        topics |= {disk_slug for disk_slug in disk if disk_slug.startswith(slug)}
    if not matched and not topics:
        return None

    return topics


def _assemble_target(topic: str, refs: list[BranchRef], hosted: dict[str, set[str]], disk: set[str]) -> DeleteTarget:
    """Assemble one topic's target from the full inventory under the pointer model.

    The own branch is found BY NAME — a ref is part of the target only
    when its normalized name equals the topic slug — never by tree
    carriage, so a branch carrying the topic as merged work never turns
    into a deletion of the integration branch. The lookup walks the full
    inventory, never the tier that matched, so repeated identifiers of
    one topic in any order assemble the identical target.

    Args:
        topic: The identified topic slug.
        refs: The full branch inventory.
        hosted: The hosted topic slugs per ref display name.
        disk: The on-disk topic slugs of the year.

    Returns:
        The assembled target — the own local branch, the origin twin
        short name, and the survivor-gated disk presence: the directory
        joins the target only when no branch surviving the deletion
        carries the topic, for a survivor's tree outlives the deletion
        and removing the working-copy directory would dirty its checkout
        while the topic lives on in its commits. The survivors are the
        inventory minus the target's own refs — the own branch's own
        tree dies with the branch and never gates the directory.

    Raises:
        click.ClickException: the topic has carriers but no branch of
            its own — there is nothing to delete, it is history (no
            hosting branch is named); or several local refs normalize
            into the slug — they are all named in the error, and one of
            them must go first.
    """
    own_named = [ref for ref in refs if _normalized_name(ref) == topic]
    if not own_named:
        if any(topic in hosted[ref.name] for ref in refs):
            raise click.ClickException(
                f"topic {topic!r} has no branch — there is nothing to delete; it is history"
            )
        # Directory-only hygiene: nothing hosts the topic, so the disk
        # directory is all there is to remove.
        return DeleteTarget(topic=topic, branch=None, remote=None, has_dir=topic in disk)

    # Two local refs normalizing into one slug must never pick one of
    # them by inventory order — the named branch could be the one left
    # behind. The error is order-independent by construction.
    local_names = [ref.name for ref in own_named if not ref.remote]
    if len(local_names) > 1:
        names = ", ".join(local_names)
        raise click.ClickException(
            f"several branches host topic {topic!r}: {names} — remove all but one of them before deleting"
        )

    branch = local_names[0] if local_names else None
    # The twin is the *origin* twin — the one remote the deletion push of
    # the git cell addresses. A tracking ref of another remote named
    # after the topic stays an own ref, but it contributes no deletable
    # twin: its short name would otherwise be pushed at origin — a wrong
    # remote's branch deleted or a phantom "remote ref does not exist"
    # after the local branch is already gone.
    twin = next((ref for ref in own_named if ref.remote and ref.name.startswith("origin/")), None)
    remote = _short_name(twin.name) if twin is not None else None

    survivors = [ref for ref in refs if ref.name != branch and (twin is None or ref.name != twin.name)]
    carried = any(topic in hosted[ref.name] for ref in survivors)
    has_dir = topic in disk and not carried

    return DeleteTarget(topic=topic, branch=branch, remote=remote, has_dir=has_dir)


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
            raise click.ClickException(f"the current branch hosts topic {target.topic!r} — switch away before deleting")


def delete_topics(targets: list[DeleteTarget], year: str | None = None) -> str:
    """Delete confirmed targets — the local branch, the origin twin, and the topic directory of each.

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
        3. Emit the deletion notification of the target — after its full
           removal, with the removal composition
        4. Return the single outcome line

    Requirements:
        The commit is captured before the local deletion — after it the
        name no longer resolves.

        Targets removed before a failure stay removed; a failed remote
        deletion restores the failing target's local branch at the
        captured commit, and a failure of the restore itself is
        suppressed so the original remote reason surfaces.

        A target fires its deletion notification only after its complete
        removal — targets removed before a later failure already fired
        theirs, and a failure midway through a target raises before the
        emission, so nothing fires for it. No deleted-commit hash is
        carried.

        The directory removal is idempotent on absence — a missing
        directory is not an error.

    Constraints:
        Do not confirm, check merges, or re-resolve — the caller resolved
        the targets and owns the confirmation.

    Raises:
        click.ClickException: a git infrastructure failure (its stderr
            when git reports one, or a missing git binary), an OS failure
            of the removal, or the fatal ``ImportError`` of the
            hooks-registry assembly.
    """
    try:
        return _delete_topics(targets, year)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        raise click.ClickException(f"git failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(f"git is not available: {exc}") from exc
    except ImportError as exc:
        # The per-target emissions build the run registry on first delivery
        # — a broken ``goga_tool_*`` package is the platform's single fatal
        # case and surfaces here as one clean error, the ``switch_topic``
        # and ``ensure_topic`` boundary.
        raise click.ClickException(str(exc)) from exc
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
                # removed. Nothing fires for the failing target — the raise
                # precedes the emission below.
                if target.branch is not None:
                    with contextlib.suppress(subprocess.CalledProcessError, OSError):
                        create_branch_at_commit(target.branch, commit)
                raise
        directory_removed = remove_topic_dir(target.topic, resolved_year) if target.has_dir else False

        # The deletion notification fires after the target's full removal —
        # the identity carries no branch fact (the removal composition
        # carries the branch names instead) and no deleted-commit hash; the
        # facts come from the operation's own data, no git reads.
        identity = TopicIdentity(slug=target.topic, year=resolved_year, branch=None)
        TopicHooks().emit_deleted(
            identity,
            local_branch=target.branch,
            origin_twin=target.remote,
            directory_removed=directory_removed,
        )

    slugs = ", ".join(target.topic for target in targets)
    return f"Deleted {len(targets)} topic(s) of {resolved_year}: {slugs}"
