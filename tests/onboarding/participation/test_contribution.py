"""Contract and logic tests for the entity declared in
``goga/onboarding/participation/CODEMANIFEST`` with ``location: contribution.py``:

- ``ToolContribution(tool, invited, answers)`` — the moment-two surface of
  one tool, the config contribution context and its staged buffer

The surface buffers what an amend-config hook contributes — the amendments
and the config files. The contribution is staged: the buffers apply only
after every hook of the tool completed without failure; writing the same
file again replaces at write time, not here.
"""

from __future__ import annotations

import pytest
from goga.hooks import wrap_context
from goga.onboarding.participation import ToolContribution

from tests.conftest import is_kw_only_dataclass

_CELL_ALL = ["ToolContribution", "ToolDeclaration", "ToolParticipation"]

# --- Contract tests ---


class TestToolContributionContract:
    def test_entity_is_importable_from_the_package_facade(self) -> None:
        """The surface lives on the cell package and its ``__all__`` is exact."""
        import goga.onboarding.participation as cell

        assert cell.ToolContribution is ToolContribution
        assert cell.__all__ == _CELL_ALL

    def test_keyword_construction_starts_with_empty_buffers(self) -> None:
        """``ToolContribution(tool=..., invited=..., answers=...)`` — the buffers start empty."""
        surface = ToolContribution(tool="t", invited=True, answers={"language": "python"})

        assert surface.tool == "t"
        assert surface.invited is True
        assert surface.answers == {"language": "python"}
        assert surface.amendments == []
        assert surface.files == []

    def test_the_surface_is_a_kw_only_dataclass(self) -> None:
        """The construction is keyword-only; positional arguments are refused."""
        assert is_kw_only_dataclass(ToolContribution)

        with pytest.raises(TypeError):
            ToolContribution("t", True, {})  # type: ignore[misc]

    def test_the_surface_passes_the_delivery_view(self) -> None:
        """Reads resolve and buffer calls pass through the ``wrap_context`` proxy."""
        proxy = wrap_context(ToolContribution(tool="t", invited=True, answers={}))

        assert proxy.tool == "t"
        assert proxy.invited is True

        proxy.answer("tools", {"t": "latest"})
        proxy.write_config("service.yml", {"interval": 60})

        assert proxy.amendments == [("tools", {"t": "latest"})]
        assert proxy.files == [("service.yml", {"interval": 60})]


# --- Logic tests ---


class TestAnswer:
    def test_answer_buffers_amendments_in_call_order(self) -> None:
        """The path and the value land as one tuple per call, in call order."""
        surface = ToolContribution(tool="t", invited=True, answers={})

        surface.answer("tools", {"t": "1.0"})
        surface.answer("pipeline.env", {"REPORT_URL": "https://example.com"})

        assert surface.amendments == [("tools", {"t": "1.0"}), ("pipeline.env", {"REPORT_URL": "https://example.com"})]

    def test_answer_is_silent_about_the_addressed_state(self) -> None:
        """Substituting a user's answer is buffered, not applied — the engine commits."""
        surface = ToolContribution(tool="t", invited=True, answers={"language": "python"})

        surface.answer("language", "golang")

        assert surface.amendments == [("language", "golang")]
        assert surface.answers == {"language": "python"}


class TestWriteConfig:
    def test_write_config_buffers_files_in_call_order(self) -> None:
        """The file name and the data land as one tuple per call, in call order."""
        surface = ToolContribution(tool="t", invited=True, answers={})

        surface.write_config("service.yml", {"token_source": "env"})
        surface.write_config("other.yml", {"interval": 60})

        assert surface.files == [("service.yml", {"token_source": "env"}), ("other.yml", {"interval": 60})]

    def test_a_repeated_file_keeps_both_entries(self) -> None:
        """Replacement happens at write time — the buffer keeps the call order."""
        surface = ToolContribution(tool="t", invited=True, answers={})

        surface.write_config("service.yml", {"token_source": "env"})
        surface.write_config("service.yml", {"interval": 60})

        assert surface.files == [("service.yml", {"token_source": "env"}), ("service.yml", {"interval": 60})]
