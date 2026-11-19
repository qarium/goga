"""Contract and logic tests for the ``render_contribution`` routine.

The contract class verifies the public API declared by the workflow-cell
CODEMANIFEST: importability from the facade (including the ``__all__``
obligation), the two-parameter signature with no defaults, and the
``WorkflowDocument`` annotations. The logic class covers the field-level
rendering behavior: the depth-driven walk over typed model fields and
verbatim extend bodies, string keys rendered with collision detection,
non-string scalars carried unchanged, purity, and the document dot-path
error vocabulary.
"""

from __future__ import annotations

import copy
import inspect
from typing import Any, get_type_hints

import pytest
from goga.pipeline.workflow import (
    WorkflowAssistant,
    WorkflowBuild,
    WorkflowDelegation,
    WorkflowDocument,
    WorkflowExtendStage,
    WorkflowGates,
    WorkflowGateStep,
    WorkflowMemory,
    WorkflowRepeat,
    WorkflowStage,
    render_contribution,
)
from jinja2 import Undefined


class TestRenderContributionContract:
    """Contract tests — the public API declared by the workflow-cell CODEMANIFEST."""

    def test_render_contribution_importable_from_facade(self) -> None:
        """render_contribution is importable from the facade and listed in ``__all__``."""
        import goga.pipeline.workflow as facade

        assert facade.render_contribution is render_contribution
        assert "render_contribution" in facade.__all__

    def test_render_contribution_signature_declares_document_and_context(self) -> None:
        """The signature declares exactly document and profile_data with no defaults."""
        parameters = inspect.signature(render_contribution).parameters

        assert list(parameters) == ["document", "profile_data"]
        assert all(parameter.default is inspect.Parameter.empty for parameter in parameters.values())

    def test_render_contribution_annotations_declare_document_types(self) -> None:
        """The annotations declare the document/context parameters and the document return."""
        hints = get_type_hints(render_contribution)

        assert hints["document"] is WorkflowDocument
        assert hints["profile_data"] == dict[str, Any]
        assert hints["return"] is WorkflowDocument


