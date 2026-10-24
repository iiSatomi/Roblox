"""The bootstrap pins a release and starts current-client mode only by opt-in."""
import hashlib
import unittest

from engine_harness import Harness, lua_table


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.h.lua.execute("""
            seen = nil
            fakeLoader = { start = function(fetch, cache, compile,
                    manifest, dependencies)
                seen = { manifest = manifest, dependencies = dependencies,
                    fetch = fetch, cache = cache, compile = compile }
                return { alive = true }, nil
            end }
            fakeGame = { PlaceId = 73897506680154 }
            function fakeGame:GetService(name)
                if name == 'Players' then
                    return { LocalPlayer = { Name = 'user-a' } }
                end
                if name == 'HttpService' then return {} end
            end
        """)
        self.h.lua.globals().pysha = lambda source: hashlib.sha256(
            source.encode()).hexdigest()
        self.bootstrap = self.h.load("Bootstrap.luau")
        self.release = lua_table(self.h.lua, {
            "manifest": {"releaseCommit": "a" * 40},
            "commit": "a" * 40,
            "place": "73897506680154",
            "gameVersion": "0.26.530",
            "fingerprint": "b" * 64,
            "directory": "IdleMafiaEmber",
            "allowedFeatures": {"jobs": True, "bosses": True},
        })
        self.adapters = lua_table(self.h.lua, {
            "Loader": self.h.lua.globals().fakeLoader,
            "Manifest": self.h.lua.table(),
            "fetch": self.h.lua.eval("function() end"),
            "cache": self.h.lua.table(),
            "compile": self.h.lua.eval("function() end"),
            "clientGame": self.h.lua.globals().fakeGame,
            "clientRequire": self.h.lua.eval("function() end"),
            "clientHash": self.h.lua.eval(
                "function(source, algorithm) "
                "if algorithm == 'sha256' then return pysha(source) end end"),
            "executorEnv": self.h.lua.table(),
            "scheduler": self.h.lua.table(),
            "Ember": self.h.lua.table(),
        })

    def test_default_is_inert_and_identity_is_current_player(self):
        app, reason = self.bootstrap.start(self.release, self.adapters)
        self.assertIsNone(reason)
        self.assertIsNotNone(app)
        deps = self.h.lua.globals().seen.dependencies
        self.assertFalse(deps.activateRuntimeHost)
        self.assertFalse(deps.activateAutomation)
        self.assertFalse(deps.activateStorage)
        self.assertFalse(deps.activateCurrentClient)
        self.assertEqual(deps.identity.account, "user-a")
        self.assertEqual(deps.identity.place, "73897506680154")
        self.assertEqual(deps.sha256("data"), hashlib.sha256(
            b"data").hexdigest())

    def test_explicit_current_runtime_mode_passes_pins(self):
        app, reason = self.bootstrap.start(
            self.release, self.adapters, True)
        self.assertIsNone(reason)
        deps = self.h.lua.globals().seen.dependencies
        self.assertTrue(deps.activateRuntimeHost)
        self.assertTrue(deps.activateAutomation)
        self.assertTrue(deps.activateStorage)
        self.assertTrue(deps.activateCurrentClient)
        self.assertEqual(deps.expectedCommit, "a" * 40)
        self.assertEqual(deps.expectedGameVersion, "0.26.530")
        self.assertEqual(deps.fingerprint, "b" * 64)
        self.assertEqual(deps.release, "a" * 40)
        self.assertTrue(deps.allowedFeatures.jobs)
        self.assertTrue(deps.allowedFeatures.bosses)

    def test_active_release_requires_explicit_allowlist(self):
        self.release["allowedFeatures"] = None
        app, reason = self.bootstrap.start(self.release, self.adapters, True)
        self.assertIsNone(app)
        self.assertEqual(reason,
                         "Functional release needs an explicit feature allowlist")
        self.assertIsNone(self.h.lua.globals().seen)

    def test_wrong_place_or_manifest_pin_never_calls_loader(self):
        self.h.lua.globals().fakeGame.PlaceId = 1
        self.assertIsNone(self.bootstrap.start(
            self.release, self.adapters, True)[0])
        self.assertIsNone(self.h.lua.globals().seen)
        self.h.lua.globals().fakeGame.PlaceId = 73897506680154
        self.release.manifest.releaseCommit = "c" * 40
        self.assertIsNone(self.bootstrap.start(
            self.release, self.adapters, True)[0])
        self.assertIsNone(self.h.lua.globals().seen)

    def test_broken_hash_provider_never_calls_loader(self):
        self.adapters.clientHash = self.h.lua.eval(
            "function() return string.rep('0', 64) end")
        app, reason = self.bootstrap.start(
            self.release, self.adapters, True)
        self.assertIsNone(app)
        self.assertEqual(reason, "Bootstrap SHA-256 unavailable")
        self.assertIsNone(self.h.lua.globals().seen)


if __name__ == "__main__":
    unittest.main()
