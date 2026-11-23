"""
Intermediate Representation (IR) models for UiPath Activities.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

@dataclass
class ActivityIR:
    id: str
    category: str  # assign, control_flow, loop, excel, file, ui, web, logging, exception, invoke, custom
    activity_type: str
    display_name: str
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, str] = field(default_factory=dict)
    children: List['ActivityIR'] = field(default_factory=list)
    body: List['ActivityIR'] = field(default_factory=list)
    then_branch: List['ActivityIR'] = field(default_factory=list)
    else_branch: List['ActivityIR'] = field(default_factory=list)
    catches: List[Dict[str, Any]] = field(default_factory=list)
    finally_branch: List['ActivityIR'] = field(default_factory=list)
    source_file: str = ""
    source_line: int = 0
    raw_tag: str = ""
    is_supported: bool = True
    conversion_notes: str = ""

