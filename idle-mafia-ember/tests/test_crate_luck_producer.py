"""Crate luck comes from the native rule for the exact full Sync."""
import unittest

from engine_harness import Harness, lua_table


class CrateLuckProducerTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.producer = self.h.load("src/tabs/inventory/CrateLuckProducer.luau")
        self.source_module = self.h.load(
            "src/tabs/inventory/NativeCrateLuckSource.luau")
        rule = self.h.lua.execute("""return {
            crateLuck = function(native) return native.luckBonus end,
        }""")
        self.source, reason = self.source_module.new(rule, "release-a")
        self.assertIsNone(reason)
        self.raw = self.h.snapshot(native={
            "fullSync": True, "luckBonus": 0.25})
        self.context = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0})

    def test_rule_value_is_bound_to_exact_snapshot(self):
        proof, reason = self.producer.derive(
            self.raw, self.context, self.source)
        self.assertIsNone(reason)
        self.assertEqual(proof.luck, 0.25)
        self.assertEqual(proof.revision, 1)
        self.context["revision"] = 2
        self.assertIsNone(self.producer.derive(
            self.raw, self.context, self.source)[0])

    def test_missing_rule_and_bad_luck_fail_closed(self):
        self.assertIsNone(self.source_module.new(
            self.h.lua.table(), "release-a")[0])
        self.raw["native"]["luckBonus"] = 11
        self.assertIsNone(self.producer.derive(
            self.raw, self.context, self.source)[0])
        self.raw["native"]["luckBonus"] = 0.25
        self.source["release"] = "another-release"
        self.assertIsNone(self.producer.derive(
            self.raw, self.context, self.source)[0])


if __name__ == "__main__":
    unittest.main()
