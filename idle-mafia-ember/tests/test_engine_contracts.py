"""Pure contract and monotonic clock checks; no game client is used."""
from pathlib import Path
import unittest

from lupa import LuaRuntime


ROOT = Path(__file__).resolve().parents[1]


def table(lua, value):
    if isinstance(value, dict):
        return lua.table_from({key: table(lua, item) for key, item in value.items()})
    if isinstance(value, list):
        return lua.table_from([table(lua, item) for item in value])
    return value


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        contracts_path = ROOT / "src/engine/Contracts.luau"
        clock_path = ROOT / "src/engine/Clock.luau"
        self.assertTrue(contracts_path.is_file(), "Contracts module is missing")
        self.assertTrue(clock_path.is_file(), "Clock module is missing")
        self.contracts = self.lua.execute(contracts_path.read_text(encoding="utf-8"))
        self.clock = self.lua.execute(clock_path.read_text(encoding="utf-8"))
        self.expected = {
            "session": "run-a", "account": "user-a", "place": "73897506680154",
            "release": "release-a",
        }

    def snapshot(self, **changes):
        value = {**self.expected, "revision": 7, "capturedAt": 10.0}
        value.update(changes)
        return table(self.lua, value)

    def proposal(self, **changes):
        value = {
            **self.expected, "revision": 7, "feature": "jobs",
            "actionKey": "jobs:j_watch:7", "resources": {"energy": 1},
            "intent": {"kind": "job", "jobId": "j_watch"},
        }
        value.update(changes)
        return table(self.lua, value)

    def test_snapshot_copies_valid_header_and_rejects_wrong_identity(self):
        raw = self.snapshot()
        view, reason = self.contracts.validateSnapshot(raw, table(self.lua, self.expected))
        self.assertIsNone(reason)
        self.assertEqual(view["revision"], 7)
        raw["revision"] = 8
        self.assertEqual(view["revision"], 7)
        for field in self.expected:
            rejected, reason = self.contracts.validateSnapshot(
                self.snapshot(**{field: "different"}), table(self.lua, self.expected)
            )
            self.assertIsNone(rejected)
            self.assertIn(field, reason)

    def test_snapshot_requires_finite_time_and_integer_revision(self):
        for change in ({"capturedAt": float("nan")}, {"capturedAt": -1},
                       {"revision": 1.5}, {"revision": None}):
            rejected, reason = self.contracts.validateSnapshot(
                self.snapshot(**change), table(self.lua, self.expected)
            )
            self.assertIsNone(rejected)
            self.assertTrue(reason)

    def test_proposal_requires_current_revision_and_safe_exposure(self):
        snapshot = self.snapshot()
        original = self.proposal()
        view, reason = self.contracts.validateProposal(original, snapshot)
        self.assertIsNone(reason)
        self.assertEqual(view["resources"]["energy"], 1)
        original["resources"]["energy"] = 999
        self.assertEqual(view["resources"]["energy"], 1)
        original["intent"]["jobId"] = "j_tag"
        self.assertIsNotNone(view["intent"], "Validated intent missing")
        self.assertEqual(view["intent"]["jobId"], "j_watch")
        for change in ({"revision": 6}, {"account": "other"},
                       {"actionKey": ""}, {"resources": {"energy": -1}},
                       {"resources": {"energy": float("inf")}},
                       {"intent": {"kind": "job", "nested": {"bad": True}}},
                       {"intent": {"kind": ""}}):
            rejected, reason = self.contracts.validateProposal(
                self.proposal(**change), snapshot
            )
            self.assertIsNone(rejected)
            self.assertTrue(reason)

    def test_clock_clamps_regression_and_rejects_invalid_sample(self):
        samples = [10.0, 9.0, 10.5]
        callback = self.lua.eval("function(f) return function() return f() end end")
        clock = self.clock.new(callback(lambda: samples.pop(0)))
        self.assertEqual(clock.Now(clock), 10.0)
        self.assertEqual(clock.Now(clock), 10.0)
        self.assertEqual(clock.Now(clock), 10.5)
        invalid = self.clock.new(callback(lambda: float("nan")))
        with self.assertRaises(Exception):
            invalid.Now(invalid)


if __name__ == "__main__":
    unittest.main()
