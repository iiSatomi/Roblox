"""Offline actual Crew heal App/adapter acceptance; no live Stamina use."""
import unittest
import test_crew_equip_runtime as equip_fixture
from engine_harness import lua_table
class CrewHealRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.e=equip_fixture.CrewEquipRuntimeTests();self.e.setUp();self.f=self.e.f;self.h=self.e.h
        self.f.app.Destroy(self.f.app);self.f.feature_id='crewHeal'
        self.f.tab_dependencies['CrewHeal']=self.h.load('src/tabs/crew/CrewHeal.luau');self.f.start_current()
    def tearDown(self):self.f.tearDown()
    def raw(self,revision=1,stamina=15,injury=1601):
        raw=self.f.f.raw(revision=revision)
        raw.native.pools=lua_table(self.h.lua,{'stamina':stamina,'energy':50})
        raw.native.crew[2].healId='injury-a';raw.native.crew[2].injuredUntil=injury
        return raw
    def step(self,revision=1,stamina=15,injury=1601):
        raw=self.raw(revision,stamina,injury);self.h.at(raw.capturedAt);self.f.app.Step(self.f.app,raw);return raw
    def choose(self):self.f.app.Set(self.f.app,'crewHeal.enabled',True);self.f.app.Resume(self.f.app)
    def test_actual_native_heal_uses_exact_member_episode_and_stamina_effect(self):
        self.choose();self.step();self.f.drain();call=self.f.executor.calls[1]
        self.assertEqual(call.remote,'CrewAction');self.assertEqual(call.args.n,3)
        self.assertEqual((call.args[1],call.args[2]),('heal',2))
        self.assertEqual(call.args[3].memberId,'injury-a');self.assertEqual(call.args[3].injuredUntil,1601)
        self.assertEqual(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)[1].resources.stamina,5)
        self.step(2,10,1301);self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.crewHeal,'confirmed')
    def test_saved_exact_heal_recovers_without_replaying_stamina_spend(self):
        self.choose();self.step();self.f.drain();self.f.restart()
        after=self.raw(0,10,1301);after.native.serverNow=1005;self.f.app.Step(self.f.app,after)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.crewHeal,'confirmed')
        self.assertEqual(len(self.f.executor.calls),1)
    def test_other_stamina_hold_cannot_borrow_the_configured_reserve(self):
        self.h.lua.globals().crewExternalHold=lua_table(self.h.lua,{
            'account':self.h.session['account'],'place':self.h.session['place'],'release':self.h.session['release'],
            'feature':'bosses','actionKey':'uncertain-hit','claims':{'allCrew':False,'allItems':False,
                'members':{},'items':{},'funds':{'stamina':5}}})
        self.choose();self.step();self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
    def test_pending_negative_reply_cannot_release_injury_custody(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':False,'pending':True})
        self.choose();self.step();self.f.drain();self.step(2)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.crewHeal)
    def test_natural_expiry_and_unrelated_stamina_debit_do_not_prove_healing(self):
        self.choose();self.step(injury=1100);self.f.drain()
        after=self.raw(2,13,1100);after.native.serverNow=1200;self.h.at(2);self.f.app.Step(self.f.app,after)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.crewHeal)

    def stamina_hold(self):
        self.h.lua.globals().crewExternalHold=lua_table(self.h.lua,{
            'account':self.h.session['account'],'place':self.h.session['place'],'release':self.h.session['release'],
            'feature':'bosses','actionKey':'new-hit','claims':{'allCrew':False,'allItems':False,
                'members':{},'items':{},'funds':{'stamina':5}}})
    def test_other_stamina_hold_appearing_after_queue_blocks_emission(self):
        self.choose();self.step();self.stamina_hold();self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
    def test_changed_injury_episode_blocks_queued_heal(self):
        self.choose();self.step();self.step(2,injury=1701);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
    def test_saved_wrong_stamina_or_member_remains_held(self):
        self.choose();self.step();self.f.drain();self.f.restart()
        after=self.raw(0,11,1301);after.native.serverNow=1005;self.f.app.Step(self.f.app,after)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).recoveries.crewHeal)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),1)
    def test_queued_disable_and_unload_prevent_heal(self):
        self.choose();self.step();self.f.app.Set(self.f.app,'crewHeal.enabled',False);self.f.app.Destroy(self.f.app);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
    def test_exact_rejection_does_not_count_as_healed(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':False})
        self.choose();self.step();self.f.drain();self.step(2)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.crewHeal,'rejected')
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
