"""The session answer space of the onboarding session.

The entity declared in the cell CODEMANIFEST with ``location: answers.py``:
the accumulator ``SessionAnswers``. The space is the single mutable
accumulator of one run — every answer, core and tool, lands here exactly
once. The structure is nested mappings keyed by question ids — groups hold
mappings, no dotted keys are ever stored.
"""

from __future__ import annotations

from copy import deepcopy


def _resolve_parent(data: dict, segments: list[str]) -> dict:
    """Walk the leading segments of one answer path, creating the intermediate mappings.

    A non-mapping value met mid-path — a scalar recorded earlier at a shorter
    path — is replaced by a fresh mapping: the authoritative writer extends
    the space.

    Args:
        data: The nested mapping the walk mutates in place.
        segments: Every segment of the dot-path but the leaf name of the
            addressed entry.

    Returns:
        The mapping that holds the leaf name — the parent of the addressed
        entry.
    """
    node: dict = data

    for segment in segments:
        child = node.get(segment)

        if not isinstance(child, dict):
            child = {}
            node[segment] = child

        node = child

    return node


def _merge_into(target: dict, source: dict) -> None:
    """Recursively merge ``source`` into ``target`` — mappings merge, the rest replaces.

    Args:
        target: The mapping merged into, mutated in place.
        source: The mapping whose entries win at every conflicting leaf.
    """
    for key, value in source.items():
        existing = target.get(key)

        if isinstance(existing, dict) and isinstance(value, dict):
            _merge_into(existing, value)
        else:
            target[key] = value


class SessionAnswers:
    """The answer space of one session — the single mutable accumulator of the run.

    The question-to-value mapping shared by the survey, the tool
    participation, and the file generation. The survey records, the tool
    contributions amend, the generator snapshots — the space itself stays
    silent and total: it raises nothing and logs nothing.

    Requirements:
        - Created empty — the space holds no answers; ``tools`` reserves the
          top-level keys of the tool sections without creating them; the
          structure is nested mappings keyed by question ids — groups hold
          mappings, no dotted keys are ever stored
        - Every answer, core and tool, lands here exactly once
    """

    def __init__(self, tools: list[str] | None = None) -> None:
        """Create the empty space.

        Args:
            tools: The reserved top-level keys of the tool sections — the
                identities of the tools whose blocks the plan carries; None
                when the space holds no tool sections.
        """
        self._tool_sections = frozenset(tools or ())
        self._data: dict = {}

    def record(self, id: str, value: str | bool | dict) -> None:
        """Record the user's answer collected by the survey.

        Recording replaces — a later record at the same path overwrites the
        earlier value; merging belongs to amendments.

        Args:
            id: The dot-path of the answered question in the plan tree.
            value: The answer value of the question kind.
        """
        segments = id.split(".")

        parent = _resolve_parent(self._data, segments[:-1])

        parent[segments[-1]] = value

    def amend(self, id: str, value: str | bool | dict) -> None:
        """Apply one amendment of a tool contribution at the addressed location.

        An existing mapping at the leaf merges recursively with ``value``; a
        scalar or a list replaces; an absent leaf is created. Substituting a
        user's answer is a tool's lawful right — the amendment applies
        silently.

        Args:
            id: The dot-path of the addressed entry.
            value: The amendment value.
        """
        segments = id.split(".")

        parent = _resolve_parent(self._data, segments[:-1])

        name = segments[-1]
        existing = parent.get(name)

        if isinstance(existing, dict) and isinstance(value, dict):
            _merge_into(existing, value)
        else:
            parent[name] = value

    def view_for(self, tool: str) -> dict:
        """Return the isolated answer view of one tool.

        The core section — every top-level key except the reserved
        tool-section names — plus the tool's own section re-keyed by local
        names, without the tool prefix. The answers of other tools are never
        present: coordination goes through amendments of shared sections, not
        through reading foreign data.

        Args:
            tool: The tool identity.

        Returns:
            The isolated view — a deep copy; amendments applied after the
            call do not appear in it.
        """
        view = {key: deepcopy(value) for key, value in self._data.items() if key not in self._tool_sections}

        if tool in self._tool_sections:
            own = self._data.get(tool)

            if isinstance(own, dict):
                view.update(deepcopy(own))

        return view

    def snapshot(self) -> dict:
        """Return the full answer space for generation.

        Returns:
            The complete nested structure — the core and every committed tool
            section — as a deep copy of the committed state at the call
            moment.
        """
        return deepcopy(self._data)
