"""Compiler cell — pure transformer from goga DSL pipeline-files to afm flow-files.

Built incrementally: each entity task adds its module's import and ``__all__``
entry. Once all entity tasks land, all 16 contract names are re-exported here.
"""

from .body_format import BodyFormat
from .compile_flow import compile_flow, translate_role
from .flow_document import FlowDocument
from .flow_memory import FlowMemory
from .flow_stage import FlowStage
from .parse_dsl import StructuralError, parse_dsl
from .phase_step import PhaseStep
from .phases_body import PhasesBody
from .pipeline_document import PipelineDocument
from .pipeline_header import PipelineHeader
from .pipeline_roles import PipelineRoles
from .serialize_flow import serialize_flow
from .stage_step import StageStep
from .stages_body import StagesBody

__all__: list[str] = [
    "BodyFormat",
    "FlowDocument",
    "FlowMemory",
    "FlowStage",
    "PhaseStep",
    "PhasesBody",
    "PipelineDocument",
    "PipelineHeader",
    "PipelineRoles",
    "StageStep",
    "StagesBody",
    "StructuralError",
    "compile_flow",
    "parse_dsl",
    "serialize_flow",
    "translate_role",
]
