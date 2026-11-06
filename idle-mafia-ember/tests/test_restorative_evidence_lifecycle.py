"""Actual App/broker custody survives ambiguous player-consumable replies."""
import unittest

import test_automation_runtime as runtime_fixture
from engine_harness import lua_table
from test_inventory_restoratives import ITEMS


class RestorativeEvidenceLifecycleTests(unittest.TestCase):
    def frame(self, f, revision=1, changed=False):
        raw = f.raw(revision)
        raw.native.serverNow = 2000000 + revision
        raw.native.consumableUseSequence = 5 if changed else 4
        raw.native.consumableReadyAt = 2000003 if changed else 1999999
        raw.native.pools = lua_table(f.h.lua, {"health": 80 if changed else 30,
                                             "energy": 100, "stamina": 50})
        raw.native.stats = lua_table(f.h.lua, {"maxHealth": 100, "maxStamina": 100})
        raw.native.derived.effMaxEnergy = 100
        raw.native.inventory = lua_table(f.h.lua, {"con_medkit_small": 1})
        raw.native.inventoryBound = lua_table(f.h.lua, {"con_medkit_small": 0 if changed else 1})
        raw.restorativeCatalog = lua_table(f.h.lua, {"release": "release-a",
            "catalogKey": "a" * 64, "cooldown": 3,
            "items": [{"id": item, "pool": pool, "percent": percent}
                      for item, pool, percent in ITEMS]})
        return raw

    def prepare(self, reply):
        f = runtime_fixture.AutomationRuntimeTests()
        f.setUp()
        h = f.h
        feature = h.load("src/tabs/inventory/Restoratives.luau")
        spec = lua_table(h.lua, {"id": "restoratives", "reader": feature,
                                "planner": feature, "evidence": feature})
        f.runtime.features.restoratives = spec
        h.lua.eval("function(rows, row) rows[#rows + 1] = row end")(f.runtime.order, spec)
        executor = f.install_native_adapter()
        executor.reply = lua_table(h.lua, reply)
        plan = h.load("src/transport/NativeCallPlan.luau")
        plan = plan.withInventory(plan, h.load("src/tabs/inventory/InventoryCallPlan.luau"))
        f.runtime.session.broker.transport = h.load("src/transport/NativeDispatchAdapter.luau").new(plan, executor)
        app = f.start_test_app()
        app.Set(app, "restoratives.enabled", True)
        app.Set(app, "restoratives.custom.healthBelow", 50)
        app.Resume(app)
        app.Step(app, self.frame(f))
        executor.Drain(executor)
        app.Pause(app)
        self.assertEqual(len(executor.calls), 1)
        self.assertEqual(executor.calls[1].remote, "UseConsumable")
        self.assertEqual([executor.calls[1].args[i] for i in (1, 2, 3)],
                         ["con_medkit_small", True, 4])
        return f, app, executor

    def test_ambiguous_replies_retain_bound_copy_after_timeout_without_replay(self):
        for reply in ({"ok": False}, {"ok": False, "code": "rate_limited"},
                      {"ok": True, "pending": True, "sequence": 5, "readyAt": 2000003,
                       "resource": "health", "gain": 50}):
            with self.subTest(reply=reply):
                f, app, executor = self.prepare(reply)
                f.h.at(1)
                app.Step(app, self.frame(f, 2, changed=True))
                f.h.at(46)
                app.Step(app, self.frame(f, 3, changed=True))
                records = f.runtime.checkpoint.Records(f.runtime.checkpoint)
                self.assertEqual(len(records), 1)
                self.assertEqual(records[1].custody["items"]["B:con_medkit_small"], 1)
                self.assertEqual(len(executor.calls), 1)
                app.Destroy(app)

    def test_exact_success_and_unchanged_terminal_rejection_still_resolve(self):
        for reply, changed, outcome in (({"ok": False}, False, "rejected"),
                ({"ok": True, "sequence": 5, "readyAt": 2000003,
                  "resource": "health", "gain": 50}, True, "confirmed")):
            with self.subTest(outcome=outcome):
                f, app, executor = self.prepare(reply)
                f.h.at(1)
                app.Step(app, self.frame(f, 2, changed))
                self.assertEqual(f.runtime.Status(f.runtime).outcomes.restoratives, outcome)
                self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 0)
                self.assertEqual(len(executor.calls), 1)
                app.Destroy(app)
