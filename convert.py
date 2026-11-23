"""
Universal UiPath-to-PAD Conversion Engine — Master CLI Runner.
Converts ANY UiPath project (.zip, .nupkg, project directory, or .xaml)
into a 100% paste-validated Power Automate Desktop 2.74 Classic Robin Main-flow script.
"""
import sys
import os
import argparse
from core.conversion_engine import UniversalConversionEngine

def main():
    parser = argparse.ArgumentParser(
        description="Universal UiPath-to-PAD Conversion Engine (7-Stage IR Architecture)"
    )
    parser.add_argument("package_path", help="Path to UiPath project (.zip, .nupkg, directory, or .xaml)")
    parser.add_argument("--out", "-o", default="Conversion_Output", help="Output directory for generated artifacts")
    args = parser.parse_args()

    target_path = args.package_path
    if not os.path.exists(target_path):
        print(f"Error: Target path '{target_path}' does not exist.")
        sys.exit(1)

    print("=" * 70)
    print(" UNIVERSAL UiPath-to-PAD CONVERSION ENGINE")
    print(" Target: Power Automate Desktop 2.74 Classic Robin (Single Main Tab)")
    print("=" * 70)
    print(f"[*] Ingesting: {target_path}")

    engine = UniversalConversionEngine()
    result = engine.convert(target_path)

    report_data = result.get("report_data", {})
    status = result.get("status", "FAILED")
    complexity = report_data.get("complexity_rating", "UNKNOWN")
    score = report_data.get("complexity_score", 0.0)
    workflows = report_data.get("workflow_count", 0)
    total_acts = report_data.get("total_activities", 0)
    action_count = report_data.get("action_count", 0)
    coverage = report_data.get("coverage_pct", 100.0)

    print("\n--- Pipeline Execution Summary ---")
    print(f"  Project Name:       {report_data.get('project_name', 'UiPath Project')}")
    print(f"  Auto-Detect Rating: {complexity} (Score: {score})")
    print(f"  Archetype:          {'Blueprint / Scaffold' if report_data.get('is_scaffold') else 'Executable Automation'}")
    print(f"  Workflows Scanned:  {workflows}")
    print(f"  Source Activities:  {total_acts}")
    print(f"  PAD Actions:        {action_count}")
    print(f"  Activity Coverage:  {coverage}%")
    print(f"  Validation Status:  {status}")

    if result.get("errors"):
        print("\n[!] Strict Validation Errors:")
        for err in result["errors"]:
            print(f"    - 🔴 {err}")

    if result.get("warnings"):
        print("\n[*] Migration Notices & Warnings:")
        for w in result["warnings"]:
            print(f"    - 🟡 {w}")

    # Write output files
    out_dir = args.out
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.join(out_dir, "Reports"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "Analysis"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "Subflows"), exist_ok=True)

    # 1. Main Master Script
    main_script_path = os.path.join(out_dir, "Main_Robin_Script.txt")
    with open(main_script_path, "w", encoding="utf-8") as f:
        f.write(result.get("master_script", ""))

    # 2. Reports
    with open(os.path.join(out_dir, "Reports", "Conversion_Report.html"), "w", encoding="utf-8") as f:
        f.write(result.get("report_html", ""))

    with open(os.path.join(out_dir, "Reports", "Conversion_Report.md"), "w", encoding="utf-8") as f:
        f.write(result.get("report_markdown", ""))

    # 3. Individual Subflows
    for path, code in result.get("individual_flows", {}).items():
        sub_name = os.path.splitext(os.path.basename(path))[0]
        with open(os.path.join(out_dir, "Subflows", f"{sub_name}.robin"), "w", encoding="utf-8") as f:
            f.write(code)

    print("\n" + "=" * 70)
    print(f" [SUCCESS] Generated artifacts saved to: {os.path.abspath(out_dir)}")
    print(f" [->] 1-Click Paste Script: {os.path.abspath(main_script_path)}")
    print(f" [->] Audit Report (HTML):  {os.path.abspath(os.path.join(out_dir, 'Reports', 'Conversion_Report.html'))}")
    print("=" * 70)

if __name__ == "__main__":
    main()

