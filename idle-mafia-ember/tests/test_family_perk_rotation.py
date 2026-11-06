"""Family multi-perk choices preserve native order and confirmed-only rotation."""
import unittest
import hashlib
import test_family_contributions as unit
import test_family_contribution_pipeline as pipeline
from engine_harness import lua_table


class FamilyPerkRotationTests(unittest.TestCase):
    def setUp(self):
        self.f = unit.FamilyContributionsTests()
        self.f.setUp()
        self.h = self.f.h

    def test_native_order_rotation_and_exact_batch_skip(self):
        view = self.f.view(perks={"enforcers": 0, "guardians": 0, "runners": 0},
            progress={"enforcers": 0, "guardians": 0, "runners": 0},
            staminaTracks={"enforcers": True, "guardians": True, "runners": True},
            staminaTrackOrder={"enforcers": 3, "guardians": 1, "runners": 2})
        settings = self.f.settings(amount=5, reserve=0, selectedPerk="enforcers",
            selectedPerks="enforcers,runners,guardians")
        def choice():
            proposal, reason = self.f.module.stamina.propose(view, settings, lua_table(self.h.lua, {}))
            self.assertIsNone(reason)
            return proposal.intent.perkId
        self.assertEqual(choice(), "guardians")
        view.lastStaminaPerk = "guardians"
        self.assertEqual(choice(), "runners")
        view.lastStaminaPerk = "runners"
        self.assertEqual(choice(), "enforcers")
        view.lastStaminaPerk = "enforcers"
        view.perks.guardians = 2  # no next cost in the native catalog
        view.progress.runners = 28  # exact five does not fit
        self.assertEqual(choice(), "enforcers")

    def test_malformed_selection_cannot_fall_back_to_singular(self):
        for value in ("enforcers,unknown", "enforcers,enforcers", ",", True, "enforcers,"):
            proposal, _ = self.f.module.stamina.propose(self.f.view(),
                self.f.settings(amount=1, reserve=0, selectedPerk="enforcers", selectedPerks=value),
                lua_table(self.h.lua, {}))
            self.assertIsNone(proposal, value)

    def test_source_captures_order_and_detaches_it(self):
        f = pipeline.FamilyContributionPipelineTests(); f.setUp()
        f.config.FAMILY.perkTracks.enforcers.order = 7
        state = f.source.new(f.config, "a"*64, "release-a",f.player_source)
        raw = state.Enrich(state, f.raw())[0]
        self.assertEqual(raw.familyContributionCatalog.staminaTrackOrder.enforcers, 7)
        f.config.FAMILY.perkTracks.enforcers.order = 1
        raw.familyContributionCatalog.staminaTrackOrder.enforcers = 2
        self.assertEqual(state.Enrich(state, f.raw())[0].familyContributionCatalog.staminaTrackOrder.enforcers, 7)


