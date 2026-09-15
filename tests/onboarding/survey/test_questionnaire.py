"""Contract and logic tests for the entity declared in
``goga/onboarding/survey/CODEMANIFEST`` with ``location: questionnaire.py``:

- ``Questionnaire()`` — the interactive survey engine of the session

The engine asks the declarative records of the plan itself — the conditional
core sections and the tool blocks under their attribution headings — and
records every value at its plan path. Confirm gates are presentational and
never recorded; a skipped subtree is never asked; an unaskable question is
skipped with a warning naming its path.
"""

from __future__ import annotations

import logging
from pathlib import Path

import click
import pytest
import yaml
from click.testing import CliRunner, Result
from goga.config import load_project_config
from goga.onboarding.participation import ToolDeclaration
from goga.onboarding.questions import Question, QuestionGroup, SessionAnswers
from goga.onboarding.survey import (
    Questionnaire,
    SessionPlan,
    apply_skips,
    assemble_session_plan,
    core_questions,
)

_CELL_ALL = ["Questionnaire", "SessionPlan", "apply_skips", "assemble_session_plan", "core_questions"]

# The last completed hint of the python family of `image_defaults` — the
# offered default of every image ask after the python language choice (the
# hints follow the selected language; a language never asked falls back to
# the last hint of every family, the swift one).
_PYTHON_LAST_HINT_1_3 = "qarium/goga-python-3.14:1.3"


def _declaration(tool: str, *items: Question | QuestionGroup) -> ToolDeclaration:
    """Build one delivered declaration of a tool — items declared, no skips."""
    surface = ToolDeclaration(tool=tool, invited=True)
    for item in items:
        surface.declare(item)
    return surface


def _minimal_plan(*declarations: ToolDeclaration) -> SessionPlan:
    """Build a plan from a minimal core — the language choice only."""
    core = QuestionGroup(
        id="core",
        children=[Question(id="language", kind="choice", prompt="Language", choices=["python", "golang"])],
    )
    return assemble_session_plan(core, list(declarations))


def _full_plan(convention_exists: bool) -> SessionPlan:
    """Build the plan of the full core tree with the 1.3 tag and a project name."""
    core = core_questions("1.3", "my-app", convention_exists)
    return assemble_session_plan(core, [])


def _run_survey(plan: SessionPlan, answers: SessionAnswers, inputs: list[str]) -> Result:
    """Drive one survey through a click command under the CliRunner."""
    runner = CliRunner()

    @click.command()
    def _session() -> None:
        Questionnaire().run(plan, answers)

    return runner.invoke(_session, input="".join(f"{line}\n" for line in inputs))


# --- Contract tests ---


class TestQuestionnaireContract:
    def test_entity_is_importable_from_the_package_facade(self) -> None:
        """The engine lives on the cell package and its ``__all__`` is exact."""
        import goga.onboarding.survey as cell

        assert cell.Questionnaire is Questionnaire
        assert cell.__all__ == _CELL_ALL

    def test_the_engine_constructs_with_no_arguments(self) -> None:
        """``Questionnaire()`` carries no required collaborators."""
        assert Questionnaire() is not None

    def test_the_public_methods_are_callable(self) -> None:
        """``run``, ``ask_question``, and ``ask_group`` are callable."""
        engine = Questionnaire()

        assert callable(engine.run)
        assert callable(engine.ask_question)
        assert callable(engine.ask_group)

    def test_ask_group_one_argument_shape_returns_the_mapping(self) -> None:
        """The declared one-argument call asks the children and returns their mapping."""
        engine = Questionnaire()
        group = QuestionGroup(id="g", prompt="--- G ---", children=[Question(id="token", kind="input", prompt="Token")])
        runner = CliRunner()

        @click.command()
        def _ask() -> None:
            click.echo(f"collected={engine.ask_group(group)}")

        result = runner.invoke(_ask, input="t0\n")

        assert result.exit_code == 0
        assert "'token': 't0'" in result.output


# --- Logic tests — the run over the plan ---


