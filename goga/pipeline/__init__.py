"""Pipeline cell — discovery and run coordination of goga pipeline files."""

import sys
from importlib import import_module
from types import ModuleType
from typing import Any

from .afm_config import write_afm_config
from .afm_skin import materialize_afm_skin
from .apply_skip_stages import apply_skip_stages
from .cli import pipeline_cli
from .describe_pipelines import describe_pipelines
from .gate_env_wrappers import apply_gate_env_wrappers
from .hook_bridge import build_run_event, build_stage_event, map_event_action, run_hook
from .list_pipelines import list_pipelines
from .order_stages import order_stages
from .pipeline_card import CardStage, PipelineCard
from .pipeline_entry import PipelineEntry, PipelineSource
from .pipeline_summary import PipelineSummary
from .resolve_workflow import resolve_workflow
from .stage_env_wrappers import apply_stage_env_wrappers

__all__: list[str] = [
    "CardStage",
    "PipelineCard",
    "PipelineEntry",
    "PipelineSource",
    "PipelineSummary",
    "apply_gate_env_wrappers",
    "apply_skip_stages",
    "apply_stage_env_wrappers",
    "build_run_event",
    "build_stage_event",
    "describe_pipeline",
    "describe_pipelines",
    "list_pipelines",
    "map_event_action",
    "materialize_afm_skin",
    "order_stages",
    "pipeline_cli",
    "resolve_workflow",
    "run_hook",
    "run_pipeline",
    "write_afm_config",
]

# The platform-carrying re-exports resolve on first attribute access (PEP 562)
# so a hook process never pays their import cost on the fast path; every other
# facade import above stays static.
_LAZY_REEXPORTS: dict[str, str] = {
    "describe_pipeline": ".describe_pipeline",
    "run_pipeline": ".run_pipeline",
}


class _FacadeModule(ModuleType):
    """Package module that keeps the lazy facade names bound to their routines.

    Each lazy name collides with its own submodule name, so importing that
    submodule by its dotted path would bind the module object onto the package
    under the facade name and ``from goga.pipeline import run_pipeline`` would
    hand out the module. The interception re-binds the submodule's routine
    instead, keeping the pre-laziness facade semantics in every import order.
    """

    def __setattr__(self, name: str, value: Any) -> None:
        """Bind a lazy facade name to the submodule's routine, not the module.

        Args:
            name: The attribute being bound on the package.
            value: The value being bound; a lazy submodule triggers the rebind.
        """
        if name in _LAZY_REEXPORTS and isinstance(value, ModuleType):
            value = getattr(value, name)

        super().__setattr__(name, value)


def __getattr__(name: str) -> Any:
    """Resolve a lazy facade re-export by importing its submodule (PEP 562).

    Args:
        name: The requested attribute name.

    Returns:
        The submodule's exported object, imported and bound on first
        access; the binding serves every later lookup.

    Raises:
        AttributeError: The name is not a lazy facade re-export.
    """
    if name not in _LAZY_REEXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    value = getattr(import_module(_LAZY_REEXPORTS[name], __name__), name)
    globals()[name] = value

    return value


# Adopt the guarded module class last: the static imports above ran under plain
# module semantics, and every later submodule binding passes through the guard.
sys.modules[__name__].__class__ = _FacadeModule
