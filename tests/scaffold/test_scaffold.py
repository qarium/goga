from __future__ import annotations

import inspect
from typing import get_type_hints
from unittest import mock


class TestContract:
    """Contract-level tests for the Scaffold facade entity.

    ``Scaffold`` must be importable from the ``goga.scaffold`` facade (re-export
    wired in Task 5 STEP 2), constructible with the declared defaults and kwargs,
    and expose ``generate``/``upgrade`` with the declared signatures.
    """

    def test_scaffold_importable_from_facade(self) -> None:
        from goga.scaffold import Scaffold

        assert isinstance(Scaffold, type)

    def test_scaffold_is_a_class(self) -> None:
        from goga.scaffold import Scaffold

        assert inspect.isclass(Scaffold)

    def test_scaffold_constructible_with_defaults(self) -> None:
        from goga.scaffold import Scaffold

        instance = Scaffold()
        assert isinstance(instance, Scaffold)
        assert instance.dst_path == "."
        assert instance.answers_file == ".goga/scaffold.yml"

    def test_scaffold_constructible_with_kwargs(self) -> None:
        from goga.scaffold import Scaffold

        instance = Scaffold(dst_path=".", answers_file=".goga/scaffold.yml")
        assert isinstance(instance, Scaffold)

    def test_scaffold_has_generate_method(self) -> None:
        from goga.scaffold import Scaffold

        assert hasattr(Scaffold, "generate")
        assert callable(Scaffold.generate)

    def test_scaffold_has_upgrade_method(self) -> None:
        from goga.scaffold import Scaffold

        assert hasattr(Scaffold, "upgrade")
        assert callable(Scaffold.upgrade)

    def test_scaffold_generate_signature(self) -> None:
        from goga.scaffold import Scaffold

        signature = inspect.signature(Scaffold.generate)
        params = list(signature.parameters)
        # 'self' is the receiver for the unbound method.
        assert params == ["self", "template_input", "ref_override"]
        hints = get_type_hints(Scaffold.generate)
        assert hints["template_input"] is str
        assert hints["ref_override"] == str | None
        assert hints["return"] is int

    def test_scaffold_upgrade_signature(self) -> None:
        from goga.scaffold import Scaffold

        signature = inspect.signature(Scaffold.upgrade)
        params = list(signature.parameters)
        # 'self' plus the single ref_override parameter; no template argument.
        assert params == ["self", "ref_override"]
        hints = get_type_hints(Scaffold.upgrade)
        assert hints["ref_override"] == str | None
        assert hints["return"] is int

    def test_scaffold_init_signature(self) -> None:
        from goga.scaffold import Scaffold

        signature = inspect.signature(Scaffold.__init__)
        params = signature.parameters
        assert list(params) == ["self", "dst_path", "answers_file"]
        assert params["dst_path"].default == "."
        assert params["answers_file"].default == ".goga/scaffold.yml"


