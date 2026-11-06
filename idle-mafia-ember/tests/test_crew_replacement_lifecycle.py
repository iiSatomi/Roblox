"""Real funded replacement ownership; no Roblox transport or native autoroll."""
import unittest

from engine_harness import Harness, lua_table


class CrewReplacementLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness()
        self.store=self.h.lua.execute('''return {data={},strictRecovery=true,
            Read=function(self,key) return self.data[key] end,
            Write=function(self,key,value) self.data[key]=value;return true end}''')
        odds=[0,100,0,0,0,0,0,0]
        self.helper,reason=self.h.load('src/tabs/crew/CrewReplacement.luau').new(
            lua_table(self.h.lua,{'CREW':{'hireTiers':[{'id':'street','cost':100,
                'odds':odds,'oddsLucky':odds}]}}),'a'*64,'release-a')
        self.assertIsNone(reason)
        self.transactions=self.h.load('src/tabs/crew/CrewReplacementTransactions.luau')
        self.runtimeModule=self.h.load('src/tabs/crew/CrewReplacementRuntime.luau')
        self.settings=lua_table(self.h.lua,{'enabled':True,'allowDismiss':True,
            'policy':'Bounded replacement','slot':2,'tier':'street','targetRarity':2,
            'maxDismissRarity':1,'cashReserve':100,'minHome':1,'maxCost':100,
            'maxSpend':100,'maxAttempts':1})
        self.runtime=self.new_runtime()
        self.before=self.raw()

    def new_runtime(self):
        runtime,reason=self.runtimeModule.new(lua_table(self.h.lua,{'storage':self.store,
            'identity':self.h.session,'clock':self.h.clock,'helper':self.helper,
            'transactions':self.transactions}))
        self.assertIsNone(reason)
        return runtime

    def raw(self,revision=1,stage='original',cash=1000,runtime=None,mutate=None):
        selected=({'name':'Weak','rarity':1,'atk':1,'def':1,'healId':'old'} if stage=='original'
            else {} if stage=='empty' else {'name':'New','rarity':2,'atk':7,'def':8,'healId':'new'})
        raw=self.h.snapshot(revision=revision,native={'fullSync':True,'serverNow':99+revision,
            'cash':cash,'cityId':'ny','derived':{'luckyHire':False},'crew':[{},selected,
                {'name':'Keep','rarity':3,'atk':3,'def':3,'healId':'keep'}]},
            economyProof={'account':'user-a','capturedAt':self.h.lua.globals().testNow,
                'city':'ny','revision':1,'familyId':'','rulerId':'','hirePct':0})
        if mutate: mutate(raw)
        raw=self.helper.Enrich(self.helper,raw)[0]
        current=runtime or self.runtime
        return current.Enrich(current,raw,lua_table(self.h.lua,{'crewRoll':self.settings}))

    def plan(self):
        view,reason=self.helper.read(self.before,self.before);self.assertIsNone(reason)
        proposal,reason=self.helper.propose(view,self.settings);self.assertIsNone(reason)
        return proposal

    def prepare(self,proposal,before):
        baseline,reason=self.helper.capture(proposal,before);self.assertIsNone(reason)
        prepared=self.runtime.lifecycle.prepare(proposal,before,baseline,0)
        self.assertTrue(prepared[0] if isinstance(prepared,tuple) else prepared)
        return baseline

    def send(self,proposal,before):
        call,reason=self.runtime.lifecycle.authorize(proposal,before,0);self.assertIsNone(reason)
        return call

    def empty_stage(self):
        proposal=self.plan();baseline=self.prepare(proposal,self.before)
        call=self.send(proposal,self.before)
        self.assertEqual([call.args[i] for i in (1,2)],['dismiss',2])
        self.assertTrue(self.runtime.lifecycle.returned(proposal,lua_table(self.h.lua,{'ok':True}))[0])
        after=self.raw(2,'empty')
        self.assertTrue(self.runtime.lifecycle.resolve(proposal,'confirmed',after,0))
        self.assertEqual(self.runtime.owner.Active(self.runtime.owner).stage,'observedEmpty')
        return after,proposal,baseline

    def hire_stage(self):
        empty,_,_=self.empty_stage()
        funded=self.runtime.owner.Active(self.runtime.owner).funded
        proposal,reason=self.helper.FundedHire(empty,funded);self.assertIsNone(reason)
        baseline=self.prepare(proposal,empty)
        return empty,proposal,baseline

    def test_explicit_dismiss_permission_and_funding_are_required_before_any_owner_write(self):
        view=self.helper.read(self.before,self.before)[0]
        for permission in (False,None):
            with self.subTest(permission=permission):
                self.settings.allowDismiss=permission
                self.assertIsNone(self.helper.propose(view,self.settings)[0])
                self.assertIsNone(self.runtime.owner.Active(self.runtime.owner))
        self.settings.allowDismiss=True
        for field,value in (('cash',199),('autoRolls',{'native':True})):
            with self.subTest(field=field):
                before=self.raw();before.native[field]=lua_table(self.h.lua,value)
                viewed=self.helper.read(before,before)
                view=viewed[0] if isinstance(viewed,tuple) else viewed
                self.assertTrue(view is None or self.helper.propose(view,self.settings)[0] is None)
        self.assertEqual(self.runtime.owner.Usage(self.runtime.owner).attempted,0)

    def test_two_exact_stages_persist_attempt_before_dismiss_and_spend_before_hire(self):
        empty,hire,baseline=self.hire_stage()
        owner=self.runtime.owner
        self.assertEqual((owner.Usage(owner).attempted,owner.Usage(owner).spent),(1,0))
        call=self.send(hire,empty)
        self.assertEqual([call.args[i] for i in (1,2,3)],['hire','street',100])
        self.assertEqual(owner.Usage(owner).spent,100)
        self.assertIsNone(owner.SubmitCall(owner,empty,0)[0])
        reply=lua_table(self.h.lua,{'ok':True,'index':2,
            'member':{'name':'New','rarity':2,'atk':7,'def':8,'healId':'new'}})
        self.assertTrue(self.runtime.lifecycle.returned(hire,reply)[0])
        after=self.raw(3,'member',900)
        self.assertEqual(self.helper.evaluate(hire,empty,after,reply,baseline),'confirmed')
        self.assertTrue(self.runtime.lifecycle.resolve(hire,'confirmed',after,0)[0])
        self.assertIsNone(owner.Active(owner))
        restored=self.new_runtime()
        self.assertEqual((restored.owner.Usage(restored.owner).attempted,restored.owner.Usage(restored.owner).spent),(1,100))

    def test_each_prepared_or_sent_stage_loses_emission_permission_after_restart(self):
        for stage in ('preparedDismiss','sentDismiss','preparedHire','sentHire'):
            with self.subTest(stage=stage):
                self.setUp()
                if stage.endswith('Dismiss'):
                    before=self.before;proposal=self.plan();self.prepare(proposal,before)
                else:
                    before,proposal,_=self.hire_stage()
                if stage.startswith('sent'): self.send(proposal,before)
                restored=self.new_runtime();owner=restored.owner
                self.assertEqual(owner.Active(owner).stage,stage)
                self.assertFalse(owner.IsPreparedHere(owner))
                self.assertFalse(owner.MarkSending(owner,before,0)[0])
                self.assertIsNone(owner.SubmitCall(owner,before,0)[0])
                self.assertFalse(owner.CancelUnsent(owner,proposal.actionKey)[0])
                self.assertFalse(owner.ClearObserved(owner)[0])
                exposure,reason=owner.ReservationClaims(owner,
                    self.h.load('src/engine/ResourceReservations.luau'),before)
                self.assertIsNone(reason)
                self.assertEqual(exposure.claims.funds.cash,100)
                if stage.endswith('Hire'): self.assertTrue(exposure.claims.allCrew)
                else: self.assertTrue(exposure.claims.members['id:old'])

    def test_rejected_hire_keeps_funded_empty_custody_and_spend_until_explicit_review(self):
        empty,hire,_=self.hire_stage();self.send(hire,empty)
        reply=lua_table(self.h.lua,{'ok':False,'code':'cash'})
        self.runtime.lifecycle.returned(hire,reply)
        after=self.raw(3,'empty')
        self.assertTrue(self.runtime.lifecycle.resolve(hire,'rejected',after,0))
        restored=self.new_runtime();owner=restored.owner
        self.assertEqual(owner.Active(owner).stage,'sentHire')
        self.assertEqual(owner.Usage(owner).spent,100)
        self.assertIsNone(owner.PrepareHire(owner,after,0)[0])
        self.assertFalse(owner.CancelUnsent(owner,hire.actionKey)[0])
        self.assertTrue(owner.ReleaseRejectedHire(owner,after,0)[0])
        self.assertEqual(owner.Resolution(owner).kind,'rejected')
        self.assertEqual(owner.Usage(owner).spent,100)

    def test_hire_requires_exact_new_member_cash_and_unchanged_other_roster(self):
        for change in ('cash','other','member','index','incomplete'):
            with self.subTest(change=change):
                self.setUp()
                empty,hire,baseline=self.hire_stage();self.send(hire,empty)
                reply=lua_table(self.h.lua,{'ok':True,'index':3 if change=='index' else 2,
                    'member':{'name':'New','rarity':2,'atk':7,'def':8,'healId':'new'}})
                self.runtime.lifecycle.returned(hire,reply)
                def mutate(raw):
                    if change=='cash': raw.native.cash=901
                    if change=='other': raw.native.crew[3].atk=4
                    if change=='member': raw.native.crew[2].healId='unrelated'
                    if change=='incomplete': raw.native.fullSync=False
                after=self.raw(3,'member',900,mutate=mutate)
                self.assertEqual(self.helper.evaluate(hire,empty,after,reply,baseline),'pending')
                self.assertEqual(self.runtime.owner.Active(self.runtime.owner).stage,'sentHire')

    def test_transient_native_negative_reply_does_not_release_dismissal_custody(self):
        proposal=self.plan();baseline=self.prepare(proposal,self.before);self.send(proposal,self.before)
        reply=lua_table(self.h.lua,{'ok':False,'code':'rate_limited'})
        self.runtime.lifecycle.returned(proposal,reply)
        after=self.raw(2)
        self.assertEqual(self.helper.evaluate(proposal,self.before,after,reply,baseline),'pending')
        self.assertFalse(self.runtime.lifecycle.resolve(proposal,'rejected',after,0)[0])
        self.assertEqual(self.runtime.owner.Active(self.runtime.owner).stage,'sentDismiss')

    def test_observed_empty_restart_can_only_continue_the_original_funded_hire(self):
        _,dismiss,_=self.empty_stage()
        self.h.session['session']='run-b'
        self.runtime=self.new_runtime()
        before=self.raw(0,'empty')
        before.native.serverNow=105
        funded=self.runtime.owner.Active(self.runtime.owner).funded
        hire,reason=self.helper.FundedHire(before,funded);self.assertIsNone(reason)
        self.assertEqual((hire.intent.attemptedBefore,hire.intent.cost),(0,100))
        self.assertNotEqual(hire.actionKey,dismiss.actionKey)
        self.prepare(hire,before)
        call=self.send(hire,before)
        self.assertEqual(call.args[1],'hire')
        self.assertEqual(self.runtime.owner.Usage(self.runtime.owner).attempted,1)

    def test_persistence_failure_cannot_authorize_and_ambiguous_write_stays_held_on_restart(self):
        for mode in ('nil','false','throw','write_nil'):
            with self.subTest(mode=mode):
                self.setUp()
                self.store.mode=mode
                self.store.Write=self.h.lua.eval('''function(self,key,value)
                    if self.mode=='throw' then error('test refusal') end
                    if self.mode=='write_nil' then self.data[key]=value end
                    if self.mode=='false' then return false end
                    return nil end''')
                proposal=self.plan()
                baseline=self.helper.capture(proposal,self.before)[0]
                self.assertFalse(self.runtime.lifecycle.prepare(proposal,self.before,baseline,0)[0])
                self.assertIsNone(self.runtime.owner.Active(self.runtime.owner))
                self.assertIsNone(self.runtime.lifecycle.authorize(proposal,self.before,0)[0])
                restored=self.new_runtime()
                active=restored.owner.Active(restored.owner)
                if mode=='write_nil':
                    self.assertEqual(active.stage,'preparedDismiss')
                    self.assertFalse(restored.owner.IsPreparedHere(restored.owner))
                    self.assertEqual(restored.owner.Usage(restored.owner).attempted,1)
                else:
                    self.assertIsNone(active)
                    self.assertEqual(restored.owner.Usage(restored.owner).attempted,0)

    def test_known_unsent_hire_restores_only_its_funded_empty_stage_without_new_cycle(self):
        empty,hire,_=self.hire_stage();self.send(hire,empty)
        owner=self.runtime.owner
        self.assertTrue(owner.CancelUnsent(owner,hire.actionKey)[0])
        self.assertEqual(owner.Active(owner).stage,'observedEmpty')
        self.assertEqual((owner.Usage(owner).attempted,owner.Usage(owner).spent),(1,0))
        self.assertEqual(owner.Resolution(owner).kind,'known_unsent')
        restored=self.new_runtime()
        self.assertEqual(restored.owner.Active(restored.owner).stage,'observedEmpty')
        self.assertEqual(restored.owner.Usage(restored.owner).attempted,1)

    def test_funded_cash_and_member_custody_remain_reserved_after_restart(self):
        empty,_,_=self.empty_stage()
        restored=self.new_runtime();owner=restored.owner
        reservations=self.h.load('src/engine/ResourceReservations.luau')
        provider=self.h.lua.eval('''function(owner,reservations) return {id='replacement',
            read=function(raw) return owner:ReservationClaims(reservations,raw) end} end''')(owner,reservations)
        shared=reservations.new(lua_table(self.h.lua,self.h.session),
            self.h.lua.eval('function() return {} end'),lua_table(self.h.lua,[provider]))
        held,reason=shared.Held(shared,empty);self.assertIsNone(reason)
        self.assertEqual(held.funds.cash,100)
        self.assertTrue(held.members['id:old'])
        other=self.h.proposal('skills','skills:other',revision=2)
        other.resources=lua_table(self.h.lua,{'cash':901})
        other.intent=lua_table(self.h.lua,{'kind':'skills'})
        self.assertIsNone(shared.Check(shared,other,empty)[0])
        other.resources.cash=900
        self.assertIsNotNone(shared.Check(shared,other,empty)[0])

    def test_replacement_cash_reserve_includes_other_pending_funding_before_dismissal(self):
        reservations=self.h.load('src/engine/ResourceReservations.luau')
        other=lua_table(self.h.lua,{**self.h.session,'feature':'jobs','actionKey':'other',
            'resources':{'cash':850}})
        shared=reservations.new(lua_table(self.h.lua,self.h.session),
            self.h.lua.eval('function(record) return function() return {record} end end')(other))
        dismiss=self.plan()
        self.assertIsNone(shared.Check(shared,dismiss,self.before)[0])
        other.resources.cash=800
        self.assertIsNotNone(shared.Check(shared,dismiss,self.before)[0])
        empty,_,_=self.empty_stage()
        hire,reason=self.helper.FundedHire(empty,self.runtime.owner.Active(self.runtime.owner).funded)
        self.assertIsNone(reason)
        other.resources.cash=850
        self.assertIsNone(shared.Check(shared,hire,empty)[0])
        other.resources.cash=800
        self.assertIsNotNone(shared.Check(shared,hire,empty)[0])

    def test_pending_hire_reply_survives_restart_without_refund_or_new_emission(self):
        empty,hire,_=self.hire_stage();self.send(hire,empty)
        reply=lua_table(self.h.lua,{'ok':True,'pending':True})
        self.runtime.lifecycle.returned(hire,reply)
        restored=self.new_runtime();owner=restored.owner
        self.assertEqual(owner.Active(owner).stage,'sentHire')
        self.assertTrue(owner.Active(owner).reply.pending)
        self.assertEqual((owner.Usage(owner).attempted,owner.Usage(owner).spent),(1,100))
        self.assertFalse(owner.CancelUnsent(owner,hire.actionKey)[0])
        self.assertIsNone(owner.SubmitCall(owner,empty,0)[0])
        after=self.raw(3,'empty')
        self.assertFalse(owner.ReleaseRejectedHire(owner,after,0)[0])
        self.assertFalse(owner.ClearObserved(owner)[0])

    def test_stale_owner_cannot_overwrite_newer_prepared_generation(self):
        stale=self.new_runtime()
        proposal=self.plan();self.prepare(proposal,self.before)
        self.assertFalse(stale.owner.PrepareDismiss(stale.owner,proposal,self.before,0)[0])
        self.assertIsNotNone(stale.owner.fault)
        restored=self.new_runtime()
        self.assertEqual(restored.owner.Active(restored.owner).stage,'preparedDismiss')
        self.assertEqual(restored.owner.Usage(restored.owner).attempted,1)


if __name__=='__main__': unittest.main()