class TestRenderContributionLogic:
    """Logic tests — the field-level rendering behavior of the ``render_contribution`` routine."""

    def test_template_free_document_renders_to_an_equal_document(self) -> None:
        """A depth-covering document without template syntax renders to an equal document.

        Positive: every string value, string key, and nested model flows
        through the walk unchanged; the stage order and the input document
        survive the call untouched.
        """
        document = WorkflowDocument(
            prompt="plain",
            stages={"build": WorkflowStage(prompt="stage prompt", skills=["lint"], env={"A": "1"})},
            extend={"scan": WorkflowExtendStage(body={"title": "Scan", "roles": ["builder"]})},
            memory=WorkflowMemory(),
            agent="codex",
            env={"A": "1"},
        )

        rendered = render_contribution(document, {"model": "sonnet"})

        assert rendered == document
        assert list(rendered.stages) == ["build"]
        assert document.prompt == "plain"

    def test_renders_values_and_keys_at_any_depth(self) -> None:
        """Every string leaf and string mapping key renders at any depth of the document.

        Positive: stage map keys, stage prompts, notes keys, gate-step
        names and scripts, extend-body strings, assistant keys and fields,
        the build env map, and the global agent all render under the
        profile context.
        """
        document = WorkflowDocument(
            stages={
                "build-{{ suffix }}": WorkflowStage(
                    prompt="Run {{ model }}",
                    notes={"run-{{ suffix }}": "note {{ model }}"},
                    gates=[WorkflowGateStep(name="check-{{ suffix }}", script="echo {{ suffix }}")],
                ),
            },
            extend={
                "scan": WorkflowExtendStage(
                    body={"title": "Scan {{ suffix }}", "nested": {"deep": "{{ model }}"}},
                ),
            },
            assistants={
                "rev-{{ suffix }}": WorkflowAssistant(name="rev-{{ suffix }}", prompt="Review {{ model }}"),
            },
            build=WorkflowBuild(env={"K_{{ suffix }}": "{{ model }}"}),
            agent="agent-{{ suffix }}",
        )

        rendered = render_contribution(document, {"suffix": "ci", "model": "sonnet"})
        stage = rendered.stages["build-ci"]

        assert list(rendered.stages) == ["build-ci"]
        assert stage.prompt == "Run sonnet"
        assert stage.notes == {"run-ci": "note sonnet"}
        assert stage.gates[0].name == "check-ci"
        assert stage.gates[0].script == "echo ci"
        assert rendered.extend["scan"].body["title"] == "Scan ci"
        assert rendered.extend["scan"].body["nested"] == {"deep": "sonnet"}
        assert list(rendered.assistants) == ["rev-ci"]
        assert rendered.assistants["rev-ci"].name == "rev-ci"
        assert rendered.assistants["rev-ci"].prompt == "Review sonnet"
        assert rendered.build is not None
        assert rendered.build.env == {"K_ci": "sonnet"}
        assert rendered.agent == "agent-ci"

    def test_empty_context_renders_missing_keys_empty(self) -> None:
        """Without an active profile the render runs against an empty context.

        Edge: template syntax still processes and a missing top-level key
        interpolates empty — the standard Undefined semantics.
        """
        document = WorkflowDocument(prompt="a{{ missing }}b")

        rendered = render_contribution(document, {})

        assert rendered.prompt == "ab"

    def test_non_string_scalars_carried_unchanged(self) -> None:
        """Non-string scalars — including zeros, bools, and None — carry unchanged.

        Edge: an authored ``0`` and an explicit ``False`` are values, never
        absences; the int/bool/None fields never enter the engine.
        """
        document = WorkflowDocument(
            stages={"build": WorkflowStage(loop=3, skip=True, manual=False)},
            memory=None,
            delegation=WorkflowDelegation(depth=2, max_tasks=50),
            repeat=WorkflowRepeat(max_cycles=0, keep_runs=None),
            gates=WorkflowGates(patience=1),
        )

        rendered = render_contribution(document, {"x": "y"})
        stage = rendered.stages["build"]

        assert stage.loop == 3
        assert stage.skip is True
        assert stage.manual is False
        assert rendered.memory is None
        assert rendered.delegation == WorkflowDelegation(depth=2, max_tasks=50)
        assert rendered.repeat is not None
        assert rendered.repeat.max_cycles == 0
        assert rendered.repeat.keep_runs is None
        assert rendered.gates is not None
        assert rendered.gates.patience == 1

    def test_syntax_error_raises_with_class_message_and_dot_path(self) -> None:
        """A template syntax error raises one strict error with class, message, and dot-path.

        Negative: the unclosed print statement names the Jinja error class,
        the Jinja message, and the stage-prompt dot-path from source keys.
        """
        document = WorkflowDocument(stages={"build": WorkflowStage(prompt="Model: {{ model")})

        with pytest.raises(
            ValueError,
            match=r"template error at stages\.build\.prompt: TemplateSyntaxError: unexpected end of template",
        ):
            render_contribution(document, {"model": "sonnet"})

    def test_nested_undefined_access_raises_with_dot_path(self) -> None:
        """Nested access on a missing context key fails strict with the dot-path.

        Negative: the Jinja ``UndefinedError`` surfaces with its class name
        at the failing stage-prompt path.
        """
        document = WorkflowDocument(stages={"build": WorkflowStage(prompt="{{ worker.model }}")})

        with pytest.raises(ValueError, match=r"template error at stages\.build\.prompt: UndefinedError"):
            render_contribution(document, {})

    def test_error_in_a_dead_global_field_is_strict(self) -> None:
        """A template error in a never-merging global field fails strict — no field is exempt.

        Negative: the broken ``profile`` string raises even though a valid
        stage contribution exists beside it.
        """
        document = WorkflowDocument(profile="{{ broken", stages={"b": WorkflowStage(prompt="ok")})

        with pytest.raises(ValueError, match=r"template error at profile: TemplateSyntaxError"):
            render_contribution(document, {})

    def test_rendered_key_collision_names_map_sources_and_result(self) -> None:
        """Two source keys rendering to one result key raise one strict collision error.

        Negative: the message names the map dot-path, both source keys, and
        the colliding result key.
        """
        document = WorkflowDocument(
            stages={
                "build": WorkflowStage(prompt="ok"),
                'buil{{ "d" }}': WorkflowStage(prompt="fine"),
            },
        )

        with pytest.raises(
            ValueError,
            match=r"rendered key collision in stages: keys 'build' and 'buil\{\{ \"d\" \}\}' both render to 'build'",
        ):
            render_contribution(document, {})

    def test_error_path_indexes_lists_and_disambiguates_gates(self) -> None:
        """Error paths index list elements and disambiguate the two gates shapes positionally.

        Negative: a stage check-step list reports
        ``stages.<name>.gates[i].<field>`` while an extend-body list
        reports ``extend.<name>.body.<field>[i]``.
        """
        broken_stage = WorkflowDocument(
            stages={"review": WorkflowStage(gates=[WorkflowGateStep(name="check", script="{{ oops")])},
        )
        broken_extend = WorkflowDocument(
            extend={"scan": WorkflowExtendStage(body={"roles": ["fine", "{{ oops"]})},
        )

        with pytest.raises(
            ValueError,
            match=r"template error at stages\.review\.gates\[0\]\.script: TemplateSyntaxError",
        ):
            render_contribution(broken_stage, {})

        with pytest.raises(
            ValueError,
            match=r"template error at extend\.scan\.body\.roles\[1\]: TemplateSyntaxError",
        ):
            render_contribution(broken_extend, {})

    def test_rendered_empty_string_stays_present(self) -> None:
        """A rendered empty string is a value, not an absence — presence never changes.

        Edge: the missing key renders empty and the field stays present.
        """
        document = WorkflowDocument(prompt="{{ gone }}")

        rendered = render_contribution(document, {})

        assert rendered.prompt is not None
        assert rendered.prompt == ""

    def test_purity_the_input_tree_is_never_mutated(self) -> None:
        """The input tree is never mutated — the result is a fully new document.

        Positive: a deep snapshot survives the call identically and the
        rendered containers are new objects (equal, not identical).
        """
        document = WorkflowDocument(
            prompt="plain",
            stages={"build": WorkflowStage(prompt="stage", env={"A": "1"})},
            extend={"scan": WorkflowExtendStage(body={"title": "Scan"})},
            env={"A": "1"},
        )
        snapshot = copy.deepcopy(document)

        rendered = render_contribution(document, {"model": "sonnet"})

        assert document == snapshot
        assert rendered.stages is not document.stages
        assert rendered.stages == document.stages
        assert rendered.stages["build"] is not document.stages["build"]
        assert rendered.env is not document.env
        assert rendered.extend is not document.extend

    def test_walk_reconstructs_dataclasses_with_type_preserved(self) -> None:
        """The walk rebuilds every dataclass with its concrete type preserved.

        Positive: ``dataclasses.replace`` reconstructs each nested model —
        subclasses survive the render unchanged in type.
        """
        document = WorkflowDocument(
            stages={"build": WorkflowStage(gates=[WorkflowGateStep(name="check")])},
            extend={"scan": WorkflowExtendStage(body={"title": "Scan"})},
            assistants={"rev": WorkflowAssistant(name="rev")},
            build=WorkflowBuild(),
        )

        rendered = render_contribution(document, {})

        assert type(rendered) is WorkflowDocument
        assert type(rendered.stages["build"]) is WorkflowStage
        assert type(rendered.stages["build"].gates[0]) is WorkflowGateStep
        assert type(rendered.extend["scan"]) is WorkflowExtendStage
        assert type(rendered.assistants["rev"]) is WorkflowAssistant
        assert type(rendered.build) is WorkflowBuild

    def test_tuple_containers_recurse_and_rebuild_as_tuples(self) -> None:
        """Tuple containers recurse and rebuild as tuples at any nesting depth.

        Edge: the extend body is open-ended — a tuple of a string and a
        nested tuple walks element-wise and keeps the tuple types.
        """
        document = WorkflowDocument(
            extend={
                "scan": WorkflowExtendStage(
                    before=("build",),
                    body={"roles": ("a{{ x }}", ("deep-{{ x }}",))},
                ),
            },
        )

        rendered = render_contribution(document, {"x": "ci"})
        stage = rendered.extend["scan"]

        assert stage.before == ("build",)
        assert isinstance(stage.before, tuple)
        assert stage.body["roles"] == ("aci", ("deep-ci",))
        assert isinstance(stage.body["roles"], tuple)
        assert isinstance(stage.body["roles"][1], tuple)

    def test_template_free_strings_carry_their_bytes_verbatim(self) -> None:
        """A template-free string carries its exact bytes — CR sequences included.

        Edge: the Jinja lexer normalizes ``\\r\\n`` and ``\\r`` to ``\\n`` at
        compile; a string without template syntax never enters the engine,
        so every byte survives the render (the byte-identity contract).
        """
        windows = "line one\r\nline two\rplain"
        document = WorkflowDocument(
            prompt=windows,
            extend={"scan": WorkflowExtendStage(body={"crlf\r\nkey": windows})},
        )

        rendered = render_contribution(document, {"model": "sonnet"})

        assert rendered.prompt == windows
        assert list(rendered.extend["scan"].body) == ["crlf\r\nkey"]
        assert rendered.extend["scan"].body["crlf\r\nkey"] == windows

    def test_render_environment_carries_the_fixed_flags(self) -> None:
        """The contribution environment carries the same four flags render_workflow fixes.

        The flags are the contract, not object identity — a divergence
        between the two environments would ship silently.
        """
        from goga.pipeline.workflow.render_contribution import _RENDER_ENVIRONMENT

        assert _RENDER_ENVIRONMENT.trim_blocks is True
        assert _RENDER_ENVIRONMENT.lstrip_blocks is True
        assert _RENDER_ENVIRONMENT.keep_trailing_newline is True
        assert _RENDER_ENVIRONMENT.autoescape is False
        assert _RENDER_ENVIRONMENT.undefined is Undefined

    def test_block_tags_render_with_the_workflow_file_semantics(self) -> None:
        """Block tags render under the workflow-file flag semantics.

        Positive: ``trim_blocks``/``lstrip_blocks`` strip the block-tag
        newlines — a contributed ``{% for %}`` loop over the profile renders
        without dangling blank lines, exactly as the same body would inside
        a workflow-file.
        """
        loop = "{% for key, value in worker.env.items() %}{{ key }}={{ value }}\n{% endfor %}"
        document = WorkflowDocument(
            extend={"scan": WorkflowExtendStage(body={"exports": loop})},
        )

        rendered = render_contribution(document, {"worker": {"env": {"A": "1", "B": "2"}}})

        assert rendered.extend["scan"].body["exports"] == "A=1\nB=2\n"

    def test_non_string_mapping_keys_carry_and_their_values_render(self) -> None:
        """Non-string mapping keys carry verbatim; their values walk under bracket paths.

        Edge: the extend body is open-ended — an int key keeps its identity
        while its value renders, and a template error under it reports the
        bracket-repr path ``extend.<name>.body[<key>]``.
        """
        document = WorkflowDocument(
            extend={"scan": WorkflowExtendStage(body={1: "{{ model }}", "k": "v"})},
        )
        broken = WorkflowDocument(
            extend={"scan": WorkflowExtendStage(body={7: "{{ oops"})},
        )

        rendered = render_contribution(document, {"model": "sonnet"})

        assert list(rendered.extend["scan"].body) == [1, "k"]
        assert rendered.extend["scan"].body[1] == "sonnet"
        assert rendered.extend["scan"].body["k"] == "v"

        with pytest.raises(
            ValueError,
            match=r"template error at extend\.scan\.body\[7\]: TemplateSyntaxError",
        ):
            render_contribution(broken, {})

    def test_values_outside_the_walked_vocabulary_carry_verbatim(self) -> None:
        """Containers outside the walked vocabulary — a set — carry verbatim.

        Edge: the walk enumerates str, dataclass, dict, list, and tuple; a
        set of template strings is not a walked surface — the whole value
        carries unchanged, like every other non-walked leaf.
        """
        roles = {"a-{{ x }}", "b"}
        document = WorkflowDocument(
            extend={"scan": WorkflowExtendStage(body={"roles": roles})},
        )

        rendered = render_contribution(document, {"x": "ci"})

        assert rendered.extend["scan"].body["roles"] == {"a-{{ x }}", "b"}
