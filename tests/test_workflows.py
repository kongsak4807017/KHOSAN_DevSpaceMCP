import unittest

from ops.workflows import WorkflowError, WorkflowRouter


class WorkflowRouterTests(unittest.TestCase):
    def setUp(self):
        self.router = WorkflowRouter()

    def test_initial_workflow_contracts_are_explicit(self):
        expected = {
            "inspect-only": (False, ("inspection",), False),
            "bugfix": (True, ("targeted-tests", "regression"), False),
            "feature": (True, ("targeted-tests", "regression"), False),
            "test-only": (False, ("tests",), False),
            "build-release": (True, ("tests", "build"), False),
            "production-change": (True, ("tests", "deployment"), True),
        }

        for name, (writable, evidence, human_gate) in expected.items():
            with self.subTest(name=name):
                definition = self.router.resolve(name)
                self.assertEqual(definition.name, name)
                self.assertEqual(definition.writable, writable)
                self.assertEqual(definition.required_evidence, evidence)
                self.assertEqual(definition.human_gate, human_gate)

    def test_unknown_workflow_fails_closed(self):
        with self.assertRaisesRegex(WorkflowError, "unknown workflow"):
            self.router.resolve("invented-by-agent")


if __name__ == "__main__":
    unittest.main()
