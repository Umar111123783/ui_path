"""
Complexity & Capability Analyzer for automatic project profiling.
"""
from typing import Dict, Any, Tuple
from core.project_model import ProjectInventory

INTEGRATION_ACTIVITIES = {
    "ExcelApplicationScope", "ReadRange", "WriteRange", "ExecuteQuery", "ExecuteNonQuery",
    "HttpClient", "SoapClient", "SendMail", "GetIMAPMailMessages", "DatabaseConnect"
}

ADVANCED_ACTIVITIES = {
    "StateMachine", "State", "Transition", "Parallel", "Pick", "PickBranch",
    "InvokeCode", "InvokePowerShell", "InvokeComMethod"
}

SCAFFOLD_ACTIVITIES = {
    "LogMessage", "WriteLine", "Comment", "CommentOut"
}

class ComplexityAnalyzer:
    def analyze(self, inventory: ProjectInventory) -> Dict[str, Any]:
        workflow_count = len(inventory.workflows)
        total_activities = 0
        max_nesting = 0
        invoke_count = 0
        integration_count = 0
        advanced_count = 0
        scaffold_count = 0

        for wf in inventory.workflows.values():
            total_activities += wf.activity_count
            max_nesting = max(max_nesting, wf.max_depth)
            invoke_count += len(wf.invoked_workflows)
            
            # Inspect node types
            if wf.root_activity:
                i_cnt, a_cnt, s_cnt = self._inspect_node(wf.root_activity)
                integration_count += i_cnt
                advanced_count += a_cnt
                scaffold_count += s_cnt

        dependency_count = len(inventory.dependencies)
        is_scaffold = total_activities > 0 and (scaffold_count / total_activities) >= 0.60

        metrics = {
            "workflow_count": workflow_count,
            "activity_count": total_activities,
            "nesting_depth": max_nesting,
            "dependency_count": dependency_count,
            "invoke_count": invoke_count,
            "integration_count": integration_count,
            "advanced_activity_count": advanced_count,
            "scaffold_activity_count": scaffold_count,
            "is_scaffold": is_scaffold
        }

        rating, score = self.score_complexity(metrics)

        return {
            "rating": rating,
            "score": round(score, 2),
            "is_scaffold": is_scaffold,
            "metrics": metrics
        }

    def _inspect_node(self, node) -> Tuple[int, int, int]:
        int_cnt = 1 if node.type_name in INTEGRATION_ACTIVITIES else 0
        adv_cnt = 1 if node.type_name in ADVANCED_ACTIVITIES else 0
        scf_cnt = 1 if node.type_name in SCAFFOLD_ACTIVITIES else 0
        for ch in node.children:
            c_int, c_adv, c_scf = self._inspect_node(ch)
            int_cnt += c_int
            adv_cnt += c_adv
            scf_cnt += c_scf
        return int_cnt, adv_cnt, scf_cnt

    def score_complexity(self, metrics: Dict[str, Any]) -> Tuple[str, float]:
        score = 0.0
        score += min(metrics["workflow_count"] * 1.0, 20.0)
        score += min(metrics["activity_count"] * 0.15, 20.0)
        score += min(metrics["nesting_depth"] * 3.0, 15.0)
        score += min(metrics["dependency_count"] * 2.0, 10.0)
        score += min(metrics["invoke_count"] * 2.0, 10.0)
        score += min(metrics["integration_count"] * 3.0, 15.0)
        score += min(metrics["advanced_activity_count"] * 2.0, 10.0)

        if score <= 15:
            return "SIMPLE", score
        elif score <= 35:
            return "INTERMEDIATE", score
        elif score <= 60:
            return "ADVANCED", score
        else:
            return "ENTERPRISE", score

