"""The active entry verifies bytes and fails closed without current game bindings."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path
import subprocess
import unittest

from engine_harness import Harness, lua_table


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "1e6b6805f7ddf0545d433396633072a3da2e159a"
MANIFEST = "f01fff0120543ca65a57b594fda01b957b6cd813"


@lru_cache(maxsize=3)
def committed_tree(commit):
    names = subprocess.check_output(["git", "ls-tree", "--full-tree", "-r", "--name-only", commit], cwd=ROOT.parent).decode("utf-8").splitlines()
    names = [name for name in names if name.startswith("idle-mafia-ember/")]
    request = "".join(f"{commit}:{name}\n" for name in names).encode("utf-8")
    output = subprocess.check_output(["git", "cat-file", "--batch"], input=request, cwd=ROOT.parent)
    files, cursor = {}, 0
    for name in names:
        end = output.index(b"\n", cursor)
        header = output[cursor:end].split()
        assert header[1] == b"blob", name
        size = int(header[2]); cursor = end + 1
        files[name.removeprefix("idle-mafia-ember/")] = output[cursor:cursor+size].decode("utf-8")
        cursor += size
        assert output[cursor:cursor+1] == b"\n", name
        cursor += 1
    assert cursor == len(output)
    return files

def committed(commit, path):
    return committed_tree(commit)[path]


class RuntimeEntryTests(unittest.TestCase):
    def test_only_reviewed_rollout_builds_reach_loader_initialization(self):
        source = (ROOT / "RuntimeEntry.luau").read_text(encoding="utf-8")
        for build in (654,655,656):
            h=Harness();h.lua.globals().game=h.lua.table(PlaceVersion=build)
            with self.assertRaisesRegex(Exception,"SHA-256 API unavailable" if build in (654,655) else "Unreviewed Idle Mafia build"):
                h.lua.execute(source)

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
            "0aebb331911619d0c791de1d0d3e9b2e51ead3fb4472cd038807155ad8bcf412"
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
            game = { PlaceId = 73897506680154, PlaceVersion = 654, sends = 0 }
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
