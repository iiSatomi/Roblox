"""Ambiguous Collection callbacks retain durable copies in the actual App path."""
import unittest
import test_automation_runtime as runtime_fixture
from engine_harness import lua_table


class CollectionEvidenceLifecycleTests(unittest.TestCase):
    def prepare(self, reply):
        f = runtime_fixture.AutomationRuntimeTests()
        f.setUp()
        h = f.h
        donate = h.load("src/tabs/collection/CollectionDonate.luau")
        spec = lua_table(h.lua, {"id": "collectionDonate", "reader": donate,
                               "planner": donate, "evidence": donate})
        f.runtime.features.collectionDonate = spec
        h.lua.eval("function(rows, row) rows[#rows + 1] = row end")(f.runtime.order, spec)
        executor = f.install_native_adapter()
        executor.reply = lua_table(h.lua, reply)
        plan = h.load("src/transport/NativeCallPlan.luau")
        plan = plan.withCollection(plan, h.load("src/tabs/collection/CollectionCallPlan.luau"))
        f.runtime.session.broker.transport = h.load("src/transport/NativeDispatchAdapter.luau").new(plan, executor)
        app = f.start_test_app()
        app.Set(app, "collectionDonate.enabled", True)
        app.Set(app, "collectionDonate.custom.maxBatch", 2)
        app.Set(app, "collectionDonate.custom.sparesToKeep", 1)
        app.Resume(app)
        before = self.frame(f, 1, 4, 9)
        before.collectionCatalog = lua_table(h.lua, {
            "release": "release-a", "catalogKey": "a" * 64,
            "items": {"w_a": {"kind": "weapon", "rarity": 4}},
            "rarity": [1, 2, 3, 5],
            "tiers": [{"count": 1, "mult": 1}, {"count": 10, "mult": 2}]})
        app.Step(app, before)
        executor.Drain(executor)
        self.assertEqual(len(executor.calls), 1)
        self.assertEqual([executor.calls[1].args[i] for i in (1, 2, 3)], ["deposit", "w_a", 2])
        return f, app, executor

    def frame(self, f, revision, loose, collected):
        raw = f.raw(revision)
        raw.native.inventory = lua_table(f.h.lua, {"w_a": loose})
        raw.native.collection = lua_table(f.h.lua, {"w_a": collected})
        raw.native.crew = lua_table(f.h.lua, [{"name": "Player", "weapon": "w_a"},
                                           {"name": "Ally", "rarity": 4}])
        return raw

    def test_transient_success_and_changed_rejection_keep_saved_copy_custody(self):
        for reply in ({"ok": True, "moved": 2, "pending": True},
                      {"ok": True, "moved": 2, "code": "busy"},
                      {"ok": False, "code": "rate_limited"}, {"ok": False}):
            with self.subTest(reply=reply):
                f, app, executor = self.prepare(reply)
                f.h.at(1)
                app.Step(app, self.frame(f, 2, 2, 11))
                records = f.runtime.checkpoint.Records(f.runtime.checkpoint)
                self.assertEqual(len(records), 1)
                claims = records[1].custody
                self.assertEqual(claims["items"]["L:w_a"], 2)
                f.h.at(46)
                app.Step(app, self.frame(f, 3, 2, 11))
                self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 1)
                self.assertEqual(len(executor.calls), 1)
                self.assertNotEqual(f.runtime.Status(f.runtime).outcomes.collectionDonate, "confirmed")
                app.Destroy(app)
                prior = f.runtime.checkpoint
                checkpoint = f.h.load("src/storage/Checkpoint.luau").new(f.storage,
                    prior.familyUsageModule, prior.reservationModule, prior.pendingModule,
                    prior.eventUsageModule, prior.rentUsageModule, prior.hireUsageModule,
                    prior.fightUsageModule, prior.chestUsageModule, prior.shopUsageModule)
                _, reason = checkpoint.Load(checkpoint, f.h.session['account'], f.h.session['place'], f.h.session['release'])
                self.assertIsNone(reason)
                saved = checkpoint.Records(checkpoint)
                self.assertEqual(len(saved), 1)
                self.assertEqual(saved[1].custody["items"]["L:w_a"], 2)
                data, reason = checkpoint.Recovery(checkpoint, saved[1].actionKey)
                self.assertIsNone(reason)
                self.assertEqual(data.reply.ok, reply['ok'])

    def test_terminal_exact_move_and_unchanged_rejection_resolve_normally(self):
        for reply, loose, collected, expected in (({"ok": True, "moved": 2}, 2, 11, "confirmed"),
                                                    ({"ok": False}, 4, 9, "rejected")):
            with self.subTest(expected=expected):
                f, app, executor = self.prepare(reply)
                f.h.at(1)
                app.Step(app, self.frame(f, 2, loose, collected))
                self.assertEqual(f.runtime.Status(f.runtime).outcomes.collectionDonate, expected)
                self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 0)
                self.assertEqual(len(executor.calls), 1)
                app.Destroy(app)


if __name__ == "__main__":
    unittest.main()
