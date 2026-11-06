"""Executor file capabilities are checked and confined to relative paths."""
import unittest

from engine_harness import Harness


class ExecutorStorageAdapterTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.adapter = self.h.load(
            "src/storage/ExecutorStorageAdapter.luau")
        self.api = self.h.lua.execute("""return {
            folders = {}, files = {},
            isfolder = function(path) return api.folders[path] == true end,
            makefolder = function(path) api.folders[path] = true end,
            isfile = function(path) return api.files[path] ~= nil end,
            readfile = function(path) return api.files[path] end,
            writefile = function(path, value) api.files[path] = value end,
            jsonEncode = function() return '{}' end,
            jsonDecode = function() return {} end,
            hash = function() return string.rep('A', 64) end,
        }""")
        self.h.lua.globals().api = self.api

    def test_relative_directory_and_file_roundtrip(self):
        caps, reason = self.adapter.new(self.api)
        self.assertIsNone(reason)
        self.assertTrue(caps["files"].EnsureDirectory(
            caps["files"], "IdleMafiaEmber/state/profiles"))
        self.assertTrue(self.api.folders["IdleMafiaEmber/state"])
        path = "IdleMafiaEmber/state/profiles/a.json"
        self.assertIsNone(caps["files"].ReadFile(caps["files"], path))
        self.assertTrue(caps["files"].WriteFile(
            caps["files"], path, "{}"))
        self.assertEqual(caps["files"].ReadFile(caps["files"], path), "{}")
        self.assertEqual(caps["sha256"]("bytes"), "a" * 64)

    def test_unsafe_path_and_wrong_hash_fail_closed(self):
        caps, _ = self.adapter.new(self.api)
        self.assertFalse(caps["files"].EnsureDirectory(
            caps["files"], "../elsewhere"))
        self.assertFalse(caps["files"].WriteFile(
            caps["files"], "../elsewhere/a", "x"))
        with self.assertRaises(Exception):
            caps["files"].ReadFile(caps["files"], "../elsewhere/a")
        self.api["hash"] = self.h.lua.eval("function() return 'abc' end")
        with self.assertRaises(Exception):
            caps["sha256"]("bytes")

    def test_missing_capability_does_not_create_storage(self):
        self.api["writefile"] = None
        caps, reason = self.adapter.new(self.api)
        self.assertIsNone(caps)
        self.assertIn("Missing", reason)


    def test_optional_listing_confines_and_normalizes_direct_children(self):
        self.api.listfiles=self.h.lua.eval("function() return {[[IdleMafiaEmber\\state\\record.a.json]]} end")
        caps,_=self.adapter.new(self.api);paths,reason=caps.files.ListFiles(caps.files,"IdleMafiaEmber/state")
        self.assertIsNone(reason);self.assertEqual(paths[1],"IdleMafiaEmber/state/record.a.json")
        for code in ("return {'elsewhere/record.a.json'}","return {'IdleMafiaEmber/state/../record.a.json'}","return {[1]='IdleMafiaEmber/state/a',[3]='IdleMafiaEmber/state/b'}"):
            self.api.listfiles=self.h.lua.eval("function() "+code+" end")
            self.assertIsNone(caps.files.ListFiles(caps.files,"IdleMafiaEmber/state")[0])
    def test_missing_listing_is_unavailable_without_reading_or_writing_files(self):
        caps,_=self.adapter.new(self.api);paths,reason=caps.files.ListFiles(caps.files,"IdleMafiaEmber/state")
        self.assertIsNone(paths);self.assertIn("unavailable",reason.lower());self.assertEqual(len(self.api.files),0)

if __name__ == "__main__":
    unittest.main()
