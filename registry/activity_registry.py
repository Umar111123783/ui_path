"""
Activity Registry for resolving UiPath activities to PAD equivalents.
"""
import os
import json
from typing import Dict, Any, Optional

class ActivityRegistry:
    def __init__(self, mapping_path: str = None, unsupported_path: str = None):
        base_dir = os.path.dirname(__file__)
        if not mapping_path:
            mapping_path = os.path.join(base_dir, "activity_mapping.json")
        if not unsupported_path:
            unsupported_path = os.path.join(base_dir, "unsupported_activities.json")

        self.mappings: Dict[str, Any] = {}
        self.unsupported: Dict[str, Any] = {}

        if os.path.exists(mapping_path):
            with open(mapping_path, "r", encoding="utf-8") as f:
                self.mappings = json.load(f)

        if os.path.exists(unsupported_path):
            with open(unsupported_path, "r", encoding="utf-8") as f:
                self.unsupported = json.load(f)

    def get_mapping(self, activity_type: str) -> Optional[Dict[str, Any]]:
        return self.mappings.get(activity_type)

    def is_supported(self, activity_type: str) -> bool:
        if activity_type in self.unsupported:
            return not self.unsupported[activity_type].get("strict_mode_blocking", False)
        return activity_type in self.mappings or activity_type.endswith("Assign") or activity_type.endswith("If")

    def get_unsupported_info(self, activity_type: str) -> Optional[Dict[str, Any]]:
        return self.unsupported.get(activity_type)