class TestRunSurvey:
    def test_questionnaire_records_core_and_tool_answers(self) -> None:
        """Core answers land at their section path; tool answers nest under the tool key."""
        plan = _minimal_plan(_declaration("my-tool", Question(id="token", kind="input", prompt="Token")))
        answers = SessionAnswers(tools=["my-tool"])

        result = _run_survey(plan, answers, ["python", "t0"])

        assert result.exit_code == 0
        assert answers.snapshot() == {"language": "python", "my-tool": {"token": "t0"}}

    def test_unknown_kind_is_skipped_with_warning(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """An unknown kind is never asked — a warning names the question path."""
        plan = _minimal_plan(
            _declaration(
                "my-tool",
                Question(id="bad", kind="text", prompt="Weird"),
                Question(id="ok", kind="input", prompt="Token"),
            )
        )
        answers = SessionAnswers(tools=["my-tool"])

        with caplog.at_level(logging.WARNING):
            result = _run_survey(plan, answers, ["python", "t0"])

        assert result.exit_code == 0
        assert answers.snapshot() == {"language": "python", "my-tool": {"ok": "t0"}}
        assert any("my-tool.bad" in record.message for record in caplog.records)
        assert "Weird" not in result.output

    def test_missing_parameterization_is_skipped_with_warning(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A choice without choices is unaskable — skipped with a warning."""
        plan = _minimal_plan(
            _declaration(
                "my-tool",
                Question(id="pick", kind="choice", prompt="Pick"),
                Question(id="ok", kind="input", prompt="Token"),
            )
        )
        answers = SessionAnswers(tools=["my-tool"])

        with caplog.at_level(logging.WARNING):
            result = _run_survey(plan, answers, ["python", "t0"])

        assert result.exit_code == 0
        assert answers.snapshot() == {"language": "python", "my-tool": {"ok": "t0"}}
        assert any("my-tool.pick" in record.message for record in caplog.records)

    def test_the_session_header_is_echoed(self) -> None:
        """The run opens with the ported session header and wizard description."""
        plan = _minimal_plan()
        answers = SessionAnswers()

        result = _run_survey(plan, answers, ["python"])

        assert "=== Goga Project Initialization ===" in result.output
        assert "This wizard will help you set up a new goga project." in result.output

    def test_an_emptied_tool_block_is_suppressed(self) -> None:
        """A block emptied by skips renders no heading and asks nothing."""
        plan = _minimal_plan(
            _declaration("my-tool", Question(id="token", kind="input", prompt="Token")),
            _declaration("viewer", Question(id="opt", kind="confirm", prompt="Opt in")),
        )
        skips = [("my-tool", "token"), ("viewer", "opt")]
        answers = SessionAnswers(tools=["my-tool", "viewer"])

        result = _run_survey(apply_skips(plan, skips), answers, ["python"])

        assert result.exit_code == 0
        assert answers.snapshot() == {"language": "python"}
        assert "--- Tool: my-tool ---" not in result.output
        assert "--- Tool: viewer ---" not in result.output

    def test_nested_tool_groups_record_at_nested_paths(self) -> None:
        """A nested group of a tool block records under its group key."""
        plan = _minimal_plan(
            _declaration(
                "my-tool",
                QuestionGroup(
                    id="reporting",
                    children=[Question(id="enabled", kind="confirm", prompt="Enable reporting")],
                ),
                Question(id="token", kind="input", prompt="Token"),
            )
        )
        answers = SessionAnswers(tools=["my-tool"])

        result = _run_survey(plan, answers, ["python", "y", "t0"])

        assert result.exit_code == 0
        assert answers.snapshot() == {
            "language": "python",
            "my-tool": {"reporting": {"enabled": True}, "token": "t0"},
        }
        assert "--- reporting ---" in result.output

    def test_click_abort_propagates(self) -> None:
        """An interrupted prompt aborts the session — the engine swallows nothing."""
        plan = _minimal_plan()
        answers = SessionAnswers()

        result = _run_survey(plan, answers, [])

        assert result.exit_code != 0


# --- Logic tests — the core-section patterns (ported from the old wizard) ---


class TestCorePatterns:
    def test_convention_acceptance_prefills_codemanifest(self) -> None:
        """Accepting the gate pre-fills usages and annotations; the pull image defaults."""
        answers = SessionAnswers()

        result = _run_survey(
            _full_plan(convention_exists=False),
            answers,
            [
                "python",  # Language
                "y",  # Download base convention
                "n",  # Add codemanifest usages?
                "n",  # Add codemanifest annotations?
                "n",  # Configure a build agent?
                "n",  # Create Dockerfile?
                "",  # Docker image → the last hint default
                "n",  # Configure a pipeline agent?
                "n",  # Add tools?
                "n",  # Add usages records?
            ],
        )

        assert result.exit_code == 0
        assert answers.snapshot() == {
            "language": "python",
            "codemanifest": {
                "usages": {"conventions": ".goga/usages/conventions.md"},
                "annotations": "Use `conventions` for code writing rules and testing.",
            },
            "docker_image": {"image": _PYTHON_LAST_HINT_1_3},
        }
        # The gate itself is presentational — never a recorded section.
        assert "convention" not in answers.snapshot()
        # The pull branch renders the hints, never the FROM label.
        assert "qarium/goga-python-3.14:1.3" in result.output
        assert "Available images:" in result.output
        assert "Base image" not in result.output

    def test_convention_rejection_records_no_codemanifest(self) -> None:
        """Declining the gate leaves no codemanifest entries; a custom pull image stands."""
        answers = SessionAnswers()

        result = _run_survey(
            _full_plan(convention_exists=False),
            answers,
            [
                "golang",  # Language
                "n",  # Download base convention
                "n",  # Add codemanifest usages?
                "n",  # Add codemanifest annotations?
                "n",  # Configure a build agent?
                "n",  # Create Dockerfile?
                "my-custom/golang:2.0",  # Docker image (free-form)
                "n",  # Configure a pipeline agent?
                "n",  # Add tools?
                "n",  # Add usages records?
            ],
        )

        assert result.exit_code == 0
        assert answers.snapshot() == {"language": "golang", "docker_image": {"image": "my-custom/golang:2.0"}}
        assert "codemanifest" not in answers.snapshot()

    def test_existing_convention_drops_the_gate(self) -> None:
        """A core built with convention_exists=True never asks the gate."""
        answers = SessionAnswers()

        result = _run_survey(
            _full_plan(convention_exists=True),
            answers,
            [
                "python",  # Language
                "n",  # Add codemanifest usages?
                "n",  # Add codemanifest annotations?
                "n",  # Configure a build agent?
                "n",  # Create Dockerfile?
                "",  # Docker image → the last hint default
                "n",  # Configure a pipeline agent?
                "n",  # Add tools?
                "n",  # Add usages records?
            ],
        )

        assert result.exit_code == 0
        assert "Download base convention" not in result.output
        assert answers.snapshot() == {"language": "python", "docker_image": {"image": _PYTHON_LAST_HINT_1_3}}

    def test_duplicate_usage_name_is_skipped_with_a_note(self) -> None:
        """A repeated usage name is skipped; the collection continues (ported)."""
        answers = SessionAnswers()

        result = _run_survey(
            _full_plan(convention_exists=False),
            answers,
            [
                "python",  # Language
                "y",  # Download base convention
                "y",  # Add codemanifest usages?
                "conventions",  # duplicate of the prefill entry
                "y",  # Add another codemanifest usage?
                "custom",  # usage name
                ".goga/usages/custom.md",  # usage value
                "n",  # Add another codemanifest usage?
                "n",  # Add codemanifest annotations?
                "n",  # Configure a build agent?
                "n",  # Create Dockerfile?
                "",  # Docker image → the last hint default
                "n",  # Configure a pipeline agent?
                "n",  # Add tools?
                "n",  # Add usages records?
            ],
        )

        assert result.exit_code == 0
        assert answers.snapshot()["codemanifest"]["usages"] == {
            "conventions": ".goga/usages/conventions.md",
            "custom": ".goga/usages/custom.md",
        }
        assert 'already exists, skipping.' in result.output

    def test_agent_gates_collect_env_with_suggested_keys(self) -> None:
        """Accepting an agent gate records agent + env; suggested keys render first (ported)."""
        answers = SessionAnswers()

        result = _run_survey(
            _full_plan(convention_exists=True),
            answers,
            [
                "python",  # Language
                "n",  # Add codemanifest usages?
                "n",  # Add codemanifest annotations?
                "y",  # Configure a build agent?
                "claude",  # Build agent
                "n",  # Set suggested keys?
                "y",  # Add another pair?
                "API_KEY",  # key
                "secret",  # value
                "y",  # Add another?
                "MODEL",  # key
                "gpt-4",  # value
                "n",  # Add another?
                "n",  # Create Dockerfile?
                "",  # Docker image → the last hint default
                "y",  # Configure a pipeline agent?
                "codex",  # Pipeline agent
                "y",  # Set suggested keys? (CODEX_MODEL)
                "gpt-5",  # CODEX_MODEL value
                "n",  # Add another pair?
                "n",  # Add tools?
                "n",  # Add usages records?
            ],
        )

        assert result.exit_code == 0
        snapshot = answers.snapshot()
        assert snapshot["build"] == {"agent": "claude", "env": {"API_KEY": "secret", "MODEL": "gpt-4"}}
        assert snapshot["pipeline"] == {"agent": "codex", "env": {"CODEX_MODEL": "gpt-5"}}
        assert "CODEX_MODEL" in result.output

    def test_declining_the_agent_gates_records_nothing(self) -> None:
        """Declining both executor gates leaves no build or pipeline sections."""
        answers = SessionAnswers()

        result = _run_survey(
            _full_plan(convention_exists=True),
            answers,
            [
                "python",  # Language
                "n",  # Add codemanifest usages?
                "n",  # Add codemanifest annotations?
                "n",  # Configure a build agent?
                "n",  # Create Dockerfile?
                "",  # Docker image → the last hint default
                "n",  # Configure a pipeline agent?
                "n",  # Add tools?
                "n",  # Add usages records?
            ],
        )

        assert result.exit_code == 0
        assert answers.snapshot() == {"language": "python", "docker_image": {"image": _PYTHON_LAST_HINT_1_3}}

    def test_dockerfile_branch_records_path_from_and_built_name(self) -> None:
        """Accepting the Dockerfile gate asks path, FROM base, and built name (ported)."""
        answers = SessionAnswers()

        result = _run_survey(
            _full_plan(convention_exists=True),
            answers,
            [
                "python",  # Language
                "n",  # Add codemanifest usages?
                "n",  # Add codemanifest annotations?
                "n",  # Configure a build agent?
                "y",  # Create Dockerfile?
                "",  # Dockerfile path → .goga/Dockerfile
                "",  # Base image (FROM) → the last hint default
                "",  # Built image name → my-app:latest
                "n",  # Configure a pipeline agent?
                "n",  # Add tools?
                "n",  # Add usages records?
            ],
        )

        assert result.exit_code == 0
        assert answers.snapshot()["docker_image"] == {
            "dockerfile": ".goga/Dockerfile",
            "base_image": _PYTHON_LAST_HINT_1_3,
            "image": "my-app:latest",
        }
        assert "Base image (FROM)" in result.output
        assert "Built image name" in result.output
        assert "qarium/goga-python-3.14:1.3" in result.output

    def test_a_skipped_base_image_collapses_the_from(self) -> None:
        """Skipping base_image never asks the FROM; the built name still records."""
        plan = apply_skips(_full_plan(convention_exists=True), [("skipper", "docker_image.base_image")])
        answers = SessionAnswers()

        result = _run_survey(
            plan,
            answers,
            [
                "python",  # Language
                "n",  # Add codemanifest usages?
                "n",  # Add codemanifest annotations?
                "n",  # Configure a build agent?
                "y",  # Create Dockerfile?
                "",  # Dockerfile path → .goga/Dockerfile
                "",  # Built image name → my-app:latest
                "n",  # Configure a pipeline agent?
                "n",  # Add tools?
                "n",  # Add usages records?
            ],
        )

        assert result.exit_code == 0
        assert answers.snapshot()["docker_image"] == {"dockerfile": ".goga/Dockerfile", "image": "my-app:latest"}
        assert "Base image" not in result.output

    def test_a_skipped_dockerfile_runs_the_pull_branch_without_the_gate(self) -> None:
        """Skipping dockerfile collapses the gate — the pull image directly."""
        plan = apply_skips(_full_plan(convention_exists=True), [("skipper", "docker_image.dockerfile")])
        answers = SessionAnswers()

        result = _run_survey(
            plan,
            answers,
            [
                "python",  # Language
                "n",  # Add codemanifest usages?
                "n",  # Add codemanifest annotations?
                "n",  # Configure a build agent?
                "",  # Docker image → the last hint default (no gate asked)
                "n",  # Configure a pipeline agent?
                "n",  # Add tools?
                "n",  # Add usages records?
            ],
        )

        assert result.exit_code == 0
        assert answers.snapshot()["docker_image"] == {"image": _PYTHON_LAST_HINT_1_3}
        assert "Create Dockerfile?" not in result.output
        assert "Available images:" in result.output

    def test_tools_pairs_empty_version_reads_as_latest(self) -> None:
        """The tools gate opens the name → version loop; an empty version is latest."""
        answers = SessionAnswers()

        result = _run_survey(
            _full_plan(convention_exists=True),
            answers,
            [
                "python",  # Language
                "n",  # Add codemanifest usages?
                "n",  # Add codemanifest annotations?
                "n",  # Configure a build agent?
                "n",  # Create Dockerfile?
                "",  # Docker image → the last hint default
                "n",  # Configure a pipeline agent?
                "y",  # Add tools?
                "goga-lint",  # Tool name
                "",  # Tool version → latest
                "y",  # Add another tool?
                "goga-mkdocs",  # Tool name
                "1.0",  # Tool version
                "n",  # Add another tool?
                "n",  # Add usages records?
            ],
        )

        assert result.exit_code == 0
        assert answers.snapshot()["tools"] == {"goga-lint": "latest", "goga-mkdocs": "1.0"}

    def test_usages_record_loop_accumulates_nested_records(self) -> None:
        """The usages loop nests records under their group; optional entries omit."""
        answers = SessionAnswers()

        result = _run_survey(
            _full_plan(convention_exists=True),
            answers,
            [
                "python",  # Language
                "n",  # Add codemanifest usages?
                "n",  # Add codemanifest annotations?
                "n",  # Configure a build agent?
                "n",  # Create Dockerfile?
                "",  # Docker image → the last hint default
                "n",  # Configure a pipeline agent?
                "n",  # Add tools?
                "y",  # Add usages records?
                "goga-hooks",  # Usage group
                "goga-lint",  # Dependency name
                "https://github.com/qarium/goga-lint",  # Git URL
                "",  # Ref (optional)
                "",  # Root (optional)
                "y",  # Add another usage record?
                "goga-hooks",  # the same group merges under its key
                "goga-viewer",  # Dependency name
                "https://github.com/qarium/goga-viewer",  # Git URL
                "0.1.0",  # Ref (optional)
                "",  # Root (optional)
                "n",  # Add another usage record?
            ],
        )

        assert result.exit_code == 0
        assert answers.snapshot()["usages"] == {
            "goga-hooks": {
                "goga-lint": {"git": "https://github.com/qarium/goga-lint"},
                "goga-viewer": {"git": "https://github.com/qarium/goga-viewer", "ref": "0.1.0"},
            }
        }

    def test_usages_inputs_the_config_loader_rejects_re_ask(self) -> None:
        """A separator name, an absolute or escaping root, and a whitespace git re-ask."""
        answers = SessionAnswers()

        result = _run_survey(
            _full_plan(convention_exists=True),
            answers,
            [
                "python",  # Language
                "n",  # Add codemanifest usages?
                "n",  # Add codemanifest annotations?
                "n",  # Configure a build agent?
                "n",  # Create Dockerfile?
                "",  # Docker image → the last hint default
                "n",  # Configure a pipeline agent?
                "n",  # Add tools?
                "y",  # Add usages records?
                "my/org",  # Usage group — a separator name re-asks
                "goga-hooks",  # the accepted Usage group
                "..",  # Dependency name — a traversal segment re-asks
                "goga-lint",  # the accepted Dependency name
                " ",  # Git URL — a whitespace-only entry re-asks
                "https://github.com/qarium/goga-lint",  # the accepted Git URL
                "",  # Ref (optional)
                "/docs",  # Root (optional) — an absolute root re-asks
                "../docs",  # an escaping root re-asks
                "docs",  # the accepted Root
                "n",  # Add another usage record?
            ],
        )

        assert result.exit_code == 0
        assert result.output.count("Error:") == 5
        assert answers.snapshot()["usages"] == {
            "goga-hooks": {
                "goga-lint": {"git": "https://github.com/qarium/goga-lint", "root": "docs"}
            }
        }

    def test_whitespace_only_usages_ref_and_root_read_as_absent(self) -> None:
        """A whitespace-only optional ref or root omits the entry — no load failure."""
        answers = SessionAnswers()

        result = _run_survey(
            _full_plan(convention_exists=True),
            answers,
            [
                "python",  # Language
                "n",  # Add codemanifest usages?
                "n",  # Add codemanifest annotations?
                "n",  # Configure a build agent?
                "n",  # Create Dockerfile?
                "",  # Docker image → the last hint default
                "n",  # Configure a pipeline agent?
                "n",  # Add tools?
                "y",  # Add usages records?
                "goga-hooks",  # Usage group
                "goga-lint",  # Dependency name
                "https://github.com/qarium/goga-lint",  # Git URL
                " ",  # Ref (optional) — reads as absent
                " ",  # Root (optional) — reads as absent
                "n",  # Add another usage record?
            ],
        )

        assert result.exit_code == 0
        assert answers.snapshot()["usages"] == {
            "goga-hooks": {"goga-lint": {"git": "https://github.com/qarium/goga-lint"}}
        }

    def test_recorded_usages_pass_the_project_config_loader(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The usages records the survey accepts load through the project config loader."""
        answers = SessionAnswers()

        result = _run_survey(
            _full_plan(convention_exists=True),
            answers,
            [
                "python",  # Language
                "n",  # Add codemanifest usages?
                "n",  # Add codemanifest annotations?
                "n",  # Configure a build agent?
                "n",  # Create Dockerfile?
                "",  # Docker image → the last hint default
                "n",  # Configure a pipeline agent?
                "n",  # Add tools?
                "y",  # Add usages records?
                "goga-hooks",  # Usage group
                "goga-lint",  # Dependency name
                "  https://github.com/qarium/goga-lint  ",  # Git URL — recorded stripped
                " 0.1.0 ",  # Ref (optional) — recorded stripped
                "docs\\sub",  # Root (optional) — normalized to forward slashes
                "n",  # Add another usage record?
            ],
        )

        assert result.exit_code == 0
        config_dir = tmp_path / ".goga"
        config_dir.mkdir()
        (config_dir / "config.yml").write_text(
            yaml.safe_dump({"language": "python", "usages": answers.snapshot()["usages"]}),
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        config = load_project_config()

        dep = config.usages["goga-hooks"]["goga-lint"]
        assert dep.git == "https://github.com/qarium/goga-lint"
        assert dep.ref == "0.1.0"
        assert dep.root == "docs/sub"

    def test_custom_annotations_append_to_the_prefill(self) -> None:
        """Accepting the annotations collection appends to the convention prefill."""
        answers = SessionAnswers()

        result = _run_survey(
            _full_plan(convention_exists=False),
            answers,
            [
                "python",  # Language
                "y",  # Download base convention
                "n",  # Add codemanifest usages?
                "y",  # Add codemanifest annotations?
                "Keep it small.",  # the custom annotation
                "n",  # Configure a build agent?
                "n",  # Create Dockerfile?
                "",  # Docker image → the last hint default
                "n",  # Configure a pipeline agent?
                "n",  # Add tools?
                "n",  # Add usages records?
            ],
        )

        assert result.exit_code == 0
        assert answers.snapshot()["codemanifest"]["annotations"] == (
            "Use `conventions` for code writing rules and testing.\nKeep it small."
        )

    def test_custom_annotations_without_prefill_stand_alone(self) -> None:
        """A declined gate leaves no prefill — the custom annotation stands alone."""
        answers = SessionAnswers()

        result = _run_survey(
            _full_plan(convention_exists=False),
            answers,
            [
                "python",  # Language
                "n",  # Download base convention
                "n",  # Add codemanifest usages?
                "y",  # Add codemanifest annotations?
                "Keep it small.",  # the custom annotation
                "n",  # Configure a build agent?
                "n",  # Create Dockerfile?
                "",  # Docker image → the last hint default
                "n",  # Configure a pipeline agent?
                "n",  # Add tools?
                "n",  # Add usages records?
            ],
        )

        assert result.exit_code == 0
        assert answers.snapshot()["codemanifest"]["annotations"] == "Keep it small."

    def test_usages_collection_without_prefill_starts_empty(self) -> None:
        """A declined gate leaves no prefill — the collected usages stand alone."""
        answers = SessionAnswers()

        result = _run_survey(
            _full_plan(convention_exists=False),
            answers,
            [
                "python",  # Language
                "n",  # Download base convention
                "y",  # Add codemanifest usages?
                "docs",  # usage name
                ".goga/usages/docs.md",  # usage value
                "n",  # Add another codemanifest usage?
                "n",  # Add codemanifest annotations?
                "n",  # Configure a build agent?
                "n",  # Create Dockerfile?
                "",  # Docker image → the last hint default
                "n",  # Configure a pipeline agent?
                "n",  # Add tools?
                "n",  # Add usages records?
            ],
        )

        assert result.exit_code == 0
        assert answers.snapshot()["codemanifest"]["usages"] == {"docs": ".goga/usages/docs.md"}

    def test_usages_record_with_a_root_entry(self) -> None:
        """A non-empty Root lands in the record; the optional entry is kept."""
        answers = SessionAnswers()

        result = _run_survey(
            _full_plan(convention_exists=True),
            answers,
            [
                "python",  # Language
                "n",  # Add codemanifest usages?
                "n",  # Add codemanifest annotations?
                "n",  # Configure a build agent?
                "n",  # Create Dockerfile?
                "",  # Docker image → the last hint default
                "n",  # Configure a pipeline agent?
                "n",  # Add tools?
                "y",  # Add usages records?
                "goga-hooks",  # Usage group
                "goga-lint",  # Dependency name
                "https://github.com/qarium/goga-lint",  # Git URL
                "0.1.0",  # Ref (optional)
                "src",  # Root (optional)
                "n",  # Add another usage record?
            ],
        )

        assert result.exit_code == 0
        assert answers.snapshot()["usages"] == {
            "goga-hooks": {
                "goga-lint": {
                    "git": "https://github.com/qarium/goga-lint",
                    "ref": "0.1.0",
                    "root": "src",
                }
            }
        }

    def test_image_hints_and_default_follow_the_selected_language(self) -> None:
        """The rendered hints are the selected language's family; its last entry defaults."""
        answers = SessionAnswers()

        result = _run_survey(
            _full_plan(convention_exists=True),
            answers,
            [
                "golang",  # Language
                "n",  # Add codemanifest usages?
                "n",  # Add codemanifest annotations?
                "n",  # Configure a build agent?
                "n",  # Create Dockerfile?
                "",  # Docker image → the golang family default
                "n",  # Configure a pipeline agent?
                "n",  # Add tools?
                "n",  # Add usages records?
            ],
        )

        assert result.exit_code == 0
        assert answers.snapshot()["docker_image"]["image"] == "qarium/goga-golang-1.26:1.3"
        assert "qarium/goga-golang-1.26:1.3" in result.output
        assert "goga-python" not in result.output
        assert "goga-swift" not in result.output

    def test_a_language_never_asked_falls_back_to_every_hint(self) -> None:
        """A skipped language question offers the tree default — every family's last hint."""
        plan = apply_skips(_full_plan(convention_exists=True), [("skipper", "language")])
        answers = SessionAnswers()

        result = _run_survey(
            plan,
            answers,
            [
                "n",  # Add codemanifest usages?
                "n",  # Add codemanifest annotations?
                "n",  # Configure a build agent?
                "n",  # Create Dockerfile?
                "",  # Docker image → the tree default (the swift family's last)
                "n",  # Configure a pipeline agent?
                "n",  # Add tools?
                "n",  # Add usages records?
            ],
        )

        assert result.exit_code == 0
        assert answers.snapshot()["docker_image"]["image"] == "qarium/goga-swift-6.2:1.3"


class TestToolBlockPatterns:
    def test_a_tool_pairs_question_offers_its_suggested_keys(self) -> None:
        """A pairs record carrying keys renders the suggested-keys offer first."""
        plan = _minimal_plan(
            _declaration("my-tool", Question(id="kv", kind="pairs", prompt="Service keys", keys=["API_KEY", "MODEL"]))
        )
        answers = SessionAnswers(tools=["my-tool"])

        result = _run_survey(plan, answers, ["python", "y", "secret", "gpt-4", "n"])

        assert result.exit_code == 0
        assert answers.snapshot()["my-tool"]["kv"] == {"API_KEY": "secret", "MODEL": "gpt-4"}
        assert "Suggested keys:" in result.output
        assert "API_KEY" in result.output


# --- Logic tests — a tool-declared skip of a core child collapses the branch ---


class TestSkippedCoreChildren:
    """Every core child skip target collapses its ask — the sibling path stands.

    A child absent from the post-skip section is never asked; the remaining
    children of the section still are, and only the asked children record.
    """

    @pytest.mark.parametrize(
        ("skips", "inputs", "absent_prompt", "expected_snapshot"),
        [
            pytest.param(
                [("skipper", "build.agent")],
                ["python", "n", "n", "y", "n", "n", "", "n", "n", "n"],
                "Build agent",
                {"language": "python", "docker_image": {"image": _PYTHON_LAST_HINT_1_3}},
                id="build-agent",
            ),
            pytest.param(
                [("skipper", "build.env")],
                ["python", "n", "n", "y", "claude", "n", "", "n", "n", "n"],
                "Build environment variables",
                {
                    "language": "python",
                    "build": {"agent": "claude"},
                    "docker_image": {"image": _PYTHON_LAST_HINT_1_3},
                },
                id="build-env",
            ),
            pytest.param(
                [("skipper", "codemanifest.usages")],
                ["python", "n", "n", "n", "", "n", "n", "n"],
                "Add codemanifest usages?",
                {"language": "python", "docker_image": {"image": _PYTHON_LAST_HINT_1_3}},
                id="codemanifest-usages",
            ),
            pytest.param(
                [("skipper", "codemanifest.annotations")],
                ["python", "n", "n", "n", "", "n", "n", "n"],
                "Add codemanifest annotations?",
                {"language": "python", "docker_image": {"image": _PYTHON_LAST_HINT_1_3}},
                id="codemanifest-annotations",
            ),
            pytest.param(
                [("skipper", "docker_image.image")],
                ["python", "n", "n", "n", "y", "", "", "n", "n", "n"],
                "Built image name",
                {
                    "language": "python",
                    "docker_image": {"dockerfile": ".goga/Dockerfile", "base_image": _PYTHON_LAST_HINT_1_3},
                },
                id="docker-image-dockerfile-branch",
            ),
            pytest.param(
                [("skipper", "docker_image.image")],
                ["python", "n", "n", "n", "n", "n", "n", "n"],
                "Docker image",
                {"language": "python"},
                id="docker-image-pull-branch",
            ),
            pytest.param(
                [("skipper", "docker_image.base_image")],
                ["python", "n", "n", "n", "n", "", "n", "n", "n"],
                "Available images:",
                {"language": "python", "docker_image": {"image": "my-app:latest"}},
                id="base-image-pull-branch",
            ),
        ],
    )
    def test_a_skipped_child_is_never_asked(
        self,
        skips: list[tuple[str, str]],
        inputs: list[str],
        absent_prompt: str,
        expected_snapshot: dict,
    ) -> None:
        """The absent child is neither asked nor recorded; the snapshot matches."""
        plan = apply_skips(_full_plan(convention_exists=True), skips)
        answers = SessionAnswers()

        result = _run_survey(plan, answers, inputs)

        assert result.exit_code == 0, result.output
        assert absent_prompt not in result.output
        assert answers.snapshot() == expected_snapshot
