"""The interactive survey engine of the onboarding session.

The entity declared in the cell CODEMANIFEST with ``location: questionnaire.py``:
the engine ``Questionnaire``. The engine asks the declarative records of
the plan itself — the conditional core sections and the tool blocks under
their attribution headings — and records every collected value into the
answer space at its plan path; a tool hook is never called to survey.
"""

from __future__ import annotations

import logging

import click

from ..questions import Question, QuestionGroup, SessionAnswers
from .core import agent_env_defaults, image_defaults
from .plan import SessionPlan

logger = logging.getLogger(__name__)

# The prefill pair the base-convention gate contributes to the codemanifest
# section on acceptance — ported from the old wizard's ask_base_convention.
_CONVENTION_USAGES_PREFILL = {"conventions": ".goga/usages/conventions.md"}
_CONVENTION_ANNOTATIONS_PREFILL = "Use `conventions` for code writing rules and testing."


def _hint_lines(prompt: str) -> list[str]:
    """Collect the hint entries a question prompt carries as list lines.

    The core tree embeds the completed image hints as ``- name:tag`` list
    lines of the ``base_image`` prompt; the pull branch re-renders them for
    the image ask without the FROM label.

    Args:
        prompt: The prompt text of the question carrying the hints.

    Returns:
        The hint entries in prompt order; an empty list when the prompt
        carries no list lines.
    """
    hints: list[str] = []
    for line in prompt.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            hints.append(stripped[2:])
    return hints


def _language_hints(base_image: Question, language: str | None) -> tuple[list[str], str | None]:
    """Filter the hint lines of the ``base_image`` prompt by the selected language.

    The core tree embeds the completed hints of every language family; the
    engine renders the family of the selected language with its last entry
    as the offered default (the ``image_defaults`` practice — the hints
    depend on the selected language). An absent or unknown language falls
    back to every hint with the tree default.

    Args:
        base_image: The base image question carrying the hint lines of the
            tree.
        language: The recorded language answer; None when the language
            question was never asked.

    Returns:
        The hint lines to render and the offered default.
    """
    hints = _hint_lines(base_image.prompt)
    if language is None:
        return hints, base_image.default

    names = set(image_defaults.get(language, []))
    family = [hint for hint in hints if hint.rsplit(":", 1)[0] in names]
    if not family:
        return hints, base_image.default

    return family, family[-1]


