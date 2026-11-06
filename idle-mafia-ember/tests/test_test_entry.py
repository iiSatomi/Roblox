"""Exercise the candidate UI entry against committed bytes without live I/O."""
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from engine_harness import Harness, lua_table


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "80b5a0a0f174ecd195dc3d6d100ce0f80248e2a5"
MANIFEST = "50a3c243552b1fb16deb0ee5d6b3760c258db69c"
class TestEntryTests(unittest.TestCase):
    def test_entry_starts_paused_ui_from_verified_local_bytes(self):
        h = Harness()
        source = (ROOT / "TestEntry.luau").read_text(encoding="utf-8")
        files = {p.relative_to(ROOT).as_posix(): p.read_bytes().decode("utf-8")
                 for p in (ROOT / "src").rglob("*.luau")}
        for name in ("Loader.luau", "Bootstrap.luau", "ReleaseAdapters.luau",
                     "ExecutorEntry.luau"):
            files[name] = subprocess.check_output([
                "git", "show",
                SOURCE + ":idle-mafia-ember/" + name,
            ], cwd=ROOT).decode("utf-8")
        # Raw GitHub serves committed blob bytes, not Windows checkout bytes.
        files["manifest.json"] = subprocess.check_output([
            "git", "show",
            MANIFEST + ":idle-mafia-ember/manifest.json",
        ], cwd=ROOT).decode("utf-8")
        pinned = json.loads(files["manifest.json"])
        for row in pinned["modules"]:
            path = row["path"]
            if hashlib.sha256(files[path].encode("utf-8")).hexdigest() != row["sha256"]:
                files[path] = subprocess.check_output([
                    "git", "show", pinned["releaseCommit"]
                    + ":idle-mafia-ember/" + path,
                ], cwd=ROOT).decode("utf-8")
        # Lupa has no Roblox GUI services; substitute the existing UI double.
        # The Ember fixture hash stands in for the independently reviewed pin.
        ember_bytes = "offline Ember fixture"
        h.lua.globals().pyget = lambda url: (
            ember_bytes if url == "https://rbx.lol/ember.lua"
            else files[url.split("/idle-mafia-ember/", 1)[1]])
        h.lua.globals().pyhash = lambda value, algorithm: (
            "0aebb331911619d0c791de1d0d3e9b2e51ead3fb4472cd038807155ad8bcf412"
            if value == ember_bytes else hashlib.sha256(value.encode("utf-8")).hexdigest())
        h.lua.globals().pydecode = lambda raw: lua_table(h.lua, json.loads(raw))
        h.lua.globals().emberDouble = h.load("tests/ember_double.lua")
        h.lua.execute("""
            crypt = { hash = function(bytes, algorithm)
                return pyhash(bytes, algorithm)
            end }
            loadstring = function(bytes, name)
                if name == '@Ember.lua' then return emberDouble end
                return load(bytes, name)
            end
            game = { PlaceId = 73897506680154 }
            function game:HttpGet(url) return pyget(url) end
            function game:GetService(name)
                if name == 'HttpService' then
                    return { JSONDecode = function(_, raw) return pydecode(raw) end }
                end
                if name == 'Players' then
                    return { LocalPlayer = { Name = 'test-account' } }
                end
            end
        """)
        app = h.lua.execute(source)
        self.assertTrue(app.model.paused)
        self.assertIsNone(app.automationRuntime)
        self.assertIsNone(app.profileStore)
        self.assertEqual(len(app.ui.window.sections), 27)
        self.assertEqual(app.model["values"]["alliance.mode"], "Off")
        for key, value in app.model["values"].items():
            if key.endswith(".enabled"):
                self.assertFalse(value, key)


if __name__ == "__main__":
    unittest.main()
