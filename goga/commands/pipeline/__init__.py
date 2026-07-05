"""Pipeline command cell — host-side launcher for the single goga pipeline command."""

from .pipeline import pipeline
from .run_pipeline_container import run_pipeline_container

__all__: list[str] = ["pipeline", "run_pipeline_container"]
