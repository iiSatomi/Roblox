"""Family uses verified player ID while retaining the existing named storage account."""
import unittest

from engine_harness import Harness, lua_table


class FamilyNamedIdentityTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.h.session['account'] = 'SamplePlayer'
        h = self.h
        self.source = h.lua.execute("""return {
            Current=function() return true end,
            Read=function(_,native)
                if native.userId~=123 then return nil end
                return {userId=123,name='SamplePlayer'}
            end}
        """)
        deps = {"identity":h.session,"playerInfoSource":self.source,"fingerprint":"a"*64,
            "release":"release-a","config":{"FAMILY":{"donateMin":100,"contributeMax":5,
                "baseCap":30,"capPerLevel":5,"maxCap":50,"capSlotMax":10,
                "staminaPerkCosts":[10,20],"perkTracks":{"boost":{"kind":"stamina"}}}}}
        for name in ('FamilyQuery','FamilyContributionState','FamilyContributions','FamilyContributionEvidence'):
            deps[name] = h.load('src/tabs/family/'+name+'.luau')
        deps['FamilyBlocked'] = h.load('src/features/FamilyBlocked.luau')
        deps['FamilyState'] = h.load('src/game/FamilyState.luau')
        self.tab = h.load('src/tabs/family/Module.luau').new(lua_table(h.lua,deps))
        self.reader = h.load('src/transport/NativeSnapshotReader.luau').new(
            lua_table(h.lua,h.session),h.clock,'a'*64)
        self.native = {"userId":123,"serverNow":100,"family":{"id":"fam"},"cash":1000,
            "pools":{"stamina":10},"inventory":{"gold_bar":5},"inventoryBound":{}}
        self.assertTrue(self.reader.ObserveSync(self.reader,lua_table(h.lua,self.native)))
        self.family = {"id":"fam","level":1,"capSlots":0,"memberCap":30,
            "members":[{"userId":123,"donated":0,"donatedGold":0,"contributed":0}],
            "perks":{"boost":0},"perkProgress":{"boost":0}}

    def observed_family(self):
        h = self.h
        raw,reason = self.reader.Capture(self.reader)
        self.assertIsNone(reason)
        read = self.tab.ReadSources(self.tab,self.reader)[1]
        request,reason = read.prepare(raw)
        self.assertIsNone(reason)
        staged,reason = read.accept(raw,request,lua_table(h.lua,{"ok":True,"family":self.family}))
        self.assertIsNone(reason)
        self.assertTrue(read.commit(staged))
        raw,reason = self.reader.Capture(self.reader)
        self.assertIsNone(reason)
        return raw

    def test_named_account_composes_queries_sends_confirms_and_preserves_durable_usage(self):
        h = self.h
        raw = self.observed_family()
        composed,reason = h.load('src/tabs/TabComposition.luau').build(lua_table(h.lua,[self.tab]),
            h.load('src/ui/Catalog.luau'),h.load('src/engine/FeatureRegistry.luau'),
            h.load('src/tabs/TabSnapshotAssembler.luau'))
        self.assertIsNone(reason)
        modules = {"Contracts":h.contracts}
        for name,folder in (("Broker","engine"),("Journal","engine"),("Scheduler","engine"),
                ("Session","engine"),("Context","game"),("Checkpoint","storage"),("PendingAction","storage")):
            modules[name] = h.load(f'src/{folder}/{name}.luau')
        modules['FamilyContributionUsage'] = h.load('src/tabs/family/FamilyContributionUsage.luau')
        store = h.lua.execute("return {strictRecovery=true,data={},Read=function(self,k) return self.data[k] end,Write=function(self,k,v) self.data[k]=v;return true end}")
        runtime = h.load('src/engine/AutomationRuntime.luau').new(lua_table(h.lua,{
            "modules":modules,"features":composed.features,"featurePages":composed.featurePages,
            "snapshotAssembler":composed.snapshotAssembler,"tabInstances":composed.tabs,
            "clock":h.clock,"transport":h.transport,"storage":store,"identity":h.session}))
        runtime.Resume(runtime)
        settings = lua_table(h.lua,{"familyCash":{"enabled":True,"amount":100,"reserve":0,
            "runBudget":200,"maxAttempts":2}})
        status = runtime.Step(runtime,raw,settings)
        self.assertEqual(len(h.transport.sent),1,str(status.reasons.familyCash))
        proposal = h.transport.sent[1]
        self.assertEqual((proposal.account,proposal.intent.actorId),('SamplePlayer',123))
        self.family['members'][0]['donated'] = 100
        h.transport.callbacks[1](lua_table(h.lua,{"ok":True,"family":self.family}))
        h.at(1)
        self.native.update(cash=900,serverNow=101)
        self.assertTrue(self.reader.ObserveSync(self.reader,lua_table(h.lua,self.native)))
        after = self.reader.Capture(self.reader)[0]
        settings.familyCash.enabled = False
        status = runtime.Step(runtime,after,settings)
        self.assertEqual(status.outcomes.familyCash,'confirmed')
        self.assertFalse(status.storageFault)
        restarted = modules['Checkpoint'].new(store,modules['FamilyContributionUsage'],None,modules['PendingAction'])
        _,reason = restarted.Load(restarted,'SamplePlayer',h.session['place'],'release-a')
        self.assertIsNone(reason)
        usage,reason = restarted.FamilyContributionUsage(restarted,after)
        self.assertIsNone(reason)
        self.assertEqual((usage.usage.familyCash.attempted,usage.usage.familyCash.spent),(1,100))
        self.assertEqual(h.session['account'],'SamplePlayer')

    def test_foreign_native_or_source_identity_cannot_stage_a_personal_family(self):
        self.source.Read = self.h.lua.eval("function() return {userId=999,name='SamplePlayer'} end")
        raw = self.reader.Capture(self.reader)[0]
        staged,reason = self.tab.state.Stage(self.tab.state,raw,lua_table(self.h.lua,{"ok":True,"family":self.family}))
        self.assertIsNone(staged)
        self.assertIsNotNone(reason)

    def test_reviewed_family_capacity_accepts_57_and_60_members_but_rejects_61_and_excess_slots(self):
        for count in (57,60,61):
            with self.subTest(count=count):
                self.setUp()
                self.family.update(level=137,capSlots=10,memberCap=60)
                self.family['members'] += [{'userId':200+i} for i in range(count-1)]
                raw = self.reader.Capture(self.reader)[0]
                staged,reason = self.tab.state.Stage(self.tab.state,raw,
                    lua_table(self.h.lua,{'ok':True,'family':self.family}))
                if count <= 60:
                    self.assertIsNone(reason)
                    self.assertEqual(staged.familyContributionProof.family.memberCap,60)
                else:
                    self.assertIsNone(staged)
        for level,slots,reported,count in ((1,0,30,31),(137,11,61,57),(1,0,60,1),(137,0,60,57)):
            with self.subTest(level=level,slots=slots,reported=reported,count=count):
                self.setUp()
                self.family.update(level=level,capSlots=slots,memberCap=reported)
                self.family['members'] += [{'userId':200+i} for i in range(count-1)]
                raw = self.reader.Capture(self.reader)[0]
                self.assertIsNone(self.tab.state.Stage(self.tab.state,raw,
                    lua_table(self.h.lua,{'ok':True,'family':self.family}))[0])

    def test_full_configured_family_donation_uses_retained_capacity_for_reply_and_recovery(self):
        self.family.update(level=137,capSlots=10,memberCap=60)
        self.family['members'] += [{'userId':200+i} for i in range(56)]
        self.test_named_account_composes_queries_sends_confirms_and_preserves_durable_usage()


if __name__ == '__main__': unittest.main()
