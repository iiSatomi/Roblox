"""Exercise the published UI entry against committed bytes without live I/O."""
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from urllib.parse import urlsplit

from engine_harness import Harness, lua_table


ROOT = Path(__file__).resolve().parents[1]
class TestEntryTests(unittest.TestCase):
    def start_entry(self, tamper_path=None):
        h = Harness()
        source = (ROOT / "TestEntry.luau").read_text(encoding="utf-8")
        # Lupa has no Roblox GUI services; substitute the existing UI double.
        # The Ember fixture hash stands in for the independently reviewed pin.
        ember_bytes = "offline Ember fixture"
        def fetch(url):
            if url == "https://rbx.lol/ember.lua":
                return ember_bytes
            parsed = urlsplit(url)
            self.assertEqual(parsed.scheme, "https")
            self.assertEqual(parsed.netloc, "raw.githubusercontent.com")
            self.assertFalse(parsed.query or parsed.fragment)
            owner, repository, commit, path = parsed.path.lstrip("/").split("/", 3)
            self.assertEqual((owner, repository), ("iiSatomi", "Roblox"))
            self.assertRegex(commit, r"^[0-9a-f]{40}$")
            self.assertTrue(path.startswith("idle-mafia-ember/"))
            self.assertNotIn("..", path.split("/"))
            # Resolve the requested commit as GitHub does. Checkout files may
            # be newer and may contain Windows line endings.
            blob = subprocess.check_output([
                "git", "show", commit + ":" + path,
            ], cwd=ROOT).decode("utf-8")
            if path == tamper_path:
                blob += "\nerror('tampered module executed')\n"
            return blob
        h.lua.globals().pyget = fetch
        h.lua.globals().pyhash = lambda value, algorithm: (
            "c6ec2ad2ad732a2ed704d044fd068b685d7e6c2613f60a07c39316666576390a"
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
        return h.lua.execute(source)

    def test_entry_starts_paused_ui_from_verified_pinned_commit_bytes(self):
        app = self.start_entry()
        self.assertTrue(app.model.paused)
        self.assertIsNone(app.automationRuntime)
        self.assertIsNone(app.profileStore)
        self.assertEqual(len(app.ui.window.sections), 25)

    def test_tampered_pinned_module_is_rejected_before_execution(self):
        with self.assertRaisesRegex(Exception, "SHA-256 mismatch: Loader.luau"):
            self.start_entry("idle-mafia-ember/Loader.luau")


if __name__ == "__main__":
    unittest.main()
