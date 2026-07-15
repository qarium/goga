"""Compiler cell — pure transformer from goga DSL pipeline-files to afm flow-files.

Built incrementally: each entity task adds its module's import and ``__all__``
entry. Once all entity tasks land, all 12 contract names are re-exported here.
"""

from .body_format import BodyFormat
from .flow_document import FlowDocument
from .flow_stage import FlowStage
from .parse_dsl import StructuralError, parse_dsl
from .phase_step import PhaseStep
from .phases_body import PhasesBody
from .pipeline_header import PipelineHeader
from .serialize_flow import serialize_flow
from .stage_step import StageStep
from .stages_body import StagesBody

__all__: list[str] = [
    "BodyFormat",
    "FlowDocument",
    "FlowStage",
    "PhaseStep",
    "PhasesBody",
    "PipelineHeader",
    "StageStep",
    "StagesBody",
    "StructuralError",
    "parse_dsl",
    "serialize_flow",
]