class Questionnaire:
    """The interactive survey engine of the session.

    The engine asks the declarative records of the plan itself: the core
    sections through their conditional patterns, then every tool block under
    its attribution heading, in plan order. Confirm gates are
    presentational — they drive control flow and are never recorded; only
    the children present in the post-skip section are asked; an unaskable
    question (an unknown kind or a missing parameterization) is skipped with
    a warning naming its path.

    Requirements:
        a tool hook is never called to survey — the engine asks the
        buffered records itself; ``click.Abort`` propagates to the caller.
    """

    def __init__(self) -> None:
        """Create the engine with no active answer space.

        The space of the run and the path of the question being asked are
        engine state held only while ``run`` is active — the public ask
        methods stay callable outside a run and then merely return values.
        """
        self._answers: SessionAnswers | None = None
        self._current_path: str | None = None

    # --- Public API ---

    def run(self, plan: SessionPlan, answers: SessionAnswers) -> None:
        """Run the whole survey of one plan into the answer space.

        Echoes the session header, surveys the core sections in order
        through their conditional patterns, then every tool block under its
        attribution heading — an emptied block is suppressed. Every
        collected value lands in ``answers`` at its plan path
        (``"{tool}.{local}"`` for tool answers).

        Args:
            plan: The assembled plan with skips applied.
            answers: The session answer space receiving the collected
                values.

        Raises:
            click.Abort: Propagates from any interrupted prompt.
        """
        self._answers = answers
        try:
            click.echo("=== Goga Project Initialization ===")
            click.echo("This wizard will help you set up a new goga project.\n")

            state: dict = {}
            for child in plan.root.children or []:
                if child.id in plan.tools and isinstance(child, QuestionGroup):
                    self._survey_tool_block(child)
                else:
                    self._survey_core_section(child, state)
        finally:
            self._answers = None
            self._current_path = None

    def ask_question(self, question: Question) -> str | bool | dict[str, str] | None:
        """Ask one simple question of its kind.

        Args:
            question: The question record — its prompt, offered choices or
                keys, and default are rendered as asked.

        Returns:
            The answer value of the kind — a string for the choice and
            input kinds, a boolean for the confirm kind, a mapping of
            strings for the pairs kind; None when the question is
            unaskable (an unknown kind or a missing parameterization) —
            announced with a warning naming the question path, never
            asked, never recorded.
        """
        path = self._current_path or question.id

        if question.kind == "choice":
            if not question.choices:
                logger.warning("skipped the question %s: %s", path, "the choice kind requires choices")
                return None
            return click.prompt(question.prompt, type=click.Choice(question.choices))

        if question.kind == "input":
            return click.prompt(question.prompt, default=question.default)

        if question.kind == "confirm":
            return click.confirm(question.prompt, default=question.default or False)

        if question.kind == "pairs":
            return self._ask_pairs(question.prompt, question.keys)

        logger.warning("skipped the question %s: %s", path, f"unknown kind {question.kind}")
        return None

    def ask_group(self, group: QuestionGroup, prefix: str | None = None) -> dict:
        """Ask one group — its children in order.

        Echoes the group prompt as the heading (a heading derived from the
        group id when the group carries no prompt), then asks the children
        in order, recursing into nested groups. The optional ``prefix``
        (the tool id) qualifies the record paths — ``"{tool}.{local}"`` for
        the answers of a tool block — through the answer space of the
        active run; outside a run the call only returns the mapping.

        Args:
            group: The group node — a section or a tool block.
            prefix: The record-path prefix of the group — the tool id for
                a tool block, the dotted parent path for a nested group.

        Returns:
            The mapping of the children's answers keyed by child ids.
        """
        heading = group.prompt if group.prompt is not None else f"--- {group.id} ---"
        click.echo(f"\n{heading}")

        collected: dict = {}
        for child in group.children or []:
            path = f"{prefix}.{child.id}" if prefix else child.id
            if isinstance(child, QuestionGroup):
                collected[child.id] = self.ask_group(child, prefix=path)
                continue
            self._current_path = path
            try:
                value = self.ask_question(child)
            finally:
                self._current_path = None
            if value is None:
                continue
            collected[child.id] = value
            self._record(path, value)

        return collected

    # --- Recording and asking helpers ---

    def _record(self, path: str, value: str | bool | dict) -> None:
        """Record one collected value at its plan path through the run's answer space.

        Args:
            path: The plan dot-path of the answered question.
            value: The answer value of the question kind.
        """
        if self._answers is not None:
            self._answers.record(path, value)

    def _ask_pairs(self, prompt: str, keys: list[str] | None) -> dict[str, str]:
        """Collect one repeated key-value collection of the pairs kind.

        The proposed keys — the suggested env keys of an agent or the
        ``keys`` parameterization of the record — are rendered and offered
        first through a confirm; the add-another loop then collects
        arbitrary key-value pairs (the old ``_collect_agent_env`` pattern).

        Args:
            prompt: The prompt text of the pairs question.
            keys: The proposed keys offered first; None or empty offers
                the arbitrary loop only.

        Returns:
            The collected mapping; empty when nothing was collected.
        """
        pairs: dict[str, str] = {}

        click.echo(prompt)

        suggested = keys or []
        if suggested:
            click.echo("Suggested keys:")
            for key in suggested:
                click.echo(f"  - {key}")
            if click.confirm("Set suggested keys?", default=False):
                for key in suggested:
                    pairs[key] = click.prompt(f"  {key}")

        if click.confirm("Add another pair?", default=False):
            while True:
                key = click.prompt("Key")
                pairs[key] = click.prompt("Value")
                if not click.confirm("Add another?", default=False):
                    break

        return pairs

    # --- The core-section conditional patterns ---

    def _survey_core_section(self, section: Question | QuestionGroup, state: dict) -> None:
        """Survey one core section through its conditional pattern.

        The pattern is selected by the section id; the eight core sections
        carry their own surveys, anything else degrades to the generic
        group or single-question ask.

        Args:
            section: The core section — a question or a group.
            state: The per-run survey state carrying the recorded language
                and the codemanifest prefill of the base-convention gate.
        """
        if isinstance(section, QuestionGroup) and section.prompt is not None:
            click.echo(f"\n{section.prompt}")

        simple = {
            "build": self._survey_build,
            "pipeline": self._survey_pipeline,
            "tools": self._survey_tools,
        }
        if section.id == "language":
            self._survey_language(section, state)
        elif section.id == "convention":
            self._survey_convention(section, state)
        elif section.id == "codemanifest":
            self._survey_codemanifest(section, state)
        elif section.id == "docker_image":
            self._survey_docker_image(section, state)
        elif section.id == "usages":
            self._survey_usages()
        elif (handler := simple.get(section.id)) is not None:
            handler(section)
        elif isinstance(section, QuestionGroup):
            self.ask_group(section)
        else:
            value = self.ask_question(section)
            if value is not None:
                self._record(section.id, value)

    def _survey_language(self, section: Question, state: dict) -> None:
        """Survey the language choice — the first question of every session.

        The recorded language drives the image hint family of the docker
        image section.
        """
        language = self.ask_question(section)
        self._record("language", language)
        state["language"] = language

    def _survey_convention(self, section: QuestionGroup, state: dict) -> None:
        """Survey the base-convention gate.

        The gate is presentational — its answer is never recorded; it only
        pre-fills the codemanifest section on acceptance.

        Args:
            section: The convention section — the adopt confirm.
            state: The per-run survey state receiving the prefill pair.
        """
        adopt = next((child for child in section.children or [] if child.id == "adopt"), None)
        accepted = bool(self.ask_question(adopt)) if adopt is not None else False

        if accepted:
            state["codemanifest_usages"] = _CONVENTION_USAGES_PREFILL
            state["codemanifest_annotations"] = _CONVENTION_ANNOTATIONS_PREFILL

    def _survey_codemanifest(self, section: QuestionGroup, state: dict) -> None:
        """Survey the codemanifest entries — the usages pairs, then the annotations input.

        Both records carry no tree defaults: the prefill of the convention
        gate is engine-side state offered first.

        Args:
            section: The codemanifest section — usages and annotations.
            state: The per-run survey state carrying the prefill pair.
        """
        children = {child.id: child for child in section.children or []}

        usages_question = children.get("usages")
        if usages_question is not None:
            usages = self._collect_usages(usages_question, state.get("codemanifest_usages"))
            if usages:
                self._record("codemanifest.usages", usages)

        annotations_question = children.get("annotations")
        if annotations_question is not None:
            annotations = self._collect_annotations(annotations_question, state.get("codemanifest_annotations"))
            if annotations is not None:
                self._record("codemanifest.annotations", annotations)

    def _collect_usages(self, question: Question, prefill: dict | None) -> dict | None:
        """Collect the codemanifest usages onto the prefill of the convention gate.

        The prefill entries are offered first; the gate then offers the
        repeated name-value collection, a repeated name skipped with a
        note — ported from the old wizard's ask_codemanifest_usages.

        Args:
            question: The usages pairs record.
            prefill: The pre-filled entries of the convention gate; None
                when the gate was declined or absent.

        Returns:
            The merged usages mapping; None when neither prefill nor input
            exists.
        """
        usages = dict(prefill) if prefill else None

        click.echo(question.prompt)
        if usages:
            click.echo("Prefilled usages:")
            for name, path in usages.items():
                click.echo(f"  {name}: {path}")

        if click.confirm("Add codemanifest usages?", default=False):
            if usages is None:
                usages = {}
            while True:
                name = click.prompt("Usage name")
                if name in usages:
                    click.echo(f'Usage "{name}" already exists, skipping.')
                else:
                    usages[name] = click.prompt("Usage value")
                if not click.confirm("Add another codemanifest usage?", default=False):
                    break

        return usages

    def _collect_annotations(self, question: Question, prefill: str | None) -> str | None:
        """Collect the codemanifest annotations appended to the prefill text.

        Args:
            question: The annotations input record.
            prefill: The pre-filled text of the convention gate; None when
                the gate was declined or absent.

        Returns:
            The merged annotations text; None when neither exists.
        """
        annotations = prefill

        if click.confirm("Add codemanifest annotations?", default=False):
            custom = click.prompt(question.prompt)
            annotations = f"{annotations}\n{custom}" if annotations is not None else custom

        return annotations

    def _survey_build(self, section: QuestionGroup) -> None:
        """Survey the build executor — the agent gate, then agent and env."""
        self._survey_executor(section, "build")

    def _survey_pipeline(self, section: QuestionGroup) -> None:
        """Survey the pipeline executor — the agent gate, then agent and env."""
        self._survey_executor(section, "pipeline")

    def _survey_executor(self, section: QuestionGroup, section_id: str) -> None:
        """Survey one executor section — the gated agent choice plus env pairs.

        The gate is presentational: declining records nothing for the
        section. Accepting asks the agent choice, then the env pairs with
        the suggested keys of the selected agent offered first and
        arbitrary additions after. A child absent from the post-skip
        section is never asked — the branch collapses to the remaining
        path.

        Args:
            section: The executor section — agent and env.
            section_id: The section local name (build or pipeline).
        """
        if not click.confirm(f"Configure a {section_id} agent?", default=False):
            return

        children = {child.id: child for child in section.children or []}

        agent: str | None = None
        agent_question = children.get("agent")
        if agent_question is not None:
            agent = self.ask_question(agent_question)
            self._record(f"{section_id}.agent", agent)

        env_question = children.get("env")
        if env_question is not None:
            env = self._ask_pairs(env_question.prompt, agent_env_defaults.get(agent, []))
            if env:
                self._record(f"{section_id}.env", env)

    def _survey_docker_image(self, section: QuestionGroup, state: dict) -> None:
        """Survey the docker image section through the Dockerfile decision.

        A skipped ``dockerfile`` question collapses the gate — the pull
        branch runs directly. With the gate: acceptance asks the Dockerfile
        path, the base image of the FROM (only when present), and the
        built-image name; rejection pulls a pre-built image instead. A
        skipped ``base_image`` collapses the FROM — never asked, never
        recorded. The rendered hints and the offered default follow the
        family of the recorded language (the ``image_defaults`` practice).

        Args:
            section: The docker image section — dockerfile, base_image,
                image.
            state: The per-run survey state carrying the recorded language.
        """
        children = {child.id: child for child in section.children or []}
        language = state.get("language")

        if "dockerfile" not in children:
            self._ask_pull_image(children, language)
            return

        if not click.confirm("Create Dockerfile?", default=False):
            self._ask_pull_image(children, language)
            return

        self._record("docker_image.dockerfile", self.ask_question(children["dockerfile"]))

        base_image = children.get("base_image")
        if base_image is not None:
            hints, default = _language_hints(base_image, language)
            self._render_hints(hints)
            self._record("docker_image.base_image", click.prompt("Base image (FROM)", default=default))

        image = children.get("image")
        if image is not None:
            self._record("docker_image.image", self.ask_question(image))

    def _render_hints(self, hints: list[str]) -> None:
        """Echo the hint lines of one image ask — the family of the selected language.

        Args:
            hints: The hint lines to render; empty renders nothing.
        """
        if hints:
            click.echo("Available images:")
            for hint in hints:
                click.echo(f"  - {hint}")

    def _ask_pull_image(self, children: dict, language: str | None) -> None:
        """Ask the pre-built image to pull — the no-Dockerfile branch.

        The hints of the ``base_image`` record are rendered when the tree
        carries them, filtered to the family of the selected language (its
        last entry is the offered default); without them the ask is plain
        free-form.

        Args:
            children: The children of the post-skip docker image section,
                keyed by local name.
            language: The recorded language answer; None renders every
                hint of the tree.
        """
        image = children.get("image")
        if image is None:
            return

        base_image = children.get("base_image")
        if base_image is not None:
            hints, default = _language_hints(base_image, language)
            self._render_hints(hints)
            value = click.prompt("Docker image", default=default)
        else:
            value = click.prompt("Docker image", default=image.default)

        self._record("docker_image.image", value)

    def _survey_tools(self, section: Question) -> None:
        """Survey the tools collection — the confirm-gated name → version pairs.

        The gate is presentational; the prompt documents the four version
        grammar forms; an empty version input reads as latest.

        Args:
            section: The tools pairs record.
        """
        click.echo(section.prompt)

        if not click.confirm("Add tools?", default=False):
            return

        tools: dict[str, str] = {}
        while True:
            name = click.prompt("Tool name")
            version = click.prompt("Tool version", default="latest")
            tools[name] = version
            if not click.confirm("Add another tool?", default=False):
                break

        self._record("tools", tools)

    def _survey_usages(self) -> None:
        """Survey the usages records — the confirm-gated record loop.

        The section is structural — no declarable children; the engine
        drives the record loop. Per record: group, dependency name, git
        URL, optional ref and root (an empty input omits the optional
        entry). The records accumulate as
        ``{group: {dep: {git, ref?, root?}}}`` — a later record of the
        same group merges under the group key.
        """
        if not click.confirm("Add usages records?", default=False):
            return

        records: dict[str, dict[str, dict[str, str]]] = {}
        while True:
            group = click.prompt("Usage group")
            dependency = click.prompt("Dependency name")
            entry: dict[str, str] = {"git": click.prompt("Git URL")}
            ref = click.prompt("Ref (optional)", default="")
            if ref:
                entry["ref"] = ref
            root = click.prompt("Root (optional)", default="")
            if root:
                entry["root"] = root
            records.setdefault(group, {})[dependency] = entry
            if not click.confirm("Add another usage record?", default=False):
                break

        self._record("usages", records)

    # --- The tool blocks ---

    def _survey_tool_block(self, block: QuestionGroup) -> None:
        """Survey one tool block under its attribution heading.

        An emptied block is suppressed — no heading, no questions. The
        heading renders from the block id when the block carries no
        prompt.

        Args:
            block: The tool block group — the buffered records of one
                tool's declaration.
        """
        if not block.children:
            return
        self.ask_group(block, prefix=block.id)
