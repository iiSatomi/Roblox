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
        self.assertEqual(source, "return { alive = true }")
        self.assertEqual(self.h.lua.globals().fetched[1],
                         "https://raw.githubusercontent.com/iiSatomi/Roblox/"
                         + self.commit + "/idle-mafia-ember/src/ui/Catalog.luau")
        digest = hashlib.sha256(source.encode()).hexdigest()
        self.assertTrue(made.cache.Write(made.cache, self.commit,
                                         "src/ui/Catalog.luau", source,
                                         digest))
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

    def test_verified_content_cache_reuses_unchanged_module_across_commits(self):
        first, reason = self.adapters.new(self.commit, self.api)
        self.assertIsNone(reason)
        other_commit = "b" * 40
        second, reason = self.adapters.new(other_commit, self.api)
        self.assertIsNone(reason)
        path = "src/ui/Catalog.luau"
        source = "return { alive = true }"
        digest = hashlib.sha256(source.encode()).hexdigest()
        self.assertTrue(first.cache.Write(first.cache, self.commit,
                                          path, source, digest))
        self.assertEqual(second.cache.Read(second.cache, other_commit,
                                           path, digest), source)
        self.assertIsNone(second.cache.Read(second.cache, other_commit,
                                            path, "c" * 64))


if __name__ == "__main__":
    unittest.main()
