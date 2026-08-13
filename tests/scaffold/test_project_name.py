from __future__ import annotations

import inspect


class TestContract:
    """Contract-level tests for resolve_scaffold_name.

    The facade re-export (``from goga.scaffold import resolve_scaffold_name``)
    is wired and verified in Task 5; these tests target the module path
    ``goga.scaffold.project_name`` directly.
    """

    def test_resolve_scaffold_name_importable_from_module(self) -> None:
        from goga.scaffold.project_name import resolve_scaffold_name

        assert callable(resolve_scaffold_name)

    def test_resolve_scaffold_name_takes_no_required_args(self) -> None:
        from goga.scaffold.project_name import resolve_scaffold_name

        signature = inspect.signature(resolve_scaffold_name)
        required = [
            name
            for name, param in signature.parameters.items()
            if param.default is inspect.Parameter.empty
            and param.kind
            not in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            )
        ]
        assert required == []


class TestLogic:
    """Logic tests — verbatim scenarios from the design."""

    def test_resolve_scaffold_name_uses_git_name(self, monkeypatch) -> None:
        from goga.scaffold import project_name

        monkeypatch.setattr(
            "goga.scaffold.project_name.resolve_project_name",
            lambda: "my-proj",
        )

        assert project_name.resolve_scaffold_name() == "my-proj"

    def test_resolve_scaffold_name_prompts_when_git_name_is_none(
        self,
        monkeypatch,
    ) -> None:
        from goga.scaffold import project_name

        monkeypatch.setattr(
            "goga.scaffold.project_name.resolve_project_name", lambda: None
        )

        def fake_prompt(*_args: object, **_kwargs: object) -> str:
            return "typed-name"

        monkeypatch.setattr(
            "goga.scaffold.project_name.click.prompt", fake_prompt
        )

        assert project_name.resolve_scaffold_name() == "typed-name"

    def test_resolve_scaffold_name_does_not_raise_on_git_none(
        self,
        monkeypatch,
    ) -> None:
        from goga.scaffold import project_name

        monkeypatch.setattr(
            "goga.scaffold.project_name.resolve_project_name", lambda: None
        )

        def fake_prompt(*_args: object, **_kwargs: object) -> str:
            return "fallback-name"

        monkeypatch.setattr(
            "goga.scaffold.project_name.click.prompt", fake_prompt
        )

        # No exception propagates on the git-None path (constraint honored).
        assert project_name.resolve_scaffold_name() == "fallback-name"
