"""Actual Market payout tab/App/adapter/checkpoint path; no trade commands."""
import unittest
import test_automation_runtime as runtime_fixture
from engine_harness import ROOT, lua_table


class MarketPayoutRuntimeFixture:
    def setUp(self):
        base = runtime_fixture.AutomationRuntimeTests()
        base.setUp()
        self.h,self.modules,self.storage = base.h,base.runtime.modules,base.storage
        self.modules.MarketRentUsage = self.h.load('src/tabs/blackMarket/MarketRentUsage.luau')
        base.runtime.Close(base.runtime)
        self.executor = self.h.lua.execute('''return {queued={},calls={},
            Schedule=function(self,callback) self.queued[#self.queued+1]=callback; return true end,
            Invoke=function(self,remote,method,...)
                self.calls[#self.calls+1]={remote=remote,args=table.pack(...)}
                return self.reply or {ok=true} end,
            Drain=function(self) local pending=self.queued; self.queued={}; for _,callback in ipairs(pending) do callback() end end}''')
        self.tab_module = self.h.load('src/tabs/blackMarket/Module.luau')
        self.deps = {path.stem:self.h.load(path.relative_to(ROOT).as_posix())
            for path in (ROOT/'src/tabs/blackMarket').glob('*.luau') if path.stem != 'Module'}
        for name in ('MarketEarnings','MarketEarningsEvidence','MarketBrowse','MarketPrices','MarketRap','MarketReadRuntime'):
            self.deps[name] = self.h.load('src/features/'+name+'.luau')
        self.deps['MarketEarningsState'] = self.h.load('src/game/MarketEarningsState.luau')
        self.deps.update({'fingerprint':'a'*64,'release':'release-a','config':{'MARKET':{
            'maxPages':5,'minLevel':20,'slots':5,'maxSlots':20,'rentPerPeriod':2,'rentPeriodHours':12,'rentMaxDays':7,
            'feePct':.1,'permanentFeePct':.07,'minFee':1,'minPrice':2,'maxPrice':9999999,
            'maxQuantity':999,'minPriceByRarity':{5:3}}}})
        self.start()

    def start(self):
        self.deps.update({'storage':self.storage,'identity':self.h.session})
        self.tab = self.tab_module.new(lua_table(self.h.lua,self.deps))
        selected = getattr(self,'feature_id','marketManage')
        descriptor = next(row for row in self.tab.Descriptors(self.tab).values() if row.id==selected)
        self.assertIsNotNone(descriptor.recoverSaved)
        native = self.h.load('src/transport/NativeCallPlan.luau')
        plan = native.withMarket(native,self.h.load('src/tabs/blackMarket/MarketCallPlan.luau'))
        adapter = self.h.load('src/transport/NativeDispatchAdapter.luau').new(plan,self.executor)
        self.runtime = self.h.load('src/engine/AutomationRuntime.luau').new(lua_table(self.h.lua,{
            'clock':self.h.clock,'transport':adapter,'storage':self.storage,'identity':self.h.session,
            'modules':self.modules,'features':[descriptor],'featurePages':{selected:'blackMarket'},
            'tabInstances':[self.tab],'reservationSources':self.tab.ReservationSources(self.tab),
            'snapshotAssembler':self.h.load('src/tabs/TabSnapshotAssembler.luau').new(lua_table(self.h.lua,[self.tab]))}))
        self.app = self.h.load('src/App.luau').start(lua_table(self.h.lua,{
            'Ember':self.h.load('tests/ember_double.lua')(),'Catalog':self.h.load('src/ui/Catalog.luau'),
            'Settings':self.h.load('src/storage/Settings.luau'),'EmberAdapter':self.h.load('src/ui/EmberAdapter.luau'),
            'BlackMarketTab':self.tab_module,'automationRuntimeInstance':self.runtime}))

    def tearDown(self): self.app.Destroy(self.app)

    def restart(self):
        self.app.Destroy(self.app)
        self.h.session['session']='payout-reloaded'
        self.h.at(0)
        self.start()

    def step(self,revision=1,earnings=50,gold=10,now=1001):
        raw = self.h.snapshot(revision=revision,captured_at=revision,native={
            'fullSync':True,'serverNow':now,'market':{'earnings':earnings},
            'inventory':{'gold_bar':gold},'inventoryBound':{}})
        self.h.at(raw.capturedAt)
        self.assertTrue(self.app.Step(self.app,raw)[0])
        return raw

    def choose(self):
        self.assertTrue(self.app.Set(self.app,'marketManage.enabled',True)[0])
        self.app.Resume(self.app)

