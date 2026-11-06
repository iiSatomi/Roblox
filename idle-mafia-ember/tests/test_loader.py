"""Inert release loading under fake fetch/cache/compiler adapters."""
import hashlib
import unittest

from engine_harness import Harness, lua_table


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.lua = self.h.lua
        self.lua.execute("execCount=0; startCount=0; destroyCount=0; compileCount=0")
        self.loader = self.h.load("Loader.luau")
        self.validator = self.h.load("src/loader/Manifest.luau")
        self.bytes = {
            "src/A.luau": "execCount=execCount+1; return {name='A'}",
            "src/App.luau": "execCount=execCount+1; return {start=function(deps) "
                "startCount=startCount+1; return {Destroy=function() "
                "destroyCount=destroyCount+1 end} end}",
        }
        self.manifest = self.make_manifest("a" * 40)
        self.lua.globals().fetchBytes = lua_table(self.lua, self.bytes)
        self.lua.globals().cacheBytes = self.lua.table()
        self.lua.globals().fetchCalls = self.lua.table()
        self.fetch = self.lua.eval("""
            function(commit, path)
                fetchCalls[#fetchCalls+1] = commit .. ':' .. path
                return fetchBytes[path]
            end
        """)
        self.cache = self.lua.execute("""
            return { Read=function(self, commit, path) return cacheBytes[commit .. ':' .. path] end,
                Write=function(self, commit, path, bytes)
                    cacheBytes[commit .. ':' .. path] = bytes
                end }
        """)
        self.compile = self.lua.eval("""
            function(bytes, path)
                compileCount=compileCount+1
                return load(bytes, path)
            end
        """)
        self.lua.globals().pysha = lambda blob: hashlib.sha256(blob.encode()).hexdigest()
        self.sha256 = self.lua.eval("function(bytes) return pysha(bytes) end")
        self.deps = lua_table(self.lua, {"Manifest": self.validator,
                                         "sha256": self.sha256,
                                         "expectedCommit": "a" * 40})

    def make_manifest(self, commit):
        def entry(name, deps):
            path = f"src/{name}.luau"
            return {"id": name, "path": path,
                    "sha256": hashlib.sha256(self.bytes[path].encode()).hexdigest(),
                    "deps": deps}
        return {"schema": 1, "releaseCommit": commit,
                "modules": [entry("App", ["A"]), entry("A", [])]}

    def start(self):
        return self.loader.start(
            self.fetch, self.cache, self.compile,
            lua_table(self.lua, self.manifest), self.deps,
        )

    def test_complete_release_compiles_all_then_starts_once(self):
        app, reason = self.start()
        self.assertIsNone(reason)
        self.assertIsNotNone(app)
        self.assertEqual(self.lua.globals().compileCount, 2)
        self.assertEqual(self.lua.globals().execCount, 2)
        self.assertEqual(self.lua.globals().startCount, 1)
        again, reason = self.start()
        self.assertIsNone(reason)
        self.assertTrue(self.lua.eval("function(a,b) return a==b end")(again, app))
        self.assertEqual(self.lua.globals().startCount, 1)

    def test_missing_or_wrong_download_never_compiles_or_starts(self):
        for failure in (None, "tampered"):
            with self.subTest(failure=failure):
                self.lua.globals().fetchBytes["src/A.luau"] = failure
                app, reason = self.start()
                self.assertIsNone(app)
                self.assertIsNotNone(reason)
                self.assertEqual(self.lua.globals().compileCount, 0)
                self.assertEqual(self.lua.globals().startCount, 0)

    def test_compile_failure_never_executes_any_module(self):
        self.bytes["src/A.luau"] = "this is invalid luau/lua"
        self.manifest = self.make_manifest("a" * 40)
        self.lua.globals().fetchBytes = lua_table(self.lua, self.bytes)
        app, reason = self.start()
        self.assertIsNone(app)
        self.assertIsNotNone(reason)
        self.assertEqual(self.lua.globals().execCount, 0)
        self.assertEqual(self.lua.globals().startCount, 0)

    def test_verified_cache_recovers_failed_fetch(self):
        self.lua.globals().fetchBytes["src/A.luau"] = None
        self.lua.globals().cacheBytes["a" * 40 + ":src/A.luau"] = self.bytes["src/A.luau"]
        app, reason = self.start()
        self.assertIsNotNone(app)
        self.assertIsNone(reason)

    def test_cache_from_another_commit_cannot_rescue_missing_module(self):
        self.lua.globals().fetchBytes["src/A.luau"] = None
        self.lua.globals().cacheBytes["b" * 40 + ":src/A.luau"] = self.bytes["src/A.luau"]
        app, reason = self.start()
        self.assertIsNone(app)
        self.assertIsNotNone(reason)
        self.assertTrue(all(call.startswith("a" * 40) for call in self.lua.globals().fetchCalls.values()))

    def test_unsafe_manifest_never_fetches(self):
        self.manifest["modules"][1]["path"] = "src/../secret.luau"
        app, reason = self.start()
        self.assertIsNone(app)
        self.assertIsNotNone(reason)
        self.assertEqual(len(self.lua.globals().fetchCalls), 0)

    def test_manifest_cannot_choose_another_commit(self):
        self.manifest["releaseCommit"] = "b" * 40
        app, reason = self.start()
        self.assertIsNone(app)
        self.assertEqual(reason, "Release commit differs from bootstrap pin")
        self.assertEqual(len(self.lua.globals().fetchCalls), 0)

    def test_close_destroys_app_and_allows_fresh_start(self):
        self.start()
        self.assertEqual(self.loader.close(), True)
        self.assertEqual(self.lua.globals().destroyCount, 1)
        self.start()
        self.assertEqual(self.lua.globals().startCount, 2)

    def test_ui_unload_allows_fresh_start_without_loader_close(self):
        app, _ = self.start()
        app["alive"] = False
        next_app, reason = self.start()
        self.assertIsNone(reason)
        self.assertIsNotNone(next_app)
        self.assertEqual(self.lua.globals().startCount, 2)

    def test_execution_error_prevents_app_start(self):
        self.bytes["src/A.luau"] = "error('module failed')"
        self.manifest = self.make_manifest("a" * 40)
        self.lua.globals().fetchBytes = lua_table(self.lua, self.bytes)
        app, reason = self.start()
        self.assertIsNone(app)
        self.assertIsNotNone(reason)
        self.assertEqual(self.lua.globals().compileCount, 2)
        self.assertEqual(self.lua.globals().startCount, 0)

    def test_different_release_cannot_start_beside_active_app(self):
        self.start()
        self.manifest["releaseCommit"] = "b" * 40
        app, reason = self.start()
        self.assertIsNone(app)
        self.assertEqual(reason, "Release commit differs from bootstrap pin")


if __name__ == "__main__":
    unittest.main()
