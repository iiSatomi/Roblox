"""Active-profile edits sync only by explicit opt-in and survive failed/yielding I/O."""
import unittest
import test_profile_next_launch as fixture
from engine_harness import lua_table
class ProfileSyncTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.ProfileNextLaunchTests();self.f.setUp();self.h=self.f.h;self.app=self.f.app;self.store=self.f.store
    def tearDown(self):self.f.tearDown()
    def test_manual_default_does_not_silently_save_active_profile_edits(self):
        self.assertFalse(self.app.profileSync)
        self.app.Set(self.app,"jobs.enabled",True)
        self.assertFalse(self.store.Load(self.store,"usual")[0]["values"]["jobs.enabled"])
        self.assertTrue(self.app.profileModified)
    def test_explicit_opt_in_saves_later_active_profile_edits_and_persists_preference(self):
        self.assertTrue(self.app.SetProfileSync(self.app,True)[0])
        self.assertTrue(self.app.Set(self.app,"jobs.enabled",True)[0])
        self.assertTrue(self.store.Load(self.store,"usual")[0]["values"]["jobs.enabled"])
        self.assertFalse(self.app.profileModified)
        launched=self.f.launch(False);self.assertTrue(launched.profileSync)
        self.assertTrue(launched.SetProfileSync(launched,False)[0]);self.assertFalse(self.store.GetSync(self.store)[0])
    def test_save_failure_preserves_local_choice_as_unsaved_and_pauses(self):
        self.app.SetProfileSync(self.app,True);self.f.f.base.storage.fail=True
        accepted,reason=self.app.Set(self.app,"jobs.enabled",True)
        self.assertFalse(accepted);self.assertIn("save",reason.lower());self.assertTrue(self.app.model.paused)
        self.assertTrue(self.app.model["values"]["jobs.enabled"]);self.assertTrue(self.app.profileModified)
        self.f.f.base.storage.fail=False
        self.assertFalse(self.store.Load(self.store,"usual")[0]["values"]["jobs.enabled"])
    def test_enabling_sync_does_not_silently_overwrite_existing_unsaved_edits(self):
        self.app.Set(self.app,"jobs.enabled",True);self.app.SetProfileSync(self.app,True)
        self.assertFalse(self.store.Load(self.store,"usual")[0]["values"]["jobs.enabled"])
        self.assertTrue(self.app.profileModified)
    def test_yielding_save_refuses_competing_edits_and_rename_then_releases_lock(self):
        self.app.SetProfileSync(self.app,True)
        original=self.f.f.base.storage.Write;self.h.lua.globals().syncWrite=original
        self.f.f.base.storage.Write=self.h.lua.eval("function(self,key,value) coroutine.yield('saving');return syncWrite(self,key,value) end")
        self.h.lua.globals().syncApp=self.app
        self.h.lua.execute("syncEdit=coroutine.create(function() return syncApp:Set('jobs.enabled',true) end);assert(select(2,coroutine.resume(syncEdit))=='saving')")
        self.assertFalse(self.app.Set(self.app,"bank.enabled",True)[0])
        self.assertFalse(self.app.CanReplace(self.app)[0])
        self.assertFalse(self.app.ApplyProfile(self.app,lua_table(self.h.lua,{"schema":1,"values":{}}))[0])
        self.assertFalse(self.store.Rename(self.store,"usual","renamed")[0])
        self.assertFalse(self.app.SetNextLoad(self.app,"usual")[0])
        self.h.lua.execute("assert(coroutine.resume(syncEdit))")
        self.f.f.base.storage.Write=original
        self.assertTrue(self.store.Load(self.store,"usual")[0]["values"]["jobs.enabled"])
        self.assertFalse(self.store.Load(self.store,"usual")[0]["values"]["bank.enabled"])
    def test_corrupt_sync_preference_starts_manual_and_does_not_grant_opt_in(self):
        self.f.f.base.storage.data[self.store.ScopeKey(self.store)+":sync"]=lua_table(self.h.lua,{"version":1,"account":"other","place":"place-a","enabled":True})
        app=self.f.launch(False);self.assertFalse(app.profileSync)
        self.assertIsNotNone(app.profileSyncError)
    def test_sync_toggle_observes_latest_user_selection_and_never_autosaves_on_start(self):
        toggle=self.app.ui.profiles.syncToggle
        toggle.Set(toggle,True);toggle.Set(toggle,False);self.f.f.ember.Flush(True)
        self.assertFalse(self.app.profileSync);self.assertFalse(self.store.GetSync(self.store)[0])
    def test_unload_during_yielding_sync_does_not_revive_app(self):
        self.app.SetProfileSync(self.app,True);self.h.lua.globals().syncApp=self.app
        self.h.lua.globals().syncWrite=self.f.f.base.storage.Write
        self.f.f.base.storage.Write=self.h.lua.eval("function(self,key,value) coroutine.yield('saving');return syncWrite(self,key,value) end")
        self.h.lua.execute("syncEdit=coroutine.create(function() return syncApp:Set('jobs.enabled',true) end);assert(select(2,coroutine.resume(syncEdit))=='saving')")
        self.app.Destroy(self.app);self.h.lua.execute("assert(coroutine.resume(syncEdit))")
        self.assertFalse(self.app.alive)
    def test_runtime_pauses_while_saving_and_resumes_only_if_user_did_not_pause(self):
        app=self.f.launch();app.SaveProfile(app,"usual");app.SetProfileSync(app,True)
        runtime=app.automationRuntime;runtime.pauses=0;runtime.resumes=0
        runtime.Pause=self.h.lua.eval("function(self) self.pauses=self.pauses+1 end")
        runtime.Resume=self.h.lua.eval("function(self) self.resumes=self.resumes+1 end")
        self.assertTrue(app.Set(app,"jobs.enabled",True)[0])
        self.assertEqual(runtime.pauses,1);self.assertEqual(runtime.resumes,1)
        self.h.lua.globals().syncApp=app;self.h.lua.globals().syncWrite=self.f.f.base.storage.Write
        self.f.f.base.storage.Write=self.h.lua.eval("function(self,key,value) coroutine.yield('saving');return syncWrite(self,key,value) end")
        self.h.lua.execute("syncEdit=coroutine.create(function() return syncApp:Set('jobs.enabled',false) end);assert(select(2,coroutine.resume(syncEdit))=='saving')")
        app.Pause(app);self.h.lua.execute("assert(coroutine.resume(syncEdit))")
        self.assertTrue(app.model.paused);self.assertEqual(runtime.resumes,1)
    def test_ui_refusal_does_not_save_an_unaccepted_choice(self):
        self.app.SetProfileSync(self.app,True)
        self.app.ui.ApplyValues=self.h.lua.eval("function() return false,'display refused' end")
        self.assertFalse(self.app.Set(self.app,"jobs.enabled",True)[0])
        self.assertFalse(self.store.Load(self.store,"usual")[0]["values"]["jobs.enabled"])
        self.assertFalse(self.app.profileSaving)
    def test_same_value_does_not_write_and_pause_stop_do_not_rewrite_desired_choices(self):
        self.app.SetProfileSync(self.app,True)
        self.h.lua.globals().syncWrite=self.f.f.base.storage.Write
        self.f.f.base.storage.Write=self.h.lua.eval("function(self,key,value) syncWriteCount=(syncWriteCount or 0)+1;return syncWrite(self,key,value) end")
        self.app.Set(self.app,"jobs.enabled",False);self.assertIsNone(self.h.lua.globals().syncWriteCount)
        self.app.Set(self.app,"jobs.enabled",True);self.assertEqual(self.h.lua.globals().syncWriteCount,1)
        self.app.Pause(self.app);self.app.Stop(self.app)
        self.assertEqual(self.h.lua.globals().syncWriteCount,1)
        self.assertTrue(self.store.Load(self.store,"usual")[0]["values"]["jobs.enabled"])
    def test_failed_opt_in_is_not_granted_and_lock_releases_after_exception(self):
        self.f.f.base.storage.fail=True
        self.assertFalse(self.app.SetProfileSync(self.app,True)[0]);self.assertFalse(self.app.profileSync)
        self.f.f.base.storage.fail=False
        self.assertFalse(self.store.GetSync(self.store)[0]);self.assertFalse(self.store.writing)
        self.assertTrue(self.app.SetProfileSync(self.app,True)[0])
    def test_another_store_for_same_adapter_cannot_overwrite_a_yielding_profile_map(self):
        other=self.f.f.base.module.new(self.f.f.base.storage,self.app.model,self.h.session["account"],self.h.session["place"])
        self.app.SetProfileSync(self.app,True);self.h.lua.globals().syncApp=self.app
        self.h.lua.globals().syncWrite=self.f.f.base.storage.Write
        self.f.f.base.storage.Write=self.h.lua.eval("function(self,key,value) coroutine.yield('saving');return syncWrite(self,key,value) end")
        self.h.lua.execute("syncEdit=coroutine.create(function() return syncApp:Set('jobs.enabled',true) end);assert(select(2,coroutine.resume(syncEdit))=='saving')")
        self.assertFalse(other.Save(other,"lost",lua_table(self.h.lua,{"schema":1,"values":{}}))[0])
        self.h.lua.execute("assert(coroutine.resume(syncEdit))")
        self.assertIsNone(other.Load(other,"lost")[0])
    def test_shared_reserve_saves_with_current_profile_without_an_extra_feature_toggle(self):
        self.app.SetProfileSync(self.app,True);self.assertTrue(self.app.Set(self.app,"shared.energyReserve",25)[0])
        saved=self.store.Load(self.store,"usual")[0]
        self.assertEqual(saved["values"]["shared.energyReserve"],25)
        self.assertFalse(saved["values"]["jobs.enabled"])
if __name__=="__main__":unittest.main()