class TestLogic:
    """Logic tests — verbatim scenarios from the design (copier mocked)."""

    def test_scaffold_generate_invokes_copier_run_copy_and_returns_zero(self, tmp_path) -> None:
        with (
            mock.patch("goga.scaffold.scaffold.copier") as copier,
            mock.patch(
                "goga.scaffold.scaffold.resolve_scaffold_name",
                return_value="my-proj",
            ),
        ):
            from goga.scaffold import Scaffold

            answers_file = str(tmp_path / ".goga" / "scaffold.yml")
            scaffold = Scaffold(dst_path=str(tmp_path), answers_file=answers_file)

            result = scaffold.generate("https://example.com/tpl.git#v1.0", None)

            assert result == 0
            copier.run_copy.assert_called_once()
            call_args = copier.run_copy.call_args
            assert call_args.args[0] == "https://example.com/tpl.git"
            assert call_args.args[1] == str(tmp_path)
            assert call_args.args[2] == {"project_name": "my-proj"}
            assert call_args.kwargs["answers_file"] == answers_file
            assert call_args.kwargs["vcs_ref"] == "v1.0"
            assert call_args.kwargs["defaults"] is True

    def test_scaffold_upgrade_invokes_copier_run_update_with_overwrite_and_vcs_ref(self, tmp_path) -> None:
        state_file = tmp_path / ".goga" / "scaffold.yml"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text("_src_path: https://example.com/tpl.git\n")

        with mock.patch("goga.scaffold.scaffold.copier") as copier:
            from goga.scaffold import Scaffold

            scaffold = Scaffold(dst_path=str(tmp_path), answers_file=str(state_file))

            result = scaffold.upgrade("v2.0")

            assert result == 0
            copier.run_update.assert_called_once()
            call_args = copier.run_update.call_args
            assert call_args.args == (str(tmp_path),)
            assert call_args.kwargs["answers_file"] == str(state_file)
            assert call_args.kwargs["vcs_ref"] == "v2.0"
            assert call_args.kwargs["overwrite"] is True
            assert call_args.kwargs["defaults"] is True

    def test_scaffold_upgrade_missing_state_file_is_nonzero(self, tmp_path) -> None:
        with mock.patch("goga.scaffold.scaffold.copier") as copier:
            from goga.scaffold import Scaffold

            scaffold = Scaffold(
                dst_path=str(tmp_path),
                answers_file=str(tmp_path / ".goga" / "scaffold.yml"),
            )

            result = scaffold.upgrade()

            assert result == 1
            copier.run_update.assert_not_called()

    def test_scaffold_generate_returns_nonzero_on_copier_error(self, tmp_path) -> None:
        with (
            mock.patch("goga.scaffold.scaffold.copier") as copier,
            mock.patch(
                "goga.scaffold.scaffold.resolve_scaffold_name",
                return_value="my-proj",
            ),
        ):
            copier.run_copy.side_effect = RuntimeError("bad template")

            from goga.scaffold import Scaffold

            scaffold = Scaffold(
                dst_path=str(tmp_path),
                answers_file=str(tmp_path / ".goga" / "scaffold.yml"),
            )

            result = scaffold.generate("https://example.com/tpl.git", None)

            assert result == 1

    def test_scaffold_generate_ref_override_wins_over_fragment(self, tmp_path) -> None:
        with (
            mock.patch("goga.scaffold.scaffold.copier") as copier,
            mock.patch(
                "goga.scaffold.scaffold.resolve_scaffold_name",
                return_value="my-proj",
            ),
        ):
            from goga.scaffold import Scaffold

            scaffold = Scaffold(
                dst_path=str(tmp_path),
                answers_file=str(tmp_path / ".goga" / "scaffold.yml"),
            )

            result = scaffold.generate("https://example.com/tpl.git#v1.0", "main")

            assert result == 0
            call_kwargs = copier.run_copy.call_args.kwargs
            assert call_kwargs["vcs_ref"] == "main"

    def test_scaffold_generate_no_fragment_no_override_yields_none_vcs_ref(self, tmp_path) -> None:
        with (
            mock.patch("goga.scaffold.scaffold.copier") as copier,
            mock.patch(
                "goga.scaffold.scaffold.resolve_scaffold_name",
                return_value="my-proj",
            ),
        ):
            from goga.scaffold import Scaffold

            scaffold = Scaffold(
                dst_path=str(tmp_path),
                answers_file=str(tmp_path / ".goga" / "scaffold.yml"),
            )

            result = scaffold.generate("https://example.com/tpl.git", None)

            assert result == 0
            call_kwargs = copier.run_copy.call_args.kwargs
            assert call_kwargs["vcs_ref"] is None

    def test_scaffold_upgrade_ref_override_none_passes_none_vcs_ref(self, tmp_path) -> None:
        state_file = tmp_path / ".goga" / "scaffold.yml"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text("_src_path: https://example.com/tpl.git\n")

        with mock.patch("goga.scaffold.scaffold.copier") as copier:
            from goga.scaffold import Scaffold

            scaffold = Scaffold(dst_path=str(tmp_path), answers_file=str(state_file))

            result = scaffold.upgrade(None)

            assert result == 0
            call_kwargs = copier.run_update.call_args.kwargs
            assert call_kwargs["vcs_ref"] is None

    def test_scaffold_upgrade_returns_nonzero_on_copier_error(self, tmp_path) -> None:
        state_file = tmp_path / ".goga" / "scaffold.yml"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text("_src_path: https://example.com/tpl.git\n")

        with mock.patch("goga.scaffold.scaffold.copier") as copier:
            copier.run_update.side_effect = RuntimeError("bad update")

            from goga.scaffold import Scaffold

            scaffold = Scaffold(dst_path=str(tmp_path), answers_file=str(state_file))

            result = scaffold.upgrade()

            assert result == 1
