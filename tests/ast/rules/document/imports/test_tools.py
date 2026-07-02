from __future__ import annotations

import inspect

from goga.ast.rules.document.imports.tools import signature_contains_type_name


class TestContract:
    """Contract tests — verify function exists, is callable, has correct signature."""

    def test_callable(self):
        assert callable(signature_contains_type_name)

    def test_signature(self):
        sig = inspect.signature(signature_contains_type_name)
        params = list(sig.parameters)
        assert params == ["signature", "type_name"]
        assert sig.return_annotation == "bool"

    def test_module_location(self):
        assert signature_contains_type_name.__module__ == ("goga.ast.rules.document.imports.tools")

    def test_accessible_from_submodule(self):
        from goga.ast.rules.document.imports import signature_contains_type_name as fn

        assert fn is signature_contains_type_name

    def test_accessible_from_facade(self):
        from goga.ast.rules import signature_contains_type_name as fn

        assert fn is signature_contains_type_name


class TestLogical:
    """Logical tests — verify behaviour per contract specification."""

    # --- Positive cases ---

    def test_type_as_parameter_value(self):
        assert signature_contains_type_name("(param: TypeName)", "TypeName") is True

    def test_type_in_return(self):
        assert signature_contains_type_name("(param: Type) -> rv:TypeName", "TypeName") is True

    def test_type_in_middle(self):
        assert signature_contains_type_name("(param: TypeName, param_2: Type)", "TypeName") is True

    def test_type_at_start(self):
        assert signature_contains_type_name("TypeName(param)", "TypeName") is True

    def test_type_in_list_brackets(self):
        assert signature_contains_type_name("(param: list[TypeName])", "TypeName") is True

    def test_type_in_nested_brackets(self):
        assert signature_contains_type_name("(param: dict[str, TypeName])", "TypeName") is True

    def test_type_in_return_list(self):
        assert signature_contains_type_name("() -> items:list[TypeName]", "TypeName") is True

    def test_type_after_return_colon(self):
        assert signature_contains_type_name("() -> label:TypeName", "TypeName") is True

    # --- Negative cases ---

    def test_type_as_prefix(self):
        assert signature_contains_type_name("(param: TypeNameOne)", "TypeName") is False

    def test_type_as_suffix(self):
        assert signature_contains_type_name("(param: TwoTypeName)", "TypeName") is False

    def test_type_in_string_literal(self):
        assert signature_contains_type_name('(param: Type: = "TypeName")', "TypeName") is False

    def test_type_as_part_of_bracketed(self):
        assert signature_contains_type_name("(param: list[TypeNameExtra])", "TypeName") is False

    # --- Edge cases ---

    def test_empty_type_name(self):
        assert signature_contains_type_name("(param: SomeType)", "") is False

    def test_empty_signature(self):
        assert signature_contains_type_name("", "TypeName") is False

    def test_type_name_at_signature_start(self):
        assert signature_contains_type_name("TypeName()", "TypeName") is True

    # --- Dynamic parameters (...args / ...kwargs) ---

    def test_dynamic_vararg_param(self):
        assert signature_contains_type_name("(...args: Type)", "args") is True

    def test_dynamic_kwarg_param(self):
        assert signature_contains_type_name("(...kwargs: Type)", "kwargs") is True

    def test_dynamic_param_in_full_signature(self):
        sig = "dynamic_signature(...args: Type, ...kwargs: Type) -> value:Type"
        assert signature_contains_type_name(sig, "args") is True

    def test_dynamic_kwarg_in_full_signature(self):
        sig = "dynamic_signature(...args: Type, ...kwargs: Type) -> value:Type"
        assert signature_contains_type_name(sig, "kwargs") is True

    def test_dynamic_prefix_does_not_match_dotted_type(self):
        assert signature_contains_type_name("(x: foo.args)", "args") is False

    def test_dynamic_prefix_does_not_match_suffix(self):
        assert signature_contains_type_name("(x: args.extra)", "args") is False

    def test_single_dot_is_not_dynamic_prefix(self):
        assert signature_contains_type_name(".args", "args") is False

    def test_two_dots_are_not_dynamic_prefix(self):
        assert signature_contains_type_name("..args", "args") is False
