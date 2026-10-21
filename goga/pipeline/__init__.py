"""Pipeline cell — discovery and run coordination of goga pipeline files."""

from importlib import import_module
from typing import Any

from .afm_config import write_afm_config
from .apply_skip_stages import apply_skip_stages
from .cli import pipeline_cli
from .describe_pipelines import describe_pipelines
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
    "apply_skip_stages",
    "apply_stage_env_wrappers",
    "build_run_event",
    "build_stage_event",
    "describe_pipeline",
    "describe_pipelines",
    "list_pipelines",
    "map_event_action",
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
