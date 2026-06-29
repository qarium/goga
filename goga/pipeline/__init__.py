"""Pipeline cell — discovery and run coordination of goga pipeline files."""

from .list_pipelines import list_pipelines
from .pipeline_entry import PipelineEntry, PipelineSource
from .run_pipeline import run_pipeline

__all__: list[str] = [
    "PipelineEntry",
    "PipelineSource",
    "list_pipelines",
    "run_pipeline",
]
