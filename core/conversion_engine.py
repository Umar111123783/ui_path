"""
Universal UiPath-to-PAD Conversion Engine Coordinator.
Coordinates scanning, parsing, complexity analysis, IR construction,
activity translation, workflow flattening, strict validation, and reporting.
"""
import io
import json
import zipfile
from typing import Dict, Any, Union

from core.project_model import ProjectInventory
from core.conversion_context import ConversionContext
from core.exceptions import StrictValidationError
from scanner.project_scanner import ProjectScanner
from scanner.workflow_graph import WorkflowGraph
from parsers.xaml_parser import XamlParser
from analyzer.complexity_analyzer import ComplexityAnalyzer
from registry.activity_registry import ActivityRegistry
from converters.workflow_flattener import WorkflowFlattener
from validators.strict_validator import StrictValidator
from generators.report_generator import ReportGenerator

class UniversalConversionEngine:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.scanner = ProjectScanner()
        self.parser = XamlParser()
        self.analyzer = ComplexityAnalyzer()
        self.registry = ActivityRegistry()
        self.validator = StrictValidator()
        self.report_gen = ReportGenerator()

    def convert(self, package_input: Union[str, bytes]) -> Dict[str, Any]:
        """
        Executes the 7-stage conversion pipeline:
        Stage 1: Discovery
        Stage 2: Intelligence & Parsing
        Stage 3: Auto Detect Complexity
        Stage 4: Intermediate Representation (IR)
        Stage 5: Conversion Registry & Flattener
        Stage 6: Robin Code Generation
        Stage 7: Strict Validation
        """
        ctx = ConversionContext(self.config)

        # Stage 1: Discovery
        inventory = self.scanner.scan(package_input)

        # Stage 2: XAML Intelligence
        wf_graph = WorkflowGraph()
        for path, raw_bytes in inventory.raw_files.items():
            wf = inventory.workflows[path]
            raw_xml = raw_bytes.decode("utf-8", "ignore")
            self.parser.parse_workflow(wf, raw_xml)
            wf_graph.add_workflow(path)
            for inv in wf.invoked_workflows:
                # Match invoked workflow name with relative path
                matched = [p for p in inventory.workflows if p.lower().endswith(inv.lower())]
                if matched:
                    wf_graph.add_call(path, matched[0])

        # Stage 3: Auto Detect Complexity
        analysis = self.analyzer.analyze(inventory)
        ctx.complexity_rating = analysis["rating"]
        ctx.complexity_score = analysis["score"]

        # Execution order from graph
        execution_order = wf_graph.get_execution_order(inventory.main_entry)

        # Stage 4 & 5: Activity Conversion & Flattening into Single Main
        flattener = WorkflowFlattener(ctx)
        master_script, individual_flows = flattener.flatten(inventory, execution_order)

        # Stage 6 & 7: Strict Validation
        strict_mode = self.config.get("validation", {}).get("block_missing_variables", True)
        val_res = self.validator.validate(master_script, strict_mode=strict_mode)

        if analysis.get("is_scaffold"):
            val_res["warnings"].append(
                f"Blueprint/Scaffold Notice: Source project consists primarily of LogMessage/placeholder stubs ({analysis['metrics']['scaffold_activity_count']} of {analysis['metrics']['activity_count']} activities). Replace placeholder actions with executable PAD actions (Excel, Loops, Files)."
            )

        # Activity coverage metrics
        total_discovered = sum(w.activity_count for w in inventory.workflows.values())
        supported_count = sum(ctx.activity_stats.values())
        unsupported_count = len(ctx.unsupported_activities)
        coverage_pct = round((supported_count / max(1, total_discovered)) * 100.0, 2)
        if coverage_pct > 100.0:
            coverage_pct = 100.0

        report_data = {
            "project_name": inventory.name,
            "version": inventory.version,
            "entry_point": inventory.main_entry,
            "complexity_rating": ctx.complexity_rating,
            "complexity_score": ctx.complexity_score,
            "is_scaffold": analysis.get("is_scaffold", False),
            "workflow_count": len(inventory.workflows),
            "total_activities": total_discovered,
            "supported_count": supported_count,
            "unsupported_list": ctx.unsupported_activities,
            "coverage_pct": coverage_pct,
            "action_count": val_res.get("action_count", 0),
            "validation_status": val_res["status"],
            "validation_errors": val_res["errors"],
            "validation_warnings": val_res["warnings"]
        }

        report_md = self.report_gen.generate_markdown(report_data)
        report_html = self.report_gen.generate_html(report_data)

        # Build Output Bundle
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as out_z:
            out_z.writestr("Main_Robin_Script.txt", master_script)
            out_z.writestr("Reports/Conversion_Report.html", report_html)
            out_z.writestr("Reports/Validation_Report.json", json.dumps(val_res, indent=2))
            out_z.writestr("Reports/Conversion_Report.md", report_md)
            out_z.writestr("Analysis/Complexity_Analysis.json", json.dumps(analysis, indent=2))
            
            # Subflow individual files
            for p, code in individual_flows.items():
                fname = f"Subflows/{p.replace('/', '_')}.robin"
                out_z.writestr(fname, code)

        bundle_bytes = zip_buf.getvalue()

        return {
            "success": val_res["valid"],
            "status": val_res["status"],
            "master_script": master_script,
            "individual_flows": individual_flows,
            "report_markdown": report_md,
            "report_html": report_html,
            "report_data": report_data,
            "analysis": analysis,
            "bundle_bytes": bundle_bytes,
            "errors": val_res["errors"],
            "warnings": val_res["warnings"]
        }
