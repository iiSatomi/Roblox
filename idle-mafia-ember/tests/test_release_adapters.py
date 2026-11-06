"""Executor release adapters keep fetch and cache inside one pinned commit."""
import hashlib
import unittest

from engine_harness import Harness


class ReleaseAdaptersTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.h.lua.execute("""
            files, folders, fetched = {}, {}, {}
            api = {
                httpGet = function(url)
                    fetched[#fetched + 1] = url
                    return 'return { alive = true }'
                end,
                isfolder = function(path) return folders[path] == true end,
                makefolder = function(path) folders[path] = true end,
                isfile = function(path) return files[path] ~= nil end,
                readfile = function(path) return files[path] end,
                writefile = function(path, bytes) files[path] = bytes end,
                compile = function(bytes, name) return load(bytes, name) end,
            }
        """)
        self.adapters = self.h.load("ReleaseAdapters.luau")
        self.commit = "a" * 40
        self.api = self.h.lua.globals().api

    def test_pinned_fetch_and_verified_cache_round_trip(self):
        made, reason = self.adapters.new(self.commit, self.api)
        self.assertIsNone(reason)
        source = made.fetch(self.commit, "src/ui/Catalog.luau")
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        self.assertEqual(source, "return { alive = true }")
        self.assertEqual(self.h.lua.globals().fetched[1],
                         "https://raw.githubusercontent.com/iiSatomi/Roblox/"
                         + self.commit + "/idle-mafia-ember/src/ui/Catalog.luau")
        self.assertTrue(made.cache.Write(made.cache, self.commit,
                                         "src/ui/Catalog.luau", source, digest))
        self.assertEqual(made.cache.Read(made.cache, self.commit,
                                         "src/ui/Catalog.luau", digest), source)
        self.assertTrue(made.compile(source, "src/ui/Catalog.luau")().alive)

    def test_wrong_commit_and_unsafe_paths_do_not_fetch_or_write(self):
        made, reason = self.adapters.new(self.commit, self.api)
        self.assertIsNone(reason)
        self.assertIsNone(made.fetch("b" * 40, "src/App.luau"))
        self.assertIsNone(made.fetch(self.commit, "src/../App.luau"))
        self.assertFalse(made.cache.Write(made.cache, self.commit,
                                          "src/../App.luau", "bad"))
        self.assertEqual(len(self.h.lua.globals().fetched), 0)
        self.assertEqual(len(self.h.lua.globals().files), 0)

    def test_oversized_response_is_not_cached(self):
        self.api.httpGet = self.h.lua.eval(
            "function() return string.rep('x', 1000001) end")
        made, reason = self.adapters.new(self.commit, self.api)
        self.assertIsNone(reason)
        self.assertIsNone(made.fetch(self.commit, "src/App.luau"))

    def test_cache_requires_digest_and_keeps_versions_separate(self):
        made, reason = self.adapters.new(self.commit, self.api)
        self.assertIsNone(reason)
        path = "src/App.luau"
        old, new = "return {version=1}", "return {version=2}"
        old_hash = hashlib.sha256(old.encode()).hexdigest()
        new_hash = hashlib.sha256(new.encode()).hexdigest()
        self.assertFalse(made.cache.Write(made.cache, self.commit, path, old))
        self.assertTrue(made.cache.Write(made.cache, self.commit, path, old, old_hash))
        self.assertTrue(made.cache.Write(made.cache, self.commit, path, new, new_hash))
        self.assertEqual(made.cache.Read(made.cache, self.commit, path, old_hash), old)
        self.assertEqual(made.cache.Read(made.cache, self.commit, path, new_hash), new)
        self.assertIsNone(made.cache.Read(made.cache, self.commit, path))
        self.assertIsNone(made.cache.Read(made.cache, "b" * 40, path, old_hash))


if __name__ == "__main__":
    unittest.main()
