"""Storage discovery verifies scoped keys rather than trusting filenames or listings."""
import unittest
import test_redundant_store as fixture
from engine_harness import lua_table
class StorageDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.RedundantStoreTests();self.f.setUp();self.h=self.f.h;self.store=self.f.store
        self.h.lua.globals().discoveryList=lambda path:lua_table(self.h.lua,sorted(self.f.disk))
        self.store.files.ListFiles=self.h.lua.eval("function(self,path) return discoveryList(path) end")
    def test_verified_keys_are_unique_across_both_slots(self):
        for key in ("old-release","current-release"):
            for value in (1,2):self.store.Write(self.store,key,lua_table(self.h.lua,{"value":value}))
        keys,reason=self.store.ListKeys(self.store);self.assertIsNone(reason)
        self.assertEqual(sorted(keys.values()),["current-release","old-release"])
    def test_missing_enumeration_and_malformed_slot_do_not_report_an_empty_store(self):
        self.store.files.ListFiles=None;self.assertIsNone(self.store.ListKeys(self.store)[0])
        self.store.files.ListFiles=self.h.lua.eval("function(self,path) return discoveryList(path) end")
        self.store.Write(self.store,"old-release",lua_table(self.h.lua,{"value":1}))
        self.f.disk[self.store.Paths(self.store,"old-release")[0]]="damaged"
        self.assertIsNone(self.store.ListKeys(self.store)[0])
    def test_wrong_path_hash_or_sparse_inventory_is_refused(self):
        for values in (("elsewhere/"+"a"*64+".a.json",),):
            self.store.files.ListFiles=self.h.lua.eval("function() return {'"+values[0]+"'} end")
            self.assertIsNone(self.store.ListKeys(self.store)[0])
        self.store.files.ListFiles=self.h.lua.eval("function() return {[2]='state/a.a.json'} end")
        self.assertIsNone(self.store.ListKeys(self.store)[0])
    def test_valid_envelope_copied_to_another_hash_path_is_refused(self):
        self.store.Write(self.store,"old-release",lua_table(self.h.lua,{"value":1}))
        original=self.store.Paths(self.store,"old-release")[0]
        self.f.disk["state/"+"f"*64+".a.json"]=self.f.disk.pop(original)
        self.assertIsNone(self.store.ListKeys(self.store)[0])
    def test_sparse_duplicate_and_oversized_discovery_are_not_empty_success(self):
        for expression in ("{[1]='state/a',[3]='state/b'}","{'state/a','state/a'}"):
            self.store.files.ListFiles=self.h.lua.eval("function() return "+expression+" end")
            self.assertIsNone(self.store.ListKeys(self.store)[0])
        self.store.files.ListFiles=self.h.lua.eval("function() local rows={};for i=1,513 do rows[i]='state/'..i end;return rows end")
        self.assertIsNone(self.store.ListKeys(self.store)[0])
    def test_strict_newer_damage_cannot_be_hidden_by_an_older_valid_slot(self):
        self.store.strictRecovery=True
        self.store.Write(self.store,"old-release",lua_table(self.h.lua,{"value":1}))
        self.store.Write(self.store,"old-release",lua_table(self.h.lua,{"value":2}))
        a,b=self.store.Paths(self.store,"old-release");self.f.disk[b]="damaged newer commit"
        self.assertIsNone(self.store.ListKeys(self.store)[0])
if __name__=="__main__":unittest.main()
