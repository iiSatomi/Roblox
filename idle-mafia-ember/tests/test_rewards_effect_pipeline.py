"""Tab-owned effects survive App scheduling and the exact native call boundary."""
import unittest

import test_group_income_effect as fixture
from engine_harness import lua_table


class RewardsEffectPipelineTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.GroupIncomeEffectTests()
        self.fixture.setUp()
        self.h, self.tab = self.fixture.h, self.fixture.tab
        self.spec = next(row for row in self.tab.Descriptors(self.tab).values() if row.id == "playtime")

    def raw(self, revision=1, claimed=False):
        raw = self.fixture.base.raw(revision=revision)
        raw.native.derived.effMaxEnergy = 40
        raw.native.playtime.todaySeconds = 900
        raw.native.playtime.laddersClaimed = lua_table(self.h.lua, {"1": 2, "2": 2} if claimed else {"1": 2})
        return self.tab.Enrich(self.tab, raw)[0]

    def test_income_claim_and_refill_are_available_in_native_order(self):
        raw = self.raw()
        raw.native.playtime.laddersClaimed["1"] = None
        context = self.h.lua.table_from({key: value for key, value in raw.items()})
        context.serverNow = raw.native.serverNow
        view, reason = self.spec.reader.read(raw, context)
        self.assertIsNone(reason)
        self.assertEqual(len(view.ready), 2)
        self.assertEqual(view.ready[1].index, 1)
        proposal, reason = self.spec.planner.propose(view, lua_table(self.h.lua, {"enabled": True}))
        self.assertIsNone(reason)
        self.assertEqual(proposal.intent.index, 1)
        raw.native.cash = None
        view, reason = self.spec.reader.read(raw, context)
        self.assertIsNone(reason)
        self.assertEqual(view.ready[1].index, 2)

    def start_app(self):
        executor = self.h.lua.execute("""return {calls={},
            Schedule=function(self,callback) callback(); return true end,
            Invoke=function(self,remote,method,...)
                self.calls[#self.calls+1]={remote=remote,args={...},count=select('#',...)}
                return {ok=true}
            end}""")
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(
            self.h.load("src/transport/NativeCallPlan.luau"), executor)
        runtime = self.h.load("src/engine/AutomationRuntime.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "transport": adapter, "storage": self.fixture.base.storage,
            "identity": self.h.session, "modules": self.fixture.base.runtime.modules, "features": [self.spec]}))
        app = self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": self.h.load("tests/ember_double.lua")(), "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"), "automationRuntimeInstance": runtime}))
        return app,runtime,executor

    def test_fractional_replicated_seconds_cross_readiness_without_local_rounding(self):
        app,runtime,executor=self.start_app()
        try:
            app.Set(app,'playtime.enabled',True);app.Resume(app)
            before=self.raw();before.native.playtime.todaySeconds=899.999
            app.Step(app,before);self.assertEqual(len(executor.calls),0)
            self.h.at(.25);earned=self.raw(2);earned.native.playtime.todaySeconds=900.001
            app.Step(app,earned)
            self.assertEqual(len(executor.calls),1,runtime.Status(runtime).reasons.playtime)
            self.assertEqual(executor.calls[1].args[1],2)
            app.Set(app,'playtime.enabled',False);self.h.at(1)
            after=self.raw(3,True);after.native.playtime.todaySeconds=900.125;after.native.pools.energy=40
            app.Step(app,after)
            self.assertEqual(runtime.Status(runtime).outcomes.playtime,'confirmed')
            self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)),0)
            self.assertEqual(len(executor.calls),1)
        finally:app.Destroy(app)

    def test_app_claim_needs_refill_after_marker_before_confirmation(self):
        app,runtime,executor=self.start_app()
        try:
            app.Set(app, "playtime.enabled", True)
            app.Resume(app)
            app.Step(app, self.raw())
            call = executor.calls[1]
            self.assertEqual((call.remote, call.count, call.args[1]), ("ClaimLadder", 1, 2))
            self.h.at(1)
            app.Step(app, self.raw(2, True))
            self.assertNotEqual(runtime.Status(runtime).outcomes.playtime, "confirmed")
            self.h.at(2)
            after = self.raw(3, True)
            after.native.pools.energy = 40
            app.Step(app, after)
            self.assertEqual(runtime.Status(runtime).outcomes.playtime, "confirmed")
            self.assertEqual(len(executor.calls), 1)
        finally:
            app.Destroy(app)

    def test_missing_effect_balance_blocks_before_any_proposal(self):
        raw = self.raw()
        raw.native.derived.effMaxEnergy = None
        raw.native.playtime.laddersClaimed["1"] = 2
        raw.serverNow = raw.native.serverNow
        view, reason = self.spec.reader.read(raw, raw)
        self.assertIsNone(view)
        self.assertIn("baseline", reason)

    def test_saved_app_refill_and_marker_recover_with_settings_off(self):
        app,runtime,executor=self.start_app();app.Set(app,"playtime.enabled",True);app.Resume(app)
        before=self.raw();before.native.playtime.todaySeconds=900.25;app.Step(app,before);app.Destroy(app)
        app,runtime,executor=self.start_app();self.h.at(1)
        after=self.raw(2,True);after.native.playtime.todaySeconds=900.75;after.native.pools.energy=40;app.Step(app,after)
        self.assertEqual(runtime.Status(runtime).recoveries.playtime,"confirmed")
        self.assertEqual(len(executor.calls),0);app.Destroy(app)

    def test_same_revision_negative_is_not_a_rejection(self):
        raw=self.raw();raw.serverNow=raw.native.serverNow
        view=self.spec.reader.read(raw,raw)[0]
        proposal=self.spec.planner.propose(view,lua_table(self.h.lua,{"enabled":True}))[0]
        baseline=self.spec.evidence.capture(proposal,raw)[0]
        self.assertEqual(self.spec.evidence.evaluate(proposal,raw,raw,
            lua_table(self.h.lua,{"ok":False}),baseline),"pending")

    def test_saved_app_marker_without_effect_stays_uncertain(self):
        app,runtime,executor=self.start_app();app.Set(app,"playtime.enabled",True);app.Resume(app)
        app.Step(app,self.raw());app.Destroy(app)
        app,runtime,executor=self.start_app();self.h.at(1);app.Step(app,self.raw(2,True))
        self.assertIsNone(runtime.Status(runtime).recoveries.playtime)
        self.assertEqual(len(executor.calls),0);app.Destroy(app)


if __name__ == "__main__":
    unittest.main()
