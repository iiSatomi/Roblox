"""Runtime-owned Bank savings reserve for enabled cash purchases."""
import unittest

from engine_harness import Harness, lua_table


class PurchaseSavingsTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.producer = self.h.load("src/engine/PurchaseSavings.luau")
        self.raw = self.h.snapshot(native={"fullSync": True,
                                            "cash": 1000})
        self.context = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0})
        self.reserves = lua_table(self.h.lua, {"cash": 0,
                                              "uncertainCash": 0})
        self.spec = self.h.lua.execute("""return {
            reader = { read = function(raw) return raw.native end },
            planner = { propose = function(view, config)
                return { resources = { cash = config.cost } }
            end },
        }""")

    def derive(self, settings, features=None):
        return self.producer.derive(self.raw, self.context,
            lua_table(self.h.lua, settings),
            lua_table(self.h.lua, features or {}), self.reserves)

    def test_no_purchase_keeps_no_extra_cash(self):
        proof, reason = self.derive({"bank": {"enabled": True}})
        self.assertIsNone(reason)
        self.assertEqual(proof["amount"], 0)
        self.assertEqual(proof["revision"], 1)

    def test_enabled_purchases_sum_costs_and_keep_largest_reserve(self):
        proof, reason = self.derive({
            "operations": {"enabled": True, "cost": 150,
                           "cashReserve": 100},
            "safehouse": {"enabled": True, "cost": 200,
                          "cashReserve": 50},
        }, {"operations": self.spec, "safehouse": self.spec})
        self.assertIsNone(reason)
        self.assertEqual(proof["amount"], 450)

    def test_unknown_enabled_purchase_keeps_all_cash(self):
        proof, reason = self.derive({"shop": {"enabled": True}})
        self.assertIsNone(reason)
        self.assertEqual(proof["amount"], 1000)

    def test_stale_or_partial_snapshot_has_no_proof(self):
        self.raw["revision"] = 2
        self.assertIsNone(self.derive({})[0])
        self.raw["revision"] = 1
        self.raw["native"]["fullSync"] = False
        self.assertIsNone(self.derive({})[0])


if __name__ == "__main__":
    unittest.main()
