"""Explicit source/usage-gated Prestige through real App/broker/native adapter."""
import unittest
import test_automation_runtime as runtime_fixture

from engine_harness import Harness, ROOT, lua_table


class PrestigeResetTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        path = ROOT / "src/tabs/prestige/PrestigeReset.luau"
        self.assertTrue(path.is_file(), "Missing source-gated Prestige reset")
        self.module = self.h.load(path.relative_to(ROOT).as_posix())
        self.reader_module = self.h.load("src/game/PrestigeState.luau")
        self.config = {"PRESTIGE": {"maxRank": 6,
            "levelByRank": [200, 200, 200, 210, 220, 230]}}
        self.reader = self.reader_module.new(lua_table(self.h.lua, self.config), "a" * 64, "release-a")
        self.reset = self.module.new(self.reader)

    def raw(self, rank=0, level=200, xp=1234, revision=1, attempted=0, controllers=True):
        raw = self.h.snapshot(revision=revision, native={"fullSync": True,
            "prestige": rank, "level": level, "xp": xp})
        raw.prestigeUsageProof = lua_table(self.h.lua, {**self.h.session,
            "revision": revision, "capturedAt": raw.capturedAt,
            "attempted": attempted, "controllersClear": controllers})
        return self.reader.Enrich(self.reader, raw)[0]

    def settings(self, **changes):
        values = {"enabled": True, "allowReset": True, "targetRank": 6, "maxResets": 1}
        values.update(changes)
        return lua_table(self.h.lua, values)

    def proposal(self, raw=None):
        raw = raw if raw is not None else self.raw()
        view, reason = self.reader.read(raw, raw)
        self.assertIsNone(reason)
        proposal, reason = self.reset.propose(view, self.settings())
        self.assertIsNone(reason)
        return proposal

    def test_exact_native_reset_call_zero_resources_and_stable_rank_action_identity(self):
        raw = self.raw()
        proposal = self.proposal(raw)
        self.assertEqual(proposal.actionKey, "prestige:0:1")
        self.assertEqual(len(proposal.resources), 0)
        call, reason = self.module.describe(proposal)
        self.assertIsNone(reason)
        self.assertEqual((call.remote, call.method, call.arity, call.args[1]),
                         ("PrestigeAction", "InvokeServer", 1, "prestige"))
        baseline, reason = self.reset.capture(proposal, raw)
        self.assertIsNone(reason)
        self.assertEqual((baseline.rank, baseline.level, baseline.xp), (0, 200, 1234))
        next_revision = self.raw(revision=2)
        self.assertEqual(self.proposal(next_revision).actionKey, proposal.actionKey)

    def test_meaningful_preview_and_legacy_missing_xp_never_reset(self):
        raw = self.raw()
        view = self.reader.read(raw, raw)[0]
        self.assertTrue(view.xpKnown)
        self.assertEqual(view.xp, 1234)
        self.assertIn("200", view.preview)
        self.assertIn("1234", view.preview)
        raw.native.xp = None
        view, reason = self.reader.read(raw, raw)
        self.assertIsNone(reason)
        self.assertTrue(view.ready)
        self.assertFalse(view.xpKnown)
        self.assertIsNone(self.reset.propose(view, self.settings())[0])

    def test_explicit_opt_in_rank_target_readiness_and_independent_caps(self):
        for changes in ({"enabled": False}, {"allowReset": False}, {"maxResets": 0},
                        {"maxResets": -1}, {"targetRank": 0}, {"targetRank": 7}):
            self.assertIsNone(self.reset.propose(self.reader.read(self.raw(), self.raw())[0],
                self.settings(**changes))[0])
        for raw in (self.raw(level=199), self.raw(rank=6, level=230),
                    self.raw(rank=1, level=230), self.raw(attempted=1)):
            view = self.reader.read(raw, raw)[0]
            settings = self.settings(targetRank=1) if raw.native.prestige == 1 else self.settings()
            self.assertIsNone(self.reset.propose(view, settings)[0])

    def test_usage_and_native_controller_proof_must_match_all_current_headers(self):
        for change in ("missing", "count", "controller", "controller-type", "revision",
                       "session", "account", "place", "release", "capturedAt"):
            raw = self.raw()
            if change == "missing": raw.prestigeUsageProof = None
            elif change == "count": raw.prestigeUsageProof.attempted = 0.5
            elif change == "controller": raw.prestigeUsageProof.controllersClear = False
            elif change == "controller-type": raw.prestigeUsageProof.controllersClear = "true"
            else: raw.prestigeUsageProof[change] = -1 if change in ("revision", "capturedAt") else "other"
            view = self.reader.read(raw, raw)[0]
            self.assertIsNone(self.reset.propose(view, self.settings())[0], change)

    def test_capture_rechecks_manual_changes_catalog_usage_and_zero_exposure(self):
        for change in ("rank", "level", "xp", "catalog", "limits", "controller", "resource"):
            raw = self.raw()
            proposal = self.proposal(raw)
            if change == "rank": raw.native.prestige = 1
            elif change == "level": raw.native.level = 201
            elif change == "xp": raw.native.xp = 1235
            elif change == "catalog": raw.prestigeCatalog.levels[6] = 231
            elif change == "limits": raw.prestigeUsageProof.attempted = 1
            elif change == "controller": raw.prestigeUsageProof.controllersClear = False
            else: proposal.resources.cash = 1
            self.assertIsNone(self.reset.capture(proposal, raw)[0], change)

    def test_only_exact_newer_rank_level_xp_and_positive_matching_reply_confirm(self):
        before = self.raw()
        proposal = self.proposal(before)
        baseline = self.reset.capture(proposal, before)[0]
        after = self.raw(rank=1, level=1, xp=0, revision=2, attempted=1)
        self.assertEqual(self.reset.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True, "rank": 1}), baseline), "confirmed")
        for reply in (None, {"ok": True}, {"ok": True, "rank": 2},
                {"ok": True, "rank": 1, "pending": True},
                {"ok": True, "rank": 1, "code": "rate_limited"}, {"ok": False, "rank": 1}):
            self.assertEqual(self.reset.evaluate(proposal, before, after,
                lua_table(self.h.lua, reply), baseline), "pending")
        for changes in ({"rank": 2}, {"level": 2}, {"xp": 1}, {"revision": 1}):
            values = dict(rank=1, level=1, xp=0, revision=2)
            values.update(changes)
            changed = self.raw(**values)
            self.assertEqual(self.reset.evaluate(proposal, before, changed,
                lua_table(self.h.lua, {"ok": True, "rank": 1}), baseline), "pending")

    def test_wrong_scope_malformed_xp_and_missing_full_sync_do_not_confirm(self):
        before = self.raw()
        proposal = self.proposal(before)
        baseline = self.reset.capture(proposal, before)[0]
        for key, value in (("account", "other"), ("session", "restart"),
                           ("place", "other"), ("release", "new")):
            after = self.raw(rank=1, level=1, xp=0, revision=2)
            after[key] = value
            self.assertEqual(self.reset.evaluate(proposal, before, after,
                lua_table(self.h.lua, {"ok": True, "rank": 1}), baseline), "pending")
        for value in (-1, float("nan"), float("inf"), "0", False):
            raw = self.raw(xp=value)
            self.assertIsNone(self.reader.read(raw, raw)[0])
        after = self.raw(rank=1, level=1, xp=0, revision=2)
        after.native.fullSync = False
        self.assertEqual(self.reset.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True, "rank": 1}), baseline), "pending")

    def test_saved_recovery_requires_exact_baseline_scope_and_nonregressing_native_time(self):
        before=self.raw();before.native.serverNow=1000
        proposal=self.proposal(before);baseline=self.reset.capture(proposal,before)[0]
        saved=lua_table(self.h.lua,{'proposal':proposal,'before':before,'baseline':baseline,'reply':{'ok':True,'rank':1}})
        after=self.raw(rank=1,level=1,xp=0,revision=2,attempted=1);after.native.serverNow=1001
        self.assertEqual(self.reset.recoverSaved(saved,after),'confirmed')
        for key in ('account','place','release'):
            old=after[key];after[key]='other';self.assertIsNone(self.reset.recoverSaved(saved,after));after[key]=old
        after.native.serverNow=999;self.assertIsNone(self.reset.recoverSaved(saved,after));after.native.serverNow=1001
        after.revision=1;self.assertIsNone(self.reset.recoverSaved(saved,after));after.revision=2
        baseline.xp=1235;self.assertIsNone(self.reset.recoverSaved(saved,after));baseline.xp=1234
        baseline.extra='unowned';self.assertIsNone(self.reset.recoverSaved(saved,after))

    def test_optional_tab_descriptor_and_catalog_defaults(self):
        tab_module = self.h.load("src/tabs/prestige/Module.luau")
        deps = lua_table(self.h.lua, {"PrestigeState": self.reader_module,
            "PrestigeBlocked": self.h.load("src/features/PrestigeBlocked.luau"),
            "PrestigeReset": self.module, "config": self.config,
            "fingerprint": "a" * 64, "release": "release-a"})
        tab = tab_module.new(deps)
        spec = tab.Descriptors(tab)[1]
        view = spec.reader.read(self.raw(), self.raw())[0]
        self.assertIsNotNone(spec.planner.propose(view, self.settings())[0])
        deps.PrestigeReset = None
        old_tab = tab_module.new(deps)
        fallback = old_tab.Descriptors(old_tab)[1]
        self.assertIsNone(fallback.planner.propose(view, self.settings())[0])
        model = self.h.load("src/storage/Settings.luau").new(self.h.load("src/ui/Catalog.luau"))
        self.assertFalse(model["values"]["prestige.enabled"])
        self.assertFalse(model["values"]["prestige.custom.allowReset"])
        self.assertEqual(model["values"]["prestige.custom.targetRank"], 6)
        self.assertEqual(model["values"]["prestige.custom.maxResets"], 0)

    def test_planner_rejects_forged_threshold_and_describe_rejects_nested_extra_intent(self):
        raw = self.raw()
        view = self.reader.read(raw, raw)[0]
        view.requiredLevel = 1
        self.assertIsNone(self.reset.propose(view, self.settings())[0])
        proposal = self.proposal(raw)
        proposal.intent.args = self.h.lua.table()
        self.assertIsNone(self.module.describe(proposal)[0])

    def test_changed_action_key_or_malformed_baseline_cannot_confirm(self):
        before = self.raw()
        proposal = self.proposal(before)
        baseline = self.reset.capture(proposal, before)[0]
        after = self.raw(rank=1, level=1, xp=0, revision=2)
        proposal.actionKey = "different"
        self.assertEqual(self.reset.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True, "rank": 1}), baseline), "pending")
        proposal.actionKey = "prestige:0:1"
        baseline.rank = "bad"
        self.assertEqual(self.reset.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True, "rank": 1}), baseline), "pending")

    def app_runtime(self, max_resets=1):
        base = runtime_fixture.AutomationRuntimeTests()
        base.setUp()
        self.h = base.h
        base.runtime.Close(base.runtime)
        self.reader_module = self.h.load("src/game/PrestigeState.luau")
        self.reader = self.reader_module.new(lua_table(self.h.lua, self.config), "a" * 64, "release-a")
        reset_module = self.h.load("src/tabs/prestige/PrestigeReset.luau")
        self.reset = reset_module.new(self.reader)
        executor = self.h.lua.execute("""return {calls={},
            Schedule=function(self, cb) self.callback=cb; return true end,
            Invoke=function(self, remote, method, ...)
                self.calls[#self.calls+1]={remote=remote,args=table.pack(...)}
                return {ok=true,rank=1}
            end}""")
        native = self.h.load("src/transport/NativeCallPlan.luau")
        plan = native.withPrestige(native, reset_module)
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(plan, executor)
        runtime = self.h.load("src/engine/AutomationRuntime.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "transport": adapter, "storage": base.storage,
            "identity": self.h.session, "modules": base.runtime.modules,
            "features": [{"id": "prestige", "reader": self.reader,
                "planner": self.reset, "evidence": self.reset}]}))
        app = self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": self.h.load("tests/ember_double.lua")(),
            "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "PrestigeTab": self.h.load("src/tabs/prestige/Module.luau"),
            "automationRuntimeInstance": runtime}))
        for key, value in (("prestige.enabled", True), ("prestige.custom.allowReset", True),
                           ("prestige.custom.maxResets", max_resets)):
            self.assertTrue(app.Set(app, key, value)[0])
        app.Resume(app)
        return app, runtime, executor

    def test_app_refuses_caller_supplied_controller_clear_and_attempt_proof(self):
        app,runtime,executor=self.app_runtime()
        self.assertIn("native controller",app.ui.features.prestige.blockedReason)
        app.Step(app,self.raw())
        self.assertEqual(len(executor.calls),0)
        self.assertIsNone(executor.callback)
        self.assertIn("controller-clear",runtime.Status(runtime).reasons.prestige)
        app.Destroy(app)

    def test_opt_in_and_forged_zero_usage_cannot_bypass_native_controller_owner(self):
        app,runtime,executor=self.app_runtime(max_resets=6)
        for index in range(3):
            self.h.at(index)
            app.Step(app,self.raw(revision=index+1,attempted=0,controllers=True))
        self.assertEqual(len(executor.calls),0)
        self.assertIsNone(executor.callback)
        app.Destroy(app)


if __name__ == "__main__":
    unittest.main()
