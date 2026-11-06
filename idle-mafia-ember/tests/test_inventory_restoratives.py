"""Player restoratives require owned custody, cooldown and sequence evidence."""
import unittest

from engine_harness import Harness, lua_table


ITEMS = (("con_bandages", "health", 25),
         ("con_medkit_small", "health", 50),
         ("con_medkit_large", "health", 100),
         ("con_energy_small", "energy", 25),
         ("con_energy", "energy", 50),
         ("con_energy_pack", "energy", 100),
         ("con_peanuts", "stamina", 25),
         ("con_sandwich", "stamina", 50),
         ("con_lunchbox", "stamina", 100))


class InventoryRestorativesTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        source = self.h.load(
            "src/tabs/inventory/NativeRestorativeCatalog.luau")
        self.feature = self.h.load(
            "src/tabs/inventory/Restoratives.luau")
        data = lua_table(self.h.lua, {"ITEMS_BY_ID": {
            item: {"id": item, "kind": "consumable",
                   "restore": {"pool": pool, "percent": percent}}
            for item, pool, percent in ITEMS}})
        catalog = source.new(data, lua_table(self.h.lua,
            {"CONSUMABLES": {"cooldownSeconds": 3}}),
            "e" * 64, "release-a")
        self.before = self.h.snapshot(native={"fullSync": True,
            "serverNow": 2000000, "consumableUseSequence": 4,
            "consumableReadyAt": 1999999,
            "pools": {"health": 30, "energy": 100, "stamina": 50},
            "stats": {"maxHealth": 100, "maxStamina": 100},
            "derived": {"effMaxEnergy": 100},
            "inventoryBound": {"con_medkit_small": 1},
            "inventory": {"con_medkit_small": 1}})
        self.before, reason = catalog.Enrich(catalog, self.before)
        self.assertIsNone(reason)
        self.context = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0, "serverNow": 2000000,
            "restorativeCatalogKey": "e" * 64})

    def settings(self):
        return lua_table(self.h.lua, {"enabled": True,
            "policy": "Balanced recovery", "custom": {
                "healthBelow": 50, "energyBelow": 25,
                "staminaBelow": 25, "minUsefulPercent": 10,
                "custody": "Bound only"}})

    def plan(self):
        view, reason = self.feature.read(self.before, self.context)
        self.assertIsNone(reason)
        proposal, reason = self.feature.propose(view, self.settings())
        self.assertIsNone(reason)
        return proposal

    def test_each_pool_policy_overrides_shared_and_off_skips_empty_pool(self):
        for pool in ("health", "energy", "stamina"):
            for policy, percent in (("Small first", 25), ("Large first", 100), ("Balanced recovery", 50)):
                self.before.native.pools = lua_table(self.h.lua, {"health": 100, "energy": 100, "stamina": 100})
                self.before.native.pools[pool] = 30
                self.before.native.inventoryBound = lua_table(self.h.lua, {item: 1 for item, _, _ in ITEMS})
                view, _ = self.feature.read(self.before, self.context)
                settings = self.settings()
                settings.policy = "Large first" if policy != "Large first" else "Small first"
                settings.custom[pool + "Below"] = 50
                settings.custom[pool + "Policy"] = policy
                proposal, reason = self.feature.propose(view, settings)
                self.assertIsNone(reason)
                expected = next(item for item, resource, size in ITEMS if resource == pool and size == percent)
                self.assertEqual(proposal.intent.itemId, expected)
                view.pools[pool].current = 0
                settings.custom[pool + "Policy"] = "Off"
                self.assertIsNone(self.feature.propose(view, settings)[0])

    def test_pool_off_preserves_health_energy_stamina_priority_and_bound_first(self):
        self.before.native.pools = lua_table(self.h.lua, {"health": 0, "energy": 0, "stamina": 0})
        self.before.native.inventoryBound = lua_table(self.h.lua, {"con_bandages": 1, "con_energy_small": 1, "con_peanuts": 1})
        self.before.native.inventory = lua_table(self.h.lua, {"con_energy_pack": 1})
        view, _ = self.feature.read(self.before, self.context)
        settings = self.settings()
        settings.custom.healthPolicy = "Off"
        settings.custom.energyPolicy = "Large first"
        settings.custom.custody = "Bound or tradable"
        proposal, _ = self.feature.propose(view, settings)
        self.assertEqual(proposal.intent.itemId, "con_energy_small")
        self.assertTrue(proposal.intent.fromBound)
        settings.custom.energyPolicy = "Off"
        proposal, _ = self.feature.propose(view, settings)
        self.assertEqual(proposal.intent.itemId, "con_peanuts")

    def test_invalid_pool_policy_refuses_and_shared_policy_preserves_existing_behavior(self):
        view, _ = self.feature.read(self.before, self.context)
        settings = self.settings()
        for value in ("Unknown", False, 1):
            settings.custom.healthPolicy = value
            self.assertIsNone(self.feature.propose(view, settings)[0])
        settings.custom.healthPolicy = "Shared policy"
        self.assertEqual(self.feature.propose(view, settings)[0].intent.itemId, "con_medkit_small")

    def test_fractional_threshold_boundaries_and_invalid_values(self):
        view, _ = self.feature.read(self.before, self.context)
        settings = self.settings()
        settings.custom.healthBelow = 25.5
        for current, eligible in ((25.499, True), (25.5, True), (25.501, False)):
            view.pools.health.current = current
            self.assertEqual(self.feature.propose(view, settings)[0] is not None, eligible)
        for key in ("healthBelow", "energyBelow", "staminaBelow"):
            for invalid in (-0.001, 100.001, float("nan"), float("inf"), -float("inf"), True, "25.5"):
                settings.custom[key] = invalid
                self.assertIsNone(self.feature.propose(view, settings)[0])
            settings.custom[key] = 25.5
        view.pools.health.current = 0
        settings.custom.healthBelow = 0
        self.assertIsNotNone(self.feature.propose(view, settings)[0])
        settings.custom.healthPolicy = "Off"
        self.assertIsNone(self.feature.propose(view, settings)[0])
        settings.custom.healthPolicy = "Shared policy"
        settings.custom.healthBelow = 100
        view.pools.health.current = 90
        self.assertIsNotNone(self.feature.propose(view, settings)[0])
        settings.custom.minUsefulPercent = 0.5
        self.assertIsNone(self.feature.propose(view, settings)[0])

    def test_balanced_compares_waste_before_size_even_for_tiny_fractional_waste(self):
        self.before.native.inventoryBound = lua_table(self.h.lua, {"con_bandages": 1, "con_medkit_small": 1})
        view, _ = self.feature.read(self.before, self.context)
        settings = self.settings()
        settings.custom.healthBelow = 75
        for current, expected in ((50.001, "con_bandages"), (50.00000001, "con_bandages"),
                                  (50, "con_medkit_small"), (49.999, "con_medkit_small")):
            for policy in ("Shared policy", "Balanced recovery"):
                view.pools.health.current = current
                settings.custom.healthPolicy = policy
                proposal, reason = self.feature.propose(view, settings)
                self.assertIsNone(reason)
                self.assertEqual(proposal.intent.itemId, expected)
        # A better ordinary-origin waste result never bypasses bound-first custody.
        view.pools.health.current = 50.001
        view.bound.con_bandages = 0
        view.ordinary.con_bandages = 1
        settings.custom.custody = "Bound or tradable"
        proposal, _ = self.feature.propose(view, settings)
        self.assertEqual(proposal.intent.itemId, "con_medkit_small")
        self.assertTrue(proposal.intent.fromBound)

    def test_bound_first_and_exact_newer_sequence(self):
        proposal = self.plan()
        self.assertEqual(proposal["intent"]["itemId"], "con_medkit_small")
        self.assertTrue(proposal["intent"]["fromBound"])
        self.assertEqual(proposal["intent"]["sequence"], 4)
        baseline, reason = self.feature.capture(proposal, self.before)
        self.assertIsNone(reason)
        after = self.h.snapshot(revision=2, native={"fullSync": True,
            "serverNow": 2000001, "consumableUseSequence": 5,
            "consumableReadyAt": 2000003,
            "pools": {"health": 80},
            "inventoryBound": {"con_medkit_small": 0},
            "inventory": {"con_medkit_small": 1}})
        reply = lua_table(self.h.lua, {"ok": True,
            "sequence": 5, "readyAt": 2000003,
            "resource": "health", "gain": 50})
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            after, reply, baseline), "confirmed")
        after["native"]["inventoryBound"]["con_medkit_small"] = 1
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            after, reply, baseline), "pending")


    def result_fixture(self, effect=False):
        return self.h.snapshot(revision=2,native={"fullSync":True,"serverNow":2000001,
            "consumableUseSequence":5 if effect else 4,
            "consumableReadyAt":2000003 if effect else 1999999,
            "pools":{"health":80 if effect else 30},
            "inventoryBound":{"con_medkit_small":0 if effect else 1},
            "inventory":{"con_medkit_small":1}})

    def test_pending_and_transient_replies_keep_inventory_custody(self):
        proposal=self.plan();baseline,reason=self.feature.capture(proposal,self.before)
        self.assertIsNone(reason)
        for status in ({"pending":True},{"code":"rate_limited"},{"code":"busy"},{"code":"presence"}):
            for ok in (False,True):
                with self.subTest(status=status,ok=ok):
                    reply=lua_table(self.h.lua,{"ok":ok,"sequence":5,"readyAt":2000003,
                        "resource":"health","gain":50,**status})
                    for effect in (False,True):
                        self.assertEqual(self.feature.evaluate(proposal,self.before,self.result_fixture(effect),reply,baseline),"pending")

    def test_negative_reply_rejects_only_complete_unchanged_owned_state(self):
        proposal=self.plan();baseline,reason=self.feature.capture(proposal,self.before)
        self.assertIsNone(reason)
        reply=lua_table(self.h.lua,{"ok":False,"code":"not_ready"})
        self.assertEqual(self.feature.evaluate(proposal,self.before,self.result_fixture(),reply,baseline),"rejected")
        for change in ("partial","sequence","cooldown","item","otherOrigin","pool","missingPool"):
            with self.subTest(change=change):
                after=self.result_fixture()
                if change=="partial":after.native.fullSync=False
                elif change=="sequence":after.native.consumableUseSequence=5
                elif change=="cooldown":after.native.consumableReadyAt=2000003
                elif change=="item":after.native.inventoryBound.con_medkit_small=0
                elif change=="otherOrigin":after.native.inventory.con_medkit_small=0
                elif change=="pool":after.native.pools.health=80
                else:after.native.pools=None
                self.assertEqual(self.feature.evaluate(proposal,self.before,after,reply,baseline),"pending")

    def test_cooldown_and_sequence_fence(self):
        proposal = self.plan()
        self.before["native"]["consumableReadyAt"] = 2000002
        self.assertIsNone(self.feature.capture(proposal, self.before)[0])
        self.before["native"]["consumableReadyAt"] = 1999999
        self.before["native"]["consumableUseSequence"] = 5
        self.assertIsNone(self.feature.capture(proposal, self.before)[0])

    def test_fractional_server_and_cooldown_times_are_valid(self):
        self.before["native"]["serverNow"] = 2000000.5
        self.before["native"]["consumableReadyAt"] = 1999999.25
        self.context["serverNow"] = 2000000.5
        proposal = self.plan()
        baseline, reason = self.feature.capture(proposal, self.before)
        self.assertIsNone(reason)
        self.assertEqual(baseline["sequence"], 4)

    def test_no_use_when_recovery_would_be_too_small(self):
        self.before["native"]["pools"]["health"] = 96
        view, reason = self.feature.read(self.before, self.context)
        self.assertIsNone(reason)
        settings = self.settings()
        settings["custom"]["healthBelow"] = 100
        proposal, _ = self.feature.propose(view, settings)
        self.assertIsNone(proposal)
        settings["custom"]["minUsefulPercent"] = 4
        self.assertIsNotNone(self.feature.propose(view, settings)[0])

    def test_new_full_sync_rebases_player_sequence_after_reload(self):
        old = self.plan()
        newer = self.h.snapshot(revision=2, native={
            "fullSync": True, "serverNow": 2000010,
            "consumableUseSequence": 8,
            "consumableReadyAt": 2000009,
            "pools": {"health": 30, "energy": 100, "stamina": 50},
            "stats": {"maxHealth": 100, "maxStamina": 100},
            "derived": {"effMaxEnergy": 100},
            "inventoryBound": {"con_medkit_small": 1},
            "inventory": {"con_medkit_small": 1}})
        newer["restorativeCatalog"] = self.before["restorativeCatalog"]
        context = lua_table(self.h.lua, {**self.h.session,
            "revision": 2, "capturedAt": 0,
            "serverNow": 2000010,
            "restorativeCatalogKey": "e" * 64})
        view, reason = self.feature.read(newer, context)
        self.assertIsNone(reason)
        proposal, reason = self.feature.propose(view, self.settings())
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["sequence"], 8)
        self.assertIsNone(self.feature.capture(old, newer)[0])


if __name__ == "__main__":
    unittest.main()
