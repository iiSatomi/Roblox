"""The active entry verifies bytes and fails closed without current game bindings."""
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from engine_harness import Harness, lua_table


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "256d4cd5eaf5ecf4a12536972a1e73b66fab0ef9"
MANIFEST = "77753a1e45db5036ab510ce05b1655602cf71129"


def committed(commit, path):
    return subprocess.check_output([
        "git", "show", commit + ":idle-mafia-ember/" + path,
    ], cwd=ROOT).decode("utf-8")


class RuntimeEntryTests(unittest.TestCase):
    def test_missing_current_client_blocks_before_any_gameplay_call(self):
        h = Harness()
        source = (ROOT / "RuntimeEntry.luau").read_text(encoding="utf-8")
        manifest_bytes = committed(MANIFEST, "manifest.json")
        paths = json.loads(manifest_bytes)["modules"]
        files = {row["path"]: committed(SOURCE, row["path"])
                 for row in paths}
        for path in ("Loader.luau", "Bootstrap.luau", "ReleaseAdapters.luau",
                     "ExecutorEntry.luau"):
            files[path] = committed(SOURCE, path)
        files["manifest.json"] = manifest_bytes
        ember = "offline Ember fixture"
        h.lua.globals().pyget = lambda url: (
            ember if url == "https://rbx.lol/ember.lua"
            else files[url.split("/idle-mafia-ember/", 1)[1]])
        h.lua.globals().pyhash = lambda value, algorithm: (
            "c6ec2ad2ad732a2ed704d044fd068b685d7e6c2613f60a07c39316666576390a"
            if value == ember else hashlib.sha256(value.encode("utf-8")).hexdigest())
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
            task = {
                delay = function() return 1 end,
                cancel = function() end,
                defer = function() end,
            }
            files, folders = {}, {}
            isfolder = function(path) return folders[path] == true end
            makefolder = function(path) folders[path] = true end
            isfile = function(path) return files[path] ~= nil end
            readfile = function(path) return files[path] end
            writefile = function(path, value) files[path] = value end
            game = { PlaceId = 73897506680154, sends = 0 }
            function game:HttpGet(url) return pyget(url) end
            function game:GetService(name)
                if name == 'HttpService' then
                    return {
                        JSONDecode = function(_, raw) return pydecode(raw) end,
                        GenerateGUID = function(_, wrapped)
                            assert(wrapped == false)
                            return 'entry-session-a'
                        end,
                    }
                end
                if name == 'Players' then
                    return { LocalPlayer = { Name = 'test-account' } }
                end
            end
        """)
        with self.assertRaisesRegex(Exception, "App startup failed: Current client bindings unavailable"):
            h.lua.execute(source)
        self.assertEqual(h.lua.globals().game.sends, 0)


if __name__ == "__main__":
    unittest.main()