class MarketPayoutRuntimeTests(MarketPayoutRuntimeFixture,unittest.TestCase):
    def test_off_default_then_four_argument_claim_confirms_exact_transfer(self):
        self.step()
        self.assertEqual(len(self.executor.queued),0)
        self.choose()
        self.step(revision=2)
        self.executor.Drain(self.executor)
        call = self.executor.calls[1]
        self.assertEqual(call.remote,'MarketAction')
        self.assertEqual(call.args.n,4)
        self.assertEqual([call.args[i] for i in range(1,5)],['collect',None,None,None])
        self.step(revision=3,earnings=0,gold=60)
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.marketManage,'confirmed')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(self.tab.payoutLedger.Summary(self.tab.payoutLedger).claims,1)
        self.assertEqual(self.tab.payoutLedger.Summary(self.tab.payoutLedger).gold,50)

    def test_all_off_restart_observes_exact_saved_claim_without_another_call(self):
        self.choose()
        self.step()
        self.executor.Drain(self.executor)
        self.restart()
        self.step(revision=0,earnings=0,gold=60,now=1002)
        self.assertFalse(self.app.model['values']['marketManage.enabled'])
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.marketManage,'confirmed')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(len(self.executor.calls),1)
        self.assertEqual(self.tab.payoutLedger.Summary(self.tab.payoutLedger).gold,50)

    def test_failed_ledger_write_retains_checkpoint_and_restart_counts_once(self):
        self.choose()
        self.step()
        self.executor.Drain(self.executor)
        self.storage.Write = self.h.lua.eval('''function(self,key,value)
            if key:find(':payouts:',1,true) then return false end
            self.data[key]=value; return true end''')
        self.step(revision=2,earnings=0,gold=60,now=1002)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertTrue(self.runtime.Status(self.runtime).storageFault)
        self.storage.Write = self.h.lua.eval('function(self,key,value) self.data[key]=value; return true end')
        self.restart()
        self.step(revision=0,earnings=0,gold=60,now=1003)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(self.tab.payoutLedger.Summary(self.tab.payoutLedger).claims,1)
        self.assertEqual(len(self.executor.calls),1)

    def test_unload_during_ledger_write_does_not_clear_old_checkpoint_and_reload_is_idempotent(self):
        self.choose()
        self.step()
        self.executor.Drain(self.executor)
        self.h.lua.globals().payoutWriteApp = self.app
        self.storage.Write = self.h.lua.eval('''function(self,key,value)
            self.data[key]=value
            if key:find(':payouts:',1,true) and not self.interrupted then
                self.interrupted=true; payoutWriteApp:Destroy() end
            return true end''')
        raw = self.h.snapshot(revision=2,captured_at=2,native={'fullSync':True,'serverNow':1002,
            'market':{'earnings':0},'inventory':{'gold_bar':60},'inventoryBound':{}})
        self.h.at(2)
        self.app.Step(self.app,raw)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.restart()
        self.assertEqual(self.tab.payoutLedger.Summary(self.tab.payoutLedger).claims,1)
        self.step(revision=0,earnings=0,gold=60,now=1003)
        self.assertEqual(self.tab.payoutLedger.Summary(self.tab.payoutLedger).claims,1)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(len(self.executor.calls),1)

    def test_pending_and_changed_gold_remain_held_after_restart(self):
        self.choose()
        self.executor.reply = lua_table(self.h.lua,{'ok':False,'pending':True})
        self.step()
        self.executor.Drain(self.executor)
        self.restart()
        self.step(revision=0,earnings=0,gold=60,now=1002)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.marketManage)
        self.assertEqual(len(self.executor.calls),1)

    def test_transient_native_codes_keep_exact_saved_claim_held_across_all_off_restart(self):
        for code in ('rate_limited', 'busy', 'presence'):
            with self.subTest(code=code):
                self.setUp()
                try:
                    self.choose()
                    self.executor.reply = lua_table(self.h.lua, {'ok': False, 'code': code})
                    self.step()
                    self.executor.Drain(self.executor)
                    self.step(revision=2, now=1002)
                    self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 1)
                    self.assertEqual(self.tab.payoutLedger.Summary(self.tab.payoutLedger).claims, 0)
                    self.restart()
                    self.step(revision=0, now=1003)
                    self.assertFalse(self.app.model['values']['marketManage.enabled'])
                    self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 1)
                    self.assertIsNone(self.runtime.Status(self.runtime).recoveries.marketManage)
                    self.assertEqual(self.tab.payoutLedger.Summary(self.tab.payoutLedger).claims, 0)
                    self.assertEqual(len(self.executor.calls), 1)
                finally:
                    self.tearDown()


if __name__ == '__main__': unittest.main()
