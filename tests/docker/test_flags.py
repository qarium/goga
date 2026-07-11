from __future__ import annotations

from goga.docker._flags import translate_params


class TestContract:
    """Contract-surface lock: internal module accessibility + facade non-export."""

    def test_translate_params_is_callable(self) -> None:
        assert callable(translate_params)

    def test_translate_params_is_internal_not_in_facade_all(self) -> None:
        # The helper is internal infrastructure: shared by DockerBuilder.build
        # and DockerRunner.run, but NOT re-exported through the goga.docker
        # facade. Neither the symbol nor its module may appear in __all__.
        import goga.docker

        assert "translate_params" not in goga.docker.__all__
        assert "_flags" not in goga.docker.__all__


class TestTranslateParams:
    """Behavior coverage for the shared param→flag rule."""

    def test_one_char_key_becomes_short_flag(self) -> None:
        assert translate_params({"p": "8000:8000"}) == ["-p", "8000:8000"]

    def test_multi_char_snake_case_key_becomes_long_flag(self) -> None:
        # underscores → hyphens
        assert translate_params({"add_host": "h:1"}) == ["--add-host", "h:1"]

    def test_str_value_appended_after_flag(self) -> None:
        assert translate_params({"workdir": "/workspace"}) == ["--workdir", "/workspace"]

    def test_true_value_becomes_bare_boolean_flag(self) -> None:
        assert translate_params({"rm": True}) == ["--rm"]

    def test_false_value_omits_flag_entirely(self) -> None:
        assert translate_params({"skip": False}) == []

    def test_list_value_repeats_flag_per_element(self) -> None:
        assert translate_params({"v": ["/a:/b", "/c:/d"]}) == ["-v", "/a:/b", "-v", "/c:/d"]

    def test_empty_dict_returns_empty_list(self) -> None:
        assert translate_params({}) == []

    def test_insertion_order_preserved_across_mixed_keys(self) -> None:
        result = translate_params(
            {
                "p": "8000:8000",
                "rm": True,
                "add_host": "h:1",
                "workdir": "/workspace",
                "v": ["/a:/b", "/c:/d"],
                "skip": False,
            }
        )
        assert result == [
            "-p",
            "8000:8000",
            "--rm",
            "--add-host",
            "h:1",
            "--workdir",
            "/workspace",
            "-v",
            "/a:/b",
            "-v",
            "/c:/d",
        ]

    def test_two_char_key_is_long_flag_not_short(self) -> None:
        # Boundary: only a 1-character key is short; "rm" is 2 chars → long.
        result = translate_params({"rm": True, "p": "1:1"})
        assert result == ["--rm", "-p", "1:1"]
