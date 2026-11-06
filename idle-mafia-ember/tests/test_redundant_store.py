"""Two-slot decoded-table storage recovers one interrupted file write."""
import hashlib
import json
import unittest

from lupa import lua_type

from engine_harness import Harness, lua_table


def plain(value):
    if lua_type(value) != "table":
        return value
    keys = list(value.keys())
    if keys and all(isinstance(key, int) for key in keys):
        return [plain(value[index]) for index in range(1, len(keys) + 1)]
    return {key: plain(entry) for key, entry in value.items()}


class RedundantStoreTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.disk = {}
        self.short_write = False
        self.fail_read_path = None

        def read(_self, path):
            if path == self.fail_read_path:
                raise OSError("transient read error")
            return self.disk.get(path)

        def write(_self, path, content):
            self.disk[path] = content[:10] if self.short_write else content
            return True

        globals_ = self.h.lua.globals()
        globals_.py_read = read
        globals_.py_write = write
        globals_.py_encode = lambda value: json.dumps(plain(value),
            sort_keys=True, separators=(",", ":"))
        globals_.py_decode = lambda value: lua_table(self.h.lua,
            json.loads(value))
        globals_.py_hash = lambda value: hashlib.sha256(
            value.encode()).hexdigest()
        files = self.h.lua.eval('''{
            ReadFile = function(self, path) return py_read(self, path) end,
            WriteFile = function(self, path, text)
                return py_write(self, path, text) end }''')
        codec = self.h.lua.eval('''{
            Encode = function(self, value) return py_encode(value) end,
            Decode = function(self, value) return py_decode(value) end }''')
        sha = self.h.lua.eval("function(value) return py_hash(value) end")
        self.store = self.h.load("src/storage/RedundantStore.luau").new(
            files, codec, sha, "state")

    def paths(self):
        return self.store.Paths(self.store, "checkpoint:user-a")

    def test_restart_chooses_newest_and_recovers_corrupt_inactive_slot(self):
        self.assertIsNone(self.store.Read(self.store,
            "checkpoint:user-a"))
        self.assertTrue(self.store.Write(self.store,
            "checkpoint:user-a", lua_table(self.h.lua, {"n": 1})))
        self.assertTrue(self.store.Write(self.store,
            "checkpoint:user-a", lua_table(self.h.lua, {"n": 2})))
        self.assertEqual(self.store.Read(self.store,
            "checkpoint:user-a")["n"], 2)
        first, second = self.paths()
        self.disk[second] = "interrupted"
        self.assertEqual(self.store.Read(self.store,
            "checkpoint:user-a")["n"], 1)
        self.assertTrue(self.store.Write(self.store,
            "checkpoint:user-a", lua_table(self.h.lua, {"n": 3})))
        self.assertEqual(self.store.Read(self.store,
            "checkpoint:user-a")["n"], 3)

    def test_failed_readback_keeps_previous_and_corruption_fails_closed(self):
        key = "checkpoint:user-a"
        self.assertTrue(self.store.Write(self.store, key,
            lua_table(self.h.lua, {"n": 1})))
        self.short_write = True
        self.assertFalse(self.store.Write(self.store, key,
            lua_table(self.h.lua, {"n": 2})))
        self.assertEqual(self.store.Read(self.store, key)["n"], 1)
        first, second = self.paths()
        self.disk[first] = "also corrupt"
        with self.assertRaises(Exception):
            self.store.Read(self.store, key)
        self.assertNotIn("user-a", first)
        self.assertNotIn("user-a", second)

    def test_checkpoint_reloads_unresolved_action_through_file_store(self):
        module = self.h.load("src/storage/Checkpoint.luau")
        with self.assertRaises(Exception):
            module.new(self.store)
        with self.assertRaises(Exception):
            module.new(lua_table(self.h.lua, {"Read": self.store.Read,
                "Write": self.store.Write}))
        storage_module = self.h.load("src/storage/RedundantStore.luau")
        strict = storage_module.new(self.store["files"], self.store["codec"],
            self.store["hash"], "state",
            lua_table(self.h.lua, {"strictRecovery": True}))
        scope = self.h.session
        first = module.new(strict)
        self.assertIsNone(first.Load(first, scope["account"],
            scope["place"], scope["release"])[1])
        action = self.h.proposal(key="jobs:watch:1")
        self.assertTrue(first.Save(first, action)[0])
        recovered = module.new(strict)
        records, reason = recovered.Load(recovered, scope["account"],
            scope["place"], scope["release"])
        self.assertIsNone(reason)
        self.assertEqual(records[1]["actionKey"], "jobs:watch:1")

    def test_profile_store_reloads_without_applying_switches(self):
        catalog = self.h.load("src/ui/Catalog.luau")
        settings = self.h.load("src/storage/Settings.luau").new(catalog)
        module = self.h.load("src/storage/ProfileStore.luau")
        profile = lua_table(self.h.lua, {"schema": 1,
            "values": {"jobs.enabled": True,
                       "jobs.policy": "Balanced"}})
        first = module.new(self.store, settings, "user-a", "place-a")
        self.assertTrue(first.Save(first, "main", profile)[0])
        reloaded = module.new(self.store, settings, "user-a", "place-a")
        saved, reason = reloaded.Load(reloaded, "main")
        self.assertIsNone(reason)
        self.assertTrue(saved["values"]["jobs.enabled"])
        self.assertFalse(settings["values"]["jobs.enabled"])

    def test_transient_read_error_never_rolls_back_generation(self):
        key = "checkpoint:user-a"
        self.assertTrue(self.store.Write(self.store, key,
            lua_table(self.h.lua, {"n": 1})))
        self.assertTrue(self.store.Write(self.store, key,
            lua_table(self.h.lua, {"n": 2})))
        self.fail_read_path = self.paths()[1]
        with self.assertRaises(Exception):
            self.store.Read(self.store, key)
        with self.assertRaises(Exception):
            self.store.Write(self.store, key,
                lua_table(self.h.lua, {"n": 3}))

    def test_strict_checkpoint_mode_blocks_damaged_newer_slot(self):
        module = self.h.load("src/storage/RedundantStore.luau")
        strict = module.new(self.store["files"], self.store["codec"],
            self.store["hash"], "state",
            lua_table(self.h.lua, {"strictRecovery": True}))
        key = "checkpoint:user-a"
        self.assertTrue(strict.Write(strict, key,
            lua_table(self.h.lua, {"attempts": 0})))
        self.short_write = True
        self.assertFalse(strict.Write(strict, key,
            lua_table(self.h.lua, {"attempts": 1})))
        with self.assertRaises(Exception):
            strict.Read(strict, key)
        with self.assertRaises(Exception):
            strict.Write(strict, key,
                lua_table(self.h.lua, {"attempts": 2}))


if __name__ == "__main__":
    unittest.main()
