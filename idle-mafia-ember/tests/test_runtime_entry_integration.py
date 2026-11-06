"""Execute the real entry and current bundle with synthetic release pins.

Only native discovery/source observation and Ember rendering are doubled. Pins
are substituted in memory: these tests do not certify the published release.
"""
import hashlib
import importlib.util
import json
import re
import unittest
from pathlib import Path

from engine_harness import Harness, lua_table
from runtime_entry_fixture import native_catalog

ROOT = Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def plain(value):
    if hasattr(value, "items"):
        pairs = dict(value.items())
        if pairs and set(pairs) == set(range(1, len(pairs) + 1)):
            return [plain(pairs[i]) for i in range(1, len(pairs) + 1)]
        return {str(k): plain(v) for k, v in pairs.items()}
    return value


class RuntimeEntryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.h = h = Harness()
        self.source_commit, self.manifest_commit = "a" * 40, "b" * 40
        spec = importlib.util.spec_from_file_location(
            "entry_manifest_builder", ROOT / "tools/build_release_manifest.py")
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        self.paths = sorted(p.relative_to(ROOT).as_posix()
                            for p in (ROOT / "src").rglob("*.luau"))
        sources = {p: (ROOT / p).read_text(encoding="utf-8") for p in self.paths}
        sources["src/transport/NativeClientBindings.luau"] = (
            "return {read=function() return fixtureBindings end}")
        sources["src/transport/NativeClientObserver.luau"] = (
            "return {new=function() return {Read=function() return "
            "{place='73897506680154',account='user-a',"
            "gameVersion='fixture-current',fingerprint=string.rep('c',64)} end} end}")
        entries = [{"id": builder.module_id(p), "path": p,
                    "sha256": digest(s), "deps": []} for p, s in sources.items()]
        entries.sort(key=lambda row: (row["id"] == "App", row["path"]))
        manifest_bytes = json.dumps({"schema": 1, "releaseCommit": self.source_commit,
                                     "modules": entries})
        for p in ("Loader.luau", "Bootstrap.luau", "ReleaseAdapters.luau", "ExecutorEntry.luau"):
            sources[p] = (ROOT / p).read_text(encoding="utf-8")
        sources["manifest.json"] = manifest_bytes
        ember_bytes = (ROOT / "tests/ember_double.lua").read_text(encoding="utf-8") + "\n"
        # The double file returns a factory; the external URL returns a library.
        ember_bytes = "local e=(function()\n" + ember_bytes + "\nend)()(); e.requiredParent=fixtureParent; return e"
        self.ember_bytes = ember_bytes
        h.lua.globals().fixtureSources = lua_table(h.lua, sources)
        h.lua.globals().fixtureEmberBytes = ember_bytes
        h.lua.globals().fixtureCatalog = lua_table(h.lua, native_catalog())
        h.lua.globals().fixtureSourceCommit = self.source_commit
        h.lua.globals().fixtureManifestCommit = self.manifest_commit
        h.lua.globals().pysha = digest
        h.lua.globals().pyencode = lambda v: json.dumps(plain(v), separators=(",", ":"))
        h.lua.globals().pydecode = lambda v: lua_table(h.lua, json.loads(v))
        h.lua.execute("""
            files, folders, scheduled, nativeCalls, fetchedModules = {}, {}, {}, 0, {}
            crypt = {hash=function(bytes, algorithm)
                assert(algorithm=='sha256'); return pysha(bytes) end}
            loadstring = load
            isfolder=function(p) return folders[p]==true end
            makefolder=function(p) folders[p]=true end
            isfile=function(p) return files[p]~=nil end
            readfile=function(p) assert(files[p]~=nil); return files[p] end
            writefile=function(p,b) files[p]=b end
            listfiles=function(p)
                local result={}
                for path in pairs(files) do
                    if path:sub(1,#p+1)==p..'/' then result[#result+1]=path end
                end
                return result
            end
            task={delay=function(delay,callback)
                local handle={callback=callback,delay=delay}
                scheduled[#scheduled+1]=handle; return handle end,
                defer=function(callback)
                    local handle={callback=callback}; scheduled[#scheduled+1]=handle; return handle end,
                cancel=function(handle) handle.cancelled=true end}
            local function connection() return {Disconnect=function() end} end
            local folder={}
            local sync={Parent=folder, IsA=function(_,k) return k=='RemoteEvent' end,
                OnClientEvent={Connect=function() return connection() end}}
            function folder:FindFirstChild(name)
                if name=='Sync' then return sync end
                return {Parent=folder,IsA=function(_,k) return k=='RemoteFunction' end,
                    InvokeServer=function() nativeCalls=nativeCalls+1; error('unexpected native call') end}
            end
            fixtureParent={Parent={},IsA=function(_,k) return k=='PlayerGui' end}
            fixtureBindings={remotesFolder=folder,uiParent=fixtureParent,
                userId=123, gameData=fixtureCatalog.gameData,config=fixtureCatalog.config,
                gearSets={slotBonus=function() return 0,0 end},
                combatRules={hospitalHealth=20,staminaCost=1,dailyTargetCap=5},
                nativeState={latest=function() return {cash=0,userId=123,serverNow=100} end,
                    onChanged=function() return connection() end},
                currentDailyBuffRules={isWeekend=function() return false end},
                groupLookup=function() return false end}
            local http={JSONEncode=function(_,v) return pyencode(v) end,
                JSONDecode=function(_,v) return pydecode(v) end,
                GenerateGUID=function() return 'fixture-session' end}
            game={PlaceId=73897506680154,GameId=10643795368}
            function game:GetService(name)
                if name=='Players' then return {LocalPlayer={Name='user-a',UserId=123}} end
                if name=='HttpService' then return http end
                error('unexpected service '..name)
            end
            function game:HttpGet(url)
                if url=='https://rbx.lol/ember.lua' then return fixtureEmberBytes end
                local path=url:match('/idle%-mafia%-ember/(.+)$')
                assert(path and fixtureSources[path], 'unknown fixture URL '..url)
                local commit=url:match('/Roblox/([a-f0-9]+)/')
                assert(commit==(path=='manifest.json' and fixtureManifestCommit or fixtureSourceCommit),
                    'wrong fixture commit')
                if path:sub(1,4)=='src/' then fetchedModules[path]=true end
                return fixtureSources[path]
            end
        """)
        entry = (ROOT / "RuntimeEntry.luau").read_text(encoding="utf-8")
        entry = re.sub(r'local sourceCommit = "[^"]+"',
                       f'local sourceCommit = "{self.source_commit}"', entry)
        entry = re.sub(r'local manifestCommit = "[^"]+"',
                       f'local manifestCommit = "{self.manifest_commit}"', entry)
        for path in ("Loader.luau", "src/loader/Manifest.luau", "Bootstrap.luau",
                     "ReleaseAdapters.luau", "ExecutorEntry.luau"):
            entry = re.sub(r'(pinnedModule\("' + re.escape(path) + r'", ")[^"]+',
                           lambda m: m[1] + digest(sources[path]), entry)
        entry = re.sub(r'("manifest.json",\s*")[^"]+',
                       lambda m: m[1] + digest(manifest_bytes), entry)
        entry = re.sub(r'("https://rbx.lol/ember.lua",\s*")[^"]+',
                       lambda m: m[1] + digest(ember_bytes), entry)
        entry = re.sub(r'gameVersion = "[^"]+"', 'gameVersion = "fixture-current"', entry)
        entry = re.sub(r'fingerprint = "[^"]+"', 'fingerprint = "' + "c" * 64 + '"', entry)
        self.features = [r["id"] for r in json.loads(
            (ROOT / "preview/catalog.json").read_text(encoding="utf-8"))["features"]]
        # Exercise the intended full release allowlist, without editing its pins.
        entry = re.sub(r'allowedFeatures = \{[^}]+\}',
                       'allowedFeatures = {' + ','.join(f'{f}=true' for f in self.features) + '}', entry)
        self.entry = entry

    def start(self):
        return self.h.lua.execute(self.entry)

    def test_real_entry_boots_full_runtime_with_fresh_switches_off(self):
        host = self.start()
        self.assertTrue(host.alive)
        self.assertIsNotNone(host.app.automationRuntime)
        self.assertIsNotNone(host.app.profileStore)
        self.assertEqual(len(host.app.ui.window.sections), 26)
        self.assertEqual(len(self.features), 55)
        self.assertEqual(set(self.h.lua.globals().fetchedModules), set(self.paths))
        self.assertEqual(set(host.app.automationRuntime.features), set(self.features))
        for feature in self.features:
            with self.subTest(feature=feature):
                self.assertIs(host.app.model["values"][feature + ".enabled"], False)
        self.assertEqual(self.h.lua.globals().nativeCalls, 0)
        self.assertFalse(host.app.model.paused)
        # Run the real owner timer once: all-off must remain inert after boot.
        self.h.lua.globals().scheduled[1].callback()
        self.assertEqual(self.h.lua.globals().nativeCalls, 0)
        self.assertTrue(host.Destroy(host))

    def test_saved_profile_is_inert_until_user_explicitly_selects_autoload(self):
        host = self.start()
        self.assertTrue(host.Set(host, "jobs.enabled", True)[0])
        self.assertTrue(host.SaveProfile(host, "Chosen")[0])
        self.assertTrue(host.Destroy(host))
        fresh = self.start()
        self.assertIs(fresh.app.model["values"]["jobs.enabled"], False)
        self.assertTrue(fresh.SetAutoload(fresh, "Chosen")[0])
        self.assertTrue(fresh.Destroy(fresh))
        selected = self.start()
        self.assertIs(selected.app.model["values"]["jobs.enabled"], True)
        self.assertEqual(selected.app.currentProfile, "Chosen")
        for feature in self.features:
            if feature != "jobs":
                self.assertIs(selected.app.model["values"][feature + ".enabled"], False)
        self.assertEqual(self.h.lua.globals().nativeCalls, 0)
        self.assertTrue(selected.Destroy(selected))

    def test_entry_rejects_changed_external_ember_before_runtime_start(self):
        self.h.lua.globals().fixtureEmberBytes = self.ember_bytes + "-- changed"
        with self.assertRaisesRegex(Exception, "SHA-256 mismatch: Ember"):
            self.start()
        self.assertEqual(self.h.lua.globals().nativeCalls, 0)
        self.assertEqual(len(self.h.lua.globals().scheduled), 0)

    def test_current_client_host_installs_and_retires_optional_native_briefcase_source(self):
        self.h.lua.execute("""
            fixtureBindings.currentBriefcases={definition={CASES=12,VERSION=17},
                readCurrent=function() return {serverNow=100} end}
        """)
        host = self.start()
        events = next(tab for tab in host.app.automationRuntime.tabInstances.values() if tab.id == "events")
        source = events.briefcaseSource
        self.assertIsNotNone(source)
        raw, reason = host.driver.reader.Capture(host.driver.reader)
        self.assertIsNone(reason)
        enriched, reason = source.Enrich(source, raw)
        self.assertIsNone(reason)
        self.assertFalse(enriched.briefcaseProof.active)
        host.Destroy(host)
        self.assertIsNone(source.Enrich(source, raw)[0])


if __name__ == "__main__":
    unittest.main()
