"""Explicit native-total Gold permission preserves loose-only defaults and custody."""
import unittest

from engine_harness import lua_table
import test_conditional_feature_contracts
from recovery_projection_harness import assert_projection


class FamilyGoldPoolTests(unittest.TestCase):
    setUp = test_conditional_feature_contracts.ConditionalContracts.setUp
    table = test_conditional_feature_contracts.ConditionalContracts.table
    header = test_conditional_feature_contracts.ConditionalContracts.header
    family = test_conditional_feature_contracts.ConditionalContracts.family

    def prepare(self, allow=True, loose=5, bound=2, reserve=6, amount=1):
        module,before,family = self.family()
        before.native.inventory.gold_bar = loose
        before.native.inventoryBound.gold_bar = bound
        view,reason = module.read(before,before)
        self.assertIsNone(reason)
        settings = self.table({'enabled':True,'amount':amount,'reserve':reserve,'runBudget':amount,
            'maxAttempts':1,'allowNativeGoldPool':allow})
        proposal,reason = self.h.load('src/tabs/family/FamilyContributions.luau').gold.propose(
            view,settings,self.table({}))
        return module,before,family,proposal,reason

    def test_mixed_gold_requires_explicit_boolean_opt_in_and_total_reserve(self):
        for allow in (False,None,'true',1):
            with self.subTest(allow=allow):
                self.assertIsNone(self.prepare(allow=allow,reserve=0)[3])
        self.assertIsNone(self.prepare(reserve=7)[3])
        _,_,_,proposal,reason = self.prepare()
        self.assertIsNone(reason)
        self.assertTrue(proposal.intent.allowNativeGoldPool)
        self.assertEqual(proposal.resources.gold_bar,1)
        module,before,_,_,_ = self.prepare()
        view = module.read(before,before)[0]
        self.assertIsNone(self.h.load('src/tabs/family/FamilyContributions.luau').gold.propose(view,
            self.table({'enabled':True,'amount':1,'reserve':6,'runBudget':1,'maxAttempts':1,
                'allowNativeGoldPool':True}),self.table({'uncertainGold':1}))[0])

    def test_either_or_split_origin_requires_exact_total_debit_and_personal_receipt(self):
        for amount,loose,bound in ((1,4,2),(1,5,1),(2,4,1)):
            with self.subTest(amount=amount,loose=loose,bound=bound):
                module,before,family,p,reason = self.prepare(amount=amount,reserve=7-amount)
                self.assertIsNone(reason)
                evidence = self.h.load('src/tabs/family/FamilyContributionEvidence.luau').new(module)
                baseline,reason = evidence.capture(p,before)
                self.assertIsNone(reason)
                self.assertEqual((baseline.goldLoose,baseline.goldBound,baseline.balance),(5,2,7))
                _,after,_ = self.family(2)
                after.native.inventory.gold_bar,after.native.inventoryBound.gold_bar = loose,bound
                family['members'][0]['donatedGold'] += amount
                reply = self.table({'ok':True,'family':family})
                self.assertEqual(evidence.evaluate(p,before,after,reply,baseline),'confirmed')
                # Exact total alone cannot hide an origin increase/transfer.
                after.native.inventory.gold_bar,after.native.inventoryBound.gold_bar = 4-amount,3
                self.assertEqual(evidence.evaluate(p,before,after,reply,baseline),'pending')
                after.native.inventory.gold_bar,after.native.inventoryBound.gold_bar = loose,bound
                reply.family.members[1].donatedGold -= 1
                self.assertEqual(evidence.evaluate(p,before,after,reply,baseline),'pending')

    def composed(self):
        import test_family_named_identity
        helper = test_family_named_identity.FamilyNamedIdentityTests(methodName='runTest')
        helper.setUp()
        h = helper.h
        helper.native['inventoryBound']['gold_bar'] = 2
        self.assertTrue(helper.reader.ObserveSync(helper.reader,lua_table(h.lua,helper.native)))
        raw = helper.observed_family()
        composed,reason = h.load('src/tabs/TabComposition.luau').build(lua_table(h.lua,[helper.tab]),
            h.load('src/ui/Catalog.luau'),h.load('src/engine/FeatureRegistry.luau'),h.load('src/tabs/TabSnapshotAssembler.luau'))
        self.assertIsNone(reason)
        modules = {'Contracts':h.contracts,'FamilyContributionUsage':h.load('src/tabs/family/FamilyContributionUsage.luau')}
        for name,folder in [('Broker','engine'),('Journal','engine'),('Scheduler','engine'),('Session','engine'),
                ('Context','game'),('ResourceReservations','engine'),('Checkpoint','storage'),('PendingAction','storage')]:
            modules[name] = h.load(f'src/{folder}/{name}.luau')
        store = h.lua.execute('''return {strictRecovery=true,data={},Read=function(self,k) return self.data[k] end,
            Write=function(self,k,v) self.data[k]=v;return true end}''')
        h.lua.globals().goldFamily = lua_table(h.lua,helper.family)
        executor = h.lua.execute('''return {queued={},calls={},Schedule=function(self,fn) self.queued[#self.queued+1]=fn;return true end,
            Invoke=function(self,remote,method,...)
                self.calls[#self.calls+1]={remote=remote,args=table.pack(...)}
                goldFamily.members[1].donatedGold=goldFamily.members[1].donatedGold+1
                return {ok=true,family=goldFamily}
            end,
            Drain=function(self) local q=self.queued;self.queued={};for _,fn in ipairs(q) do fn() end end}''')
        plan = h.load('src/transport/NativeCallPlan.luau')
        transport = h.load('src/transport/NativeDispatchAdapter.luau').new(
            plan.withFamily(plan,h.load('src/tabs/family/FamilyCallPlan.luau')),executor)
        runtime = h.load('src/engine/AutomationRuntime.luau').new(lua_table(h.lua,{'modules':modules,
            'identity':h.session,'clock':h.clock,'transport':transport,'storage':store,
            'features':composed.features,'featurePages':composed.featurePages,
            'snapshotAssembler':composed.snapshotAssembler,'tabInstances':composed.tabs}))
        settings = lua_table(h.lua,{'familyGold':{'enabled':True,'amount':1,'reserve':6,'runBudget':1,
            'maxAttempts':1,'allowNativeGoldPool':True}})
        runtime.SetSelectionGuard(runtime,h.lua.eval('function(settings) return function(feature) return settings[feature] end end')(settings))
        runtime.Resume(runtime)
        return helper,raw,runtime,executor,settings

    def test_composed_dispatch_revocation_is_unsent_and_one_native_purchase_reconciles_durably(self):
        helper,raw,runtime,executor,settings = self.composed()
        h = helper.h
        runtime.Step(runtime,raw,settings)
        self.assertEqual(len(executor.queued),1)
        settings.familyGold.allowNativeGoldPool = False
        executor.Drain(executor)
        self.assertEqual(len(executor.calls),0)
        self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)),0)
        usage,reason = runtime.checkpoint.FamilyContributionUsage(runtime.checkpoint,raw)
        self.assertIsNone(reason)
        self.assertEqual((usage.usage.familyGold.attempted,usage.usage.familyGold.spent),(0,0))
        # A fresh owned frame and restored explicit permission may admit one send.
        settings.familyGold.allowNativeGoldPool = True
        h.at(1)
        helper.native['serverNow'] = 101
        helper.reader.ObserveSync(helper.reader,lua_table(h.lua,helper.native))
        raw = helper.observed_family()
        status = runtime.Step(runtime,raw,settings)
        executor.Drain(executor)
        self.assertEqual(len(executor.calls),1,str(status.reasons.familyGold))
        self.assertEqual((executor.calls[1].remote,executor.calls[1].args.n),('FamilyAction',4))
        self.assertEqual([executor.calls[1].args[i] for i in (1,2,3,4)],['donategold',1,None,None])
        h.at(2)
        helper.native['serverNow'] = 102
        helper.native['inventoryBound']['gold_bar'] = 1
        helper.reader.ObserveSync(helper.reader,lua_table(h.lua,helper.native))
        after = helper.reader.Capture(helper.reader)[0]
        status = runtime.Step(runtime,after,settings)
        self.assertEqual(status.outcomes.familyGold,'confirmed')
        self.assertFalse(status.storageFault)
        self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)),0)
        checkpoint = h.load('src/storage/Checkpoint.luau').new(runtime.checkpoint.storage,
            h.load('src/tabs/family/FamilyContributionUsage.luau'),None,h.load('src/storage/PendingAction.luau'))
        _,reason = checkpoint.Load(checkpoint,h.session['account'],h.session['place'],h.session['release'])
        self.assertIsNone(reason)
        usage,reason = checkpoint.FamilyContributionUsage(checkpoint,after)
        self.assertIsNone(reason)
        self.assertEqual((usage.usage.familyGold.attempted,usage.usage.familyGold.spent),(1,1))

    def test_capture_dispatch_and_saved_recovery_bind_the_origin_permission(self):
        module,before,family,p,reason = self.prepare()
        self.assertIsNone(reason)
        evidence = self.h.load('src/tabs/family/FamilyContributionEvidence.luau').new(module)
        decoded = assert_projection(self,self.h,evidence,p,before)
        self.assertTrue(decoded.proposal.intent.allowNativeGoldPool)
        self.assertTrue(evidence.canDispatch(p,before))
        p.intent.allowNativeGoldPool = False
        self.assertFalse(evidence.canDispatch(p,before))
        self.assertIsNone(evidence.capture(p,before)[0])
        p.intent.allowNativeGoldPool = True
        family['members'][0]['donatedGold'] += 1
        decoded.reply = self.table({'ok':True,'family':family})
        _,after,_ = self.family(2)
        after.session = 'run-b'
        after.native.inventory.gold_bar,after.native.inventoryBound.gold_bar = 5,1
        self.assertEqual(evidence.recoverSaved(decoded,after),'confirmed')
        decoded.proposal.intent.allowNativeGoldPool = False
        self.assertIsNone(evidence.recoverSaved(decoded,after))

    def test_worst_case_origin_claims_and_uncertain_total_exposure_remain_held(self):
        _,before,_,p,reason = self.prepare()
        self.assertIsNone(reason)
        module = self.h.load('src/engine/ResourceReservations.luau')
        claims,reason = module.ForProposal(p,before)
        self.assertIsNone(reason)
        self.assertEqual(claims.funds.gold_bar,1)
        self.assertIsNone(claims['items']['L:gold_bar'])
        held = self.table({'members':{},'items':{'B:gold_bar':2},'funds':{},'allCrew':False,'allItems':False})
        sources = self.h.lua.eval('function(c) return {{id="other",read=function() return {account="123",place="73897506680154",release="release-a",feature="other",claims=c} end}} end')(held)
        owner = module.new(self.table(self.h.session),self.h.lua.eval('function() return {} end'),sources)
        self.assertIsNone(owner.Check(owner,p,before)[0])
        held['items']['B:gold_bar'] = 1
        # Total reserve remains binding even if every individual origin can pay.
        self.assertIsNone(owner.Check(owner,p,before)[0])
        p.intent.reserve = 5
        accepted,reason = owner.Check(owner,p,before)
        self.assertIsNotNone(accepted,reason)
        held['items']['B:gold_bar'] = None
        held['items']['L:gold_bar'] = 5
        self.assertIsNone(owner.Check(owner,p,before)[0])
        p.intent.allowNativeGoldPool = False
        claims,reason = module.ForProposal(p,before)
        self.assertIsNone(reason)
        self.assertEqual(claims['items']['L:gold_bar'],1)
        self.assertIsNone(claims.funds.gold_bar)
        held['items']['L:gold_bar'] = None
        held.funds.gold_bar = 1
        p.intent.amount,p.intent.reserve,p.resources.gold_bar = 5,0,5
        self.assertIsNone(owner.Check(owner,p,before)[0])


if __name__ == '__main__': unittest.main()
