"""One-shot launch selection and reviewed deletion use existing saved profiles."""
import unittest
import test_profile_management as fixture
from engine_harness import lua_table

class ProfileNextLaunchTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.ProfileManagementTests();self.f.setUp();self.h=self.f.h;self.app=self.f.app;self.store=self.app.profileStore;self.apps=[]
        self.app.Set(self.app,"jobs.enabled",True);self.app.SaveProfile(self.app,"once")
        self.app.Set(self.app,"jobs.enabled",False);self.app.SaveProfile(self.app,"usual")
    def tearDown(self):
        for app in self.apps:app.Destroy(app)
        self.f.tearDown()
    def launch(self,runtime=True):
        fake=self.h.lua.execute("""return {Status=function() return {state='paused',availableFeatures={}} end,
            Step=function() return true end,Pause=function() end,Resume=function() end,Stop=function() end,Close=function() end}""") if runtime else None
        deps=lua_table(self.h.lua,{"Ember":self.h.load("tests/ember_double.lua")(),"Catalog":self.h.load("src/ui/Catalog.luau"),
            "Settings":self.h.load("src/storage/Settings.luau"),"EmberAdapter":self.h.load("src/ui/EmberAdapter.luau"),
            "ProfilesTab":self.h.load("src/tabs/profiles/Module.luau"),"ProfileStore":self.f.base.module,
            "ProfileStorage":self.f.base.storage,"identity":self.h.session,"automationRuntimeInstance":fake,
            "allowedFeatures":{"jobs":True,"bosses":True}})
        app=self.h.load("src/App.luau").start(deps);self.apps.append(app);return app
    def test_next_launch_is_explicit_and_consumed_before_autoload_fallback(self):
        self.assertTrue(self.app.SetNextLoad(self.app,"once")[0]);self.store.SetAutoload(self.store,"usual")
        self.assertFalse(self.app.model["values"]["jobs.enabled"])
        first=self.launch();self.assertTrue(first.model["values"]["jobs.enabled"])
        self.assertIsNone(self.store.GetNextLoad(self.store)[0])
        first.Destroy(first);second=self.launch();self.assertFalse(second.model["values"]["jobs.enabled"])
        self.assertEqual(second.currentProfile,"usual")
    def test_inert_preview_does_not_consume_next_launch(self):
        self.app.SetNextLoad(self.app,"once");self.launch(False)
        self.assertEqual(self.store.GetNextLoad(self.store)[0],"once")
    def test_failed_consumption_does_not_fall_back_to_another_sender_selection(self):
        self.app.SetNextLoad(self.app,"once");self.store.SetAutoload(self.store,"usual")
        original=self.f.base.storage.Write
        self.f.base.storage.Write=self.h.lua.eval("function() return false end")
        launched=self.launch();self.assertIsNone(launched.currentProfile)
        self.assertFalse(launched.model["values"]["jobs.enabled"])
        self.f.base.storage.Write=original
        self.assertEqual(self.store.GetNextLoad(self.store)[0],"once")
    def test_corrupt_next_launch_blocks_autoload_and_invalid_names_never_write(self):
        self.store.SetAutoload(self.store,"once")
        self.f.base.storage.data[self.store.ScopeKey(self.store)+":next"]=lua_table(self.h.lua,{"version":1,"account":"other","place":"place-a","name":"once"})
        app=self.launch();self.assertFalse(app.model["values"]["jobs.enabled"])
        self.assertFalse(self.app.SetNextLoad(self.app,"missing")[0])
        self.assertFalse(self.app.SetNextLoad(self.app,"../once")[0])
    def test_next_launch_reference_must_be_cleared_before_rename(self):
        self.app.SetNextLoad(self.app,"once")
        self.assertFalse(self.store.Rename(self.store,"once","new")[0])
        self.app.SetNextLoad(self.app,None);self.assertTrue(self.store.Rename(self.store,"once","new")[0])
    def test_delete_requires_paused_exact_preview_and_keeps_current_choices(self):
        self.assertFalse(self.app.DeleteProfile(self.app,"once")[0])
        self.app.PreviewProfile(self.app,"once");self.assertTrue(self.app.DeleteProfile(self.app,"once")[0])
        self.assertIsNone(self.store.Load(self.store,"once")[0]);self.assertIsNone(self.app.staged)
        self.assertFalse(self.app.model["values"]["jobs.enabled"])
    def test_delete_rejects_stale_preview_and_launch_references_without_partial_changes(self):
        self.app.PreviewProfile(self.app,"once")
        self.store.Save(self.store,"once",lua_table(self.h.lua,{"schema":1,"values":{"jobs.enabled":False}}))
        self.assertFalse(self.app.DeleteProfile(self.app,"once")[0])
        self.app.PreviewProfile(self.app,"once");self.store.SetAutoload(self.store,"once")
        self.assertFalse(self.app.DeleteProfile(self.app,"once")[0])
        self.store.SetAutoload(self.store,None);self.app.SetNextLoad(self.app,"once")
        self.assertFalse(self.app.DeleteProfile(self.app,"once")[0])
        self.assertIsNotNone(self.store.Load(self.store,"once")[0])
    def test_buttons_show_one_shot_choice_and_clear_it_without_applying_choices(self):
        buttons={h.options.Text:h for h in self.app.ui.window.handles.values() if h.kind=="Button"}
        self.app.ui.profiles.profileName.Set(self.app.ui.profiles.profileName,"once",True)
        buttons["Use once on next launch"].Click(buttons["Use once on next launch"]);self.f.ember.Flush()
        self.assertEqual(self.app.ui.profiles.nextLoadStatus.value,"once")
        self.assertFalse(self.app.model["values"]["jobs.enabled"])
        buttons["Clear next launch choice"].Click(buttons["Clear next launch choice"]);self.f.ember.Flush()
        self.assertEqual(self.app.ui.profiles.nextLoadStatus.value,"Off")
    def test_missing_or_disallowed_once_profile_is_consumed_without_autoload_fallback(self):
        self.store.SetAutoload(self.store,"once")
        self.store.Save(self.store,"restricted",lua_table(self.h.lua,{"schema":1,"values":{"shop.enabled":True}}))
        self.app.SetNextLoad(self.app,"restricted")
        launched=self.launch();self.assertIsNone(launched.currentProfile)
        self.assertFalse(launched.model["values"]["jobs.enabled"]);self.assertFalse(launched.model["values"]["shop.enabled"])
        self.assertIsNone(self.store.GetNextLoad(self.store)[0]);launched.Destroy(launched)
        self.app.SetNextLoad(self.app,"usual")
        self.f.base.storage.data[self.store.ScopeKey(self.store)].profiles.usual=None
        launched=self.launch();self.assertIsNone(launched.currentProfile)
        self.assertFalse(launched.model["values"]["jobs.enabled"])
        self.assertIsNone(self.store.GetNextLoad(self.store)[0])
    def test_failed_delete_keeps_preview_file_and_current_profile_identity(self):
        self.app.PreviewProfile(self.app,"usual")
        self.f.base.storage.fail=True
        self.assertFalse(self.app.DeleteProfile(self.app,"usual")[0])
        self.f.base.storage.fail=False
        self.assertEqual(self.app.currentProfile,"usual");self.assertEqual(self.app.stagedName,"usual")
        self.assertIsNotNone(self.store.Load(self.store,"usual")[0])
        self.app.model.paused=False;self.assertFalse(self.app.DeleteProfile(self.app,"usual")[0])
    def test_next_launch_selection_is_account_and_place_scoped(self):
        self.app.SetNextLoad(self.app,"once")
        for account,place in (("other","place-a"),("user-a","elsewhere")):
            other=self.f.base.module.new(self.f.base.storage,self.app.model,account,place)
            self.assertIsNone(other.GetNextLoad(other)[0])
    def test_consumed_tombstone_uses_strict_storage_and_cannot_resurrect_old_choice(self):
        import test_redundant_store as disk_fixture
        f=disk_fixture.RedundantStoreTests();f.setUp();h=f.h
        strict=h.load("src/storage/RedundantStore.luau").new(f.store.files,f.store.codec,f.store.hash,"strict",lua_table(h.lua,{"strictRecovery":True}))
        model=h.load("src/storage/Settings.luau").new(h.load("src/ui/Catalog.luau"))
        store=h.load("src/storage/ProfileStore.luau").new(f.store,model,"user-a","place-a",strict)
        store.Save(store,"once",lua_table(h.lua,{"schema":1,"values":{"jobs.enabled":True}}))
        self.assertTrue(store.SetNextLoad(store,"once")[0]);self.assertEqual(store.ConsumeNextLoad(store)[0],"once")
        a,b=strict.Paths(strict,store.ScopeKey(store)+":next");f.disk[b]="damaged tombstone"
        name,reason=store.ConsumeNextLoad(store);self.assertIsNone(name);self.assertIn("read failed",reason)
        lenient=h.load("src/storage/ProfileStore.luau").new(f.store,model,"user-a","place-a")
        self.assertFalse(lenient.SetNextLoad(lenient,"once")[0])
if __name__=="__main__":unittest.main()
