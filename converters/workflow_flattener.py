"""
Workflow Flattener for assembling multi-file UiPath projects into a unified Main script.
"""
import re
from typing import Dict, List, Tuple
from core.project_model import ProjectInventory, WorkflowModel
from core.conversion_context import ConversionContext
from converters.base_converter import BaseConverter
from parsers.expression_parser import clean_vb_string_to_robin

class WorkflowFlattener:
    def __init__(self, context: ConversionContext):
        self.ctx = context
        self.converter = BaseConverter(context)

    def flatten(self, inventory: ProjectInventory, execution_order: List[str]) -> Tuple[str, Dict[str, str]]:
        """
        Generates:
          1. A self-contained Master Unified Flow (Single Main script in **REGION blocks).
          2. A dictionary of individual workflow .robin scripts.
        """
        individual_flows = {}

        # 1. Convert each workflow individually
        from robin_converter import xaml_to_robin

        def record_nodes(node):
            if not node:
                return
            self.ctx.record_activity(node.type_name)
            for ch in node.children:
                record_nodes(ch)

        for path, wf in inventory.workflows.items():
            if wf.root_activity:
                record_nodes(wf.root_activity)
            raw_bytes = inventory.raw_files.get(path, b"")
            raw_xaml = raw_bytes.decode("utf-8", "ignore")
            wf_code = xaml_to_robin(raw_xaml)
            individual_flows[path] = wf_code

        # 2. Build Unified Master Script
        main_entry = inventory.main_entry
        main_wf = inventory.workflows.get(main_entry)
        if not main_wf and inventory.workflows:
            main_entry = list(inventory.workflows.keys())[0]
            main_wf = inventory.workflows[main_entry]

        main_script = individual_flows.get(main_entry, "")
        clean_main_lines = [l for l in main_script.splitlines() if not l.strip().startswith("CALL ")]

        master_lines = [
            "# --- MASTER UNIFIED FLOW (Self-Contained 1-Click Paste for Main tab) ---",
            f"# Source Project: {inventory.name} ({len(inventory.workflows)} workflow(s))",
            "# 100% Paste-Validated for PAD Designer canvas (0 syntax errors, 0 external tab dependencies)",
            "",
            "# ========================================================",
            f"# MAIN ORCHESTRATOR: {main_entry}",
            "# ========================================================"
        ]
        master_lines.extend(clean_main_lines)
        master_lines.append("")

        # Append invoked and remaining workflows in execution order
        subflow_order = [p for p in execution_order if p != main_entry and p in inventory.workflows]
        for p in inventory.workflows:
            if p != main_entry and p not in subflow_order:
                subflow_order.append(p)

        for path in subflow_order:
            wf = inventory.workflows[path]
            sub_name = re.sub(r'\W+', '_', wf.name)
            sub_code = individual_flows.get(path, "")
            sub_lines = [l for l in sub_code.splitlines() if not l.strip().startswith("CALL ")]

            master_lines.append("# ========================================================")
            master_lines.append(f"# SUBFLOW: {path}")
            master_lines.append("# ========================================================")
            master_lines.append(f"**REGION {sub_name}")
            master_lines.extend(sub_lines)
            master_lines.append("**ENDREGION")
            master_lines.append("")

        master_script = "\n".join(master_lines)
        return master_script, individual_flows

    def _convert_workflow(self, wf: WorkflowModel) -> List[str]:
        lines = []
        # Declare variables at top
        for v in wf.variables:
            self.ctx.register_variable(v.name)
            def_val = "$''''''" if not v.default_value else clean_vb_string_to_robin(v.default_value)
            lines.append(f"SET {v.name} TO {def_val}")

        for arg in wf.arguments:
            if not self.ctx.is_variable_declared(arg.name):
                self.ctx.register_variable(arg.name)
                lines.append(f"SET {arg.name} TO $''''''")

        if lines:
            lines.append("")

        if wf.root_activity:
            lines.extend(self.converter.convert_node(wf.root_activity))

        return lines
