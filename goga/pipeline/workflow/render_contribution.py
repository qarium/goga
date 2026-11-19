"""The ``render_contribution`` routine — field-level Jinja rendering of committed workflow contributions."""

from __future__ import annotations

from dataclasses import fields, is_dataclass, replace
from typing import Any

from jinja2 import Environment

from .workflow_document import WorkflowDocument

# The fixed rendering environment per the jinja2 practice — the same
# four-flag contract render_workflow builds on. The flags are the contract,
# not object identity.
_RENDER_ENVIRONMENT = Environment(
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
    autoescape=False,
)


def render_contribution(
    document: WorkflowDocument,
    profile_data: dict[str, Any],
) -> WorkflowDocument:
    """Render every template surface of one committed workflow contribution.

    Walks ``document`` type-driven at any depth — over the typed model
    fields and the verbatim extend-entry bodies alike — rendering every
    string leaf and every string mapping key individually with the active
    profile's content as the template context; every non-string scalar is
    carried unchanged and field presence never changes.

    Args:
        document: the committed contribution — a raw (pre-render)
            ``WorkflowDocument``-shaped set of instructions.
        profile_data: the template context — the entire content of the
            active profile, or an empty mapping when no profile is active.

    Returns:
        A new ``WorkflowDocument`` with every template surface rendered;
        the input document is never mutated.

    Raises:
        ValueError: If any rendered surface fails as a template — the
            message carries the error class, the Jinja message, and the
            document dot-path of the failing string (built from the source
            pre-render keys). If two distinct source keys of one map render
            to the same result key — the message names the map's dot-path,
            both source keys, and the colliding result.
    """
    return _walk(document, profile_data, path="")


def _walk(value: Any, ctx: dict[str, Any], path: str) -> Any:
    """Render one walked value — a string surface, a container, or a scalar.

    Args:
        value: the walked value at ``path``.
        ctx: the rendering context — exactly the profile content.
        path: the document dot-path of ``value`` from source keys.

    Returns:
        The rendered counterpart of ``value`` — a new object for every
        container, the rendered string for every string leaf, the value
        itself for every other scalar.
    """
    if isinstance(value, str):
        return _render_surface(value, ctx, path)

    if is_dataclass(value) and not isinstance(value, type):
        rendered = {f.name: _walk(getattr(value, f.name), ctx, _child(path, f.name)) for f in fields(value)}

        return replace(value, **rendered)

    if isinstance(value, dict):
        return _walk_map(value, ctx, path)

    if isinstance(value, (list, tuple)):
        return type(value)(_walk(item, ctx, f"{path}[{index}]") for index, item in enumerate(value))

    return value


def _walk_map(mapping: dict[Any, Any], ctx: dict[str, Any], path: str) -> dict[Any, Any]:
    """Render one mapping — every string key rendered, every value walked.

    Args:
        mapping: the walked mapping at ``path``.
        ctx: the rendering context — exactly the profile content.
        path: the document dot-path of ``mapping`` from source keys.

    Returns:
        A new mapping in source insertion order — string keys rendered,
        non-string keys carried, every value walked.

    Raises:
        ValueError: If two distinct source keys render to the same result
            key — the message names the map's dot-path, both source keys,
            and the colliding result.
    """
    out: dict[Any, Any] = {}
    owner: dict[Any, Any] = {}

    for key, item in mapping.items():
        if isinstance(key, str):
            key_path = f"{path}[{key!r}]" if path else key
            result_key = _render_surface(key, ctx, key_path)

            if result_key in owner:
                raise ValueError(
                    f"rendered key collision in {path}: keys "
                    f"{owner[result_key]!r} and {key!r} both render to {result_key!r}"
                )

            owner[result_key] = key
            child = _child(path, key)

        else:
            result_key = key
            child = f"{path}[{key!r}]"

        out[result_key] = _walk(item, ctx, child)

    return out


def _render_surface(text: str, ctx: dict[str, Any], path: str) -> str:
    """Render one string surface as a template with the profile context.

    Args:
        text: the raw string — a value leaf or a mapping key.
        ctx: the rendering context — exactly the profile content.
        path: the document dot-path of the surface from source keys.

    Returns:
        The rendered string.

    Raises:
        ValueError: If the template fails — the message carries the error
            class, the Jinja message, and the surface's document dot-path.
    """
    # A string without any template marker never enters the engine: the
    # Jinja lexer normalizes CR sequences to "\n" at compile, which would
    # silently mutate marker-free strings and break the byte-identity
    # contract for template-free documents.
    if not any(marker in text for marker in ("{{", "{%", "{#")):
        return text

    try:
        return _RENDER_ENVIRONMENT.from_string(text).render(**ctx)

    except Exception as exc:
        raise ValueError(f"template error at {path}: {type(exc).__name__}: {exc}") from None


def _child(path: str, key: str) -> str:
    """Extend a dot-path with one child segment.

    Args:
        path: the parent dot-path — empty at the document root.
        key: the child's source key.

    Returns:
        The child dot-path — the bare key under the root, a joined segment
        below it.
    """
    return key if path == "" else f"{path}.{key}"
