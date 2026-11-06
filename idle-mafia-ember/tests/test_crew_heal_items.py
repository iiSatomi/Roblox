"""Owned Crew healing items require sequence, cooldown and custody proof."""
import unittest

from engine_harness import Harness, lua_table


class CrewHealItemsTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.source = self.h.load(
            "src/tabs/crew/NativeHealItemCatalog.luau")
        self.feature = self.h.load("src/tabs/crew/CrewHealItems.luau")
        items = {item: {"id": item, "kind": "consumable",
            "restore": {"pool": "health", "percent": percent}}
            for item, percent in (("con_bandages", 25),
                ("con_medkit_small", 50), ("con_medkit_large", 100))}
        self.catalog = self.source.new(lua_table(self.h.lua,
            {"ITEMS_BY_ID": items}), lua_table(self.h.lua,
            {"TERRITORY": {"injurySeconds": 1200},
             "CONSUMABLES": {"henchmanCooldownSeconds": 3}}),
            "c" * 64, "release-a")
        self.now = 2000000
        self.before = self.h.snapshot(native={"fullSync": True,
            "serverNow": self.now, "henchmanConsumableUseSequence": 7,
            "henchmanConsumableReadyAt": self.now - 1,
            "inventoryBound": {"con_bandages": 2},
            "inventory": {"con_bandages": 1},
            "crew": [{"name": "Player"}, {"name": "Ally", "rarity": 4,
                "healId": "injury-a", "injuredUntil": self.now + 700}]})
        self.before, reason = self.catalog.Enrich(self.catalog, self.before)
        self.assertIsNone(reason)
        self.context = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0, "serverNow": self.now,
            "healItemCatalogKey": "c" * 64})

    def plan(self):
        view, reason = self.feature.read(self.before, self.context)
        self.assertIsNone(reason)
        proposal, reason = self.feature.propose(view, lua_table(self.h.lua,
            {"enabled": True, "policy": "con_bandages",
             "custom": {"minRemaining": 300}}))
        self.assertIsNone(reason)
        return proposal

    def test_bound_first_payload_and_exact_confirmation(self):
        proposal = self.plan()
        validated, reason = self.h.contracts.validateProposal(proposal, self.before)
        self.assertIsNone(reason)
        call, reason = self.h.load("src/tabs/crew/CrewCallPlan.luau").describe(validated)
        self.assertIsNone(reason)
        self.assertEqual(call.arity, 3)
        args = call.args
        self.assertEqual(args[1], "healitem")
        self.assertEqual(args[2], 2)
        self.assertEqual(args[3]["itemId"], "con_bandages")
        self.assertTrue(args[3]["fromBound"])
        self.assertEqual(args[3]["sequence"], 7)
        baseline, reason = self.feature.capture(proposal, self.before)
        self.assertIsNone(reason)
        after = self.h.snapshot(revision=2, native={"fullSync": True,
            "serverNow": self.now + 2,
            "henchmanConsumableUseSequence": 8,
            "henchmanConsumableReadyAt": self.now + 3,
            "inventoryBound": {"con_bandages": 1},
            "inventory": {"con_bandages": 1},
            "crew": [{"name": "Player"}, {"name": "Ally", "rarity": 4,
                "healId": "injury-a", "injuredUntil": self.now + 400}]})
        reply = lua_table(self.h.lua, {"ok": True,
            "sequence": 8, "readyAt": self.now + 3})
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            after, reply, baseline), "confirmed")
        after["native"]["inventoryBound"]["con_bandages"] = 2
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            after, reply, baseline), "pending")

    def test_capture_rejects_tampered_item_resources_and_effect_terms(self):
        proposal = self.plan()
        proposal.resources.con_bandages = 0
        self.assertIsNone(self.feature.capture(proposal, self.before)[0])
        proposal = self.plan()
        proposal.intent.injuredUntil = self.now + 600
        self.assertIsNone(self.feature.capture(proposal, self.before)[0])

    def test_saved_effect_recovery_uses_original_baseline_and_native_time_across_restart(self):
        proposal = self.plan()
        baseline = self.feature.capture(proposal,self.before)[0]
        data = lua_table(self.h.lua,{'proposal':proposal,'before':self.before,'baseline':baseline,
            'reply':{'ok':True,'sequence':8,'readyAt':self.now+3}})
        after = self.h.snapshot(revision=0,native={'fullSync':True,'serverNow':self.now+2,
            'henchmanConsumableUseSequence':8,'henchmanConsumableReadyAt':self.now+3,
            'inventoryBound':{'con_bandages':1},'inventory':{'con_bandages':1},
            'crew':[{}, {'name':'Ally','rarity':4,'healId':'injury-a','injuredUntil':self.now+400}]})
        after.session = 'restarted'
        self.assertEqual(self.feature.recoverSaved(data,after,0),'confirmed')
        after.native.crew[2].healId = 'other-member'
        self.assertIsNone(self.feature.recoverSaved(data,after,0))
        after.native.crew[2].healId = 'injury-a'
        data.baseline.reduction = 1
        self.assertIsNone(self.feature.recoverSaved(data,after,0))

    def test_cooldown_or_sequence_change_blocks(self):
        proposal = self.plan()
        self.before["native"]["henchmanConsumableReadyAt"] = self.now + 2
        self.assertIsNone(self.feature.capture(proposal, self.before)[0])
        self.before["native"]["henchmanConsumableReadyAt"] = self.now - 1
        self.before["native"]["henchmanConsumableUseSequence"] = 8
        self.assertIsNone(self.feature.capture(proposal, self.before)[0])

    def test_complete_sync_missing_first_use_fields_defaults_to_native_zero(self):
        self.before.native.henchmanConsumableUseSequence = None
        self.before.native.henchmanConsumableReadyAt = None
        proposal = self.plan()
        self.assertEqual(proposal.intent.sequence, 0)
        self.assertIsNotNone(self.feature.capture(proposal, self.before)[0])
        self.before.native.henchmanConsumableUseSequence = False
        self.assertIsNone(self.feature.read(self.before, self.context)[0])

    def test_missing_item_or_duplicate_identity_blocks(self):
        self.before["native"]["inventoryBound"]["con_bandages"] = 0
        self.before["native"]["inventory"]["con_bandages"] = 0
        view, reason = self.feature.read(self.before, self.context)
        self.assertIsNone(reason)
        self.assertIsNone(self.feature.propose(view, lua_table(self.h.lua,
            {"enabled": True, "policy": "con_bandages",
             "custom": {"minRemaining": 300}}))[0])
        self.before["native"]["crew"][3] = lua_table(self.h.lua,
            {"name": "Ally", "rarity": 4, "healId": "injury-a"})
        self.assertIsNone(self.feature.read(self.before, self.context)[0])

    def test_same_names_distinct_ids_and_large_medkit_full_reduction(self):
        self.before.native.crew[3] = lua_table(self.h.lua,
            {"name": "Ally", "rarity": 4, "healId": "injury-b"})
        self.before.native.inventoryBound.con_medkit_large = 1
        view = self.feature.read(self.before, self.context)[0]
        proposal = self.feature.propose(view, lua_table(self.h.lua,
            {"enabled": True, "policy": "con_medkit_large", "minRemaining": 1}))[0]
        baseline = self.feature.capture(proposal, self.before)[0]
        after = self.h.snapshot(revision=2, native={"fullSync": True,
            "serverNow": self.now + 2, "henchmanConsumableUseSequence": 8,
            "henchmanConsumableReadyAt": self.now + 3,
            "inventory": {}, "inventoryBound": {}, "crew": [{},
                {"name": "Ally", "rarity": 4, "healId": "injury-a", "injuredUntil": 0}]})
        self.assertEqual(self.feature.evaluate(proposal, self.before, after,
            lua_table(self.h.lua, {"ok": True, "sequence": 8, "readyAt": self.now + 3}), baseline), "confirmed")

    def test_fractional_native_clock_and_cooldown_keep_item_proof(self):
        self.before["native"]["serverNow"] = self.now + 0.25
        self.context["serverNow"] = self.now + 0.25
        self.before["native"]["henchmanConsumableReadyAt"] = self.now - 0.5
        self.before["native"]["crew"][2]["injuredUntil"] = self.now + 700.5
        proposal = self.plan()
        baseline, reason = self.feature.capture(proposal, self.before)
        self.assertIsNone(reason)
        after = self.h.snapshot(revision=2, native={"fullSync": True,
            "serverNow": self.now + 2.5,
            "henchmanConsumableUseSequence": 8,
            "henchmanConsumableReadyAt": self.now + 3.5,
            "inventoryBound": {"con_bandages": 1},
            "inventory": {"con_bandages": 1},
            "crew": [{"name": "Player"}, {"name": "Ally", "rarity": 4,
                "healId": "injury-a", "injuredUntil": self.now + 400.5}]})
        reply = lua_table(self.h.lua, {"ok": True,
            "sequence": 8, "readyAt": self.now + 3.5})
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            after, reply, baseline), "confirmed")


if __name__ == "__main__":
    unittest.main()
