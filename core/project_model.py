"""
Project data models representing parsed UiPath projects and workflows.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

@dataclass
class VariableModel:
    name: str
    type_name: str = "System.String"
    default_value: Optional[str] = None
    scope: str = "workflow"

@dataclass
class ArgumentModel:
    name: str
    type_name: str = "System.String"
    direction: str = "InArgument"  # InArgument, OutArgument, InOutArgument
    default_value: Optional[str] = None

@dataclass
class ActivityNode:
    id: str
    type_name: str
    display_name: str
    properties: Dict[str, Any] = field(default_factory=dict)
    children: List['ActivityNode'] = field(default_factory=list)
    variables: List[VariableModel] = field(default_factory=list)
    raw_tag: str = ""
    line_number: int = 0
    annotations: Dict[str, Any] = field(default_factory=dict)

@dataclass
class WorkflowModel:
    name: str
    file_path: str
    is_main: bool = False
    variables: List[VariableModel] = field(default_factory=list)
    arguments: List[ArgumentModel] = field(default_factory=list)
    root_activity: Optional[ActivityNode] = None
    invoked_workflows: List[str] = field(default_factory=list)
    activity_count: int = 0
    max_depth: int = 0

@dataclass
class ProjectInventory:
    name: str
    version: str = "1.0.0"
    main_entry: str = "Main.xaml"
    workflows: Dict[str, WorkflowModel] = field(default_factory=dict)
    dependencies: Dict[str, str] = field(default_factory=dict)
    raw_files: Dict[str, bytes] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

