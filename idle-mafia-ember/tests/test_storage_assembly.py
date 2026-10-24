"""Profile and write-ahead stores have separate paths and recovery rules."""
import unittest

from engine_harness import Harness, lua_table


class StorageAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.assembly = self.h.load("src/storage/StorageAssembly.luau")
        self.deps = lua_table(self.h.lua, {
            "RedundantStore": self.h.load("src/storage/RedundantStore.luau"),
            "directory": "IdleMafiaEmber/state",
        })
        self.deps.files = self.h.lua.execute("""return {made = {}, fail = false,
            EnsureDirectory = function(self, path)
                if self.fail then return false end
                self.made[#self.made + 1] = path
                return true
            end,
            ReadFile = function() return nil end,
            WriteFile = function() return true end,
        }""")
        self.deps.codec = self.h.lua.execute("""return {
            Encode = function() return '{}' end,
            Decode = function() return {} end,
        }""")
        self.deps.sha256 = self.h.lua.eval(
            "function() return string.rep('a', 64) end")

    def test_separate_profile_and_strict_checkpoint_slots(self):
        stores, reason = self.assembly.new(self.deps)
        self.assertIsNone(reason)
        self.assertFalse(stores.ProfileStorage.strictRecovery)
        self.assertTrue(stores.storage.strictRecovery)
        self.assertEqual(len(self.deps.files.made), 3)
        profile = stores.ProfileStorage.Paths(stores.ProfileStorage, "key")
        checkpoint = stores.storage.Paths(stores.storage, "key")
        self.assertIn("/profiles/", profile[0])
        self.assertIn("/checkpoints/", checkpoint[0])

    def test_unsafe_directory_or_failed_creation_blocks_both_stores(self):
        self.deps.directory = "../elsewhere"
        stores, reason = self.assembly.new(self.deps)
        self.assertIsNone(stores)
        self.assertIn("unsafe", reason)
        self.deps.directory = "IdleMafiaEmber/state"
        self.deps.files.fail = True
        stores, reason = self.assembly.new(self.deps)
        self.assertIsNone(stores)
        self.assertIn("directory", reason)


if __name__ == "__main__":
    unittest.main()
