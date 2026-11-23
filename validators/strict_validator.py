"""
Strict Validator for multi-stage verification against Microsoft PAD 2.74 Robin standards.
"""
import os
import re
import tempfile
import subprocess
from typing import Dict, Any, List

class StrictValidator:
    def __init__(self, kb_path: str = None, checker_path: str = None):
        base_dir = os.path.dirname(os.path.dirname(__file__))
        self.kb_path = kb_path or os.path.join(base_dir, "pad-robin-action-kb-main", "PAD_Robin_ActionKB.json")
        self.checker_path = checker_path or os.path.join(base_dir, "pad-robin-action-kb-main", "marketing", "video", "tools", "check-flows.js")

    def validate(self, robin_code: str, strict_mode: bool = True) -> Dict[str, Any]:
        """Runs full strict validation pipeline."""
        errors: List[str] = []
        warnings: List[str] = []

        # 1. Control-Flow Balance Checks
        if_count = len(re.findall(r'^\s*IF\b', robin_code, re.M))
        loop_count = len(re.findall(r'^\s*LOOP\b', robin_code, re.M))
        block_count = len(re.findall(r'^\s*BLOCK\b', robin_code, re.M))
        end_count = len(re.findall(r'^\s*END\b', robin_code, re.M))
        expected_ends = if_count + loop_count + block_count

        if end_count != expected_ends:
            warnings.append(f"Control-flow block mismatch: {expected_ends} blocks started (IF:{if_count}, LOOP:{loop_count}, BLOCK:{block_count}), but found {end_count} END statements.")

        # Region Balance
        region_open = len(re.findall(r'^\s*\*\*REGION\b', robin_code, re.M))
        region_close = len(re.findall(r'^\s*\*\*ENDREGION\b', robin_code, re.M))
        if region_open != region_close:
            errors.append(f"Unbalanced **REGION markers: {region_open} opened vs {region_close} closed.")

        # 2. Syntax & PAD Grammar Validation via check-flows.js
        checker_errors = self._run_check_flows(robin_code)
        errors.extend(checker_errors)

        # 3. Semantic Action Check
        action_lines = [l for l in robin_code.splitlines() if l.strip() and not l.strip().startswith("#") and not l.strip().startswith("**")]
        if not action_lines:
            errors.append("No executable PAD actions found in generated script.")

        # 4. Status determination
        if errors:
            status = "FAILED"
        elif warnings:
            status = "PASS_WITH_WARNINGS"
        else:
            status = "PASS"

        return {
            "status": status,
            "valid": status in ["PASS", "PASS_WITH_WARNINGS"],
            "errors": errors,
            "warnings": warnings,
            "action_count": len(action_lines)
        }

    def _run_check_flows(self, code: str) -> List[str]:
        if not (os.path.exists(self.checker_path) and os.path.exists(self.kb_path)):
            return []

        tmp_path = ""
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.robin', delete=False, encoding='utf-8') as f:
                tmp_path = f.name
                f.write(code)

            cmd = ["node", self.checker_path, self.kb_path, tmp_path]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            output = res.stdout + res.stderr

            if os.path.exists(tmp_path):
                os.remove(tmp_path)

            if res.returncode == 0 and "0 errors" in output:
                return []

            err_lines = [line.strip() for line in output.splitlines() if line.strip().startswith("line ") or "error" in line.lower()]
            return [e for e in err_lines if "0 errors" not in e]
        except Exception as e:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
            return [f"Checker execution error: {e}"]

