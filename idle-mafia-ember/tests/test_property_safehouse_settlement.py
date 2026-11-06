"""Owned purchase outcomes tolerate passive Cash without claiming its exact debit."""
import hashlib
import json
import unittest
import test_automation_runtime as base_fixture
from engine_harness import lua_table


class PurchaseFixture:
    def __init__(self):
        base=base_fixture.AutomationRuntimeTests();base.setUp()
        self.h=base.h;self.storage=base.storage;self.modules=base.runtime.modules
        base.runtime.Close(base.runtime)
        self.h.lua.globals().purchaseHash=lambda value:hashlib.sha256(value.encode()).hexdigest()
        self.storage.hash=self.h.lua.eval('function(value)return purchaseHash(value)end')
        self.start()
    def start(self):
        h=self.h
        deps={name:h.load(path) for name,path in {
            'PropertiesState':'src/game/PropertiesState.luau',
            'Properties':'src/features/Properties.luau',
            'PropertiesEvidence':'src/features/PropertiesEvidence.luau',
            'NativePropertyCatalog':'src/tabs/property/NativePropertyCatalog.luau',
            'SafehouseState':'src/game/SafehouseState.luau',
            'SafehouseUpgrades':'src/features/SafehouseUpgrades.luau',
            'SafehouseUpgradesEvidence':'src/features/SafehouseUpgradesEvidence.luau',
            'NativeSafehouseCatalog':'src/tabs/safehouse/NativeSafehouseCatalog.luau'}.items()}
        deps.update(fingerprint='a'*64,release='release-a',gameData={'PROPERTIES':[
            {'id':'p_a','level':1,'baseCost':1000,'incomePerHour':100},
            {'id':'p_b','level':5,'baseCost':1500,'incomePerHour':300}]},config={
            'PROPERTY':{'costGrowth':1.18,'maxOwned':20},
            'SAFEHOUSE':[{'name':f'Tier {i}','cost':(i-1)*1000,'level':i,'mult':i} for i in range(1,19)]})
        self.tabs=lua_table(h.lua,[h.load('src/tabs/property/Module.luau').new(lua_table(h.lua,deps)),
            h.load('src/tabs/safehouse/Module.luau').new(lua_table(h.lua,deps))])
        specs,reason=h.load('src/engine/FeatureRegistry.luau').fromTabs(self.tabs,h.load('src/ui/Catalog.luau'))
        assert specs is not None,reason
        self.executor=h.lua.execute("""return {calls={},queued={},
            Schedule=function(self,fn)self.queued[#self.queued+1]=fn;return true end,
            Invoke=function(self,remote,method,...)self.calls[#self.calls+1]={remote=remote,args=table.pack(...)};return self.reply or {ok=true}end,
            Drain=function(self)local q=self.queued;self.queued={};for _,fn in ipairs(q)do fn()end end}""")
        adapter=h.load('src/transport/NativeDispatchAdapter.luau').new(h.load('src/transport/NativeCallPlan.luau'),self.executor)
        self.runtime=h.load('src/engine/AutomationRuntime.luau').new(lua_table(h.lua,{
            'clock':h.clock,'transport':adapter,'storage':self.storage,'identity':h.session,'modules':self.modules,
            'features':specs,'tabInstances':self.tabs,'featurePages':{'properties':'property','safehouse':'safehouse'},
            'snapshotAssembler':h.load('src/tabs/TabSnapshotAssembler.luau').new(self.tabs)}))
        self.app=h.load('src/App.luau').start(lua_table(h.lua,{'Ember':h.load('tests/ember_double.lua')(),
            'Catalog':h.load('src/ui/Catalog.luau'),'Settings':h.load('src/storage/Settings.luau'),
            'EmberAdapter':h.load('src/ui/EmberAdapter.luau'),'automationRuntimeInstance':self.runtime}))
    def raw(self,revision=1,now=1000,cash=10000,built=False,tier=3):
        raw=self.h.snapshot(revision=revision,native={'fullSync':True,'serverNow':now,'cash':cash,
            'level':15,'maxLevel':15,'safehouse':tier,'properties':{'p_a':{'owned':1},'p_b':{'owned':1 if built else 0}},
            'derived':{'territoryBonuses':{}}})
        raw.catalogKey='a'*64
        return raw
    def begin(self,feature):
        values={feature+'.enabled':True}
        if feature=='properties':values.update({'properties.custom.selection':'Only selected',
            'properties.custom.selectedIds':'p_b','properties.custom.cashReserve':0,'properties.custom.purchaseCap':2000})
        else:values.update({'safehouse.custom.maxTier':4,'safehouse.custom.cashReserve':0,'safehouse.custom.maxCost':3000})
        for key,value in values.items():
            ok,reason=self.app.Set(self.app,key,value);assert ok,reason
        self.app.Resume(self.app);self.app.Step(self.app,self.raw());self.executor.Drain(self.executor)
        assert len(self.executor.calls)==1,dict(self.runtime.Status(self.runtime).reasons.items())
        record=self.runtime.checkpoint.Records(self.runtime.checkpoint)[1]
        return self.runtime.checkpoint.Recovery(self.runtime.checkpoint,record.actionKey)[0]
    def after(self,feature,cash=None,now=1002):
        self.h.at(1)
        return self.raw(2,now,8501 if feature=='properties' and cash is None else 7001 if cash is None else cash,
            built=feature=='properties',tier=4 if feature=='safehouse' else 3)
    def evidence(self,feature):
        return self.h.load('src/features/'+('PropertiesEvidence' if feature=='properties' else 'SafehouseUpgradesEvidence')+'.luau')
    def restart(self):
        self.app.Destroy(self.app)
        def wire(value):
            if not hasattr(value,'items'):return value
            entries=dict(value.items())
            if entries and set(entries)==set(range(1,len(entries)+1)):return [wire(entries[i]) for i in range(1,len(entries)+1)]
            return {key:wire(child) for key,child in entries.items()}
        for key,value in list(self.storage.data.items()):
            self.storage.data[key]=lua_table(self.h.lua,json.loads(json.dumps(wire(value),allow_nan=False)))
        self.h.session['session']='purchase-restart';self.h.at(1);self.start()
    def close(self):self.app.Destroy(self.app)


