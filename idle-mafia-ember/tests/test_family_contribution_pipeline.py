"""Source-bound Family stages, personal receipt proof and exact native signatures."""
import unittest
import test_automation_runtime as runtime_fixture

from engine_harness import Harness, lua_table


class FamilyContributionPipelineTests(unittest.TestCase):
    def setUp(self):
        base = runtime_fixture.AutomationRuntimeTests()
        base.setUp()
        self.h = base.h
        self.runtime_modules, self.storage = base.runtime.modules, base.storage
        self.runtime_modules.FamilyContributionUsage = self.h.load("src/tabs/family/FamilyContributionUsage.luau")
        base.runtime.Close(base.runtime)
        self.h.session["account"] = "42"
        self.source = self.h.load("src/tabs/family/FamilyContributionState.luau")
        self.config = lua_table(self.h.lua, {"FAMILY": {"donateMin": 100,
            "contributeMax": 25, "baseCap":30,"capPerLevel":5,"maxCap":50,"capSlotMax":10,
            "staminaPerkCosts": [30, 60],
            "perkTracks": {"enforcers": {"kind": "stamina"},
                           "jobCut": {"kind": "cash"}}}})
        self.h.lua.globals().familyFixtureAccount = self.h.session["account"]
        self.player_source = self.h.lua.execute('''return {Current=function() return true end,
            Read=function(_,native) if native.userId~=42 then return nil end
                return {userId=42,name=familyFixtureAccount} end}''')
        self.state = self.source.new(self.config, "a" * 64, "release-a", self.player_source)
        self.query = self.h.load("src/tabs/family/FamilyQuery.luau").new(self.state)
        self.planners = self.h.load("src/tabs/family/FamilyContributions.luau")
        self.evidence = self.h.load("src/tabs/family/FamilyContributionEvidence.luau").new(self.source)
        self.calls = self.h.load("src/tabs/family/FamilyCallPlan.luau")

    def family(self, resource=None, amount=0, other_donation=0):
        return {"id": "fam-a", "level": 2, "vault": 999999 + other_donation,
            "perks": {"enforcers": 0},
            "perkProgress": {"enforcers": 20 + (amount if resource == "stamina" else 0)},
            "members": [{"userId": 42, "donated": 500 + (amount if resource == "cash" else 0),
                "donatedGold": 2 + (amount if resource == "gold_bar" else 0),
                "contributed": 10 + (amount if resource == "stamina" else 0)},
                {"userId": 43, "donated": other_donation}]}

    def raw(self, revision=1, resource=None, amount=0, **changes):
        self.h.lua.globals().familyFixtureAccount = self.h.session["account"]
        native = {"fullSync": True, "userId": 42, "serverNow": 1000 + revision,
            "family": {"id": "fam-a"},
            "cash": 1000.25 - (amount if resource == "cash" else 0),
            "pools": {"stamina": 50 - (amount if resource == "stamina" else 0)},
            "inventory": {"gold_bar": 10 - (amount if resource == "gold_bar" else 0)},
            "inventoryBound": {"gold_bar": 0}}
        native.update(changes)
        return self.state.Enrich(self.state,self.h.snapshot(revision=revision, native=native))[0]

    def staged(self):
        raw = self.raw()
        request, reason = self.query.Prepare(self.query, raw)
        self.assertIsNone(reason)
        staged, reason = self.query.Stage(self.query, raw, request,
            lua_table(self.h.lua, {"ok": True, "family": self.family()}))
        self.assertIsNone(reason)
        staged = self.state.Enrich(self.state, staged)[0]
        staged.familyUsageProof = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0, "usage": {
                "familyCash": {"attempted": 0, "spent": 0},
                "familyGold": {"attempted": 0, "spent": 0},
                "familyStamina": {"attempted": 0, "spent": 0}}})
        return staged

    def proposed(self, kind):
        before = self.staged()
        view, reason = self.source.read(before, before)
        self.assertIsNone(reason)
        amount = 100 if kind == "cash" else 5 if kind == "stamina" else 1
        settings = lua_table(self.h.lua, {"enabled": True, "amount": amount,
            "reserve": 0, "runBudget": 200, "maxAttempts": 1,
            "selectedPerk": "enforcers"})
        proposal, reason = self.planners[kind].propose(view, settings, lua_table(self.h.lua, {}))
        self.assertIsNone(reason)
        return before, proposal, amount

    def test_exact_native_calls_and_personal_receipts_for_three_resources(self):
        for kind, resource, command in (("cash", "cash", "donate"),
                ("gold", "gold_bar", "donategold"), ("stamina", "stamina", "contribute")):
            with self.subTest(kind=kind):
                before, proposal, amount = self.proposed(kind)
                call, reason = self.calls.describe(proposal)
                self.assertIsNone(reason)
                self.assertEqual((call.remote, call.arity, call.args[1]),
                                 ("FamilyAction", 4, command))
                baseline, reason = self.evidence.capture(proposal, before)
                self.assertIsNone(reason)
                reply = lua_table(self.h.lua, {"ok": True,
                    "family": self.family(resource, amount, other_donation=5000)})
                after = self.raw(2, resource, amount)
                self.assertEqual(self.evidence.evaluate(proposal, before, after, reply, baseline),
                                 "confirmed")
                after.native.family.id = "other"
                self.assertEqual(self.evidence.evaluate(proposal, before, after, reply, baseline),
                                 "pending")

    def test_large_member_roster_remains_bounded_and_requires_unique_own_actor(self):
        family=self.family();family['members'].extend({'userId':actor} for actor in range(44,100))
        self.assertIsNotNone(self.source.parseFamily(lua_table(self.h.lua,family),42))
        family['members'].append({'userId':42})
        self.assertIsNone(self.source.parseFamily(lua_table(self.h.lua,family),42))
        family['members']=[{'userId':actor}for actor in range(1,258)]
        self.assertIsNone(self.source.parseFamily(lua_table(self.h.lua,family),42))

    def test_native_actor_and_account_binding_remain_required_at_send_and_receipt(self):
        self.h.session["account"]="PlayerName"
        before, proposal, amount=self.proposed("cash")
        baseline=self.evidence.capture(proposal,before)[0]
        proposal.intent.actorAccount="OtherName"
        self.assertIsNone(self.evidence.capture(proposal,before)[0])
        proposal.intent.actorAccount="PlayerName"
        for actor in (None,43,False,"42"):
            after=self.raw(2,"cash",amount,userId=actor)
            reply=lua_table(self.h.lua,{"ok":True,"family":self.family("cash",amount)})
            self.assertEqual(self.evidence.evaluate(proposal,before,after,reply,baseline),"pending")

    def test_shared_vault_delta_or_reply_alone_is_not_our_contribution(self):
        before, proposal, amount = self.proposed("cash")
        baseline = self.evidence.capture(proposal, before)[0]
        for after, receipt in ((self.raw(2), self.family("cash", amount)),
                (self.raw(2, "cash", amount), self.family(other_donation=amount)),
                (self.raw(2, "cash", 99), self.family("cash", amount))):
            self.assertEqual(self.evidence.evaluate(proposal, before, after,
                lua_table(self.h.lua, {"ok": True, "family": receipt}), baseline), "pending")
        for reply in ({"ok": True, "pending": True}, {"ok": True, "code": "rate_limited"}):
            reply["family"] = self.family("cash", amount)
            self.assertEqual(self.evidence.evaluate(proposal, before,
                self.raw(2, "cash", amount), lua_table(self.h.lua, reply), baseline), "pending")

    def test_query_generation_and_snapshot_binding(self):
        raw = self.raw()
        old = self.query.Prepare(self.query, raw)[0]
        current = self.query.Prepare(self.query, raw)[0]
        reply = lua_table(self.h.lua, {"ok": True, "family": self.family()})
        self.assertIsNone(self.query.Stage(self.query, raw, old, reply)[0])
        self.assertIsNone(self.query.Stage(self.query, self.raw(2), current, reply)[0])
        self.assertIsNotNone(self.query.Stage(self.query, raw, current, reply)[0])

    def test_missing_usage_and_malformed_personal_custody_fail_closed(self):
        before = self.staged()
        before.familyUsageProof.revision = 0
        view = self.source.read(before, before)[0]
        self.assertIsNone(view.usage)
        before.native.inventoryBound.gold_bar = False
        self.assertIsNone(self.source.read(before, before)[0])
        family = self.family()
        family["members"].append({"userId": 42})
        self.assertIsNone(self.source.parseFamily(lua_table(self.h.lua, family), 42))

    def tab(self):
        return self.h.load("src/tabs/family/Module.luau").new(lua_table(self.h.lua, {
            "FamilyQuery": self.h.load("src/tabs/family/FamilyQuery.luau"),
            "FamilyState": self.h.load("src/game/FamilyState.luau"),
            "FamilyBlocked": self.h.load("src/features/FamilyBlocked.luau"),
            "FamilyContributionState": self.source, "FamilyContributions": self.planners,
            "FamilyContributionEvidence": self.h.load("src/tabs/family/FamilyContributionEvidence.luau"),
            "config": self.config, "fingerprint": "a" * 64, "release": "release-a",
            "playerInfoSource": self.player_source}))

    def test_app_settings_broker_and_native_adapter_confirm_one_cash_donation(self):
        tab = self.tab()
        executor = self.h.lua.execute("""return { calls = {},
            Schedule = function(self, callback) callback(); return true end,
            Invoke = function(self, remote, method, ...)
                self.calls[#self.calls+1] = {remote=remote, method=method, args=table.pack(...)}
                return self.reply
            end }""")
        executor.reply = lua_table(self.h.lua, {"ok": True, "family": self.family("cash", 100)})
        native = self.h.load("src/transport/NativeCallPlan.luau")
        plan = native.withFamily(native, self.calls)
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(plan, executor)
        runtime = self.h.load("src/engine/AutomationRuntime.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "transport": adapter, "storage": self.storage,
            "identity": self.h.session, "modules": self.runtime_modules,
            "features": tab.Descriptors(tab), "tabInstances":[tab],
            "snapshotAssembler": self.h.load("src/tabs/TabSnapshotAssembler.luau").new(lua_table(self.h.lua,[tab])),
            "featurePages": {"familyCash":"family","familyStamina":"family","familyGold":"family"}}))
        ember = self.h.load("tests/ember_double.lua")()
        app = self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": ember, "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "FamilyTab": self.h.load("src/tabs/family/Module.luau"),
            "automationRuntimeInstance": runtime}))
        for key, value in (("familyCash.enabled", True),
                ("familyCash.custom.runBudget", 100), ("familyCash.custom.maxAttempts", 1)):
            self.assertTrue(app.Set(app, key, value)[0])
        self.assertTrue(app.Resume(app)[0])
        before=self.staged();before.familyContributionCatalog=None
        self.assertTrue(app.Step(app, before)[0])
        self.assertEqual(len(executor.calls), 1)
        self.assertEqual(executor.calls[1].args.n, 4)
        self.assertEqual(executor.calls[1].args[1], "donate")
        self.assertEqual(executor.calls[1].args[2], 100)
        self.h.at(1)
        after=self.raw(2,"cash",100);after.familyContributionCatalog=None
        self.assertTrue(app.Step(app,after)[0])
        self.assertEqual(runtime.Status(runtime).outcomes.familyCash, "confirmed")
        self.assertEqual(len(executor.calls), 1)
        self.assertFalse(app.model["values"]["familyGold.enabled"])
        app.Destroy(app)

    def test_send_time_caps_resources_and_perk_identity_cannot_drift(self):
        before, proposal, _ = self.proposed("cash")
        proposal.resources.cash = 0
        self.assertIsNone(self.evidence.capture(proposal, before)[0])
        proposal.resources.cash = 100
        proposal.intent.reserve = 950
        self.assertIsNone(self.evidence.capture(proposal, before)[0])
        before, proposal, _ = self.proposed("stamina")
        baseline = self.evidence.capture(proposal, before)[0]
        proposal.intent.perkId = "guardians"
        self.assertEqual(self.evidence.evaluate(proposal, before, self.raw(2, "stamina", 5),
            lua_table(self.h.lua, {"ok": True, "family": self.family("stamina", 5)}), baseline), "pending")

    def test_missing_native_zero_entries_and_exact_level_rollover(self):
        raw = self.raw()
        family = self.family()
        family["perks"] = {}
        family["perkProgress"] = {}
        request = self.query.Prepare(self.query, raw)[0]
        staged = self.query.Stage(self.query, raw, request,
            lua_table(self.h.lua, {"ok": True, "family": family}))[0]
        enriched = self.state.Enrich(self.state, staged)[0]
        view, reason = self.source.read(enriched, enriched)
        self.assertIsNone(reason)
        self.assertEqual(view.perks.enforcers, 0)
        self.assertEqual(view.progress.enforcers, 0)
        before, proposal, _ = self.proposed("stamina")
        before.familyContributionProof.family.progress.enforcers = 25
        view = self.source.read(before, before)[0]
        proposal = self.planners.stamina.propose(view, lua_table(self.h.lua, {
            "enabled": True, "amount": 5, "reserve": 0, "runBudget": 5,
            "maxAttempts": 1, "selectedPerk": "enforcers"}), lua_table(self.h.lua, {}))[0]
        baseline = self.evidence.capture(proposal, before)[0]
        receipt = self.family("stamina", 5)
        receipt["perks"]["enforcers"] = 1
        receipt["perkProgress"] = {}
        self.assertEqual(self.evidence.evaluate(proposal, before, self.raw(2, "stamina", 5),
            lua_table(self.h.lua, {"ok": True, "family": receipt}), baseline), "confirmed")

    def test_generation_does_not_bind_a_changed_family_with_same_header(self):
        raw = self.raw()
        request = self.query.Prepare(self.query, raw)[0]
        raw.native.family.id = "other"
        family = self.family()
        family["id"] = "other"
        self.assertIsNone(self.query.Stage(self.query, raw, request,
            lua_table(self.h.lua, {"ok": True, "family": family}))[0])
        self.assertIsNone(self.query.Stage(self.query, raw, None, {})[0])


if __name__ == "__main__":
    unittest.main()
