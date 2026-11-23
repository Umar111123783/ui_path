"""
Intermediate Representation (IR) models for Workflows and Projects.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any
from ir.activity_ir import ActivityIR
from core.project_model import VariableModel, ArgumentModel

@dataclass
class WorkflowIR:
    name: str
    file_path: str
    is_main: bool = False
    variables: List[VariableModel] = field(default_factory=list)
    arguments: List[ArgumentModel] = field(default_factory=list)
    activities: List[ActivityIR] = field(default_factory=list)
    invoked_workflows: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ProjectIR:
    name: str
    entry_point: str
    complexity_rating: str
    complexity_score: float
    workflows: Dict[str, WorkflowIR] = field(default_factory=dict)
    execution_order: List[str] = field(default_factory=list)
    dependencies: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

