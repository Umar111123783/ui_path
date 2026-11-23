"""
Workflow Dependency Graph for analyzing execution hierarchy and detecting circular calls.
"""
from typing import Dict, List, Set
from core.exceptions import CircularWorkflowError

class WorkflowGraph:
    def __init__(self):
        self.adj_list: Dict[str, List[str]] = {}
        self.all_nodes: Set[str] = set()

    def add_workflow(self, wf_path: str):
        self.all_nodes.add(wf_path)
        if wf_path not in self.adj_list:
            self.adj_list[wf_path] = []

    def add_call(self, caller: str, callee: str):
        self.add_workflow(caller)
        self.add_workflow(callee)
        if callee not in self.adj_list[caller]:
            self.adj_list[caller].append(callee)

    def detect_cycles(self) -> List[str]:
        """Detects if there is a cycle in workflow invocations."""
        visited = set()
        rec_stack = set()
        cycle_path = []

        def dfs(node: str, current_path: List[str]) -> bool:
            visited.add(node)
            rec_stack.add(node)
            current_path.append(node)

            for neighbor in self.adj_list.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor, current_path):
                        return True
                elif neighbor in rec_stack:
                    current_path.append(neighbor)
                    cycle_path.extend(current_path)
                    return True

            current_path.pop()
            rec_stack.remove(node)
            return False

        for n in self.all_nodes:
            if n not in visited:
                if dfs(n, []):
                    return cycle_path
        return []

    def get_execution_order(self, entry_point: str) -> List[str]:
        """Returns topological invocation order starting from entry_point."""
        cycles = self.detect_cycles()
        if cycles:
            raise CircularWorkflowError(f"Circular workflow reference detected: {' -> '.join(cycles)}")

        visited = set()
        order = []

        def dfs(node: str):
            if node in visited:
                return
            visited.add(node)
            order.append(node)
            for child in self.adj_list.get(node, []):
                dfs(child)

        dfs(entry_point)
        # Append any uncalled workflows at the end
        for node in sorted(self.all_nodes):
            if node not in visited:
                dfs(node)

        return order

