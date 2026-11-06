"""Pending and durable ownership protects exact members, origins and funding."""
import unittest

from engine_harness import Harness, lua_table


class ResourceReservationsTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.module = self.h.load("src/engine/ResourceReservations.luau")
        self.h.lua.globals().heldRecords = self.h.lua.table()
        self.h.lua.globals().providerClaims = None
        self.providers = self.h.lua.execute("""return {{id='durable',read=function() return providerClaims end}}""")
        self.manager = self.module.new(lua_table(self.h.lua, self.h.session),
            self.h.lua.eval("function() return heldRecords end"), self.providers)

    def raw(self):
        return self.h.snapshot(native={"fullSync": True, "serverNow": 1000,
            "cash": 1000, "pools": {"energy": 50, "stamina": 20},
            "inventory": {"w_a": 3, "con_a": 2}, "inventoryBound": {"w_a": 1},
            "crew": [{"name": "YOU"}, {"name": "A", "healId": "h1"}, {"name": "B", "healId": "h2"}]})

    def proposal(self, kind, feature="crewTrain", resources=None, **intent):
        proposal = self.h.proposal(feature, feature + ":test")
        proposal.resources = lua_table(self.h.lua, resources or {})
        proposal.intent = lua_table(self.h.lua, {"kind": kind, **intent})
        return proposal

    def hold(self, claims, feature="marketSell", action_key=None):
        self.h.lua.globals().providerClaims = lua_table(self.h.lua, {
            "account": "user-a", "place": self.h.session["place"], "release": "release-a",
            "feature": feature, "actionKey": action_key, "claims": claims})

    def claims(self, **changes):
        value = {"members": {}, "items": {}, "funds": {}, "allCrew": False}
        value.update(changes)
        return value

    def test_market_listing_reserves_only_exact_loose_copies(self):
        raw = self.raw()
        proposal = self.proposal("marketList", "marketSell", {"w_a": 3}, itemId="w_a", quantity=3)
        claims, reason = self.module.ForProposal(proposal, raw)
        self.assertIsNone(reason)
        self.assertEqual(claims["items"]["L:w_a"], 3)
        self.assertIsNone(claims.funds.w_a)
        self.hold(self.claims(items={"B:w_a": 1}))
        self.assertIsNotNone(self.manager.Check(self.manager, proposal, raw)[0])
        self.hold(self.claims(items={"L:w_a": 1}))
        self.assertIsNone(self.manager.Check(self.manager, proposal, raw)[0])
        proposal.resources.w_a = 2
        self.assertIsNone(self.module.ForProposal(proposal, raw)[0])
        proposal.intent.quantity, proposal.resources.w_a = 4, 4
        self.assertIsNone(self.module.ForProposal(proposal, raw)[0])


    def test_same_member_blocks_training_stationing_and_gear_but_other_member_can_run(self):
        self.hold(self.claims(members={"slot:2": True, "id:h1": True}), "crewRoll")
        for kind, feature in (("crewTrain", "crewTrain"), ("territoryStation", "station"), ("crewGear", "crewGear")):
            proposal = self.proposal(kind, feature, slot=2, memberSlot=2)
            self.assertIsNone(self.manager.Check(self.manager, proposal, self.raw())[0])
        self.assertIsNone(self.manager.Check(self.manager,self.proposal("crewTrain",slot=3),self.raw())[0])
        self.assertIsNotNone(self.manager.Check(self.manager,self.proposal("crewHeal","crewHeal",slot=3),self.raw())[0])

    def test_member_identity_still_blocks_after_manual_roster_reordering(self):
        self.hold(self.claims(members={"slot:2": True, "id:h1": True}), "crewRoll")
        raw = self.raw()
        raw.native.crew[2], raw.native.crew[3] = raw.native.crew[3], raw.native.crew[2]
        self.assertIsNone(self.manager.Check(self.manager, self.proposal("crewTrain", slot=3), raw)[0])

    def test_whole_roster_operations_conflict_with_any_member_and_missing_id_is_conservative(self):
        self.hold(self.claims(members={"id:h1": True}), "crewRoll")
        self.assertIsNone(self.manager.Check(self.manager, self.proposal("crewSort", "crewSort"), self.raw())[0])
        raw = self.raw()
        raw.native.crew[3].healId = None
        self.assertIsNone(self.manager.Check(self.manager, self.proposal("crewTrain", slot=3), raw)[0])

    def test_item_origins_and_spare_copies_are_counted_separately(self):
        self.hold(self.claims(items={"L:w_a": 2}))
        proposal = self.proposal("collectionDonate", "collectionDonate", {"w_a": 2}, itemId="w_a", amount=2)
        self.assertIsNone(self.manager.Check(self.manager, proposal, self.raw())[0])
        proposal.intent.amount, proposal.resources.w_a = 1, 1
        self.assertIsNotNone(self.manager.Check(self.manager, proposal, self.raw())[0])
        bound = self.proposal("restoratives", "restoratives", {"w_a": 1}, itemId="w_a", fromBound=True)
        self.assertIsNotNone(self.manager.Check(self.manager, bound, self.raw())[0])

    def test_funded_cash_is_held_but_unrelated_energy_is_not_blocked(self):
        self.hold(self.claims(funds={"cash": 750}), "crewRoll")
        self.assertIsNone(self.manager.Check(self.manager,
            self.proposal("bankDeposit", "bank", {"cash": 300}), self.raw())[0])
        self.assertIsNotNone(self.manager.Check(self.manager,
            self.proposal("job", "jobs", {"energy": 1}), self.raw())[0])

    def test_legacy_total_item_exposure_blocks_origin_specific_use_and_auto_equip(self):
        self.hold(self.claims(funds={"w_a": 3}))
        self.assertIsNone(self.manager.Check(self.manager,
            self.proposal("collectionDonate", "collectionDonate", {"w_a": 1}, itemId="w_a", amount=1), self.raw())[0])
        self.assertIsNone(self.manager.Check(self.manager, self.proposal("crewAutoEquip", "crew"), self.raw())[0])

    def test_same_saved_stage_is_not_counted_twice_by_checkpoint_and_store(self):
        claims = self.claims(funds={"cash": 700})
        self.h.lua.globals().heldRecords = lua_table(self.h.lua, [{
            "account": "user-a", "place": self.h.session["place"], "release": "release-a",
            "feature": "crewRoll", "actionKey": "same-stage", "resources": {"cash": 700}, "custody": claims}])
        self.hold(claims, "crewRoll", "same-stage")
        held, reason = self.manager.Held(self.manager, self.raw())
        self.assertIsNone(reason)
        self.assertEqual(held.funds.cash, 700)
        self.assertIsNotNone(self.manager.Check(self.manager,
            self.proposal("bankDeposit", "bank", {"cash": 300}), self.raw())[0])

    def test_sparse_pending_records_cannot_hide_custody(self):
        self.h.lua.globals().heldRecords = self.h.lua.execute("return {[2]={}}")
        self.assertIsNone(self.manager.Check(self.manager, self.proposal("job", "jobs"), self.raw())[0])

    def test_own_exact_continuation_can_use_its_reservation_but_not_another_feature(self):
        self.hold(self.claims(funds={"cash": 1000}), "crewRoll", "crewRoll:test")
        own = self.proposal("crewReplacementHire", "crewRoll", {"cash": 1000}, slot=2, cost=1000, cashReserve=0)
        self.assertIsNotNone(self.manager.Check(self.manager, own, self.raw())[0])
        self.assertIsNone(self.manager.Check(self.manager,
            self.proposal("bankDeposit", "bank", {"cash": 1}), self.raw())[0])

    def test_native_training_and_legacy_unknown_crew_requests_keep_members_reserved(self):
        raw = self.raw()
        raw.native.crew[2].training = lua_table(self.h.lua, {"endAt": 2000})
        self.assertIsNone(self.manager.Check(self.manager, self.proposal("crewGear", "crewGear", slot=2), raw)[0])
        self.h.lua.globals().heldRecords = lua_table(self.h.lua, [{
            "account": "user-a", "place": self.h.session["place"], "release": "release-a",
            "feature": "crewHeal", "actionKey": "old", "resources": {"stamina": 1}}])
        self.assertIsNone(self.manager.Check(self.manager, self.proposal("crewTrain", slot=3), self.raw())[0])

    def test_bad_claims_or_wrong_scope_fail_closed_and_copies_do_not_alias(self):
        self.hold(self.claims(items={"L:w_a": -1}))
        self.assertIsNone(self.manager.Check(self.manager, self.proposal("job", "jobs"), self.raw())[0])
        self.hold(self.claims())
        self.h.lua.globals().providerClaims.account = "other"
        self.assertIsNone(self.manager.Check(self.manager, self.proposal("job", "jobs"), self.raw())[0])
        self.h.lua.globals().providerClaims = None
        claims, reason = self.manager.Check(self.manager, self.proposal("crewTrain", slot=2), self.raw())
        self.assertIsNone(reason)
        copied = self.module.CopyClaims(claims)
        claims.members["id:h1"] = None
        self.assertTrue(copied.members["id:h1"])


    def test_funded_replacement_stages_keep_cash_floor_after_other_owned_funding(self):
        for stage in ("crewReplacementDismiss", "crewReplacementHire"):
            with self.subTest(stage=stage):
                proposal = self.proposal(stage, "crewRoll", slot=2, cost=100, cashReserve=100)
                raw = self.raw()
                if stage == "crewReplacementHire": raw.native.crew[2] = self.h.lua.table()
                self.hold(self.claims(funds={"cash": 801}), "operations")
                self.assertIsNone(self.manager.Check(self.manager, proposal, raw)[0])
                self.hold(self.claims(funds={"cash": 800}), "operations")
                self.assertIsNotNone(self.manager.Check(self.manager, proposal, raw)[0])


    def test_native_rental_uses_combined_gold_without_consuming_either_origin_hold(self):
        raw = self.raw()
        raw.native.inventory.gold_bar, raw.native.inventoryBound.gold_bar = 5, 2
        proposal = self.proposal("marketRent", "marketRent", {"gold_bar":1}, cost=1, goldReserve=5)
        claims, reason = self.module.ForProposal(proposal, raw)
        self.assertIsNone(reason)
        self.assertEqual(claims.funds.gold_bar, 1)
        self.assertIsNone(claims['items']['L:gold_bar'])
        self.hold(self.claims(items={"B:gold_bar":2}))
        self.assertIsNone(self.manager.Check(self.manager,proposal,raw)[0])
        self.hold(self.claims(items={"B:gold_bar":1}))
        self.assertIsNotNone(self.manager.Check(self.manager,proposal,raw)[0])
        proposal.intent.goldReserve=6
        self.assertIsNone(self.manager.Check(self.manager,proposal,raw)[0])
        proposal.intent.goldReserve=0
        self.hold(self.claims(items={"L:gold_bar":5}))
        self.assertIsNone(self.manager.Check(self.manager,proposal,raw)[0])
        self.hold(self.claims(funds={"gold_bar":6}))
        self.assertIsNotNone(self.manager.Check(self.manager,proposal,raw)[0])
        proposal.intent.goldReserve=1
        self.assertIsNone(self.manager.Check(self.manager,proposal,raw)[0])


if __name__ == "__main__":
    unittest.main()
