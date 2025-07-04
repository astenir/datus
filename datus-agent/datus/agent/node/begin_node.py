from typing import Dict

from datus.agent.node import Node
from datus.agent.workflow import Workflow
from datus.schemas.base import BaseResult


class BeginNode(Node):
    def update_context(self, workflow: Workflow) -> Dict:
        pass

    def setup_input(self, workflow: Workflow) -> Dict:
        return {"success": True, "message": "Start node, no input needed"}

    def execute(self) -> BaseResult:
        pass
