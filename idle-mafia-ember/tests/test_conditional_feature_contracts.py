"""Real conditional planners/evidence; no Roblox transport or account writes."""
import copy
import unittest

from engine_harness import Harness, lua_table


KEY = "a" * 64


class ConditionalContracts(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.h.session["account"] = "123"

    def table(self, value):
        return lua_table(self.h.lua, value)

    def header(self, revision=1, session=None):
        return {**self.h.session, "revision": revision, "capturedAt": revision,
                **({"session": session} if session else {})}

    def family(self, revision=1):
        state_module = self.h.load("src/tabs/family/FamilyContributionState.luau")
        owner = state_module.new(self.table({"FAMILY": {
            "donateMin": 100, "contributeMax": 25,
            "baseCap":30,"capPerLevel":5,"maxCap":50,"capSlotMax":10,
            "staminaPerkCosts": [30, 60],
            "perkTracks": {"enforcers": {"kind": "stamina"}}}}),
            KEY, self.h.session["release"], self.h.lua.execute("""return {
                Current=function() return true end,
                Read=function(_,native)
                    if native.userId==123 then return {userId=123,name='123'} end
                end}"""))
        family = {"id": "fam-a", "level":1,"capSlots":0,"memberCap":30,"members": [{"userId": 123,
            "donated": 100, "donatedGold": 2, "contributed": 29}],
            "perks": {"enforcers": 0}, "perkProgress": {"enforcers": 29}}
        raw = self.table({**self.header(revision), "native": {"fullSync": True,
            "serverNow": 100 + revision, "userId":123, "family": {"id": "fam-a"},
            "cash": 1000, "pools": {"stamina": 50},
            "inventory": {"gold_bar": 5}, "inventoryBound": {}},
            "familyUsageProof": {**self.header(revision), "usage": {
                name: {"attempted": 0, "spent": 0}
                for name in ("familyCash", "familyGold", "familyStamina")}}})
        raw, reason = owner.Enrich(owner, raw)
        self.assertIsNone(reason)
        raw, reason = owner.Stage(owner, raw, self.table({"ok": True, "family": family}))
        self.assertIsNone(reason)
        return state_module, raw, family

    def family_attempt(self, lane="cash"):
        state, before, family = self.family()
        view, reason = state.read(before, before)
        self.assertIsNone(reason)
        settings = {"enabled": True, "amount": 100 if lane == "cash" else 1,
                    "reserve": 0, "runBudget": 200, "maxAttempts": 2,
                    "selectedPerk": "enforcers"}
        planner = self.h.load("src/tabs/family/FamilyContributions.luau")[lane]
        proposal, reason = planner.propose(view, self.table(settings), self.table({}))
        self.assertIsNone(reason)
        evidence = self.h.load("src/tabs/family/FamilyContributionEvidence.luau").new(state)
        baseline, reason = evidence.capture(proposal, before)
        self.assertIsNone(reason)
        return before, family, proposal, evidence, baseline

    def test_family_cash_gold_and_stamina_require_exact_personal_receipt_and_debit(self):
        for lane, ledger in (("cash", "donated"), ("gold", "donatedGold"),
                             ("stamina", "contributed")):
            with self.subTest(lane=lane):
                before, family, proposal, evidence, baseline = self.family_attempt(lane)
                _, after, _ = self.family(2)
                receipt = copy.deepcopy(family)
                amount = proposal.intent.amount
                receipt["members"][0][ledger] += amount
                if lane == "cash":
                    after.native.cash = 900
                elif lane == "gold":
                    after.native.inventory.gold_bar = 4
                else:
                    after.native.pools.stamina = 49
                    receipt["perks"]["enforcers"] = 1
                    receipt["perkProgress"]["enforcers"] = 0
                reply = self.table({"ok": True, "family": receipt})
                self.assertEqual(evidence.evaluate(proposal, before, after, reply, baseline), "confirmed")
                after.native.userId = 999
                self.assertEqual(evidence.evaluate(proposal, before, after, reply, baseline), "pending")
                after.native.userId = 123
                reply.family.members[1].userId = 124
                self.assertEqual(evidence.evaluate(proposal, before, after, reply, baseline), "pending")
                call, reason = self.h.load("src/tabs/family/FamilyCallPlan.luau").describe(proposal)
                self.assertIsNone(reason)
                self.assertEqual(call.remote, "FamilyAction")
                self.assertEqual(call.arity, 4)
                self.assertEqual(call.args[1], {"cash": "donate", "gold": "donategold", "stamina": "contribute"}[lane])

    def test_family_unknown_usage_mixed_gold_and_uncertain_exposure_block(self):
        state, raw, _ = self.family()
        planners = self.h.load("src/tabs/family/FamilyContributions.luau")
        view, _ = state.read(raw, raw)
        settings = self.table({"enabled": True, "amount": 100, "reserve": 900,
                               "runBudget": 200, "maxAttempts": 2})
        self.assertIsNone(planners.cash.propose(view, settings,
            self.table({"uncertainCash": 1}))[0])
        view.usage = None
        self.assertIsNone(planners.cash.propose(view, settings, self.table({}))[0])
        view, _ = state.read(raw, raw)
        view.boundGold = 1
        settings.amount, settings.reserve = 1, 0
        self.assertIsNone(planners.gold.propose(view, settings, self.table({}))[0])

    def event(self):
        definition = self.table({"MEDAL": "event_medal", "MAX_ITEM_COUNT": 99,
            "CURRENCIES":{"medal":{"item":"event_medal","paidField":"paidMedals"}},
            "ROWS": [{"key": "healing", "kind": "item", "item": "pills", "count": 2, "price": 10}]})
        attributes = self.table({"GlobalEventShop": True, "GlobalEventShopEnd": 1000,
                                 "MWPaidRandomRestricted": False, "serverNow": 101})
        self.h.lua.globals().shopAttributes = attributes
        source, reason = self.h.load("src/tabs/events/NativeEventShopSource.luau").new(
            definition, self.h.lua.eval("function() return shopAttributes end"), KEY,
            self.h.session["release"])
        self.assertIsNone(reason)
        return source, self.h.load("src/tabs/events/EventShopBuyer.luau").new(source), attributes

    def event_raw(self, source, revision=1, session=None, medals=40, pills=0):
        header = self.header(revision, session)
        self.h.lua.globals().shopAttributes.serverNow = 100 + revision
        raw = self.table({**header, "native": {"fullSync": True, "serverNow": 100 + revision,
            "inventory": {}, "inventoryBound": {"event_medal": medals, "pills": pills}},
            "eventShopUsageProof": {**header, "attempted": 0, "spent": 0}})
        raw, reason = source.Enrich(source, raw)
        self.assertIsNone(reason)
        return raw

    def event_attempt(self):
        source, buyer, attrs = self.event()
        before = self.event_raw(source)
        view, reason = buyer.read(before, before)
        self.assertIsNone(reason)
        proposal, reason = buyer.propose(view, self.table({"enabled": True,
            "offerKey": "healing", "medalReserve": 30, "maxSpend": 10, "maxAttempts": 1}))
        self.assertIsNone(reason)
        baseline, reason = buyer.capture(proposal, before)
        self.assertIsNone(reason)
        return source, buyer, attrs, before, proposal, baseline

    def test_event_purchase_requires_exact_earned_medal_debit_and_acquired_custody(self):
        source, buyer, _, before, proposal, baseline = self.event_attempt()
        after = self.event_raw(source, 2, medals=30, pills=2)
        self.assertEqual(buyer.evaluate(proposal, before, after, self.table({"ok": True}), baseline), "confirmed")
        after.native.inventoryBound.pills = 1
        self.assertEqual(buyer.evaluate(proposal, before, after, self.table({"ok": True}), baseline), "pending")
        after.native.inventoryBound.pills = 2
        after.native.inventoryBound.unrelated = 1
        self.assertEqual(buyer.evaluate(proposal, before, after, self.table({"ok": True}), baseline), "pending")

    def test_event_changed_source_or_paid_medals_cannot_authorize_purchase(self):
        source, buyer, attrs, before, proposal, _ = self.event_attempt()
        self.assertTrue(source.CanDispatch(source, proposal))
        before.native.paidMedals = 1
        view, _ = buyer.read(before, before)
        self.assertIsNone(buyer.propose(view, self.table({"enabled": True,
            "offerKey": "healing", "medalReserve": 0, "maxSpend": 10, "maxAttempts": 1}))[0])
        attrs.GlobalEventShop = False
        self.assertFalse(source.CanDispatch(source, proposal))
        self.assertIsNone(buyer.read(before, before)[0])

    def test_event_restart_recovers_saved_receipt_but_not_foreign_identity(self):
        source, buyer, _, before, proposal, baseline = self.event_attempt()
        saved = self.table({"proposal": proposal, "before": before,
                            "baseline": baseline, "reply": {"ok": True}})
        after = self.event_raw(source, 1, session="run-b", medals=30, pills=2)
        after.native.serverNow = 102
        self.assertEqual(buyer.recoverSaved(saved, after), "confirmed")
        after.account = "124"
        self.assertIsNone(buyer.recoverSaved(saved, after))

    def residency_raw(self, revision=1, session=None):
        header = self.header(revision, session)
        return self.table({**header, "native": {"fullSync": True, "level": 20,
            "serverNow": 100 + revision, "derived": {"territoryBonuses": {}}},
            "residencyUsageProof": {**header, "attempted": 0},
            "residencyView": {"header": header, "districtId": "d1", "kind": "landlord",
                "status": "none", "admission": "open", "owned": True,
                "rent": 3, "share": 0.25, "count": 1, "capacity": 4, "minLevel": 1}})

    def residency_attempt(self):
        module = self.h.load("src/tabs/territory/Residency.luau")
        before = self.residency_raw()
        view, reason = module.read(before, before)
        self.assertIsNone(reason)
        proposal, reason = module.propose(view, self.table({"enabled": True, "districtId": "d1",
            "selectedKind": "landlord", "maxRentPct": 3, "minSharePct": 25,
            "allowReplace": False, "allowRequests": False, "maxAttempts": 1}))
        self.assertIsNone(reason)
        baseline, reason = module.capture(proposal, before)
        self.assertIsNone(reason)
        after = self.residency_raw(2)
        after.native.derived.residency = self.table({"d": "d1", "rent": 3, "active": True,
            "kind": "landlord", "share": 0.25})
        after.residencyView.status = "resident"
        return module, before, proposal, baseline, after

    def test_residency_terminal_lease_confirmation_and_nonterminal_reply(self):
        module, before, proposal, baseline, after = self.residency_attempt()
        self.assertEqual(module.evaluate(proposal, before, after, self.table({"ok": True}), baseline), "confirmed")
        self.assertEqual(module.evaluate(proposal, before, after,
            self.table({"ok": True, "pending": True}), baseline), "pending")

    def test_residency_replacement_requires_permission_and_restart_requires_new_server_time(self):
        module, before, proposal, baseline, after = self.residency_attempt()
        saved = self.table({"proposal": proposal, "before": before,
                            "baseline": baseline, "reply": {"ok": True}})
        after.session, after.revision = "run-b", 0
        after.residencyView = None
        self.assertEqual(module.recoverSaved(saved, after), "confirmed")
        after.native.serverNow = 101
        self.assertIsNone(module.recoverSaved(saved, after))
        before.native.derived.residency = self.table({"d": "d0", "rent": 1, "active": True})
        view, _ = module.read(before, before)
        settings = self.table({"enabled": True, "districtId": "d1", "selectedKind": "landlord",
            "maxRentPct": 3, "minSharePct": 25, "allowReplace": False,
            "allowRequests": False, "maxAttempts": 1})
        self.assertIsNone(module.propose(view, settings)[0])

    def station_raw(self, owner, revision=1):
        header = self.header(revision)
        raw = self.table({**header, "native": {"fullSync": True, "serverNow": 100 + revision,
            "family": {"id": "fam-a"}, "crew": [{},
                {"name": "A", "rarity": 1, "healId": "crew-a"},
                {"name": "B", "rarity": 1, "healId": "crew-b"}]},
            "territoryMap": {"header": header, "cityId": "city-a",
                "districts": [{"id": "d1", "mine": True}]},
            "territoryDistrict": {"header": header, "familyId": "fam-a",
                "district": {"id": "d1", "mine": True, "holderId": "fam-a",
                    "garrisonCount": 0, "revision": revision}},
            "stationReservationProof": {**header, "members": {}, "attempted": 0,
                "pendingStation": {}, "stationUnknown": False}})
        raw, reason = owner.Enrich(owner, raw)
        self.assertIsNone(reason)
        return raw

    def station_attempt(self):
        module = self.h.load("src/tabs/territory/Stationing.luau")
        owner = module.new(self.table({"TERRITORY": {"garrisonCap": 200}}),
            self.table({"DISTRICTS_BY_ID": {"d1": {"city": "city-a", "tier": 1}}}),
            KEY, self.h.session["release"])
        before = self.station_raw(owner)
        view, reason = module.read(before, before)
        self.assertIsNone(reason)
        proposal, reason = module.propose(view, self.table({"enabled": True,
            "districtId": "d1", "memberSlot": 2, "minHome": 1,
            "maxStationed": 1, "maxAttempts": 1}))
        self.assertIsNone(reason)
        baseline, reason = module.capture(proposal, before)
        self.assertIsNone(reason)
        return module, owner, before, proposal, baseline

    def test_stationing_preserves_home_member_and_confirms_only_selected_identity_duty(self):
        module, owner, before, proposal, baseline = self.station_attempt()
        self.assertEqual(proposal.intent.homeSlots, "3")
        self.assertEqual(proposal.intent.homeKey3, "id:crew-b")
        after = self.station_raw(owner, 2)
        after.native.crew[2].duty = "d1"
        self.assertEqual(module.evaluate(proposal, before, after, self.table({"ok": True}), baseline), "confirmed")
        after.native.crew[2].healId = "different-copy"
        self.assertEqual(module.evaluate(proposal, before, after, self.table({"ok": True}), baseline), "pending")
        after.native.crew[2].healId = "crew-a"
        after.native.crew[2].duty = "d2"
        self.assertEqual(module.evaluate(proposal, before, after, self.table({"ok": True}), baseline), "pending")
        call, reason = self.h.load("src/tabs/territory/TerritoryCallPlan.luau").describe(proposal)
        self.assertIsNone(reason)
        self.assertEqual((call.remote, call.arity, call.args[1], call.args[2], call.args[3]),
                         ("TerritoryAction", 4, "station", "d1", 2))

    def test_stationing_unknown_deployments_and_home_reservation_block(self):
        module, _, before, _, _ = self.station_attempt()
        view, _ = module.read(before, before)
        settings = self.table({"enabled": True, "districtId": "d1", "memberSlot": 2,
            "minHome": 1, "maxStationed": 1, "maxAttempts": 1})
        view.reserved["id:crew-b"] = True
        self.assertIsNone(module.propose(view, settings)[0])
        view.reserved["id:crew-b"] = None
        view.stationUnknown = True
        self.assertIsNone(module.propose(view, settings)[0])
        view.stationUnknown = False
        view.pendingStation["id:crew-z"] = True
        self.assertIsNone(module.propose(view, settings)[0])
        settings.mode = "Recall"
        self.assertIn("Recall", module.propose(view, settings)[1])

    def checkpoint(self, store=None):
        if store is None:
            store = self.h.lua.execute("""return {strictRecovery = true, data = {},
                Read = function(self, key) return self.data[key] end,
                Write = function(self, key, value) self.data[key] = value; return true end}
            """)
        checkpoint = self.h.load("src/storage/Checkpoint.luau").new(store,
            self.h.load("src/tabs/family/FamilyContributionUsage.luau"),
            self.h.load("src/engine/ResourceReservations.luau"),
            self.h.load("src/storage/PendingAction.luau"),
            self.h.load("src/tabs/events/EventShopUsage.luau"))
        _, reason = checkpoint.Load(checkpoint, self.h.session["account"],
            self.h.session["place"], self.h.session["release"])
        self.assertIsNone(reason)
        return checkpoint, store

    def test_family_and_event_allowances_survive_reply_resolution_and_restart(self):
        for lane in ("family", "event"):
            with self.subTest(lane=lane):
                if lane == "family":
                    before, _, proposal, _, baseline = self.family_attempt()
                else:
                    _, _, _, before, proposal, baseline = self.event_attempt()
                checkpoint, store = self.checkpoint()
                self.assertTrue(checkpoint.Save(checkpoint, proposal, before, baseline)[0])
                self.assertTrue(checkpoint.RecordReply(checkpoint, proposal.actionKey,
                    self.table({"ok": False}))[0])
                self.assertTrue(checkpoint.Resolve(checkpoint, proposal.actionKey, "rejected")[0])
                restarted, _ = self.checkpoint(store)
                if lane == "family":
                    proof, _ = restarted.FamilyContributionUsage(restarted, before)
                    actual = proof.usage.familyCash
                    self.assertEqual((actual.attempted, actual.spent), (1, 100))
                else:
                    proof, _ = restarted.EventShopUsage(restarted, before)
                    self.assertEqual((proof.attempted, proof.spent), (1, 10))
                self.assertEqual(len(restarted.Records(restarted)), 0)
                self.assertFalse(restarted.Save(restarted, proposal, before, baseline)[0])

    def test_saved_server_reply_cannot_be_reclassified_unsent_to_refund_allowance(self):
        for lane in ("family", "event"):
            with self.subTest(lane=lane):
                if lane == "family":
                    before, _, proposal, _, baseline = self.family_attempt()
                else:
                    _, _, _, before, proposal, baseline = self.event_attempt()
                checkpoint, _ = self.checkpoint()
                self.assertTrue(checkpoint.Save(checkpoint, proposal, before, baseline)[0])
                self.assertTrue(checkpoint.RecordReply(checkpoint, proposal.actionKey,
                    self.table({"ok": True, "pending": True}))[0])
                self.assertFalse(checkpoint.Resolve(checkpoint, proposal.actionKey, "schedule_failed")[0])
                self.assertEqual(len(checkpoint.Records(checkpoint)), 1)
                if lane == "family":
                    proof, _ = checkpoint.FamilyContributionUsage(checkpoint, before)
                    self.assertEqual((proof.usage.familyCash.attempted, proof.usage.familyCash.spent), (1, 100))
                else:
                    proof, _ = checkpoint.EventShopUsage(checkpoint, before)
                    self.assertEqual((proof.attempted, proof.spent), (1, 10))

    def test_known_unsent_family_and_event_attempts_can_refund_exact_allowance(self):
        for lane in ("family", "event"):
            with self.subTest(lane=lane):
                if lane == "family":
                    before, _, proposal, _, baseline = self.family_attempt()
                else:
                    _, _, _, before, proposal, baseline = self.event_attempt()
                checkpoint, _ = self.checkpoint()
                self.assertTrue(checkpoint.Save(checkpoint, proposal, before, baseline)[0])
                self.assertTrue(checkpoint.Resolve(checkpoint, proposal.actionKey, "schedule_failed")[0])
                self.assertEqual(len(checkpoint.Records(checkpoint)), 0)
                if lane == "family":
                    proof, _ = checkpoint.FamilyContributionUsage(checkpoint, before)
                    self.assertEqual((proof.usage.familyCash.attempted, proof.usage.familyCash.spent), (0, 0))
                else:
                    proof, _ = checkpoint.EventShopUsage(checkpoint, before)
                    self.assertEqual((proof.attempted, proof.spent), (0, 0))

    def test_station_and_residency_attempts_survive_resolved_record_restart(self):
        for lane in ("station", "residency"):
            with self.subTest(lane=lane):
                if lane == "station":
                    _, _, before, proposal, baseline = self.station_attempt()
                else:
                    _, before, proposal, baseline, _ = self.residency_attempt()
                checkpoint, store = self.checkpoint()
                self.assertTrue(checkpoint.Save(checkpoint, proposal, before, baseline)[0])
                self.assertTrue(checkpoint.RecordReply(checkpoint, proposal.actionKey,
                    self.table({"ok": False}))[0])
                self.assertTrue(checkpoint.Resolve(checkpoint, proposal.actionKey, "rejected")[0])
                restarted, _ = self.checkpoint(store)
                getter = restarted.StationUsage if lane == "station" else restarted.ResidencyUsage
                self.assertEqual(getter(restarted, before), 1)
                self.assertFalse(restarted.Save(restarted, proposal, before, baseline)[0])

    def test_family_durable_usage_rejects_impossible_attempt_spend_history(self):
        usage = self.h.load("src/tabs/family/FamilyContributionUsage.luau")
        for attempted, spent in ((1, 0), (2, 1), (0, 100)):
            with self.subTest(attempted=attempted, spent=spent):
                raw = usage.copy(None)
                raw.lanes.familyCash.attempted = attempted
                raw.lanes.familyCash.spent = spent
                self.assertIsNone(usage.copy(raw))
                charge = self.table({"feature": "familyCash", "amount": 100,
                    "attemptedBefore": attempted, "spentBefore": spent})
                self.assertIsNone(usage.copyCharge(charge, "familyCash", self.table({"cash": 100})))


if __name__ == "__main__":
    unittest.main()