class PropertySafehouseSettlementTests(unittest.TestCase):
    def test_actual_app_accrual_confirms_exact_owned_outcome_and_original_quote(self):
        for feature,quote in (('properties',1500),('safehouse',3000)):
            with self.subTest(feature=feature):
                f=PurchaseFixture()
                try:
                    data=f.begin(feature);self.assertEqual(data.proposal.resources.cash,quote)
                    f.app.Set(f.app,feature+'.enabled',False)
                    f.app.Step(f.app,f.after(feature))
                    self.assertEqual(f.runtime.Status(f.runtime).outcomes[feature],'confirmed')
                    self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)),0)
                    self.assertEqual(len(f.executor.calls),1)
                    self.assertEqual(data.proposal.resources.cash,quote)
                    self.assertEqual(f.executor.calls[1].args.n,2 if feature=='properties' else 0)
                finally:f.close()

    def test_actual_normal_descriptors_recover_json_saved_accrued_outcome_without_replay(self):
        for feature in ('properties','safehouse'):
            with self.subTest(feature=feature):
                f=PurchaseFixture()
                try:
                    f.begin(feature);f.restart();after=f.after(feature)
                    f.app.Step(f.app,after)
                    self.assertEqual(f.runtime.Status(f.runtime).recoveries[feature],'confirmed')
                    self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)),0)
                    self.assertEqual(len(f.executor.calls),0)
                    self.assertFalse(f.app.model['values'][feature+'.enabled'])
                finally:f.close()

    def test_legacy_receipt_clock_is_read_only_and_other_baseline_fields_still_exact(self):
        for feature in ('properties','safehouse'):
            with self.subTest(feature=feature):
                f=PurchaseFixture()
                try:
                    data=f.begin(feature);data.baseline.serverNow=None
                    old_clock=data.before.native.serverNow
                    self.assertEqual(f.evidence(feature).recoverSaved(data,f.after(feature)),'confirmed')
                    self.assertIsNone(data.baseline.serverNow)
                    self.assertEqual(data.before.native.serverNow,old_clock)
                    data.baseline.beforeCash+=1
                    self.assertIsNone(f.evidence(feature).recoverSaved(data,f.after(feature)))
                finally:f.close()

    def test_nonexact_cash_needs_strict_later_clock_full_sync_exact_target_and_finite_floor(self):
        for feature in ('properties','safehouse'):
            f=PurchaseFixture()
            try:
                data=f.begin(feature);evidence=f.evidence(feature)
                for change in ('clock_missing','clock_same','clock_older','clock_nan','lower_cash','cash_nan','full_sync',
                        'target_missing','target_jump','other_property','unknown_property'):
                    if feature=='safehouse' and change in ('other_property','unknown_property'):continue
                    with self.subTest(feature=feature,change=change):
                        after=f.after(feature)
                        if change=='clock_missing':after.native.serverNow=None
                        elif change=='clock_same':after.native.serverNow=1000
                        elif change=='clock_older':after.native.serverNow=999
                        elif change=='clock_nan':after.native.serverNow=float('nan')
                        elif change=='lower_cash':after.native.cash=8499 if feature=='properties' else 6999
                        elif change=='cash_nan':after.native.cash=float('nan')
                        elif change=='full_sync':after.native.fullSync=False
                        elif change=='target_missing':
                            if feature=='properties':after.native.properties.p_b.owned=0
                            else:after.native.safehouse=3
                        elif change=='target_jump':
                            if feature=='properties':after.native.properties.p_b.owned=2
                            else:after.native.safehouse=5
                        elif change=='other_property':after.native.properties.p_a.owned=2
                        else:after.native.properties.unknown=lua_table(f.h.lua,{'owned':1})
                        self.assertIsNone(evidence.recoverSaved(data,after))
            finally:f.close()

    def test_pending_busy_and_pending_flag_keep_positive_negative_saved_and_active_custody(self):
        for feature in ('properties','safehouse'):
            for code in ('pending','busy','pending_flag'):
                for positive in (True,False):
                    with self.subTest(feature=feature,code=code,positive=positive):
                        f=PurchaseFixture()
                        try:
                            f.executor.reply=lua_table(f.h.lua,{'ok':positive,**({'pending':True} if code=='pending_flag' else {'code':code})})
                            data=f.begin(feature)
                            after=f.after(feature,cash=(8500 if feature=='properties' else 7000)) if positive else f.raw(2,1002)
                            f.h.at(1);f.app.Step(f.app,after)
                            self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)),1)
                            f.h.at(46);after.revision=3;after.capturedAt=46;after.native.serverNow=1046
                            f.app.Step(f.app,after)
                            self.assertEqual(f.runtime.Status(f.runtime).outcomes[feature],'skipped_unconfirmed')
                            record=f.runtime.checkpoint.Records(f.runtime.checkpoint)[1]
                            self.assertEqual(record.actionKey,data.proposal.actionKey)
                            self.assertEqual(record.resources.cash,data.proposal.resources.cash)
                            f.restart();after.session=f.h.session['session'];after.revision=0
                            after.capturedAt=47;after.native.serverNow=1047;f.h.at(47)
                            f.app.Step(f.app,after)
                            self.assertIsNone(f.runtime.Status(f.runtime).recoveries[feature])
                            self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)),1)
                            self.assertEqual(len(f.executor.calls),0)
                        finally:f.close()

    def test_negative_contradictory_outcome_or_cash_keeps_saved_custody(self):
        for feature in ('properties','safehouse'):
            f=PurchaseFixture()
            try:
                f.executor.reply=lua_table(f.h.lua,{'ok':False});data=f.begin(feature)
                for changed in ('target','cash','both'):
                    with self.subTest(feature=feature,changed=changed):
                        after=f.after(feature) if changed in ('target','both') else f.raw(2,1002,cash=10001)
                        if changed=='target':after.native.cash=10000
                        self.assertIsNone(f.evidence(feature).recoverSaved(data,after))
                unchanged=f.raw(2,1002)
                self.assertEqual(f.evidence(feature).recoverSaved(data,unchanged),'rejected')
            finally:f.close()

    def test_exact_debit_path_keeps_legacy_clockless_compatibility(self):
        for feature in ('properties','safehouse'):
            with self.subTest(feature=feature):
                f=PurchaseFixture()
                try:
                    data=f.begin(feature);data.baseline.serverNow=None;data.before.native.serverNow=None
                    after=f.after(feature,cash=8500 if feature=='properties' else 7000)
                    evidence=f.evidence(feature)
                    self.assertEqual(evidence.evaluate(data.proposal,data.before,after,data.reply,data.baseline),'confirmed')
                    # Saved recovery needs a genuine historical clock even with an exact wallet.
                    self.assertIsNone(evidence.recoverSaved(data,after))
                finally:f.close()

    def test_nonexact_saved_outcome_cannot_replace_newer_revision_or_original_clock(self):
        for feature in ('properties','safehouse'):
            f=PurchaseFixture()
            try:
                data=f.begin(feature);evidence=f.evidence(feature)
                with self.subTest(feature=feature,change='same_revision'):
                    after=f.after(feature);after.revision=data.baseline.revision
                    self.assertIsNone(evidence.recoverSaved(data,after))
                with self.subTest(feature=feature,change='corrupt_new_clock'):
                    data.baseline.serverNow=1001
                    self.assertIsNone(evidence.recoverSaved(data,f.after(feature)))
                data.baseline.serverNow=None
                for clock in (None,False,float('nan')):
                    with self.subTest(feature=feature,change='missing_legacy_clock',clock=clock):
                        data.before.native.serverNow=clock
                        self.assertIsNone(evidence.recoverSaved(data,f.after(feature)))
                data.before.native.serverNow=1000
                with self.subTest(feature=feature,change='active_clock_is_header_only'):
                    header=lua_table(f.h.lua,{**f.h.session,'revision':1,'capturedAt':0})
                    self.assertEqual(evidence.evaluate(data.proposal,header,f.after(feature),data.reply,data.baseline),'pending')
            finally:f.close()

    def test_actual_saved_negative_needs_strict_new_observation_before_release(self):
        for feature in ('properties','safehouse'):
            with self.subTest(feature=feature):
                f=PurchaseFixture()
                try:
                    f.executor.reply=lua_table(f.h.lua,{'ok':False});data=f.begin(feature)
                    stale=f.raw(1,1002)
                    self.assertIsNone(f.evidence(feature).recoverSaved(data,stale))
                    f.restart();f.app.Step(f.app,f.raw(0,1000))
                    self.assertIsNone(f.runtime.Status(f.runtime).recoveries[feature])
                    self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)),1)
                    f.app.Step(f.app,f.raw(1,1002))
                    self.assertEqual(f.runtime.Status(f.runtime).recoveries[feature],'rejected')
                    self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)),0)
                    self.assertEqual(len(f.executor.calls),0)
                finally:f.close()

    def test_legacy_registry_includes_safehouse_saved_outcome_handler(self):
        f=base_fixture.AutomationRuntimeTests();f.setUp()
        try:self.assertIsNotNone(f.runtime.features.safehouse.recoverSaved)
        finally:f.runtime.Close(f.runtime)
