"""
XAML Parser for reconstructing UiPath workflows into structured ActivityNode trees.
"""
import xml.etree.ElementTree as ET
from typing import List, Tuple
from core.project_model import WorkflowModel, ActivityNode, VariableModel, ArgumentModel
from core.exceptions import XamlParseError
from parsers.expression_parser import clean_tag

STRUCTURAL_PREFIXES = ("ActivityAction", "ActivityFunc", "TextExpression", "WorkflowViewState")
STRUCTURAL_TAGS = {
    "Activity", "Sequence", "Flowchart", "FlowStep", "FlowDecision", "FlowSwitch",
    "Collection", "AssemblyReference", "String", "Dictionary", "Boolean", "Int32",
    "ViewStateData", "IdRef", "VisualBasicValue", "VisualBasicReference",
    "InArgument", "OutArgument", "InOutArgument", "TargetAnchorable", "TargetApp",
    "Target", "VerifyOptions", "Variable", "Variables", "Sequence.Variables", "List",
    "Property", "DelegateInArgument", "Catch", "Catches", "TryCatch.Catches",
    "TryCatch.Finally", "TryCatch.Try", "Members", "Null", "Literal"
}

class XamlParser:
    def parse_workflow(self, wf: WorkflowModel, raw_xml: str) -> WorkflowModel:
        """Parses raw XAML string and populates WorkflowModel."""
        try:
            root = ET.fromstring(raw_xml)
        except Exception as e:
            raise XamlParseError(f"Failed to parse XAML for {wf.file_path}: {e}")

        # 1. Extract Arguments (x:Members / x:Property)
        wf.arguments = self._extract_arguments(root)

        # 2. Extract Variables
        wf.variables = self._extract_variables(root)

        # 3. Parse Activities Hierarchy
        wf.root_activity, wf.activity_count, wf.max_depth, wf.invoked_workflows = self._parse_node(root, 0)
        return wf

    def _extract_arguments(self, root: ET.Element) -> List[ArgumentModel]:
        args = []
        for elem in root.iter():
            tag = clean_tag(elem.tag)
            if tag in ["Property", "x:Property"]:
                name = elem.get("Name")
                type_name = elem.get("Type", "InArgument(x:String)")
                direction = "InArgument"
                if "OutArgument" in type_name:
                    direction = "OutArgument"
                elif "InOutArgument" in type_name:
                    direction = "InOutArgument"
                if name:
                    args.append(ArgumentModel(name=name, type_name=type_name, direction=direction))
        return args

    def _extract_variables(self, root: ET.Element) -> List[VariableModel]:
        vars_list = []
        seen = set()
        for elem in root.iter():
            tag = clean_tag(elem.tag)
            if tag in ["Variable", "x:Variable"]:
                name = elem.get("Name")
                type_name = elem.get("TypeArguments", elem.get("Type", "x:String"))
                default_val = elem.get("Default")
                if name and name.lower() not in seen:
                    # Ignore delegate argument variables
                    if not any(clean_tag(p.tag) == "DelegateInArgument" for p in elem.iter()):
                        seen.add(name.lower())
                        vars_list.append(VariableModel(name=name, type_name=type_name, default_value=default_val))
        return vars_list

    def _parse_node(self, elem: ET.Element, current_depth: int) -> Tuple[ActivityNode, int, int, List[str]]:
        tag = clean_tag(elem.tag)
        disp = elem.get("DisplayName", tag)
        act_id = elem.get("{http://schemas.microsoft.com/netfx/2010/xaml/activities/presentation}WorkflowViewState.IdRef", tag)
        
        node = ActivityNode(
            id=act_id,
            type_name=tag,
            display_name=disp,
            properties=dict(elem.attrib),
            raw_tag=elem.tag,
            line_number=current_depth
        )

        activity_count = 1 if tag not in STRUCTURAL_TAGS and "." not in tag else 0
        max_depth = current_depth
        invokes = []

        if tag == "InvokeWorkflowFile":
            wf_path = elem.get("WorkflowFileName", "")
            if wf_path:
                invokes.append(wf_path.replace("\\", "/"))

        for child in elem:
            c_node, c_count, c_depth, c_invokes = self._parse_node(child, current_depth + 1)
            node.children.append(c_node)
            activity_count += c_count
            max_depth = max(max_depth, c_depth)
            invokes.extend(c_invokes)

        return node, activity_count, max_depth, invokes
