"""Crew hires belong to an explicitly borrowed current native hire contract."""
import unittest

from engine_harness import Harness, lua_table


class CrewHireTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.source = self.h.load("src/tabs/crew/NativeHireCatalog.luau")
        self.goal_reader = self.h.load("src/tabs/contracts/ContractGoalState.luau")
        self.goal_requests = self.h.load("src/tabs/contracts/ContractGoalRequests.luau")
        self.feature = self.h.load("src/tabs/crew/CrewHire.luau").new(self.goal_reader)
        self.config = lua_table(self.h.lua, {"CREW": {"hireTiers": [
            {"id": "street", "name": "STREET", "cost": 10000},
            {"id": "elite", "name": "ELITE", "cost": 100000} ]}})
        self.catalog = self.source.new(self.config, "b" * 64, "release-a")
        self.before = self.h.snapshot(native={"fullSync": True,
            "cash": 30000, "crew": [{"name": "Player"}, {},
                                       {"name": "Home", "rarity": 4}]},
            economyProof={"account": "user-a", "capturedAt": 0,
                "city": "ny", "revision": 3, "familyId": "",
                "rulerId": "", "shopPct": 0, "hirePct": 10,
                "marketPct": 10, "territoryShopDiscount": 0,
                "globalShopSale": 0})
        self.before["native"]["cityId"] = "ny"
        self.before, reason = self.catalog.Enrich(self.catalog, self.before)
        self.assertIsNone(reason)
        self.context = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0, "hireCatalogKey": "b" * 64})
        self.before["crewHireUsageProof"] = lua_table(self.h.lua,
            {**self.h.session, "revision": 1, "capturedAt": 0,
             "attempted": 0, "spent": 0})
        self.attach_contract(self.before,0)

    def attach_contract(self,raw,progress):
        raw.catalogKey = "b"*64
        raw.contractTemplates = lua_table(self.h.lua,[{"id":"c_hire","key":"hires"}])
        raw.native.serverNow = 100 + raw.revision
        raw.native.derived = lua_table(self.h.lua,{"contractDayReset":2000,"contractWeekReset":3000})
        rows = [{"id":"c_hire","done":progress>=1,"claimed":False,"progress":progress,"goal":1}]
        rows += [{"id":f"other_{i}","done":False,"claimed":False} for i in range(4)]
        raw.native.contracts = lua_table(self.h.lua,{"daily":rows,"weekly":rows})

    def scoped(self,view):
        goals,_ = self.goal_requests.derive(view.contractGoals,
            lua_table(self.h.lua,{"enabled":True,"borrowHires":True}))
        scoped,reason = self.feature.ForContract(view,goals.requests[1])
        self.assertIsNone(reason)
        return scoped

    def plan(self):
        view, reason = self.feature.read(self.before, self.context)
        self.assertIsNone(reason)
        view = self.scoped(view)
        proposal, reason = self.feature.propose(view, lua_table(self.h.lua,
            {"enabled": True, "policy": "street", "custom":
             {"maxCost": 20000, "cashReserve": 10000,
              "maxAttempts": 2, "maxSpend": 20000}}))
        self.assertIsNone(reason)
        return proposal

    def runtime(self):
        modules = {"Contracts": self.h.contracts}
        for name, folder in (("Broker", "engine"), ("Journal", "engine"),
                ("Context", "game"), ("Scheduler", "engine"), ("Session", "engine"),
                ("Checkpoint", "storage"), ("CrewHireUsage", "tabs/crew"), ("PendingAction", "storage")):
            modules[name] = self.h.load(f"src/{folder}/{name}.luau")
        make_tab = self.h.lua.eval("function(id,specs) return {id=id,Descriptors=function() return specs end} end")
        blocked = self.h.load("src/tabs/contracts/ContractGoalBlocked.luau")
        tabs = lua_table(self.h.lua,[make_tab("crew",lua_table(self.h.lua,[
            {"id":"crewHire","reader":self.feature,"planner":self.feature,
             "evidence":self.feature,"recoverSaved":self.feature.recoverSaved}])),
            make_tab("contracts",lua_table(self.h.lua,[{"id":"autoContracts",
                "reader":self.goal_reader,"planner":blocked,"evidence":blocked,"goals":self.goal_requests}]))])
        composition,reason = self.h.load("src/tabs/TabComposition.luau").build(tabs,
            self.h.load("src/ui/Catalog.luau"),self.h.load("src/engine/FeatureRegistry.luau"),
            self.h.load("src/tabs/TabSnapshotAssembler.luau"))
        self.assertIsNone(reason)
        storage = self.h.lua.execute("return {data={},strictRecovery=true,Read=function(self,k) return self.data[k] end,Write=function(self,k,v) self.data[k]=v;return true end}")
        runtime = self.h.load("src/engine/AutomationRuntime.luau").new(lua_table(self.h.lua,{
            "modules":modules,"features":composition.features,"featurePages":composition.featurePages,
            "clock":self.h.clock,"transport":self.h.transport,"storage":storage,"identity":self.h.session}))
        runtime.Resume(runtime)
        return runtime

    def test_composed_contract_hiring_requires_all_permissions_and_ordinary_limits(self):
        cases = ((True,True,True,2,20000,1), (False,True,True,2,20000,0),
            (True,False,True,2,20000,0), (True,True,False,2,20000,0),
            (True,True,True,0,20000,0), (True,True,True,2,0,0))
        for contracts,borrow,hire,attempts,spend,expected in cases:
            with self.subTest(contracts=contracts,borrow=borrow,hire=hire,attempts=attempts,spend=spend):
                self.setUp()
                runtime = self.runtime()
                settings = lua_table(self.h.lua,{
                    "autoContracts":{"enabled":contracts,"borrowHires":borrow},
                    "crewHire":{"enabled":hire,"policy":"street","maxCost":20000,
                        "cashReserve":10000,"maxAttempts":attempts,"maxSpend":spend}})
                status = runtime.Step(runtime,self.before,settings)
                self.assertEqual(len(self.h.transport.sent),expected, str(status.reasons.crewHire))
                if expected:
                    sent = self.h.transport.sent[1]
                    self.assertEqual(sent.feature,"crewHire")
                    self.assertEqual(sent.intent.contractId,"c_hire")
                    self.assertEqual(sent.intent.contractProgress,0)
                    self.assertTrue(status.goals.autoContracts.routed)
                runtime.Close(runtime)

    def test_exact_hire_result_without_same_contract_progress_stays_pending(self):
        proposal = self.plan()
        baseline,reason = self.feature.capture(proposal,self.before)
        self.assertIsNone(reason)
        after = self.h.snapshot(revision=2,native={"fullSync":True,"cash":19000,
            "crew":[{"name":"Player"},{"name":"New","rarity":3,"atk":8,"def":9},
                    {"name":"Home","rarity":4}]})
        reply = lua_table(self.h.lua,{"ok":True,"index":2,"member":{"name":"New","rarity":3,"atk":8,"def":9}})
        self.attach_contract(after,0)
        self.assertEqual(self.feature.evaluate(proposal,self.before,after,reply,baseline),"pending")
        self.attach_contract(after,1)
        after.native.derived.contractDayReset = 4000
        self.assertEqual(self.feature.evaluate(proposal,self.before,after,reply,baseline),"pending")
        after.native.derived.contractDayReset = 2000
        after.native.contracts.daily[1].id = "different"
        self.assertEqual(self.feature.evaluate(proposal,self.before,after,reply,baseline),"pending")

    def test_completed_or_changed_contract_cannot_recapture_or_authorize_another_hire(self):
        proposal = self.plan()
        self.before.native.contracts.daily[1].progress = 1
        self.assertIsNone(self.feature.capture(proposal,self.before)[0])
        self.attach_contract(self.before,1)
        view,reason = self.feature.read(self.before,self.context)
        self.assertIsNone(reason)
        requests,reason = self.goal_requests.derive(view.contractGoals,
            lua_table(self.h.lua,{"enabled":True,"borrowHires":True}))
        self.assertIsNone(reason)
        self.assertEqual(len(requests.requests),0)

    def test_recovery_keeps_native_contract_identity_allowance_and_quote(self):
        proposal = self.plan()
        baseline,reason = self.feature.capture(proposal,self.before)
        self.assertIsNone(reason)
        self.before.data = self.before.native
        self.before.stationCatalog = lua_table(self.h.lua,[
            {"id":f"district_{i}","holder":"x"*100,"capacity":5} for i in range(1500)])
        pending = self.h.load("src/storage/PendingAction.luau")
        encoded,reason = pending.Capture(proposal,self.before,baseline)
        self.assertIsNone(reason)
        decoded = pending.Decode(encoded)
        self.assertIsNone(decoded.before.stationCatalog)
        self.assertEqual(decoded.before.contractTemplates[1].key,"hires")
        self.assertEqual(decoded.before.crewHireUsageProof.attempted,0)
        self.assertEqual(decoded.before.hireCatalog.catalogKey,"b"*64)
        recaptured,reason = self.feature.capture(decoded.proposal,decoded.before)
        self.assertIsNone(reason)
        self.assertEqual(recaptured.intent.contractId,decoded.baseline.intent.contractId)
        self.assertTrue(pending.Same(encoded,pending.Capture(decoded.proposal,decoded.before,recaptured)[0]))

    def checkpoint(self,store=None):
        if store is None:
            store = self.h.lua.execute("return {strictRecovery=true,data={},Read=function(self,k) return self.data[k] end,Write=function(self,k,v) self.data[k]=v;return true end}")
        checkpoint = self.h.load("src/storage/Checkpoint.luau").new(store,None,None,
            self.h.load("src/storage/PendingAction.luau"),None,None,
            self.h.load("src/tabs/crew/CrewHireUsage.luau"))
        _,reason = checkpoint.Load(checkpoint,self.h.session['account'],self.h.session['place'],self.h.session['release'])
        self.assertIsNone(reason)
        return checkpoint,store

    def test_saved_hire_reply_cannot_refund_attempt_or_cash_as_unsent(self):
        for reply in ({"ok":True,"pending":True},{"ok":False},{"ok":True}):
            with self.subTest(reply=reply):
                self.setUp()
                proposal = self.plan()
                baseline = self.feature.capture(proposal,self.before)[0]
                checkpoint,store = self.checkpoint()
                self.assertTrue(checkpoint.Save(checkpoint,proposal,self.before,baseline)[0])
                self.assertTrue(checkpoint.RecordReply(checkpoint,proposal.actionKey,lua_table(self.h.lua,reply))[0])
                self.assertFalse(checkpoint.Resolve(checkpoint,proposal.actionKey,"schedule_failed")[0])
                self.assertEqual(len(checkpoint.Records(checkpoint)),1)
                restarted,_ = self.checkpoint(store)
                usage,reason = restarted.CrewHireUsage(restarted,self.before)
                self.assertIsNone(reason)
                self.assertEqual((usage.attempted,usage.spent),(1,11000))

    def test_known_unsent_hire_refunds_only_with_intact_reply_free_recovery(self):
        proposal = self.plan()
        baseline = self.feature.capture(proposal,self.before)[0]
        checkpoint,store = self.checkpoint()
        self.assertTrue(checkpoint.Save(checkpoint,proposal,self.before,baseline)[0])
        self.assertTrue(checkpoint.Resolve(checkpoint,proposal.actionKey,"schedule_failed")[0])
        restarted,_ = self.checkpoint(store)
        usage,reason = restarted.CrewHireUsage(restarted,self.before)
        self.assertIsNone(reason)
        self.assertEqual((usage.attempted,usage.spent),(0,0))
        self.assertEqual(len(restarted.Records(restarted)),0)

    def test_quote_and_exact_new_member_evidence(self):
        proposal = self.plan()
        call, reason = self.h.load("src/tabs/crew/CrewCallPlan.luau").describe(proposal)
        self.assertIsNone(reason)
        self.assertEqual(call["remote"], "CrewAction")
        self.assertEqual(call["arity"], 4)
        self.assertEqual([call["args"][i] for i in range(1, 4)],
                         ["hire", "street", 11000])
        self.assertIsNone(call["args"][4])
        baseline, reason = self.feature.capture(proposal, self.before)
        self.assertIsNone(reason)
        after = self.h.snapshot(revision=2, native={"fullSync": True,
            "cash": 19000, "crew": [{"name": "Player"},
                {"name": "New", "rarity": 3, "atk": 8, "def": 9},
                {"name": "Home", "rarity": 4}]})
        reply = lua_table(self.h.lua, {"ok": True, "index": 2,
            "member": {"name": "New", "rarity": 3, "atk": 8, "def": 9}})
        self.attach_contract(after,1)
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            after, reply, baseline), "confirmed")
        after["native"]["crew"][2]["name"] = "Other"
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            after, reply, baseline), "pending")

    def test_quote_or_slot_change_blocks_send(self):
        proposal = self.plan()
        self.before["economyProof"]["hirePct"] = 11
        self.assertIsNone(self.feature.capture(proposal, self.before)[0])
        self.before["economyProof"]["hirePct"] = 10
        self.before["native"]["crew"][2]["rarity"] = 2
        self.assertIsNone(self.feature.capture(proposal, self.before)[0])

    def test_no_replacement_or_unaffordable_tier(self):
        view, _ = self.feature.read(self.before, self.context)
        view = self.scoped(view)
        self.assertIsNone(self.feature.propose(view, lua_table(self.h.lua,
            {"enabled": True, "policy": "elite", "custom":
             {"maxCost": 20000, "cashReserve": 0,
              "maxAttempts": 2, "maxSpend": 20000}}))[0])
        self.before["native"]["crew"][2]["rolling"] = True
        self.assertIsNone(self.feature.read(self.before, self.context)[0])

    def test_allowance_must_match_account_session_and_revision(self):
        proof = self.before["crewHireUsageProof"]
        for field, invalid in (("account", "other"), ("session", "old"),
                               ("revision", 0), ("capturedAt", 1)):
            with self.subTest(field=field):
                original = proof[field]
                proof[field] = invalid
                self.assertIsNone(self.feature.read(self.before, self.context)[0])
                proof[field] = original

    def test_attempt_and_spend_limits_block_hiring(self):
        for attempted, spent in ((2, 0), (0, 10000)):
            with self.subTest(attempted=attempted, spent=spent):
                proof = self.before["crewHireUsageProof"]
                proof["attempted"], proof["spent"] = attempted, spent
                view, reason = self.feature.read(self.before, self.context)
                self.assertIsNone(reason)
                view = self.scoped(view)
                proposal, _ = self.feature.propose(view, lua_table(self.h.lua,
                    {"enabled": True, "policy": "street", "custom": {
                        "maxCost": 20000, "cashReserve": 10000,
                        "maxAttempts": 2, "maxSpend": 20000}}))
                self.assertIsNone(proposal)

    def test_capture_rechecks_allowance_and_resource_exposure(self):
        proposal = self.plan()
        self.before["crewHireUsageProof"]["attempted"] = 1
        self.assertIsNone(self.feature.capture(proposal, self.before)[0])
        self.before["crewHireUsageProof"]["attempted"] = 0
        proposal["resources"]["cash"] = 1
        self.assertIsNone(self.feature.capture(proposal, self.before)[0])

    def test_empty_slot_and_budget_do_not_authorize_unscoped_contract_hiring(self):
        view,reason = self.feature.read(self.before,self.context)
        self.assertIsNone(reason)
        proposal,_ = self.feature.propose(view,lua_table(self.h.lua,{
            "enabled":True,"policy":"street","maxCost":20000,"cashReserve":10000,
            "maxAttempts":2,"maxSpend":20000}))
        self.assertIsNone(proposal,"A current explicitly borrowed native hires goal must own the action")


if __name__ == "__main__":
    unittest.main()
