"""All modular source exports can start the inert App under one pinned release."""
import hashlib
import importlib.util
from pathlib import Path
import unittest

from engine_harness import Harness, lua_table


ROOT = Path(__file__).resolve().parents[1]


class FullBundleLoaderTests(unittest.TestCase):
    def test_all_source_modules_load_as_one_inert_release(self):
        h = Harness()
        spec = importlib.util.spec_from_file_location(
            "manifest_builder", ROOT / "tools/build_release_manifest.py")
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        commit = "a" * 40
        paths = sorted(path.relative_to(ROOT).as_posix()
                       for path in (ROOT / "src").rglob("*.luau"))
        sources = {path: (ROOT / path).read_text(encoding="utf-8")
                   for path in paths}
        entries = [{"id": builder.module_id(path), "path": path,
                    "sha256": hashlib.sha256(source.encode()).hexdigest(),
                    "deps": []}
                   for path, source in sources.items()]
        entries.sort(key=lambda row: (row["id"] == "App", row["path"]))
        manifest = lua_table(h.lua, {"schema": 1, "releaseCommit": commit,
                                     "modules": entries})
        h.lua.globals().fetchBytes = lua_table(h.lua, sources)
        h.lua.globals().pysha = lambda source: hashlib.sha256(
            source.encode()).hexdigest()
        fetch = h.lua.eval(
            "function(_, path) return fetchBytes[path] end")
        cache = h.lua.execute("""return {
            Read = function() return nil end,
            Write = function() return true end,
        }""")
        compile_ = h.lua.eval("function(source, path) return load(source, path) end")
        deps = lua_table(h.lua, {
            "Manifest": h.load("src/loader/Manifest.luau"),
            "sha256": h.lua.eval("function(source) return pysha(source) end"),
            "expectedCommit": commit,
            "Ember": h.load("tests/ember_double.lua")(),
        })
        loader = h.load("Loader.luau")
        app, reason = loader.start(fetch, cache, compile_, manifest, deps)
        self.assertIsNone(reason)
        self.assertIsNotNone(app)
        self.assertTrue(app.model.paused)
        self.assertIsNone(app.automationRuntime)
        self.assertIsNone(app.profileStore)
        self.assertEqual(len(app.ui.window.sections), 25)
        self.assertTrue(loader.close())
        h.lua.execute("""
            bootstrapGame = { PlaceId = 73897506680154 }
            function bootstrapGame:GetService(name)
                if name == 'Players' then
                    return { LocalPlayer = { Name = 'user-a' } }
                end
            end
            releaseFiles, releaseFolders = {}, {}
            releaseApi = {
                httpGet = function(url)
                    local path = url:match('/idle%-mafia%-ember/(src/.+)$')
                    return fetchBytes[path]
                end,
                isfolder = function(path)
                    return releaseFolders[path] == true
                end,
                makefolder = function(path)
                    releaseFolders[path] = true
                end,
                isfile = function(path)
                    return releaseFiles[path] ~= nil
                end,
                readfile = function(path) return releaseFiles[path] end,
                writefile = function(path, bytes)
                    releaseFiles[path] = bytes
                end,
                compile = function(source, path)
                    return load(source, path)
                end,
            }
        """)
        bootstrap = h.load("Bootstrap.luau")
        release_adapters = h.load("ReleaseAdapters.luau")
        io, reason = release_adapters.new(
            commit, h.lua.globals().releaseApi)
        self.assertIsNone(reason)
        release = lua_table(h.lua, {
            "manifest": manifest, "commit": commit,
            "place": "73897506680154", "gameVersion": "0.26.530",
            "fingerprint": "b" * 64,
            "directory": "IdleMafiaEmber",
        })
        adapters = lua_table(h.lua, {
            "Loader": loader, "Manifest": deps["Manifest"],
            "fetch": io.fetch, "cache": io.cache,
            "compile": io.compile,
            "clientGame": h.lua.globals().bootstrapGame,
            "clientRequire": h.lua.eval("function() end"),
            "clientHash": h.lua.eval(
                "function(source, algorithm) "
                "if algorithm == 'sha256' then return pysha(source) end end"),
            "Ember": deps["Ember"],
        })
        app, reason = bootstrap.start(release, adapters)
        self.assertIsNone(reason)
        self.assertTrue(app.model.paused)
        self.assertEqual(len(app.ui.window.sections), 25)
        cached_count = h.lua.eval("""function()
            local count = 0
            for _ in pairs(releaseFiles) do count = count + 1 end
            return count
        end""")
        self.assertEqual(cached_count(), len(paths))
        self.assertTrue(loader.close())
        h.lua.globals().releaseApi.httpGet = h.lua.eval(
            "function() error('offline') end")
        cached_app, reason = bootstrap.start(release, adapters)
        self.assertIsNone(reason)
        self.assertTrue(cached_app.model.paused)
        self.assertEqual(len(cached_app.ui.window.sections), 25)
        self.assertTrue(loader.close())
        entry = h.load("ExecutorEntry.luau")
        env = lua_table(h.lua, {
            "isfolder": h.lua.globals().releaseApi.isfolder,
            "makefolder": h.lua.globals().releaseApi.makefolder,
            "isfile": h.lua.globals().releaseApi.isfile,
            "readfile": h.lua.globals().releaseApi.readfile,
            "writefile": h.lua.globals().releaseApi.writefile,
            "crypt": {"hash": adapters.clientHash},
        })
        services = lua_table(h.lua, {
            "ReleaseAdapters": release_adapters,
            "Bootstrap": bootstrap,
            "Loader": loader,
            "Manifest": deps["Manifest"],
            "executorEnv": env,
            "httpGet": h.lua.globals().releaseApi.httpGet,
            "compile": h.lua.globals().releaseApi.compile,
            "clientGame": h.lua.globals().bootstrapGame,
            "clientRequire": adapters.clientRequire,
            "scheduler": h.lua.table(),
            "Ember": deps["Ember"],
        })
        entry_app, reason = entry.start(release, services)
        self.assertIsNone(reason)
        self.assertTrue(entry_app.model.paused)
        self.assertEqual(len(entry_app.ui.window.sections), 25)
        self.assertTrue(loader.close())
        app_digest = next(row["sha256"] for row in entries
                          if row["id"] == "App")
        h.lua.globals().releaseFiles[
            "IdleMafiaEmber/modules/sha256/" + app_digest
            + ".luau"] = "corrupt"
        blocked, reason = entry.start(release, services)
        self.assertIsNone(blocked)
        self.assertEqual(reason, "Missing or mismatched module: App")
        deps["activateRuntimeHost"] = True
        host, reason = loader.start(fetch, cache, compile_,
                                    manifest, deps)
        self.assertIsNone(host)
        self.assertEqual(reason, "App startup failed: Missing explicit runtime host capabilities")


if __name__ == "__main__":
    unittest.main()
