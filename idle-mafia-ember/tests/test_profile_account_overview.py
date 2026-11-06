"""Account overview is bounded same-place read-only metadata, never profile activation."""
import unittest
import test_profile_management as fixture
from engine_harness import lua_table
class ProfileAccountOverviewTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.ProfileManagementTests();self.f.setUp();self.h=self.f.h;self.app=self.f.app;self.store=self.app.profileStore
        self.f.base.storage.ListKeys=self.h.lua.eval("function(self) local keys={};for key in pairs(self.data) do keys[#keys+1]=key end;table.sort(keys);return keys,nil end")
    def tearDown(self):self.f.tearDown()
    def other(self,account,place=None):
        return self.f.base.module.new(self.f.base.storage,self.app.model,account,place or self.store.place)
    def test_same_place_accounts_show_saved_autoload_and_once_choices_without_writes(self):
        self.app.SaveProfile(self.app,"main")
        other=self.other("other");other.Save(other,"farm",lua_table(self.h.lua,{"schema":1,"values":{"jobs.enabled":True}}));other.SetAutoload(other,"farm");other.SetNextLoad(other,"farm")
        elsewhere=self.other("elsewhere","place-b");elsewhere.Save(elsewhere,"secret",lua_table(self.h.lua,{"schema":1,"values":{}}))
        self.f.base.storage.Write=self.h.lua.eval("function() error('overview must never write') end")
        overview,reason=self.store.AccountOverview(self.store);self.assertIsNone(reason)
        self.assertEqual([row.account for row in overview.rows.values()],["user-a","other"])
        self.assertEqual(overview.rows[2].autoload,"farm");self.assertEqual(overview.rows[2].once,"farm")
        self.assertEqual(other.GetNextLoad(other)[0],"farm");self.assertFalse(self.app.model["values"]["jobs.enabled"])
        self.app.ui.profiles.RefreshStorage(self.app.ui.profiles)
        self.assertIn("other",self.app.ui.profiles.accountStatus.value)
    def test_unavailable_discovery_is_explicit_and_does_not_claim_no_accounts(self):
        self.f.base.storage.ListKeys=None
        overview,reason=self.store.AccountOverview(self.store);self.assertIsNone(overview);self.assertIn("discovery",reason.lower())
        self.app.ui.profiles.RefreshStorage(self.app.ui.profiles)
        self.assertIn("Unavailable",self.app.ui.profiles.accountStatus.value)
    def test_corrupt_foreign_selection_is_displayed_as_unavailable(self):
        other=self.other("other");other.Save(other,"farm",lua_table(self.h.lua,{"schema":1,"values":{}}))
        self.f.base.storage.data[other.ScopeKey(other)+":autoload"]=lua_table(self.h.lua,{"version":1,"account":"wrong","place":"place-a","name":"farm"})
        overview,reason=self.store.AccountOverview(self.store);self.assertIsNone(reason)
        self.assertIn("unavailable",overview.rows[1].status.lower())
    def test_overview_limit_is_reported_without_writing_or_cross_place_rows(self):
        for index in range(27):
            other=self.other("account-"+str(index));other.Save(other,"farm",lua_table(self.h.lua,{"schema":1,"values":{}}))
        overview,reason=self.store.AccountOverview(self.store);self.assertIsNone(reason)
        self.assertEqual(len(overview.rows),25);self.assertTrue(overview.truncated)
if __name__=="__main__":unittest.main()
