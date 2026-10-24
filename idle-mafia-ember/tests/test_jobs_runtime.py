"""Offline Jobs composition with fake state, storage and transport."""
import unittest

from engine_harness import Harness, lua_table


class JobsRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.storage = self.h.lua.execute("""
            return { data = {}, strictRecovery = true,
                Read = function(self, key) return self.data[key] end,
                Write = function(self, key, value) self.data[key] = value end }
        """)
        modules = lua_table(self.h.lua, {
            "Clock": self.h.load("src/engine/Clock.luau"),
            "Contracts": self.h.contracts,
            "Broker": self.h.load("src/engine/Broker.luau"),
            "Journal": self.h.load("src/engine/Journal.luau"),
            "Context": self.h.load("src/game/Context.luau"),
            "JobsState": self.h.load("src/game/JobsState.luau"),
            "Jobs": self.h.load("src/features/Jobs.luau"),
            "JobsEvidence": self.h.load("src/features/JobsEvidence.luau"),
            "Scheduler": self.h.load("src/engine/Scheduler.luau"),
            "Session": self.h.load("src/engine/Session.luau"),
            "Checkpoint": self.h.load("src/storage/Checkpoint.luau"),
        })
        self.runtime = self.h.load("src/features/JobsRuntime.luau").new(
            lua_table(self.h.lua, {
                "clock": self.h.clock, "transport": self.h.transport,
                "storage": self.storage,
                "identity": self.h.session, "modules": modules,
            })
        )
        self.settings = lua_table(self.h.lua, {"enabled": True, "policy": "Balanced"})

    def raw(self, revision=1, completions=0, active=False):
        native = {
            "fullSync": True, "level": 2, "pools": {"energy": 5},
            "jobs": {"j_watch": {"completions": completions,
                                 "masteryProgress": completions, "masteryTier": 0}},
            "derived": {"autoJobs": False},
        }
        if active:
            native["autoJob"] = {"mode": "one", "jobId": "j_watch"}
        return self.h.snapshot(revision=revision, native=native,
                               catalogKey="build-1",
                               jobCatalog=[{"id": "j_watch", "level": 1,
                                            "energy": 1, "cash": 60, "xp": 2}],
                               masteryRules=[{"completions": 25,
                                              "energyDiscount": 0}])

    def step(self, raw=None, settings=None):
        return self.runtime.Step(self.runtime, raw or self.raw(),
                                 settings or self.settings)

    def test_pause_then_one_send_reply_then_exact_state_confirmation(self):
        self.step()
        self.assertEqual(len(self.h.transport["sent"]), 0)
        self.runtime.Resume(self.runtime)
        self.step()
        self.assertEqual(len(self.h.transport["sent"]), 1)
        self.h.transport["callbacks"][1](lua_table(self.h.lua, {"ok": True}))
        self.step()
        self.assertEqual(self.runtime.Status(self.runtime)["lastOutcome"], None)
        self.step(self.raw(revision=2, completions=1),
                  lua_table(self.h.lua, {"enabled": False, "policy": "Balanced"}))
        self.assertEqual(self.runtime.Status(self.runtime)["lastOutcome"], "confirmed")
        self.assertEqual(len(self.h.transport["sent"]), 1)

    def test_active_native_owner_and_disabled_settings_block_send(self):
        self.runtime.Resume(self.runtime)
        self.step(self.raw(active=True))
        self.assertEqual(len(self.h.transport["sent"]), 0)
        self.step(settings=lua_table(self.h.lua, {"enabled": False,
                                                 "policy": "Balanced"}))
        self.assertEqual(len(self.h.transport["sent"]), 0)

    def test_write_failure_and_stop_prevent_send(self):
        self.runtime.Resume(self.runtime)
        self.storage["Write"] = self.h.lua.eval("function() return false end")
        self.step()
        self.assertEqual(len(self.h.transport["sent"]), 0)
        self.assertTrue(self.runtime.Status(self.runtime)["storageFault"])
        self.runtime.Stop(self.runtime)
        self.step()
        self.assertEqual(len(self.h.transport["sent"]), 0)

    def test_unconfirmed_deadline_keeps_uncertainty_and_cools_down(self):
        self.runtime.Resume(self.runtime)
        self.step()
        self.h.at(45)
        self.step(self.raw())
        status = self.runtime.Status(self.runtime)
        self.assertEqual(status["uncertainCount"], 1)
        self.assertEqual(status["lastOutcome"], "skipped_unconfirmed")
        self.assertEqual(len(self.h.transport["sent"]), 1)

    def tearDown(self):
        self.runtime.Close(self.runtime)


if __name__ == "__main__":
    unittest.main()
