"""Actual Shop/Money tabs, native quotes, shared broker and restart evidence."""
import hashlib
import unittest

import test_automation_runtime as fixture
from engine_harness import lua_table


class ShopCashAppTests(unittest.TestCase):
    def setUp(self):
        self.base = fixture.AutomationRuntimeTests()
        self.base.setUp()
        self.base.runtime.Close(self.base.runtime)
        self.h = self.base.h
        self.h.lua.globals().shopTestHash = lambda value: hashlib.sha256(value.encode()).hexdigest()
        self.base.storage.hash = self.h.lua.eval("function(value) return shopTestHash(value) end")
        self.base.storage.Write = self.h.lua.eval("function(self,key,value) self.data[key]=value;return true end")
        self.h.lua.globals().shopHeldCash = 0
        self.data = lua_table(self.h.lua, {"SHOP": [
            {"item": "w_z", "price": 120, "limit": 2},
            {"item": "bg_a", "price": 200}, {"item": "crate_a", "price": 80}],
            "ITEMS_BY_ID": {"w_z": {"kind": "weapon", "rarity": 1},
                "bg_a": {"kind": "background", "rarity": 7},
                "crate_a": {"kind": "crate", "rarity": 8}}})
        self.start_app()

    def start_app(self):
        h = self.h
        deps = {"gameData": self.data, "fingerprint": "a" * 64, "release": "release-a", "clock": h.clock,
            "config": {"BANK": {"depositFee": .1}}}
        for reader, planner in (("ShopState", "ShopBuy"), ("BankState", "BankDeposits"), ("WithdrawalState", "PurposeWithdrawals")):
            deps[reader] = h.load("src/game/" + reader + ".luau")
            deps[planner] = h.load("src/features/" + planner + ".luau")
            deps[planner + "Evidence"] = h.load("src/features/" + planner + "Evidence.luau")
        deps["NativeShopCatalog"] = h.load("src/tabs/shop/NativeShopCatalog.luau")
        deps["NativeBankCatalog"] = h.load("src/tabs/money/NativeBankCatalog.luau")
        self.shop = h.load("src/tabs/shop/Module.luau").new(lua_table(h.lua, deps))
        self.money = h.load("src/tabs/money/Module.luau").new(lua_table(h.lua, deps))
        tabs = lua_table(h.lua, [self.shop, self.money])
        composed, why = h.load("src/tabs/TabComposition.luau").build(tabs, h.load("src/ui/Catalog.luau"),
            h.load("src/engine/FeatureRegistry.luau"), h.load("src/tabs/TabSnapshotAssembler.luau"))
        self.assertIsNone(why)
        current = h.lua.execute("""return {util={
            shopStock=function(data,now) local rows={};for _,row in ipairs(data.SHOP) do rows[row.item]=true end
                local slot=math.floor(now/300);return rows,(slot+1)*300,slot end,
            shopPrice=function(row) return row.price end},
            territory={fromData=function() return 0 end,shopPrice=function(price,territory,sale,decree) return price-territory-sale-decree end},
            globalBuff={sale=function() return 0 end},decree={pctFor=function() return 0 end},
            clock={now=function() return 1220+testNow end},mw={}}""")
        current.gameData = self.data
        self.source, why = h.load("src/tabs/shop/NativeQuoteSource.luau").new(current, "release-a", "a" * 64)
        self.assertIsNone(why)
        modules = self.base.runtime.modules
        modules.ShopQuoteProducer = h.load("src/engine/ShopQuoteProducer.luau")
        modules.shopQuoteSource = self.source
        self.executor = h.lua.execute("""return {calls={},queued={},reply={ok=true},
            Schedule=function(s,fn) s.queued[#s.queued+1]=fn;return true end,
            Invoke=function(s,remote,method,...) s.calls[#s.calls+1]={remote=remote,args=table.pack(...)};return s.reply end,
            Drain=function(s) local q=s.queued;s.queued={};for _,fn in ipairs(q) do fn() end end}""")
        transport = h.load("src/transport/NativeDispatchAdapter.luau").new(
            h.load("src/transport/NativeCallPlan.luau"), self.executor)
        self.runtime = h.load("src/engine/AutomationRuntime.luau").new(lua_table(h.lua, {
            "clock": h.clock, "transport": transport, "storage": self.base.storage,
            "identity": h.session, "modules": modules, "features": composed.features,
            "featurePages": composed.featurePages, "tabInstances": tabs, "snapshotAssembler": composed.snapshotAssembler,
            "reservationSources": h.lua.execute("""return {{id='shop-test-hold',read=function(raw)
                if shopHeldCash == 0 then return nil end
                return {account=raw.account,place=raw.place,release=raw.release,feature='marketFlip',actionKey='held-cash',
                    claims={members={},items={},funds={cash=shopHeldCash},allCrew=false,allItems=false}} end}}""")}))
        self.ember = h.load("tests/ember_double.lua")()
        self.app = h.load("src/App.luau").start(lua_table(h.lua, {"Ember": self.ember,
            "Catalog": h.load("src/ui/Catalog.luau"), "Settings": h.load("src/storage/Settings.luau"),
            "EmberAdapter": h.load("src/ui/EmberAdapter.luau"),
            "ShopTab": h.load("src/tabs/shop/Module.luau"), "MoneyTab": h.load("src/tabs/money/Module.luau"),
            "SettingsTab": h.load("src/tabs/settings/Module.luau"),
            "automationRuntimeInstance": self.runtime}))
        for key, value in {"shop.custom.cashReserve": 100, "shop.custom.purchaseCap": 1000,
                           "shop.custom.itemId": "w_z"}.items(): self.set(key, value)

    def tearDown(self): self.app.Destroy(self.app)

    def set(self, key, value):
        result = self.app.Set(self.app, key, value)
        self.assertTrue(result[0], (key, result[1]))

    def raw(self, revision=1, cash=1000, banked=10000, bought=False, item="w_z"):
        now = self.h.lua.globals().testNow
        return self.h.snapshot(revision=revision, native={"fullSync": True, "level": 10,
            "cash": cash, "banked": banked, "serverNow": 1220 + now,
            "inventory": {item: 1} if bought else {}, "inventoryBound": {},
            "collection": {}, "collectionBound": {}, "shopBought": {item: 1} if bought else {},
            "shopRotation": {"slot": int((1220 + now) // 300), "bought": {item: True} if bought else {}},
            "autoBuyRules": {"on": False}, "derived": {"noBankFees": False}})

    def select(self, mode="All cash items"):
        self.set("shop.custom.selection", mode)
        self.set("shop.enabled", True)
        self.app.Resume(self.app)

    def step(self, raw=None): return self.app.Step(self.app, raw if raw is not None else self.raw())
    def drain(self): self.executor.Drain(self.executor)

    def test_source_order_purchase_and_exact_confirmation_then_next_offer(self):
        self.select()
        self.step()
        self.drain()
        self.assertEqual(self.executor.calls[1].remote, "BuyShopItem")
        self.assertEqual([self.executor.calls[1].args[i] for i in range(1, 4)], ["w_z", None, 120])
        self.h.at(1)
        self.step(self.raw(2, cash=880, bought=True))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.shop, "confirmed")
        self.drain()
        self.assertEqual(self.executor.calls[2].args[1], "bg_a")

    def test_selected_mode_and_override_are_separate_typed_real_controls(self):
        for field, kind in (("selection", "Dropdown"), ("selectedIds", "Input"), ("rarityOverride", "Toggle")):
            self.assertEqual(self.app.ui.handles["shop.custom." + field].kind, kind)
        self.select("Selected cash items")
        self.set("shop.custom.selectedIds", "crate_a,w_z")
        self.step()
        self.drain()
        self.assertEqual(self.executor.calls[1].args[1], "w_z")

    def test_queued_reselection_prevents_purchase(self):
        self.select()
        self.step()
        self.set("shop.custom.selection", "Selected cash items")
        self.set("shop.custom.selectedIds", "crate_a")
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 0)

    def test_queued_disable_and_unload_do_not_invoke(self):
        self.select()
        self.step()
        self.set("shop.enabled", False)
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertEqual(self.allowance().spent, 0)
        self.set("shop.enabled", True)
        self.h.at(1)
        self.step(self.raw(2))
        self.app.Destroy(self.app)
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertEqual(self.allowance().spent, 120)
        self.restart()
        self.h.at(2)
        self.step(self.raw(0))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.shop, "known_unsent")
        self.assertEqual(self.allowance().spent, 0)

    def test_quote_with_fewer_than_five_seconds_left_is_not_dispatched(self):
        self.h.at(274)
        self.select()
        self.step(self.raw())
        self.h.at(276)
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)

    def test_native_auto_buy_and_unavailable_quote_block_shop_and_bank(self):
        self.select()
        self.set("withdraw.enabled", True)
        self.set("withdraw.custom.allowShop", True)
        raw = self.raw(cash=0)
        raw.native.autoBuyRules.on = True
        self.step(raw)
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)
        self.source.CashQuote = self.h.lua.eval("function() return nil end")
        self.step(self.raw(cash=0))
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)

    def test_shop_funding_is_default_off_and_exact_transfer_replans_native_offer(self):
        self.select()
        self.set("withdraw.enabled", True)
        self.step(self.raw(cash=0))
        self.assertEqual(len(self.executor.queued), 0)
        self.set("withdraw.custom.allowShop", True)
        self.step(self.raw(cash=0))
        self.drain()
        self.assertEqual(self.executor.calls[1].remote, "Withdraw")
        self.assertEqual(self.executor.calls[1].args[1], 220)
        self.h.at(1)
        self.step(self.raw(2, cash=220, banked=9780))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.withdraw, "confirmed")
        self.drain()
        self.assertEqual(self.executor.calls[2].remote, "BuyShopItem")

    def test_shop_reselection_prevents_queued_funding(self):
        self.select()
        self.set("withdraw.enabled", True)
        self.set("withdraw.custom.allowShop", True)
        self.step(self.raw(cash=0))
        self.set("shop.custom.rarityOverride", True)
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)

    def restart(self):
        self.app.Destroy(self.app)
        self.h.session["session"] = "shop-reload"
        self.start_app()

    def test_saved_positive_recovers_only_exact_cash_and_item_origins_without_replay(self):
        self.select("Single item")
        self.step()
        self.drain()
        self.restart()
        self.h.at(1)
        self.step(self.raw(0, cash=880, bought=True))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.shop, "confirmed")
        self.assertFalse(self.app.model["values"]["shop.enabled"])
        self.assertEqual(len(self.executor.calls), 0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 0)

    def test_saved_unknown_or_extra_passive_cash_stays_held_without_replay(self):
        self.executor.reply = self.h.lua.table()
        self.select()
        self.step()
        self.drain()
        self.restart()
        self.select()
        self.h.at(1)
        self.step(self.raw(0, cash=881, bought=True))
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 1)

    def test_explicit_rejection_with_unchanged_balances_resolves_in_session_and_restart(self):
        self.executor.reply = lua_table(self.h.lua, {"ok": False})
        self.select()
        self.step()
        self.drain()
        self.restart()
        self.h.at(1)
        self.step(self.raw(0))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.shop, "rejected")
        self.assertEqual(len(self.executor.calls), 0)
        self.assertEqual(self.allowance().spent, 120)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 0)

    def test_large_unrelated_inventory_is_not_copied_into_shop_recovery(self):
        self.select("Single item")
        raw = self.raw()
        for index in range(5000): raw.native.inventory["unrelated_" + str(index)] = 1
        self.step(raw)
        self.drain()
        self.assertEqual(len(self.executor.calls), 1)
        record = self.runtime.checkpoint.Records(self.runtime.checkpoint)[1]
        saved = self.runtime.checkpoint.Recovery(self.runtime.checkpoint, record.actionKey)[0]
        self.assertIsNotNone(saved)
        self.assertEqual(len(list(saved.before.native.inventory.items())), 0)
        self.assertEqual(len(list(saved.before.shopCatalog.offers.items())), 1)

    def allowance(self): return self.runtime.checkpoint.Allowance(self.runtime.checkpoint, "shop")[0]

    def test_cumulative_cap_keeps_native_order_with_remaining_budget_and_survives_reload(self):
        self.set("shop.custom.limitTotal", True)
        self.set("shop.custom.maxSpend", 200)
        self.select()
        self.step()
        self.drain()
        self.h.at(1)
        self.step(self.raw(2, cash=880, bought=True))
        self.drain()
        self.assertEqual(self.executor.calls[2].args[1], "crate_a")
        self.assertEqual(self.allowance().spent, 200)
        self.restart()
        self.assertEqual(self.allowance().spent, 200)
        self.assertFalse(self.app.model["values"]["shop.custom.limitTotal"])

    def test_changed_cap_refunds_queued_unsent_and_zero_blocks_bank(self):
        self.set("shop.custom.limitTotal", True)
        self.set("shop.custom.maxSpend", 120)
        self.select()
        self.step()
        self.assertEqual(self.allowance().spent, 120)
        self.set("shop.custom.maxSpend", 0)
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertEqual(self.allowance().spent, 0)
        self.set("withdraw.enabled", True)
        self.set("withdraw.custom.allowShop", True)
        self.h.at(1)
        self.step(self.raw(2, cash=0))
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)

    def test_positive_reply_with_exact_purchase_markers_and_later_cash_recovers(self):
        self.select()
        self.step()
        self.drain()
        self.restart()
        self.h.at(1)
        self.step(self.raw(0, cash=881, bought=True))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.shop, "confirmed")
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 0)
        self.assertEqual(self.allowance().spent, 120)
        self.assertEqual(len(self.executor.calls), 0)

    def test_cash_hold_arriving_before_send_preserves_reserve_and_refunds_unsent(self):
        self.select("Single item")
        self.step()
        self.h.lua.globals().shopHeldCash = 800
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertEqual(self.allowance().spent, 0)

    def test_cumulative_limit_and_per_purchase_limit_are_independent(self):
        self.set("shop.custom.limitTotal", True)
        self.set("shop.custom.maxSpend", 200)
        self.set("shop.custom.purchaseCap", 100)
        self.select()
        self.step()
        self.drain()
        self.assertEqual(self.executor.calls[1].args[1], "crate_a")
        self.assertEqual(self.allowance().spent, 80)
        self.set("shop.enabled", False)
        self.h.at(1)
        self.step(self.raw(2, cash=920, bought=True, item="crate_a"))
        self.set("shop.custom.purchaseCap", 200)
        self.set("shop.enabled", True)
        self.h.at(2)
        self.step(self.raw(3, cash=920, bought=True, item="crate_a"))
        self.drain()
        self.assertEqual(self.executor.calls[2].args[1], "w_z")
        self.assertEqual(self.allowance().spent, 200)

    def test_sent_unknown_retains_budget_after_45_seconds_disable_and_reload(self):
        self.executor.reply = self.h.lua.table()
        self.set("shop.custom.limitTotal", True)
        self.set("shop.custom.maxSpend", 120)
        self.select()
        self.step()
        self.drain()
        self.h.at(45)
        self.step(self.raw(2))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.shop, "skipped_unconfirmed")
        self.set("shop.enabled", False)
        self.assertEqual(self.allowance().spent, 120)
        self.restart()
        self.set("shop.custom.limitTotal", True)
        self.set("shop.custom.maxSpend", 120)
        self.select()
        self.h.at(46)
        self.step(self.raw(0))
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertEqual(self.allowance().spent, 120)
        self.app.Pause(self.app)
        self.assertIsNone(self.app.PreviewAllowance(self.app, "shop")[0])

    def test_explicit_paused_reset_is_independent_and_durable(self):
        self.set("shop.custom.limitTotal", True)
        self.set("shop.custom.maxSpend", 120)
        self.select("Single item")
        self.step()
        self.drain()
        self.set("shop.enabled", False)
        self.h.at(1)
        self.step(self.raw(2, cash=880, bought=True))
        self.app.Pause(self.app)
        self.assertEqual(self.app.PreviewAllowance(self.app, "shop")[0].spent, 120)
        self.assertTrue(self.app.ConfirmAllowance(self.app, "shop")[0])
        self.assertEqual(self.allowance().spent, 0)
        self.assertEqual(self.app.model["values"]["shop.custom.maxSpend"], 120)
        self.assertTrue(self.app.model.paused)
        self.restart()
        self.assertEqual(self.allowance().spent, 0)
        self.assertIn("Cash Shop", list(self.app.ui.settings.allowanceSelection.options.Options.values()))

    def test_custody_arriving_after_reset_preview_refuses_reset(self):
        self.select("Single item")
        self.step()
        self.drain()
        self.set("shop.enabled", False)
        self.h.at(1)
        self.step(self.raw(2, cash=880, bought=True))
        self.app.Pause(self.app)
        self.assertIsNotNone(self.app.PreviewAllowance(self.app, "shop")[0])
        self.h.lua.globals().shopHeldCash = 1
        self.assertFalse(self.app.ConfirmAllowance(self.app, "shop")[0])
        self.assertEqual(self.allowance().spent, 120)

    def test_changed_other_item_origin_cannot_confirm_or_release_custody(self):
        self.select("Single item")
        self.step()
        self.drain()
        self.restart()
        self.h.at(1)
        raw = self.raw(0, cash=880, bought=True)
        raw.native.collectionBound.w_z = 1
        self.step(raw)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 1)
        self.assertEqual(self.allowance().spent, 120)

    def test_negative_reply_with_partial_effect_retains_charge_and_custody(self):
        self.executor.reply = lua_table(self.h.lua, {"ok": False})
        self.select("Single item")
        self.step()
        self.drain()
        self.restart()
        self.h.at(1)
        self.step(self.raw(0, cash=880))
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 1)
        self.assertEqual(self.allowance().spent, 120)

    def test_pending_native_reply_cannot_confirm_even_exact_effect(self):
        self.executor.reply = lua_table(self.h.lua, {"ok": True, "pending": True})
        self.select("Single item")
        self.step()
        self.drain()
        self.restart()
        self.h.at(1)
        self.step(self.raw(0, cash=880, bought=True))
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 1)
        self.assertEqual(self.allowance().spent, 120)


    def test_native_changed_callback_defers_ui_access_to_owned_tick(self):
        self.set("shop.custom.limitTotal", True)
        self.set("shop.custom.maxSpend", 0)
        self.select("Single item")
        reader = self.h.load("src/transport/NativeSnapshotReader.luau").new(
            lua_table(self.h.lua, self.h.session), self.h.clock)
        driver = self.h.load("src/transport/RuntimeDriver.luau").new(self.app, reader)
        handle = self.app.ui.handles["bank.custom.cashToKeep"]
        self.h.lua.globals().ownedBankGet = handle.Get
        handle.Get = self.h.lua.eval("""function(self)
            assert(not nativeChangedThread, "lacking capability Plugin")
            return ownedBankGet(self)
        end""")
        self.h.at(1)
        self.h.lua.globals().nativeChangedThread = True
        try:
            # Both callback kinds only capture state; their success is a boolean.
            self.assertIs(driver.ObserveSync(driver, self.raw().native), True)
            result = driver.ObserveChanged(driver, self.raw(2, cash=1001).native)
        finally:
            self.h.lua.globals().nativeChangedThread = False
        self.assertEqual(result, True)
        self.assertFalse(self.app.model.paused)
        self.assertIsNone(self.app.ui.lastError)
        self.assertTrue(driver.Tick(driver)[0])
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)

    def test_native_shop_calculation_cannot_change_ui_thread_access(self):
        self.h.lua.globals().nativeRestrictedThreads = self.h.lua.table()
        self.h.lua.globals().nativeShopClock = self.source.current.clock.now
        self.source.current.clock.now = self.h.lua.eval("""function()
            nativeRestrictedThreads[coroutine.running()] = true
            return nativeShopClock()
        end""")
        self.source.call = self.h.lua.eval("""function(fn)
            local thread=coroutine.create(fn)
            local values=table.pack(coroutine.resume(thread))
            assert(coroutine.status(thread)=='dead')
            return table.unpack(values,1,values.n)
        end""")
        handle = self.app.ui.handles["bank.custom.cashToKeep"]
        self.h.lua.globals().nativeBankGet = handle.Get
        handle.Get = self.h.lua.eval("""function(self)
            assert(not nativeRestrictedThreads[coroutine.running()], "lacking capability Plugin")
            return nativeBankGet(self)
        end""")
        self.select("Single item")
        try:
            accepted, reason = self.step()
        finally:
            self.h.lua.globals().nativeRestrictedThreads = self.h.lua.table()
        self.assertTrue(accepted, reason)
        self.assertFalse(self.app.model.paused)
        self.drain()
        self.assertEqual(len(self.executor.calls), 1)
        self.assertEqual(self.executor.calls[1].remote, "BuyShopItem")

    def test_ui_get_failure_reports_cause_and_pauses_before_dispatch(self):
        self.select("Single item")
        handle = self.app.ui.handles["bank.custom.cashToKeep"]
        original = handle.Get
        handle.Get = self.h.lua.eval("function() error('lacking capability Plugin', 0) end")
        try:
            accepted, reason = self.step()
        finally:
            handle.Get = original
        self.assertFalse(accepted)
        self.assertIn("lacking capability Plugin", reason)
        self.assertTrue(self.app.model.paused)
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)

    def old_rotation(self, raw=None, slot=3, bought=True):
        raw = raw if raw is not None else self.raw()
        raw.native.shopRotation = lua_table(self.h.lua, {
            "slot": slot, "bought": {"w_z": bought}})
        return raw

    def test_previous_rotation_purchase_does_not_block_first_current_purchase(self):
        self.select("Single item")
        before = self.old_rotation()
        self.step(before)
        self.drain()
        self.assertEqual(len(self.executor.calls), 1)
        self.assertEqual(before.native.shopRotation.slot, 3)
        self.assertTrue(before.native.shopRotation.bought.w_z)
        self.set("shop.enabled", False)
        self.h.at(1)
        self.step(self.raw(2, cash=880, bought=True))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.shop, "confirmed")
        self.assertEqual(self.allowance().spent, 120)

    def test_no_previous_rotation_survives_exact_saved_positive_recovery(self):
        self.select("Single item")
        raw = self.raw()
        raw.native.shopRotation = None
        self.step(raw)
        self.drain()
        self.assertEqual(len(self.executor.calls), 1)
        self.restart()
        self.h.at(1)
        self.step(self.raw(0, cash=880, bought=True))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.shop, "confirmed")
        self.assertEqual(len(self.executor.calls), 0)
        self.assertEqual(self.allowance().spent, 120)

    def test_previous_rotation_rejection_recovers_without_replay(self):
        self.executor.reply = lua_table(self.h.lua, {"ok": False})
        self.select("Single item")
        self.step(self.old_rotation())
        self.drain()
        self.assertEqual(len(self.executor.calls), 1)
        self.restart()
        self.h.at(1)
        self.step(self.old_rotation(self.raw(0)))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.shop, "rejected")
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 0)
        self.assertEqual(len(self.executor.calls), 0)
        self.assertEqual(self.allowance().spent, 120)

    def test_old_rotation_rejection_resolves_before_unload(self):
        self.executor.reply = lua_table(self.h.lua, {"ok": False})
        self.select("Single item")
        self.step(self.old_rotation())
        self.drain()
        self.assertEqual(len(self.executor.calls), 1)
        self.set("shop.enabled", False)
        self.h.at(1)
        self.step(self.old_rotation(self.raw(2)))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.shop, "rejected")
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 0)
        self.assertEqual(self.allowance().spent, 120)

    def test_absent_rotation_rejection_resolves_without_creating_purchase_history(self):
        self.executor.reply = lua_table(self.h.lua, {"ok": False})
        self.select("Single item")
        before = self.raw()
        before.native.shopRotation = None
        self.step(before)
        self.drain()
        self.assertEqual(len(self.executor.calls), 1)
        self.set("shop.enabled", False)
        self.h.at(1)
        after = self.raw(2)
        after.native.shopRotation = None
        self.step(after)
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.shop, "rejected")
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 0)

    def test_old_purchase_flag_is_not_evidence_of_current_purchase(self):
        self.select("Single item")
        self.step(self.old_rotation())
        self.drain()
        self.assertEqual(len(self.executor.calls), 1)
        self.h.at(45)
        self.step(self.old_rotation(self.raw(2)))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.shop, "skipped_unconfirmed")
        self.restart()
        self.select("Single item")
        self.h.at(46)
        self.step(self.old_rotation(self.raw(0, cash=880, bought=True)))
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 1)
        self.assertEqual(self.allowance().spent, 120)

    def test_changed_old_rotation_does_not_establish_rejection(self):
        self.executor.reply = lua_table(self.h.lua, {"ok": False})
        self.select("Single item")
        self.step(self.old_rotation())
        self.drain()
        self.assertEqual(len(self.executor.calls), 1)
        self.restart()
        self.h.at(1)
        self.step(self.old_rotation(self.raw(0), slot=2))
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 1)
        self.assertEqual(self.allowance().spent, 120)

    def test_first_purchase_respects_both_caps_and_queued_disable(self):
        self.set("shop.custom.limitTotal", True)
        self.set("shop.custom.maxSpend", 100)
        self.set("shop.custom.purchaseCap", 120)
        self.select("Single item")
        self.step(self.old_rotation())
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)
        self.set("shop.custom.maxSpend", 120)
        self.set("shop.custom.purchaseCap", 100)
        self.h.at(1)
        self.step(self.old_rotation(self.raw(2)))
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)
        self.set("shop.custom.purchaseCap", 120)
        self.h.at(2)
        self.step(self.old_rotation(self.raw(3)))
        self.assertEqual(len(self.executor.queued), 1)
        self.set("shop.enabled", False)
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertEqual(self.allowance().spent, 0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 0)

    def test_future_or_malformed_purchase_rotation_refuses(self):
        self.select("Single item")
        for index, rotation in enumerate((
            {"slot": 5, "bought": {}}, {"slot": -1, "bought": {}},
            {"slot": 3.5, "bought": {}}, {"bought": {}},
            {"slot": 3, "bought": False}, {"slot": 3, "bought": {"w_z": "yes"}},
        )):
            with self.subTest(rotation=rotation):
                self.h.at(index)
                raw = self.raw(index + 1)
                raw.native.shopRotation = lua_table(self.h.lua, rotation)
                self.step(raw)
                self.drain()
                self.assertEqual(len(self.executor.calls), 0)

    def test_missing_bought_map_allows_first_purchase_but_current_flag_blocks(self):
        self.select("Single item")
        raw = self.raw()
        raw.native.shopRotation.bought.w_z = True
        self.step(raw)
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)
        self.h.at(1)
        raw = self.raw(2)
        raw.native.shopRotation.bought = None
        self.step(raw)
        self.drain()
        self.assertEqual(len(self.executor.calls), 1)


if __name__ == "__main__": unittest.main()
