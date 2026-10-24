"""Crew training uses a release-bound native quote and newer training state."""
import unittest

from engine_harness import Harness, lua_table


class CrewTrainingTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.catalog_module = self.h.load(
            "src/tabs/crew/NativeTrainingCatalog.luau")
        self.feature = self.h.load("src/tabs/crew/CrewTrain.luau")
        self.config = {"CREW": {"training": {
            "minRarity": 4, "maxLevel": 2, "maxConcurrent": 2,
            "cost": {rarity: [100 * rarity, 200 * rarity]
                     for rarity in range(4, 9)},
            "minutes": {rarity: [5, 10] for rarity in range(4, 9)}}}}
        self.native_config = lua_table(self.h.lua, self.config)
        self.catalog = self.catalog_module.new(
            self.native_config, "a" * 64, "release-a")
        self.now = 2000000
        self.raw = self.h.snapshot(native={"fullSync": True,
            "serverNow": self.now, "cash": 5000,
            "crew": [{"name": "Player"},
                     {"name": "Home", "rarity": 4},
                     {"name": "Best", "rarity": 6, "train": 0}]})
        self.raw, reason = self.catalog.Enrich(self.catalog, self.raw)
        self.assertIsNone(reason)
        self.context = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0, "serverNow": self.now,
            "trainingCatalogKey": "a" * 64})

    def settings(self, **custom):
        values = {"minRarity": 4, "targetLevel": 2, "maxCost": 5000,
                  "maxConcurrent": 1, "cashReserve": 1000}
        values.update(custom)
        return lua_table(self.h.lua, {"enabled": True, "custom": values})

    def plan(self):
        view, reason = self.feature.read(self.raw, self.context)
        self.assertIsNone(reason)
        proposal, reason = self.feature.propose(view, self.settings())
        self.assertIsNone(reason)
        return proposal

    def test_release_bound_catalog_is_copied_and_quotes_seconds(self):
        proof = self.raw["trainingCatalog"]
        self.assertEqual(proof["cost"][6][1], 600)
        self.assertEqual(proof["seconds"][6][1], 300)
        self.native_config["CREW"]["training"]["cost"][6][1] = 9999
        self.assertEqual(proof["cost"][6][1], 600)
        stale = self.h.snapshot(native={"fullSync": True})
        stale["release"] = "release-b"
        self.assertIsNone(self.catalog.Enrich(self.catalog, stale)[0])

    def test_selects_eligible_member_and_exact_training_start(self):
        proposal = self.plan()
        self.assertEqual(proposal["intent"]["remote"], "CrewAction")
        self.assertEqual(proposal["intent"]["args"][1], "train")
        self.assertEqual(proposal["intent"]["args"][2], 3)
        self.assertEqual(proposal["resources"]["cash"], 600)
        baseline, reason = self.feature.capture(proposal, self.raw)
        self.assertIsNone(reason)
        after = self.h.snapshot(native={"fullSync": True,
            "serverNow": self.now + 2, "cash": 4400,
            "crew": [{"name": "Player"},
                     {"name": "Home", "rarity": 4},
                     {"name": "Best", "rarity": 6, "train": 0,
                      "training": {"to": 1, "endsAt": self.now + 302}}]})
        after["revision"] = 2
        self.assertEqual(self.feature.evaluate(proposal, self.raw,
            after, lua_table(self.h.lua, {"ok": True}), baseline),
            "confirmed")

    def test_stale_or_ambiguous_quote_and_home_reserve_block(self):
        self.raw["trainingCatalog"]["release"] = "release-b"
        self.assertIsNone(self.feature.read(self.raw, self.context)[0])
        self.raw["trainingCatalog"]["release"] = "release-a"
        view, _ = self.feature.read(self.raw, self.context)
        self.assertIsNone(self.feature.propose(view,
            self.settings(cashReserve=4900))[0])
        self.raw["native"]["crew"][2]["duty"] = "district"
        view, _ = self.feature.read(self.raw, self.context)
        self.assertIsNone(self.feature.propose(view, self.settings())[0])

    def test_reply_alone_and_changed_member_do_not_confirm(self):
        proposal = self.plan()
        baseline, _ = self.feature.capture(proposal, self.raw)
        self.assertEqual(self.feature.evaluate(proposal, self.raw,
            self.raw, lua_table(self.h.lua, {"ok": True}), baseline),
            "pending")
        after = self.h.snapshot(native={"fullSync": True,
            "serverNow": self.now + 2, "cash": 4400,
            "crew": [{"name": "Player"},
                     {"name": "Home", "rarity": 4},
                     {"name": "Other", "rarity": 6, "train": 0,
                      "training": {"to": 1, "endsAt": self.now + 302}}]})
        after["revision"] = 2
        self.assertEqual(self.feature.evaluate(proposal, self.raw,
            after, lua_table(self.h.lua, {"ok": True}), baseline),
            "pending")

    def test_capture_rechecks_cash_reserve_and_quote_seconds(self):
        proposal = self.plan()
        self.raw["native"]["cash"] = 1500
        self.assertIsNone(self.feature.capture(proposal, self.raw)[0])
        self.raw["native"]["cash"] = 5000
        self.raw["trainingCatalog"]["seconds"][6][1] = 999
        self.assertIsNone(self.feature.capture(proposal, self.raw)[0])


if __name__ == "__main__":
    unittest.main()
