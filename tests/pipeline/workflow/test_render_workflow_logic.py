"""Logic tests for the ``render_workflow`` routine.

Covers behavior beyond the contract surface: the load-bearing env-iteration
pattern from the jinja2 practice (trim/lstrip keep the rendered text valid
YAML), the strict syntax-error surfacing with file name and line, the identity
render of template-free input, and the standard-Undefined missing-key
semantics (falsy/empty for top-level keys, a raw ``UndefinedError`` for nested
access on a missing key).
"""

from __future__ import annotations

import pytest
import yaml
from goga.pipeline.workflow import render_workflow
from jinja2 import Environment, TemplateSyntaxError, Undefined, UndefinedError


class TestRenderWorkflowLogic:
    """Logic tests — rendering behavior of the ``render_workflow`` routine."""

    def test_render_workflow_env_iteration_produces_valid_yaml(self) -> None:
        """The mapping-iteration pattern renders to YAML that round-trips the env map exactly.

        Positive: with the practice's ``{% for k, v in worker.env.items() %}``
        pattern the block tags vanish cleanly (trim_blocks + lstrip_blocks are
        load-bearing) and ``yaml.safe_load`` of the rendered text returns the
        env mapping back.
        """
        text = (
            "stages:\n"
            "  worker:\n"
            "    agent: {{ worker.agent }}\n"
            "    env:\n"
            "      {% for k, v in worker.env.items() %}\n"
            '      {{ k }}: "{{ v }}"\n'
            "      {% endfor %}\n"
        )
        profile_data = {"worker": {"agent": "codex", "env": {"A": "1", "B": "2"}}}

        document = yaml.safe_load(render_workflow(text, profile_data, source_name="w.yml"))

        assert document["stages"]["worker"]["agent"] == "codex"
        assert document["stages"]["worker"]["env"] == {"A": "1", "B": "2"}

    def test_render_workflow_syntax_error_names_file_and_line(self) -> None:
        """A Jinja syntax error raises one strict error naming the file, the line, and the cause.

        Negative: the unclosed ``{% if %}`` tag fails compilation; the message
        carries the ``source_name``, the ``lineno``, and the Jinja error text.
        """
        text = "stages:\n{% if %}\n  build:\n"
        expected_cause = _jinja_syntax_message(text)

        with pytest.raises(ValueError, match="template syntax error") as exc_info:
            render_workflow(text, {}, source_name="broken.yml")

        message = str(exc_info.value)
        assert "broken.yml" in message
        assert "line 2" in message
        assert "template syntax error" in message
        assert expected_cause in message

    def test_render_workflow_syntax_error_without_source_name_keeps_location(self) -> None:
        """The default empty source name still surfaces the line and the cause."""
        expected_cause = _jinja_syntax_message("{% if %}")

        with pytest.raises(ValueError, match="template syntax error") as exc_info:
            render_workflow("{% if %}", {})

        message = str(exc_info.value)
        assert "line 1" in message
        assert expected_cause in message

    def test_render_workflow_template_free_input_renders_to_itself(self) -> None:
        """A file without template syntax is byte-identical after rendering.

        The trailing newline survives — ``keep_trailing_newline`` is part of
        the fixed flag set.
        """
        text = "prompt: do the work\nstages:\n  build:\n    agent: claude\n"

        assert render_workflow(text, {"anything": "ignored"}, source_name="plain.yml") == text

    def test_render_workflow_missing_key_is_falsy_and_empty(self) -> None:
        """A missing top-level key follows the standard Undefined semantics.

        Falsy inside an ``{% if %}`` guard, empty string when interpolated —
        never a ``StrictUndefined`` failure.
        """
        guard = render_workflow("{% if worker %}yes{% else %}no{% endif %}", {})
        interpolated = render_workflow("agent: '{{ worker }}'", {})

        assert guard == "no"
        assert interpolated == "agent: ''"

    def test_render_workflow_nested_access_on_missing_key_raises_undefined(self) -> None:
        """Nested access on a missing key raises the Jinja ``UndefinedError`` unwrapped."""
        with pytest.raises(UndefinedError):
            render_workflow("agent: {{ worker.agent }}", {})

    def test_render_workflow_profile_context_drives_interpolation(self) -> None:
        """Every top-level profile key is a template variable — the whole profile is the context."""
        profile_data = {"worker": {"agent": "codex", "model": "sonnet"}, "flavor": "hard"}

        rendered = render_workflow("agent: {{ worker.agent }} ({{ worker.model }}, {{ flavor }})", profile_data)

        assert rendered == "agent: codex (sonnet, hard)"

    def test_render_workflow_module_reads_no_files_or_environment(self) -> None:
        """The module is pure — its source never reads files, ``os.environ``, or parses YAML."""
        import inspect
        from pathlib import Path

        from goga.pipeline.workflow import render_workflow as routine

        source = Path(inspect.getsourcefile(routine)).read_text()  # type: ignore[arg-type]

        assert "yaml" not in source
        assert "os.environ" not in source
        assert "getenv" not in source
        assert "read_text" not in source

    def test_render_workflow_environment_carries_the_fixed_flags(self) -> None:
        """The rendering environment carries the ADR-fixed flag set and the standard Undefined.

        ``autoescape`` stays off (the engine renders YAML text, not HTML) and
        the undefined class is the standard ``Undefined`` — never
        ``StrictUndefined`` or ``ChainableUndefined``.
        """
        from goga.pipeline.workflow.render_workflow import _RENDER_ENVIRONMENT

        assert _RENDER_ENVIRONMENT.trim_blocks is True
        assert _RENDER_ENVIRONMENT.lstrip_blocks is True
        assert _RENDER_ENVIRONMENT.keep_trailing_newline is True
        assert _RENDER_ENVIRONMENT.autoescape is False
        assert _RENDER_ENVIRONMENT.undefined is Undefined


def _jinja_syntax_message(text: str) -> str:
    """Return the exact Jinja syntax-error message for ``text``.

    Args:
        text: the template text jinja2 fails to compile.

    Returns:
        The ``TemplateSyntaxError.message`` jinja2 itself produces — pinning
        the carried cause without hard-coding jinja2's wording.
    """
    try:
        Environment().from_string(text)

    except TemplateSyntaxError as exc:
        return str(exc.message)

    raise AssertionError("the fixture text must carry a Jinja syntax error")
