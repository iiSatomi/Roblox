"""Tab/App/broker/native fake with explicit injected durable lifecycle hooks."""
import unittest

import test_automation_runtime as runtime_fixture
import test_crew_replacement as replacement_fixture
from engine_harness import lua_table


class CrewReplacementPipelineTests(unittest.TestCase):
    def setUp(self):
        base = runtime_fixture.AutomationRuntimeTests()
        base.setUp()
        self.h = base.h
        base.runtime.Close(base.runtime)
        self.f = replacement_fixture.CrewReplacementTests()
        self.f.h = self.h
        self.f.load_components()
        self.module = self.h.load("src/tabs/crew/Module.luau")
        self.f.config.TERRITORY = lua_table(self.h.lua, {"healStaminaCost": 5, "healSeconds": 300})
        catalog = self.h.lua.eval("""{new=function() return {
            Enrich=function(self,raw) return raw end} end}""")
        self.h.lua.globals().replacementUnrelatedFeature = self.f.source
        gear = self.h.lua.eval("{new=function() return replacementUnrelatedFeature end}")
        deps = {key: self.f.source for key in ("RosterState", "AutoEquipCrew", "CrewSort",
            "CrewHeal", "CrewTrain", "CrewHire", "CrewHealItems", "CrewRollState")}
        deps.update({"NativeTrainingCatalog": catalog, "NativeHireCatalog": catalog,
            "NativeHealItemCatalog": catalog, "CrewGear": gear, "gearSets": {}, "gameData": {},
            "config": self.f.config, "fingerprint": "a" * 64, "release": "release-a",
            "CrewReplacement": self.f.module, "CrewReplacementTransactions": self.f.tx_module})
        self.tab = self.module.new(lua_table(self.h.lua, deps))
        self.f.source = self.tab.replacement
        self.f.tx = self.tab.NewReplacementTransactions(self.tab, self.f.storage, self.f.scope)[0]
        self.assertTrue(self.tab.AttachReplacementOwner(self.tab, self.f.tx)[0])
        descriptor = next(row for row in self.tab.Descriptors(self.tab).values() if row.id == "crewRoll")
        self.executor = self.h.lua.execute("""return {calls={},
            Schedule=function(self,callback)
                local record=self.tx:Active()
                if record.stage=='observedEmpty' then assert(self.tx:PrepareHire(self.raw,self.now)) end
                assert(self.tx:MarkSending(self.raw,self.now))
                local call,reason=self.tx:SubmitCall(self.raw,self.now)
                assert(call,reason); self.authorized=call
                callback(); return true
            end,
            Invoke=function(self,remote,method,...)
                local args=table.pack(...); local call=self.authorized
                assert(call.remote==remote and call.arity==args.n)
                for i=1,args.n do assert(args[i]==call.args[i]) end
                self.calls[#self.calls+1]={remote=remote,args=args}
                local reply=args[1]=='dismiss' and {ok=true} or {
                    ok=true,member={name='New',rarity=2,atk=5,def=6}}
                assert(self.tx:AcceptReply(call.actionKey,reply)); return reply
            end}""")
        self.executor.tx = self.f.tx
        plan = self.h.load("src/transport/NativeCallPlan.luau").withCrew(
            self.h.load("src/tabs/crew/CrewCallPlan.luau"), self.f.module)
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(plan, self.executor)
        self.runtime = self.h.load("src/engine/AutomationRuntime.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "transport": adapter, "storage": base.storage,
            "identity": self.h.session, "modules": base.runtime.modules, "features": [descriptor]}))
        self.app = self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": self.h.load("tests/ember_double.lua")(), "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"), "CrewTab": self.module,
            "automationRuntimeInstance": self.runtime}))

    def tearDown(self):
        self.app.Destroy(self.app)
        self.f.tx.Close(self.f.tx)

    def choose(self):
        for key, value in (("crewRoll.enabled", True), ("crewRoll.policy", "Custom"),
                ("crewRoll.custom.allowDismiss", True), ("crewRoll.custom.targetRarity", 3),
                ("crewRoll.custom.maxDismissRarity", 2), ("crewRoll.custom.minHome", 1),
                ("crewRoll.custom.maxCost", 10000), ("crewRoll.custom.maxSpend", 10000),
                ("crewRoll.custom.cashReserve", 1000), ("crewRoll.custom.maxAttempts", 1)):
            self.assertTrue(self.app.Set(self.app, key, value)[0])
        self.app.Resume(self.app)

    def step(self, raw):
        self.h.at(raw.capturedAt)
        self.executor.raw, self.executor.now = raw, raw.capturedAt
        self.assertTrue(self.app.Step(self.app, raw)[0])

    def test_one_durable_cycle_crosses_app_and_exact_native_calls(self):
        self.choose()
        before = self.f.raw()
        self.assertTrue(self.f.tx.PrepareDismiss(self.f.tx, self.f.proposal(before), before, 1)[0])
        self.step(before)
        self.assertEqual(self.f.tx.Active(self.f.tx).stage, "sentDismiss")
        empty = self.f.raw(revision=2, stage="empty", attempted=1)
        self.assertTrue(self.f.tx.Reconcile(self.f.tx, empty, 2)[0])
        self.step(empty)
        self.assertEqual(self.f.tx.Active(self.f.tx).stage, "sentHire")
        hired = self.f.raw(revision=3, stage="hired", cash=40000, attempted=1, spent=10000)
        self.assertTrue(self.f.tx.Reconcile(self.f.tx, hired, 3)[0])
        self.step(hired)
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.crewRoll, "confirmed")
        self.assertEqual(len(self.executor.calls), 2)
        self.assertEqual(self.executor.calls[1].args[1], "dismiss")
        self.assertEqual(self.executor.calls[2].args[1], "hire")
        self.assertEqual(self.executor.calls[2].args[3], 10000)
        self.assertTrue(self.f.tx.ClearObserved(self.f.tx)[0])
        self.step(self.f.raw(revision=4, stage="hired", cash=40000, attempted=1, spent=10000))
        self.assertEqual(len(self.executor.calls), 2)

    def test_disabled_or_changed_choices_hold_saved_empty_custody(self):
        self.choose()
        empty = self.f.dismissed()
        self.app.Set(self.app, "crewRoll.enabled", False)
        self.step(empty)
        self.assertEqual(len(self.executor.calls), 0)
        self.app.Set(self.app, "crewRoll.enabled", True)
        self.app.Set(self.app, "crewRoll.custom.maxSpend", 5000)
        self.step(empty)
        self.assertEqual(len(self.executor.calls), 0)
        self.assertEqual(self.f.tx.Active(self.f.tx).stage, "observedEmpty")

    def test_legacy_goals_keep_visible_limits_and_safe_new_defaults(self):
        settings = self.f.settings(policy="Legendary or better")
        self.assertEqual(self.module.ReplacementSettings(settings).targetRarity, 5)
        settings.policy = "Mythic or better"
        self.assertEqual(self.module.ReplacementSettings(settings).targetRarity, 6)
        self.assertTrue(self.app.ui.features.crewRoll.custom.visible)
        self.assertFalse(self.app.model["values"]["crewRoll.custom.allowDismiss"])
        self.assertEqual(self.app.model["values"]["crewRoll.custom.maxSpend"], 0)


if __name__ == "__main__":
    unittest.main()
