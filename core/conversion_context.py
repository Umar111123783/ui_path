"""
Context tracker for the end-to-end conversion process.
"""
from typing import Dict, Set, List, Any

class ConversionContext:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.declared_variables: Set[str] = set()
        self.variable_types: Dict[str, str] = {}
        self.variable_mappings: Dict[str, str] = {}
        self.warnings: List[str] = []
        self.errors: List[str] = []
        self.unsupported_activities: List[Dict[str, Any]] = []
        self.activity_stats: Dict[str, int] = {}
        self.complexity_rating: str = "SIMPLE"
        self.complexity_score: float = 0.0

    def register_variable(self, name: str, type_name: str = "System.String") -> str:
        """Registers a variable and ensures case-insensitive uniqueness in Robin."""
        clean_name = name.strip()
        lower_name = clean_name.lower()
        if lower_name not in self.declared_variables:
            self.declared_variables.add(lower_name)
            self.variable_types[lower_name] = type_name
            self.variable_mappings[clean_name] = clean_name
            return clean_name
        return self.variable_mappings.get(clean_name, clean_name)

    def is_variable_declared(self, name: str) -> bool:
        return name.strip().lower() in self.declared_variables

    def add_warning(self, message: str):
        self.warnings.append(message)

    def add_error(self, message: str):
        self.errors.append(message)

    def record_activity(self, activity_type: str, supported: bool = True):
        self.activity_stats[activity_type] = self.activity_stats.get(activity_type, 0) + 1
        if not supported:
            self.unsupported_activities.append({"type": activity_type})

