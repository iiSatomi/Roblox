"""Guarded Crew healing via App, shared broker and fake native adapter only."""
import unittest

import test_automation_runtime as runtime_fixture
from engine_harness import lua_table


class CrewHealingPipelineTests(unittest.TestCase):
    def setUp(self):
        base = runtime_fixture.AutomationRuntimeTests()
        base.setUp()
        self.h, self.base = base.h, base
        base.runtime.Close(base.runtime)
        self.features = {name: self.h.load("src/tabs/crew/" + name + ".luau")
                         for name in ("CrewHeal", "CrewHealItems")}
        items = {ident: {"id": ident, "kind": "consumable",
            "restore": {"pool": "health", "percent": percent}}
            for ident, percent in (("con_bandages", 25), ("con_medkit_small", 50), ("con_medkit_large", 100))}
        self.catalog = self.h.load("src/tabs/crew/NativeHealItemCatalog.luau").new(
            lua_table(self.h.lua, {"ITEMS_BY_ID": items}), lua_table(self.h.lua, {
                "TERRITORY": {"injurySeconds": 1200}, "CONSUMABLES": {"henchmanCooldownSeconds": 3}}),
            "c" * 64, "release-a")
        self.executor = self.h.lua.execute("""return {calls={},
            Schedule=function(self,callback) callback(); return true end,
            Invoke=function(self,remote,method,...)
                self.calls[#self.calls+1]={remote=remote,args=table.pack(...)}
                return self.reply
            end}""")
        plan = self.h.load("src/transport/NativeCallPlan.luau").withCrew(
            self.h.load("src/tabs/crew/CrewCallPlan.luau"))
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(plan, self.executor)
        self.runtime = self.h.load("src/engine/AutomationRuntime.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "transport": adapter, "storage": base.storage,
            "identity": self.h.session, "modules": base.runtime.modules, "features": [
                {"id": ident, "reader": self.features[module], "planner": self.features[module],
                 "evidence": self.features[module]} for ident, module in
                (("crewHeal", "CrewHeal"), ("crewHealItems", "CrewHealItems"))]}))
        self.app = self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": self.h.load("tests/ember_double.lua")(),
            "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "automationRuntimeInstance": self.runtime}))

    def tearDown(self):
        self.app.Destroy(self.app)

    def raw(self, revision=1, healed=None):
        raw = self.h.snapshot(revision=revision, native={"fullSync": True,
            "serverNow": 1000 + (2 if healed else 0),
            "pools": {"stamina": 10 if healed == "crewHeal" else 15},
            "inventory": {"con_bandages": 1},
            "inventoryBound": {"con_bandages": 1 if healed == "crewHealItems" else 2},
            "henchmanConsumableUseSequence": 8 if healed == "crewHealItems" else 7,
            "henchmanConsumableReadyAt": 1003 if healed == "crewHealItems" else 999,
            "crew": [{}, {"name": "Ally", "rarity": 4, "healId": "member-a",
                "injuredUntil": 1400 if healed else 1700}]},
            healRules={"release": "release-a", "healStaminaCost": 5, "healSeconds": 300})
        return self.catalog.Enrich(self.catalog, raw)[0]

    def test_both_guarded_heals_confirm_exact_effect_and_disable_cleanly(self):
        for ident in ("crewHeal", "crewHealItems"):
            with self.subTest(ident=ident):
                # Close each runtime before the next setup to preserve one active session.
                if ident == "crewHealItems":
                    self.app.Destroy(self.app)
                    self.setUp()
                self.executor.reply = lua_table(self.h.lua, {"ok": True, "sequence": 8, "readyAt": 1003})
                self.assertTrue(self.app.Set(self.app, ident + ".enabled", True)[0])
                self.app.Resume(self.app)
                self.assertTrue(self.app.Step(self.app, self.raw())[0])
                self.assertEqual(len(self.executor.calls), 1)
                call = self.executor.calls[1]
                self.assertEqual((call.remote, call.args.n), ("CrewAction", 3))
                self.assertEqual(call.args[1], "heal" if ident == "crewHeal" else "healitem")
                self.assertEqual(call.args[2], 2)
                self.assertEqual(call.args[3].memberId, "member-a")
                self.assertEqual(call.args[3].injuredUntil, 1700)
                if ident == "crewHealItems":
                    self.assertEqual(call.args[3].sequence, 7)
                    self.assertTrue(call.args[3].fromBound)
                self.assertNotEqual(self.runtime.Status(self.runtime).outcomes[ident], "confirmed")
                self.h.at(1)
                self.app.Step(self.app, self.raw(2, ident))
                self.assertEqual(self.runtime.Status(self.runtime).outcomes[ident], "confirmed")
                self.assertTrue(self.app.Set(self.app, ident + ".enabled", False)[0])
                self.h.at(2)
                self.app.Step(self.app, self.raw(3))
                self.assertEqual(len(self.executor.calls), 1)

    def test_item_effect_different_identity_or_wrong_reduction_cannot_confirm(self):
        module = self.features["CrewHealItems"]
        raw = self.raw()
        view = module.read(raw, lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0, "serverNow": 1000, "healItemCatalogKey": "c" * 64}))[0]
        proposal = module.propose(view, lua_table(self.h.lua, {
            "enabled": True, "policy": "con_bandages", "minRemaining": 300}))[0]
        baseline = module.capture(proposal, raw)[0]
        reply = lua_table(self.h.lua, {"ok": True, "sequence": 8, "readyAt": 1003})
        after = self.raw(2, "crewHealItems")
        for field, value in (("healId", "replacement"), ("injuredUntil", 1300)):
            original = after.native.crew[2][field]
            after.native.crew[2][field] = value
            self.assertEqual(module.evaluate(proposal, raw, after, reply, baseline), "pending")
            after.native.crew[2][field] = original


if __name__ == "__main__":
    unittest.main()
