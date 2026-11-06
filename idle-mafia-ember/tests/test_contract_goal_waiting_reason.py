"""Goal status explains absent borrowing without enabling any ordinary route."""
import unittest
import test_contract_goal_runtime as fixture


class ContractGoalWaitingReasonTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.ContractGoalRuntimeTests()
        self.f.setup_goal("unreviewed_objective")

    def tearDown(self):
        self.f.app.Destroy(self.f.app)

    def test_all_borrow_permissions_off_reports_waiting_and_does_not_send(self):
        self.f.select(jobs=False, borrow=False)
        self.f.app.Set(self.f.app, "operations.enabled", False)
        for name in ("borrowJobs", "borrowOperations", "borrowCollect", "borrowHeists", "borrowHires"):
            self.f.app.Set(self.f.app, "autoContracts.custom." + name, False)
        self.f.app.Step(self.f.app, self.f.raw())
        status = self.f.runtime.Status(self.f.runtime)
        self.assertEqual(status.goals.autoContracts.state, "waiting")
        self.assertFalse(status.goals.autoContracts.routed)
        self.assertEqual(status.reasons.autoContracts,
                         "No ordinary borrowing permission enabled; goal routing is waiting")
        self.assertEqual(len(self.f.executor.calls), 0)
        self.assertIsNone(self.f.executor.callback)

    def test_enabled_borrow_retains_unsupported_objective_diagnostic(self):
        self.f.select(jobs=False, borrow=True)
        self.f.app.Set(self.f.app, "operations.enabled", False)
        self.f.app.Step(self.f.app, self.f.raw())
        status = self.f.runtime.Status(self.f.runtime)
        self.assertEqual(status.reasons.autoContracts, "No verified planner")
        self.assertFalse(status.goals.autoContracts.routed)
        self.assertEqual(len(self.f.executor.calls), 0)
