from dataclasses import dataclass


class WorkflowError(ValueError):
    pass


@dataclass(frozen=True)
class WorkflowDefinition:
    name: str
    writable: bool
    required_evidence: tuple[str, ...]
    human_gate: bool = False


_DEFINITIONS = {
    "inspect-only": WorkflowDefinition(
        "inspect-only", False, ("inspection",), False
    ),
    "bugfix": WorkflowDefinition(
        "bugfix", True, ("targeted-tests", "regression"), False
    ),
    "feature": WorkflowDefinition(
        "feature", True, ("targeted-tests", "regression"), False
    ),
    "test-only": WorkflowDefinition("test-only", False, ("tests",), False),
    "build-release": WorkflowDefinition(
        "build-release", True, ("tests", "build"), False
    ),
    "production-change": WorkflowDefinition(
        "production-change", True, ("tests", "deployment"), True
    ),
}


class WorkflowRouter:
    def resolve(self, workflow_type: str) -> WorkflowDefinition:
        try:
            return _DEFINITIONS[workflow_type]
        except KeyError as exc:
            raise WorkflowError(f"unknown workflow: {workflow_type}") from exc