class FamilyPerkRotationAppTests(unittest.TestCase):
    def setUp(self):
        self.f = pipeline.FamilyContributionPipelineTests(); self.f.setUp()
        self.h = self.f.h
        self.h.lua.globals().rotationHash = lambda value: hashlib.sha256(value.encode()).hexdigest()
        self.f.storage.hash = self.h.lua.eval("function(value) return rotationHash(value) end")
        self.f.storage.Write = self.h.lua.eval("function(self,key,value) self.data[key]=value; return true end")
        for perk, order in (("enforcers", 3), ("guardians", 1), ("runners", 2)):
            self.f.config.FAMILY.perkTracks[perk] = lua_table(self.h.lua, {"kind": "stamina", "order": order})
        self.family = self.f.family()
        self.family["perks"] = {perk: 0 for perk in ("enforcers", "guardians", "runners")}
        self.family["perkProgress"] = {perk: 0 for perk in self.family["perks"]}
        self.total, self.revision = 0, 1
        self.app = None
        self.start()

    def start(self):
        if self.app: self.app.Destroy(self.app)
        self.tab = self.f.tab()
        self.executor = self.h.lua.execute("""return {queued={}, calls={},
            Schedule=function(self,fn) self.queued[#self.queued+1]=fn; return true end,
            Invoke=function(self,remote,method,...)
                self.calls[#self.calls+1]={remote=remote,args=table.pack(...)}
                return self.reply
            end}""")
        native = self.h.load("src/transport/NativeCallPlan.luau")
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(
            native.withFamily(native, self.f.calls), self.executor)
        self.runtime = self.h.load("src/engine/AutomationRuntime.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "transport": adapter, "storage": self.f.storage,
            "identity": self.h.session, "modules": self.f.runtime_modules,
            "features": self.tab.Descriptors(self.tab), "tabInstances": [self.tab],
            "snapshotAssembler": self.h.load("src/tabs/TabSnapshotAssembler.luau").new(lua_table(self.h.lua, [self.tab])),
            "featurePages": {"familyCash": "family", "familyStamina": "family", "familyGold": "family"}}))
        self.app = self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": self.h.load("tests/ember_double.lua")(), "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"), "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "FamilyTab": self.h.load("src/tabs/family/Module.luau"), "automationRuntimeInstance": self.runtime}))
        for key, value in (("enabled", True), ("custom.amount", 5), ("custom.runBudget", 40),
            ("custom.maxAttempts", 8), ("custom.selectedPerks", "enforcers,runners,guardians")):
            self.assertTrue(self.app.Set(self.app, "familyStamina."+key, value)[0])
        self.assertTrue(self.app.Resume(self.app)[0])

    def snapshot(self):
        raw = self.f.raw(self.revision, "stamina", self.total)
        raw.native.family.id = self.family["id"]
        raw = self.tab.state.Enrich(self.tab.state, raw)[0]
        staged, reason = self.tab.state.Stage(self.tab.state, raw,
            lua_table(self.h.lua, {"ok": True, "family": self.family}))
        self.assertIsNone(reason)
        staged.familyContributionCatalog = None
        return staged

    def step(self):
        result = self.app.Step(self.app, self.snapshot())
        self.assertTrue(result[0], result)

    def send(self, expected, outcome="confirmed"):
        self.step()
        queued = self.executor.queued[len(self.executor.queued)]
        self.assertIsNotNone(queued)
        if outcome == "confirmed":
            self.total += 5
            self.family["members"][0]["contributed"] += 5
            self.family["perkProgress"][expected] += 5
            if self.family["perkProgress"][expected] == 30:
                self.family["perkProgress"][expected] = 0
                self.family["perks"][expected] += 1
        self.executor.reply = lua_table(self.h.lua, {"ok": outcome != "rejected", "family": self.family})
        queued()
        call = self.executor.calls[len(self.executor.calls)]
        self.assertEqual((call.remote, call.args[1], call.args[2], call.args[3], call.args.n),
            ("FamilyAction", "contribute", expected, 5, 4))
        self.app.Pause(self.app)
        self.h.at(self.h.lua.globals().testNow + 1)
        self.revision += 1
        self.step()
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.familyStamina, outcome)
        self.app.Resume(self.app)

    def test_actual_app_rotates_three_perks_after_confirmations(self):
        for perk in ("guardians", "runners", "enforcers", "guardians"):
            self.send(perk)
            self.assertEqual(self.tab.lastStaminaPerk, perk)
        self.assertEqual(len(self.executor.calls), 4)

    def test_actual_app_skips_maxed_and_nonfitting_then_rotates_two(self):
        self.family["perks"]["guardians"] = 2
        self.family["perkProgress"]["runners"] = 28
        self.send("enforcers")
        self.family["perkProgress"]["runners"] = 0
        self.send("runners")
        self.send("enforcers")

    def test_rejection_does_not_advance_cursor(self):
        self.send("guardians", "rejected")
        self.assertIsNone(self.tab.lastStaminaPerk)
        self.h.at(100)
        self.send("guardians")

    def test_change_disable_and_unload_cancel_queued_call(self):
        self.step()
        queued = self.executor.queued[1]
        self.assertTrue(self.app.Set(self.app, "familyStamina.custom.selectedPerks", "enforcers,runners")[0])
        queued()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertIsNone(self.tab.lastStaminaPerk)
        self.h.at(1); self.step()
        queued = self.executor.queued[len(self.executor.queued)]
        self.app.Set(self.app, "familyStamina.enabled", False)
        queued()
        self.assertEqual(len(self.executor.calls), 0)
        self.app.Set(self.app, "familyStamina.enabled", True)
        self.h.at(2); self.step()
        queued = self.executor.queued[len(self.executor.queued)]
        self.app.Destroy(self.app); queued()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertIsNone(self.tab.lastStaminaPerk)

    def test_session_restart_and_family_change_reset_cursor(self):
        self.send("guardians")
        self.start()
        self.assertIsNone(self.tab.lastStaminaPerk)
        self.send("guardians")
        self.family["id"] = "fam-b"
        self.h.at(10); self.revision += 1
        self.step()
        self.assertIsNone(self.tab.lastStaminaPerk)

    def test_deadline_and_wrong_perk_receipt_do_not_advance(self):
        self.step()
        self.total = 5
        self.family["members"][0]["contributed"] += 5
        self.family["perkProgress"]["enforcers"] += 5  # selected guardians did not change
        self.executor.reply = lua_table(self.h.lua, {"ok": True, "family": self.family})
        self.executor.queued[1]()
        self.h.at(45); self.revision += 1
        self.step()
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.familyStamina, "skipped_unconfirmed")
        self.assertIsNone(self.tab.lastStaminaPerk)
        self.start(); self.app.Pause(self.app); self.revision += 1
        self.step()
        self.assertIsNone(self.tab.lastStaminaPerk)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 1)
        self.assertEqual(len(self.executor.calls), 0)

    def test_saved_exact_receipt_seeds_fresh_session_cursor_without_replay(self):
        self.step()
        self.total = 5
        self.family["members"][0]["contributed"] += 5
        self.family["perkProgress"]["guardians"] += 5
        self.executor.reply = lua_table(self.h.lua, {"ok": True, "family": self.family})
        self.executor.queued[1]()
        self.h.session["session"] = "fresh-rotation-session"
        self.revision += 1; self.h.at(1)
        self.start(); self.app.Pause(self.app)
        self.step()
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.familyStamina, "confirmed")
        self.assertEqual(self.tab.lastStaminaPerk, "guardians")
        self.assertEqual(len(self.executor.calls), 0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 0)
        self.app.Resume(self.app)
        self.send("runners")

    def test_ui_has_visible_allowed_ids_and_rejects_unknown_choice(self):
        handle = self.app.ui.handles["familyStamina.custom.selectedPerks"]
        self.assertIn("enforcers", handle.options.Description)
        handle.Set(handle, "unknown,enforcers", True)
        handle.options.Callback("unknown,enforcers")
        self.assertEqual(self.app.model["values"]["familyStamina.custom.selectedPerks"], "enforcers,runners,guardians")
        self.assertIn("selectedPerks", self.app.ui.lastError)

    def tearDown(self):
        if self.app: self.app.Destroy(self.app)


if __name__ == "__main__":
    unittest.main()
