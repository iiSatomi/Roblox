"""Durable Shop authorized-Cash totals cannot be reset by reload or corrupt input."""
import unittest

from engine_harness import lua_table
import test_shop_cash_app as fixture


class ShopAllowanceTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.ShopCashAppTests()
        self.f.setUp()

    def tearDown(self): self.f.tearDown()

    def send(self):
        f = self.f
        f.select("Single item")
        f.step()
        f.drain()
        self.assertEqual(len(f.executor.calls), 1)
        return f.base.storage.data[f.runtime.checkpoint.ScopeKey(f.runtime.checkpoint)]

    def test_missing_initialized_usage_stops_instead_of_restarting_from_zero(self):
        f = self.f
        envelope = self.send()
        envelope.shopUsage = None
        f.restart()
        f.select()
        f.step()
        f.drain()
        self.assertTrue(f.runtime.Status(f.runtime).storageFault)
        self.assertEqual(len(f.executor.calls), 0)

    def test_underreported_total_or_missing_new_charge_is_corruption(self):
        f = self.f
        envelope = self.send()
        envelope.shopUsage.spent = 119
        f.restart()
        self.assertTrue(f.runtime.Status(f.runtime).storageFault)
        envelope.shopUsage.spent = 120
        envelope.records[1].shopCharge = None
        f.restart()
        self.assertTrue(f.runtime.Status(f.runtime).storageFault)
        self.assertEqual(len(f.executor.calls), 0)

    def test_legacy_pending_purchase_settles_but_past_total_stays_unknown_until_review(self):
        f = self.f
        envelope = self.send()
        record = envelope.records[1]
        data = f.runtime.checkpoint.Recovery(f.runtime.checkpoint, record.actionKey)[0]
        for key in ("attemptedBefore", "spentBefore", "limitTotal", "maxSpend"):
            data.proposal.intent[key] = None
        data.before.shopUsageProof = None
        pending = f.h.load("src/storage/PendingAction.luau")
        recovery, why = pending.Capture(data.proposal, data.before, data.baseline)
        self.assertIsNone(why)
        record.recovery = pending.WithReply(recovery, record, data.reply)[0]
        self.assertIsNotNone(record.recovery)
        record.shopCharge = None
        envelope.shopUsage = None
        envelope.shopUsageInitialized = None
        f.restart()
        f.h.at(1)
        f.step(f.raw(0, cash=880, bought=True))
        self.assertEqual(f.runtime.Status(f.runtime).recoveries.shop, "confirmed")
        self.assertTrue(f.allowance().unknown)
        f.select()
        f.step(f.raw(1, cash=880, bought=True))
        f.drain()
        self.assertEqual(len(f.executor.calls), 0)
        f.app.Pause(f.app)
        selection = f.app.ui.settings.allowanceSelection
        selection.Set(selection, "Cash Shop", True)
        buttons = {row.options.Text: row for row in f.app.ui.window.handles.values() if row.kind == "Button"}
        buttons["Review allowance"].options.Callback(None, None, None)
        status = f.app.ui.settings.allowanceStatus.Get(f.app.ui.settings.allowanceStatus)
        self.assertIn("Previous Shop Cash use is unknown", status)
        self.assertNotIn("0 counted", status)
        preview, why = f.app.PreviewAllowance(f.app, "shop")
        self.assertIsNone(why)
        self.assertTrue(preview.unknown)
        self.assertTrue(f.app.ConfirmAllowance(f.app, "shop")[0])
        self.assertIsNone(f.allowance().unknown)
        self.assertTrue(f.app.model.paused)

    def test_shop_reset_does_not_reset_another_allowance(self):
        f = self.f
        envelope = self.send()
        envelope.eventShopUsage = lua_table(f.h.lua, {"version": 1, "attempted": 1, "spent": 15})
        f.restart()
        f.h.at(1)
        f.step(f.raw(0, cash=880, bought=True))
        self.assertEqual(f.allowance().spent, 120)
        f.app.Pause(f.app)
        self.assertIsNotNone(f.app.PreviewAllowance(f.app, "shop")[0])
        self.assertTrue(f.app.ConfirmAllowance(f.app, "shop")[0])
        self.assertEqual(f.allowance().spent, 0)
        other = f.runtime.checkpoint.Allowance(f.runtime.checkpoint, "eventShop")[0]
        self.assertEqual((other.attempted, other.spent), (1, 15))

    def test_confirmed_total_survives_reopen_and_forged_snapshot_count(self):
        f = self.f
        self.send()
        f.set("shop.enabled", False)
        f.h.at(1)
        f.step(f.raw(2, cash=880, bought=True))
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 0)
        f.restart()
        f.set("shop.custom.limitTotal", True)
        f.set("shop.custom.maxSpend", 120)
        f.select()
        f.h.at(300)
        raw = f.raw(0, cash=1000)
        raw.shopUsageProof = lua_table(f.h.lua, {**f.h.session, "revision": 0,
            "capturedAt": 300, "attempted": 0, "spent": 0})
        f.step(raw)
        f.drain()
        self.assertEqual(f.allowance().spent, 120)
        self.assertEqual(len(f.executor.calls), 0)

    def test_failed_usage_write_never_invokes_native_purchase(self):
        f = self.f
        f.base.storage.Write = f.h.lua.eval("function() return false end")
        f.select()
        f.step()
        f.drain()
        self.assertTrue(f.runtime.Status(f.runtime).storageFault)
        self.assertEqual(len(f.executor.calls), 0)


if __name__ == "__main__": unittest.main()
