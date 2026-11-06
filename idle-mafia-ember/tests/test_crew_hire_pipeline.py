"""Current quoted hire call and exact debit through App and fake native transport."""
import unittest

import test_automation_runtime as runtime_fixture
from engine_harness import lua_table


class CrewHirePipelineTests(unittest.TestCase):
    def setUp(self):
        base = runtime_fixture.AutomationRuntimeTests()
        base.setUp()
        self.h, self.base = base.h, base
        base.runtime.Close(base.runtime)
        self.feature = self.h.load("src/tabs/crew/CrewHire.luau")
        self.catalog = self.h.load("src/tabs/crew/NativeHireCatalog.luau").new(
            lua_table(self.h.lua, {"CREW": {"hireTiers": [{"id": "street", "cost": 10000}]}}),
            "b" * 64, "release-a")
        self.executor = self.h.lua.execute("""return {calls={},
            Schedule=function(self,callback) callback(); return true end,
            Invoke=function(self,remote,method,...)
                self.calls[#self.calls+1]={remote=remote,args=table.pack(...)}
                return {ok=true,member={name='New',rarity=3,atk=8,def=9}}
            end}""")
        plan = self.h.load("src/transport/NativeCallPlan.luau").withCrew(
            self.h.load("src/tabs/crew/CrewCallPlan.luau"))
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(plan, self.executor)
        self.runtime = self.h.load("src/engine/AutomationRuntime.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "transport": adapter, "storage": base.storage,
            "identity": self.h.session, "modules": base.runtime.modules, "features": [
                {"id": "crewHire", "reader": self.feature, "planner": self.feature, "evidence": self.feature}]}))
        self.app = self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": self.h.load("tests/ember_double.lua")(),
            "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "automationRuntimeInstance": self.runtime}))

    def tearDown(self):
        self.app.Destroy(self.app)

    def raw(self, revision=1, hired=False, paid=False):
        raw = self.base.raw(revision=revision)
        raw.native.cash = 19000.25 if paid else 30000.25
        raw.native.crew = lua_table(self.h.lua, [{"name": "Player"},
            {"name": "New", "rarity": 3, "atk": 8, "def": 9} if hired else {},
            {"name": "Home", "rarity": 4}])
        raw.economyProof.hirePct = 10
        return self.catalog.Enrich(self.catalog, raw)[0]

    def test_quoted_cost_is_sent_then_full_sync_proves_cash_and_member(self):
        for key, value in (("crewHire.enabled", True), ("crewHire.policy", "street"),
                ("crewHire.custom.maxCost", 20000), ("crewHire.custom.cashReserve", 10000),
                ("crewHire.custom.maxAttempts",1),("crewHire.custom.maxSpend",20000)):
            self.assertTrue(self.app.Set(self.app, key, value)[0])
        self.app.Resume(self.app)
        self.assertTrue(self.app.Step(self.app, self.raw())[0])
        self.assertEqual(len(self.executor.calls), 1)
        call = self.executor.calls[1]
        self.assertEqual((call.remote, call.args.n, call.args[1], call.args[2], call.args[3], call.args[4]),
                         ("CrewAction", 4, "hire", "street", 11000, None))
        self.h.at(1)
        self.app.Step(self.app, self.raw(2, hired=True))
        self.assertNotEqual(self.runtime.Status(self.runtime).outcomes.crewHire, "confirmed")
        self.app.Step(self.app, self.raw(3, hired=True, paid=True))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.crewHire, "confirmed")
        self.assertEqual(len(self.executor.calls), 1)


if __name__ == "__main__":
    unittest.main()
