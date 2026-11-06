"""Actual Money/App/native-owner funding, including retained uncertainty."""
import unittest

import test_heist_protocol_app as fixture
import test_ui_prototype as ui_fixture
from engine_harness import lua_table


class BankFundingAppTests(unittest.TestCase):
    def setUp(self):
        self.seed = fixture.HeistProtocolAppTests()
        self.seed.setUp()
        self.seed.app.Destroy(self.seed.app)
        self.h = self.seed.h
        self.base = self.seed.base.base
        self.port = self.seed.port
        self.scope, self.epoch = self.seed.protocol.lease.scope, self.seed.protocol.lease.epoch
        self.start_app()

    def start_app(self, sources=None, native_protocol=True):
        h = self.h
        lease, reason = h.load("src/tabs/heists/NativeHeistLease.luau").new(
            self.port, h.clock, self.scope, self.epoch)
        self.assertIsNone(reason)
        self.protocol = h.load("src/tabs/heists/HeistProtocol.luau").new(lua_table(h.lua, {
            "lease": lease, "clock": h.clock, "identity": h.session,
            "hash": h.lua.eval("function(text) return heistTestHash(text) end"),
            "config": {"xpForLevel": h.lua.eval("function() return 100 end")}}))
        deps = self.seed.base.heists.deps
        deps.heistProtocol = self.protocol if native_protocol else None
        self.heists = h.load("src/tabs/heists/Module.luau").new(deps)
        money = {"config": {"BANK": {"depositFee": .1}}, "fingerprint": "a" * 64,
                 "release": "release-a", "nativeState":getattr(self,"native_money_state",None)}
        prop = {"gameData": {"PROPERTIES": [
                    {"id": "p_a", "level": 1, "baseCost": 200, "incomePerHour": 20},
                    {"id": "p_b", "level": 5, "baseCost": 500, "incomePerHour": 100}]},
                "config": {"PROPERTY": {"costGrowth": 1.18, "maxOwned": 10}},
                "fingerprint": "a" * 64, "release": "release-a"}
        for target, stems in ((money, ("BankDeposits", "PurposeWithdrawals")), (prop, ("Properties",))):
            for stem in stems:
                reader = {"BankDeposits": "BankState", "PurposeWithdrawals": "WithdrawalState",
                          "Properties": "PropertiesState"}[stem]
                target[reader] = h.load("src/game/" + reader + ".luau")
                for name in (stem, stem + "Evidence"):
                    target[name] = h.load("src/features/" + name + ".luau")
        money["NativeBankCatalog"] = h.load("src/tabs/money/NativeBankCatalog.luau")
        prop["NativePropertyCatalog"] = h.load("src/tabs/property/NativePropertyCatalog.luau")
        self.money = h.load("src/tabs/money/Module.luau").new(lua_table(h.lua, money))
        self.property = h.load("src/tabs/property/Module.luau").new(lua_table(h.lua, prop))
        self.tabs = lua_table(h.lua, [self.heists, self.money, self.property])
        composed, reason = h.load("src/tabs/TabComposition.luau").build(self.tabs,
            h.load("src/ui/Catalog.luau"), h.load("src/engine/FeatureRegistry.luau"),
            h.load("src/tabs/TabSnapshotAssembler.luau"))
        self.assertIsNone(reason)
        for feature in ("jobs", "operations", "safehouse"):
            composed.features[len(composed.features) + 1] = self.base.runtime.features[feature]
            composed.featurePages[feature] = feature
        self.executor = h.lua.execute("""return {calls={},queued={},ordinaryReply={ok=true},ownedReply={pending=true},
            Schedule=function(s,fn) s.queued[#s.queued+1]=fn;return true end,
            Invoke=function(s,remote,method,...)
                s.calls[#s.calls+1]={remote=remote,args=table.pack(...),owned=false};return s.ordinaryReply end,
            InvokeOwned=function(s,token,remote,method,...)
                s.calls[#s.calls+1]={remote=remote,args=table.pack(...),owned=true}
                return remote=='HeistAction' and s.ownedReply or s.ordinaryReply end,
            Drain=function(s) local q=s.queued;s.queued={};for _,fn in ipairs(q) do fn() end end}""")
        lane = h.load("src/engine/RequestLane.luau").new(h.clock)
        adapter = h.load("src/transport/NativeDispatchAdapter.luau").new(
            h.load("src/transport/NativeCallPlan.luau"), self.executor, lane, h.clock, None, self.protocol)
        self.runtime = h.load("src/engine/AutomationRuntime.luau").new(lua_table(h.lua, {
            "clock": h.clock, "transport": adapter, "storage": self.base.storage,
            "identity": h.session, "modules": self.base.runtime.modules,
            "features": composed.features, "featurePages": composed.featurePages,
            "reservationSources": sources or [],
            "tabInstances": self.tabs, "snapshotAssembler": composed.snapshotAssembler}))
        self.app = h.load("src/App.luau").start(lua_table(h.lua, {
            "Ember": h.load("tests/ember_double.lua")(), "Catalog": h.load("src/ui/Catalog.luau"),
            "Settings": h.load("src/storage/Settings.luau"),
            "EmberAdapter": h.load("src/ui/EmberAdapter.luau"),
            "HeistsTab": h.load("src/tabs/heists/Module.luau"),
            "MoneyTab": h.load("src/tabs/money/Module.luau"),
            "PropertyTab": h.load("src/tabs/property/Module.luau"),
            "automationRuntimeInstance": self.runtime}))
        self.set("properties.custom.purchaseCap", 1000)
        self.set("properties.custom.cashReserve", 0)

    def tearDown(self):
        self.app.Destroy(self.app)

    def set(self, key, value):
        result = self.app.Set(self.app, key, value)
        self.assertTrue(result[0], (key, result[1]))

    def raw(self, revision=1, cash=0, banked=10000):
        raw = self.base.raw(revision, active=[])
        raw.catalogKey = "a" * 64
        raw.bankConfig = None
        now = self.h.lua.globals().testNow
        raw.native.cash, raw.native.banked = cash, banked
        raw.native.level = raw.native.maxLevel = 20
        raw.native.serverNow = 2000000 + now
        raw.native.pools.energy = 20
        raw.native.properties = self.h.lua.table()
        raw.native.derived.territoryBonuses = lua_table(self.h.lua, {"buildDiscount": 0})
        raw.heistBoardProof = lua_table(self.h.lua, {"account": "user-a", "capturedAt": now,
            "board": {"ok": True, "serverNow": 2000000 + now, "rows": [], "startsLeft": 1, "bustWait": 0}})
        return raw

    def select(self, purpose="heists", permission=True):
        self.set(purpose + ".enabled", True)
        self.set("withdraw.enabled", True)
        self.set("withdraw.custom.allow" + purpose[0].upper() + purpose[1:], permission)
        self.app.Resume(self.app)

    def step(self, raw=None):
        return self.app.Step(self.app, raw if raw is not None else self.raw())

    def drain(self):
        self.executor.Drain(self.executor)

    def saved_transfer(self, feature="withdraw", reply=None):
        if feature == "withdraw":
            self.select();before=self.raw()
            self.executor.ordinaryReply=lua_table(self.h.lua,reply if reply is not None else {"ok":True})
        else:
            self.set("bank.enabled",True);self.set("bank.custom.cashToKeep",15000)
            self.set("bank.custom.depositThreshold",1);self.app.Resume(self.app)
            before=self.raw(cash=50000.25,banked=1000.75)
            before.native.derived.noBankFees=False
            self.executor.ordinaryReply=lua_table(self.h.lua,reply if reply is not None else {"ok":True,"fee":3500,"kept":31500})
        self.step(before);self.drain()
        self.assertEqual(len(self.executor.calls),1)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.app.Destroy(self.app);self.h.session["session"]="money-reload";self.start_app()
        self.h.at(1)

    def test_large_mixed_native_history_keeps_exact_transfer_recovery_without_replay(self):
        for feature in ('bank','withdraw'):
            with self.subTest(feature=feature):
                other=BankFundingAppTests();other.setUp();self.addCleanup(other.tearDown)
                original=other.raw
                def large_raw(*args,**kwargs):
                    raw=original(*args,**kwargs)
                    raw.native.heistLedger=lua_table(other.h.lua,[{'userId':i,'name':'Player '+str(i),
                        'lastAt':1000,'helped':i%3,'gotHelped':0,'helpedToday':0,
                        'lastHeistId':'h_corner','friend':False} for i in range(1000)])
                    raw.native.heistResults=lua_table(other.h.lua,[{'id':'old-run-'+str(i),'heistId':'h_corner',
                        'cash':35000,'xp':196,'collected':True,'completedAt':900} for i in range(1000)])
                    raw.data=raw.native;other.last_large_raw=raw
                    return raw
                other.raw=large_raw
                reply={'ok':True,'receiptExtra':{'unchanged':'complete native reply'}}
                if feature=='bank':reply.update(fee=3500,kept=31500)
                other.saved_transfer(feature,reply)
                self.assertEqual(len(other.last_large_raw.native.heistLedger),1000)
                self.assertEqual(len(other.last_large_raw.native.heistResults),1000)
                record=other.runtime.checkpoint.Records(other.runtime.checkpoint)[1]
                data=other.runtime.checkpoint.Recovery(other.runtime.checkpoint,record.actionKey)[0]
                self.assertEqual(data.reply.receiptExtra.unchanged,'complete native reply')
                after=other.raw(0,cash=15000.25 if feature=='bank' else 200,
                    banked=32500.75 if feature=='bank' else 9800)
                after.native.derived.noBankFees=False
                other.step(after);other.drain()
                self.assertEqual(other.runtime.Status(other.runtime).recoveries[feature],'confirmed')
                self.assertEqual(len(other.runtime.checkpoint.Records(other.runtime.checkpoint)),0)
                self.assertEqual(len(other.executor.calls),0)

    def test_saved_positive_withdrawal_recovers_paused_without_replaying_or_buying(self):
        self.saved_transfer()
        self.step(self.raw(0,cash=200,banked=9800));self.drain()
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.withdraw,"confirmed")
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(len(self.executor.calls),0)
        self.assertFalse(self.app.model["values"]["heists.enabled"])

    def test_saved_negative_withdrawal_recovers_only_unchanged_balances(self):
        self.saved_transfer(reply={"ok":False})
        self.step(self.raw(0));self.drain()
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.withdraw,"rejected")
        self.assertEqual(len(self.executor.calls),0)

    def test_saved_fractional_bank_transfer_recovers_exact_fee_and_both_balances(self):
        self.saved_transfer("bank")
        after=self.raw(0,cash=15000.25,banked=32500.75);after.native.derived.noBankFees=False
        self.step(after);self.drain()
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.bank,"confirmed")
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(len(self.executor.calls),0)

    def test_saved_bank_pending_reply_with_applied_balances_stays_held(self):
        self.saved_transfer("bank",{"ok":True,"pending":True,"fee":3500,"kept":31500})
        after=self.raw(0,cash=15000.25,banked=32500.75);after.native.derived.noBankFees=False
        self.step(after);self.drain()
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.bank)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertEqual(len(self.executor.calls),0)

    def test_saved_money_recovery_refuses_changed_source_clock_baseline_and_exposure(self):
        for feature in ("bank","withdraw"):
            with self.subTest(feature=feature):
                other=BankFundingAppTests();other.setUp();self.addCleanup(other.tearDown)
                other.saved_transfer(feature)
                record=other.runtime.checkpoint.Records(other.runtime.checkpoint)[1]
                evidence=other.money.deps.BankDepositsEvidence if feature=="bank" else other.money.deps.PurposeWithdrawalsEvidence
                def current():
                    raw=other.raw(0,cash=15000.25 if feature=="bank" else 200,
                                  banked=32500.75 if feature=="bank" else 9800)
                    raw.native.derived.noBankFees=False
                    return other.money.Enrich(other.money,raw)[0]
                for mutation in ("source","old_clock","equal_clock","partial","fractional_revision","same_session_old_revision",
                                 "account","baseline","exposure","pending","before_source","before_clock"):
                    with self.subTest(mutation=mutation):
                        data=other.runtime.checkpoint.Recovery(other.runtime.checkpoint,record.actionKey)[0]
                        after=current()
                        if mutation=="source":after.bankConfig.catalogKey="b"*64
                        elif mutation=="old_clock":after.native.serverNow=data.before.native.serverNow-1
                        elif mutation=="equal_clock":after.native.serverNow=data.before.native.serverNow
                        elif mutation=="partial":after.native.fullSync=False
                        elif mutation=="fractional_revision":after.revision=.5
                        elif mutation=="same_session_old_revision":after.session=data.proposal.session
                        elif mutation=="account":after.account="other-account"
                        elif mutation=="baseline":data.baseline.amount+=1
                        elif mutation=="exposure":data.proposal.resources.cash=1
                        elif mutation=="pending":data.reply.pending=True
                        elif mutation=="before_source":data.before.bankConfig.catalogKey="b"*64
                        elif mutation=="before_clock":data.before.native.serverNow-=1
                        self.assertIsNone(evidence.recoverSaved(data,after))
                self.assertEqual(len(other.executor.calls),0)
                self.assertEqual(len(other.runtime.checkpoint.Records(other.runtime.checkpoint)),1)

    def test_queued_native_income_change_refuses_an_unnecessary_withdrawal(self):
        self.app.Destroy(self.app)
        self.native_money_state=self.h.lua.execute("return {latest=function() return nativeMoneyFrame end}")
        self.start_app();before=self.raw();before.native.userId=42
        self.h.lua.globals().nativeMoneyFrame=before.native
        self.select();self.step(before)
        newer=self.raw(cash=200).native;newer.userId=42
        self.h.lua.globals().nativeMoneyFrame=newer
        self.drain()
        self.assertEqual(len(self.executor.calls),0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)

    def test_queued_bank_native_balance_or_reader_change_is_definitely_unsent(self):
        for mutation in ("cash","banked","actor","reader"):
            with self.subTest(mutation=mutation):
                other=BankFundingAppTests();other.setUp();self.addCleanup(other.tearDown);other.app.Destroy(other.app)
                other.native_money_state=other.h.lua.execute("return {latest=function() return nativeMoneyFrame end}")
                other.start_app();before=other.raw(cash=50000,banked=1000);before.native.userId=42;before.native.derived.noBankFees=False
                other.h.lua.globals().nativeMoneyFrame=before.native
                other.set("bank.enabled",True);other.app.Resume(other.app);other.step(before)
                newer=other.raw(cash=50000,banked=1000).native;newer.userId=42;newer.derived.noBankFees=False
                if mutation=="cash":newer.cash=49999
                elif mutation=="banked":newer.banked=1001
                elif mutation=="actor":newer.userId=43
                elif mutation=="reader":other.native_money_state.latest=other.h.lua.eval("function() return nativeMoneyFrame end")
                other.h.lua.globals().nativeMoneyFrame=newer;other.drain()
                self.assertEqual(len(other.executor.calls),0)
                self.assertEqual(len(other.runtime.checkpoint.Records(other.runtime.checkpoint)),0)

    def test_unchanged_native_bank_frame_still_sends_and_confirms_exact_transfer(self):
        self.app.Destroy(self.app)
        self.native_money_state=self.h.lua.execute("return {latest=function() return nativeMoneyFrame end}")
        self.start_app();before=self.raw(cash=50000,banked=1000);before.native.userId=42;before.native.derived.noBankFees=False
        self.h.lua.globals().nativeMoneyFrame=before.native
        self.executor.ordinaryReply=lua_table(self.h.lua,{"ok":True,"fee":3500,"kept":31500})
        self.set("bank.custom.cashToKeep",15000);self.set("bank.enabled",True);self.app.Resume(self.app)
        self.step(before);self.drain();self.assertEqual(len(self.executor.calls),1)
        self.h.at(1);after=self.raw(2,cash=15000,banked=32500);after.native.userId=42;after.native.derived.noBankFees=False
        self.h.lua.globals().nativeMoneyFrame=after.native;self.step(after)
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.bank,"confirmed")
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)

    def test_actual_money_tab_has_four_typed_independent_defaults(self):
        for purpose, expected in (("Heists", False), ("Properties", False), ("Operations", True), ("Safehouse", True)):
            key = "withdraw.custom.allow" + purpose
            self.assertEqual(self.app.model["values"][key], expected)
            self.assertEqual(self.app.ui.handles[key].kind, "Toggle")
            self.assertFalse(self.app.Set(self.app, key, "true")[0])
        self.assertFalse(self.app.model["values"]["withdraw.enabled"])
        self.assertTrue(self.app.ui.features.withdraw.tabOwned)
        self.assertEqual(len(self.executor.calls), 0)

    def test_heist_withdrawal_uses_no_sequence_until_exact_transfer_then_replans(self):
        self.select()
        self.step()
        self.assertEqual(self.port.counter, 0)
        self.drain()
        self.assertEqual(len(self.executor.calls), 1)
        self.assertEqual(self.executor.calls[1].remote, "Withdraw")
        self.assertEqual(self.executor.calls[1].args[1], 200)
        self.assertEqual(self.port.counter, 0)
        self.assertIsNone(self.port.pending)
        self.h.at(1)
        self.step(self.raw(2))
        self.drain()
        self.assertEqual(len(self.executor.calls), 1)
        self.h.at(2)
        self.step(self.raw(3, cash=200, banked=9800))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.withdraw, "confirmed")
        self.drain()
        self.assertEqual(len(self.executor.calls), 2)
        self.assertTrue(self.executor.calls[2].owned)
        self.assertEqual(self.executor.calls[2].args[1], "start")
        self.assertEqual(self.port.counter, 1)

    def test_property_funding_uses_native_quote_and_replans_after_exact_transfer(self):
        self.select("properties")
        self.set("properties.custom.cashReserve", 50)
        self.step()
        self.drain()
        self.assertEqual(self.executor.calls[1].remote, "Withdraw")
        self.assertEqual(self.executor.calls[1].args[1], 550)
        self.h.at(1)
        self.step(self.raw(2, cash=550, banked=9450))
        self.drain()
        self.assertEqual(self.executor.calls[2].remote, "BuyProperty")
        self.assertEqual(self.executor.calls[2].args[1], "p_b")

    def test_permission_off_does_not_fund_or_change_other_purposes(self):
        self.select(permission=False)
        self.step()
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)
        self.set("properties.enabled", True)
        self.set("withdraw.custom.allowProperties", True)
        self.step()
        self.assertEqual(self.runtime.session.broker.active.proposal.intent.purpose, "properties")
        self.assertFalse(self.app.model["values"]["withdraw.custom.allowHeists"])

    def test_native_heist_quote_unavailable_cannot_fund(self):
        self.port.running = True
        self.select()
        self.step()
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertEqual(self.port.counter, 0)

    def test_supplied_shortfall_cannot_bypass_native_heist_readiness(self):
        self.port.running = True
        self.select()
        raw = self.raw()
        raw.fundingRequest = lua_table(self.h.lua, {**self.h.session, "revision": 1,
            "capturedAt": 0, "purpose": "heists", "purchaseKey": "forged", "requiredCash": 200})
        self.step(raw)
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertEqual(raw.fundingRequest.purchaseKey, "forged")

    def test_supplied_amount_is_replaced_by_exact_native_purchase_shortfall(self):
        self.select("properties")
        raw = self.raw()
        raw.fundingRequest = lua_table(self.h.lua, {**self.h.session, "revision": 1,
            "capturedAt": 0, "purpose": "properties", "purchaseKey": "forged", "requiredCash": 5000})
        self.step(raw)
        self.drain()
        self.assertEqual(self.executor.calls[1].remote, "Withdraw")
        self.assertEqual(self.executor.calls[1].args[1], 500)

    def test_uninstalled_native_heist_owner_cannot_fund(self):
        self.app.Destroy(self.app)
        self.start_app(native_protocol=False)
        self.select()
        self.step()
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)

    def test_existing_operation_permission_defaults_true_and_can_be_disabled(self):
        self.set("operations.enabled", True)
        self.set("operations.policy", "Highest tier")
        self.set("withdraw.enabled", True)
        self.set("withdraw.custom.allowOperations", False)
        self.app.Resume(self.app)
        self.step()
        self.assertIsNone(self.runtime.session.broker.active)
        self.set("withdraw.custom.allowOperations", True)
        self.step()
        self.assertEqual(self.runtime.session.broker.active.proposal.intent.purpose, "operations")

    def test_existing_safehouse_permission_defaults_true_and_can_be_disabled(self):
        self.set("safehouse.enabled", True)
        self.set("withdraw.enabled", True)
        self.set("withdraw.custom.allowSafehouse", False)
        self.app.Resume(self.app)
        self.step()
        self.assertIsNone(self.runtime.session.broker.active)
        self.set("withdraw.custom.allowSafehouse", True)
        self.step()
        self.assertEqual(self.runtime.session.broker.active.proposal.intent.purpose, "safehouse")

    def hold_source(self, cash=0, energy=0, banked=0):
        self.h.lua.globals().fundingTestHold = lua_table(self.h.lua, {
            "account": "user-a", "place": self.h.session["place"], "release": "release-a",
            "feature": "crewRoll", "claims": {"members": {}, "items": {},
                "funds": {"cash": cash, "energy": energy, "banked": banked}, "allCrew": False}})
        return self.h.lua.execute("return {{id='funding-test-store',read=function() return fundingTestHold end}}")

    def test_durable_cash_custody_is_included_in_exact_shortfall(self):
        self.app.Destroy(self.app)
        self.start_app(sources=self.hold_source(cash=300))
        self.select()
        self.step()
        self.drain()
        self.assertEqual(self.executor.calls[1].remote, "Withdraw")
        self.assertEqual(self.executor.calls[1].args[1], 500)

    def test_durable_energy_custody_cannot_be_funded_as_cash(self):
        self.app.Destroy(self.app)
        self.start_app(sources=self.hold_source(energy=19))
        self.select()
        self.step()
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)

    def test_held_bank_balance_is_unavailable_for_shortfall(self):
        self.app.Destroy(self.app)
        self.start_app(sources=self.hold_source(banked=9901))
        self.select()
        self.step()
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)

    def test_tab_source_failure_cannot_be_bypassed_by_funding(self):
        self.select("properties")
        raw = self.raw()
        raw.propertyCatalog = lua_table(self.h.lua, [{"id": "forged", "level": 1,
            "baseCost": 1, "incomePerHour": 1000}])
        self.step(raw)
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)

    def test_origin_disable_fences_queued_withdrawal(self):
        self.select()
        self.step()
        self.set("heists.enabled", False)
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 0)

    def test_origin_retarget_fences_queued_withdrawal(self):
        self.select()
        self.step()
        self.set("heists.custom.selection", "Only selected")
        self.set("heists.custom.selectedIds", "h_a")
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)

    def test_purpose_permission_change_fences_queued_withdrawal(self):
        self.select("properties")
        self.step()
        self.set("withdraw.custom.allowProperties", False)
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)

    def test_unload_fences_queued_withdrawal(self):
        self.select()
        self.step()
        self.app.Destroy(self.app)
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertEqual(self.port.counter, 0)

    def test_negative_unchanged_transfer_rejects_without_purchase(self):
        self.executor.ordinaryReply = lua_table(self.h.lua, {"ok": False})
        self.select()
        self.step()
        self.drain()
        self.h.at(1)
        self.step(self.raw(2))
        self.drain()
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.withdraw, "rejected")
        self.assertEqual(len(self.executor.calls), 1)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 0)

    def uncertain(self, passive=False):
        if not passive:
            self.executor.ordinaryReply = self.h.lua.table()
        self.select()
        self.step()
        self.drain()
        self.h.at(45)
        self.step(self.raw(2, cash=201 if passive else 200, banked=9800))
        self.drain()
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.withdraw, "skipped_unconfirmed")
        self.assertEqual(len(self.executor.calls), 1)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 1)
        self.assertIn("Bank funding", self.runtime.Status(self.runtime).reasons.heists)

    def test_passive_cash_delta_is_unknown_and_cannot_start_origin_after_timeout(self):
        self.uncertain(passive=True)
        self.set("withdraw.enabled", False)
        self.h.at(91)
        self.step(self.raw(3, cash=1000, banked=9800))
        self.drain()
        self.assertEqual(len(self.executor.calls), 1)
        self.assertEqual(self.port.counter, 0)

    def test_unknown_withdrawal_restart_keeps_origin_held_without_replay(self):
        self.uncertain()
        self.app.Destroy(self.app)
        self.h.session["session"] = "funding-reload"
        self.start_app()
        self.select()
        self.h.at(46)
        self.step(self.raw(0, cash=200, banked=9800))
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 1)
        self.assertIn("Bank funding", self.runtime.Status(self.runtime).reasons.heists)

    def test_unknown_funding_keeps_unrelated_jobs_progressing(self):
        self.uncertain()
        self.set("jobs.enabled", True)
        self.h.at(46)
        self.step(self.raw(3, cash=200, banked=9800))
        self.drain()
        self.assertEqual(len(self.executor.calls), 2)
        self.assertEqual(self.executor.calls[2].remote, "DoJob")

    def test_legacy_withdrawal_without_origin_blocks_all_four_purchase_origins(self):
        # Retain an older checkpoint with no full recovery baseline.
        checkpoint = self.runtime.checkpoint
        pending = checkpoint.pendingModule
        checkpoint.pendingModule = None
        saved = checkpoint.Save(checkpoint, lua_table(self.h.lua, {
            **self.h.session, "revision": 1, "feature": "withdraw",
            "actionKey": "withdraw:legacy", "resources": {},
            "intent": {"kind": "purposeWithdrawal"}}))
        checkpoint.pendingModule = pending
        self.assertTrue(saved[0])
        for purpose in ("heists", "properties", "operations", "safehouse"):
            self.set(purpose + ".enabled", True)
        self.app.Resume(self.app)
        self.step(self.raw(cash=10000))
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)
        for purpose in ("heists", "properties", "operations", "safehouse"):
            self.assertIn("Bank funding", self.runtime.Status(self.runtime).reasons[purpose])

    def test_unknown_saved_purpose_blocks_all_four_origins_without_clearing_record(self):
        raw = self.raw(cash=1000)
        proposal = lua_table(self.h.lua, {**self.h.session, "revision": raw.revision,
            "feature": "withdraw", "actionKey": "withdraw:unknown", "resources": {},
            "intent": {"kind": "purposeWithdrawal", "purpose": "other-purpose",
                "purchaseKey": "unknown", "amount": 200, "requiredCash": 1200}})
        baseline = lua_table(self.h.lua, {**self.h.session, "revision": raw.revision,
            "purpose": "other-purpose", "purchaseKey": "unknown", "amount": 200,
            "cash": 1000, "banked": 10000})
        self.assertTrue(self.runtime.checkpoint.Save(self.runtime.checkpoint, proposal, raw, baseline)[0])
        for purpose in ("heists", "properties", "operations", "safehouse"):
            self.set(purpose + ".enabled", True)
        self.app.Resume(self.app)
        self.step(self.raw(2, cash=10000))
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 1)
        for purpose in ("heists", "properties", "operations", "safehouse"):
            self.assertIn("Bank funding", self.runtime.Status(self.runtime).reasons[purpose])

    def test_borrowed_contract_and_trophy_routes_respect_retained_origin_hold(self):
        import test_borrowed_heist_goal_app as goals_fixture
        f = goals_fixture.BorrowedHeistGoalAppTests()
        f.setUp()
        try:
            # Model a scoped unknown outcome loaded from a previous execution.
            raw = f.raw
            raw.native.banked = 10000
            raw.fundingRequest = lua_table(f.h.lua, {**f.h.session, "revision": raw.revision,
                "capturedAt": raw.capturedAt, "purpose": "heists",
                "purchaseKey": "heists:prior", "requiredCash": raw.native.cash + 200})
            context = f.runtime.context.Read(f.runtime.context, raw,
                lua_table(f.h.lua, f.h.session), 0, 2)[0]
            view = f.h.load("src/game/WithdrawalState.luau").read(raw, context)[0]
            proposal = f.h.load("src/features/PurposeWithdrawals.luau").propose(view,
                lua_table(f.h.lua, {"enabled": True, "allowHeists": True, "maxWithdrawal": 1000}))[0]
            baseline = f.h.load("src/features/PurposeWithdrawalsEvidence.luau").capture(proposal, raw)[0]
            self.assertTrue(f.runtime.checkpoint.Save(f.runtime.checkpoint, proposal, raw, baseline)[0])
            f.select()
            f.step()
            f.drain()
            self.assertEqual(len(f.executor.calls), 0)
            self.assertFalse(f.runtime.Status(f.runtime).goals.autoContracts.routed)
            self.assertFalse(f.runtime.Status(f.runtime).goals.trophyFocus.routed)
            self.assertIn("Bank funding", f.runtime.Status(f.runtime).reasons.heists)
        finally:
            f.tearDown()

    def test_ui_callbacks_preserve_all_off_activity_state(self):
        ui = ui_fixture.PrototypeTests()
        ui.setUp()
        app, ember = ui.app()
        try:
            handle = app.ui.handles["withdraw.custom.allowHeists"]
            handle.Set(handle, True)
            ember.Flush()
            self.assertTrue(app.model["values"]["withdraw.custom.allowHeists"])
            self.assertFalse(app.model["values"]["withdraw.enabled"])
            self.assertFalse(app.model["values"]["heists.enabled"])
        finally:
            app.Destroy(app)


if __name__ == "__main__":
    unittest.main()
