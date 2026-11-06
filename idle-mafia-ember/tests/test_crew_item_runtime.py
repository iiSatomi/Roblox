"""Guarded Crew consumables through actual tab source/App/checkpoint/adapter."""
import unittest
import hashlib
import test_crew_runtime as runtime_fixture
from engine_harness import lua_table


class CrewItemRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.f = runtime_fixture.CrewRuntimeTests()
        self.f.setUp()
        self.f.app.Destroy(self.f.app)
        self.h = self.f.h
        self.f.feature_id = 'crewHealItems'
        deps = self.f.tab_dependencies
        deps['CrewHealItems'] = self.h.load('src/tabs/crew/CrewHealItems.luau')
        deps['NativeHealItemCatalog'] = self.h.load('src/tabs/crew/NativeHealItemCatalog.luau')
        deps['config'].TERRITORY.injurySeconds = 1200
        deps['config'].CONSUMABLES = lua_table(self.h.lua,{'henchmanCooldownSeconds':3})
        deps['gameData'] = {'ITEMS_BY_ID': {item:{'id':item,'kind':'consumable',
            'restore':{'pool':'health','percent':percent}} for item,percent in (
                ('con_bandages',25),('con_medkit_small',50),('con_medkit_large',100))}}
        self.f.executor.Invoke = self.h.lua.eval("""function(self,remote,method,...)
            self.calls[#self.calls+1]={remote=remote,method=method,args=table.pack(...)}
            return self.reply or {ok=true,sequence=8,readyAt=1004} end """)
        self.f.start_current()
        self.h.lua.globals().itemRequestHash = lambda value: hashlib.sha256(value.encode()).hexdigest()
        self.f.storage.hash = self.h.lua.eval('function(value) return itemRequestHash(value) end')

    def tearDown(self):
        self.f.tearDown()

    def raw(self, revision=1, bound=2, loose=1, sequence=7, injured=1701, now=None):
        raw = self.f.f.raw(revision=revision)
        raw.native.serverNow = now if now is not None else 1000+revision
        raw.native.henchmanConsumableUseSequence = sequence
        raw.native.henchmanConsumableReadyAt = 1004 if sequence==8 else 1000
        raw.native.consumableUseSequence = 70
        raw.native.inventoryBound = lua_table(self.h.lua,{'con_bandages':bound})
        raw.native.inventory = lua_table(self.h.lua,{'con_bandages':loose,'w_baton':1})
        raw.native.crew = lua_table(self.h.lua,[{'name':'Player'},
            {'name':'Ally','rarity':4,'healId':'injury-a','injuredUntil':injured}])
        return raw

    def step(self, **kwargs):
        raw = self.raw(**kwargs)
        self.h.at(raw.capturedAt)
        self.assertTrue(self.f.app.Step(self.f.app,raw)[0])
        return raw

    def choose(self):
        self.f.app.Set(self.f.app,'crewHealItems.enabled',True)
        self.f.app.Set(self.f.app,'crewHealItems.policy','con_bandages')
        self.f.app.Set(self.f.app,'crewHealItems.custom.minRemaining',300)

    def test_actual_bound_item_call_and_exact_newer_effect(self):
        self.assertIsNone(self.f.app.ui.features.crewHealItems.blockedReason)
        self.choose()
        self.step()
        self.assertEqual(len(self.f.executor.queued),1,str(dict(self.f.runtime.Status(self.f.runtime).reasons.items())))
        self.f.drain()
        call = self.f.executor.calls[1]
        self.assertEqual((call.remote,call.args[1],call.args[2]),('CrewAction','healitem',2))
        self.assertEqual(call.args[3].sequence,7)
        self.assertEqual(call.args[3].memberId,'injury-a')
        self.assertTrue(call.args[3].fromBound)
        self.step(revision=2,bound=1,sequence=8,injured=1401)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.crewHealItems,'confirmed')
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
        self.assertEqual(len(self.f.executor.calls),1)

    def test_exact_saved_reply_reconciles_on_all_off_restart_without_new_use(self):
        self.choose()
        self.step()
        self.f.drain()
        self.f.restart()
        self.step(revision=0,bound=1,sequence=8,injured=1401,now=1002)
        self.assertFalse(self.f.app.model['values']['crewHealItems.enabled'])
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.crewHealItems,'confirmed')
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
        self.assertEqual(len(self.f.executor.calls),1)

    def test_unknown_send_keeps_exact_member_and_origin_hold_but_other_origin_remains_free(self):
        self.choose()
        self.f.executor.Invoke = self.h.lua.eval("""function(self,remote,method,...)
            self.calls[#self.calls+1]={remote=remote,args=table.pack(...)}; return nil end """)
        self.step(bound=1)
        self.f.drain()
        self.f.restart()
        raw = self.step(revision=2,bound=1)
        owner = self.f.runtime.reservationOwner
        held = owner.Held(owner,raw)[0]
        self.assertTrue(held.members['id:injury-a'])
        self.assertEqual(held['items']['B:con_bandages'],1)
        proposal = self.h.proposal(feature='restoratives',key='player')
        proposal.revision = raw.revision
        proposal.resources = lua_table(self.h.lua,{'con_bandages':1})
        proposal.intent = lua_table(self.h.lua,{'kind':'restoratives','itemId':'con_bandages','fromBound':True})
        self.assertIsNone(owner.Check(owner,proposal,raw)[0])
        proposal.intent.fromBound = False
        self.assertIsNotNone(owner.Check(owner,proposal,raw)[0])
        gear = self.h.proposal(feature='crewGear',key='equip')
        gear.revision = raw.revision
        gear.resources = self.h.lua.table()
        gear.intent = lua_table(self.h.lua,{'kind':'crewGear','slot':2,'itemId':'w_baton'})
        self.assertIsNone(owner.Check(owner,gear,raw)[0])
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),1)
        self.assertEqual(len(self.f.executor.calls),1)

    def test_disable_before_deferred_invocation_is_known_unsent(self):
        self.choose()
        self.step()
        self.f.app.Set(self.f.app,'crewHealItems.enabled',False)
        self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)

    def test_unbound_item_uses_its_own_origin_and_cooldown_blocks_another_send(self):
        self.choose()
        self.step(bound=0,loose=2)
        self.f.drain()
        self.assertFalse(self.f.executor.calls[1].args[3].fromBound)
        self.step(revision=2,bound=0,loose=1,sequence=8,injured=1401)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.crewHealItems,'confirmed')
        self.step(revision=3,bound=0,loose=1,sequence=8,injured=1401,now=1003)
        self.assertEqual(len(self.f.executor.queued),0)
        self.assertEqual(len(self.f.executor.calls),1)

    def test_rate_limited_pending_and_wrong_origin_effect_remain_unconfirmed_on_reload(self):
        self.choose()
        self.f.executor.reply = lua_table(self.h.lua,{'ok':False,'pending':True,'code':'rate_limited'})
        self.step()
        self.f.drain()
        self.f.restart()
        self.step(revision=0,bound=2,loose=0,sequence=8,injured=1401,now=1002)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),1)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).recoveries.crewHealItems)
        self.assertEqual(len(self.f.executor.calls),1)

    def test_unload_during_checkpoint_write_recovers_definite_unsent_without_item_use(self):
        self.choose()
        self.h.lua.globals().itemWriteApp = self.f.app
        self.f.storage.Write = self.h.lua.eval('''function(self,key,value)
            self.data[key]=value
            if key:find(':checkpoint:',1,true) and #value.records>0 and not self.interrupted then
                self.interrupted=true; itemWriteApp:Destroy() end
            return true end''')
        raw = self.raw()
        self.h.at(raw.capturedAt)
        self.f.app.Step(self.f.app,raw) # Closing inside the save legitimately closes this Step.
        self.assertEqual(len(self.f.executor.calls),0)
        self.assertEqual(len(self.f.executor.queued),0)
        self.f.restart()
        self.step(revision=0,now=1002)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.crewHealItems,'known_unsent')
        self.assertEqual(len(self.f.executor.calls),0)

    def test_old_queued_callback_appends_only_fact_and_fresh_owner_cleans_it(self):
        self.choose()
        self.step()
        self.f.restart()
        cp = self.f.runtime.checkpoint
        self.assertEqual(len(cp.Records(cp)),1)
        main = self.f.storage.data[cp.ScopeKey(cp)]
        self.f.drain()
        self.assertTrue(self.h.lua.eval('function(a,b) return a==b end')(
            main,self.f.storage.data[cp.ScopeKey(cp)]))
        self.step(revision=0,now=1002)
        self.assertEqual(len(cp.Records(cp)),0)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.crewHealItems,'known_unsent')
        self.assertEqual(len(self.f.executor.calls),0)

    def test_late_definite_unsent_fact_does_not_erase_timeout_or_cooldown(self):
        self.choose()
        self.step()
        self.step(revision=46)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.crewHealItems,'skipped_unconfirmed')
        cooldown = self.f.runtime.Status(self.f.runtime).cooldownUntil.crewHealItems
        self.f.drain()
        self.step(revision=47)
        status = self.f.runtime.Status(self.f.runtime)
        self.assertEqual(status.recoveries.crewHealItems,'known_unsent')
        self.assertEqual(status.outcomes.crewHealItems,'skipped_unconfirmed')
        self.assertEqual(status.cooldownUntil.crewHealItems,cooldown)
        self.assertEqual(len(self.f.executor.calls),0)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)

    def test_missing_unsent_fact_keeps_uncertainty_after_unload(self):
        self.choose()
        self.step()
        self.f.restart()
        self.f.storage.Write = self.h.lua.eval('''function(self,key,value)
            if key:find(':adapter-unsent:',1,true) then return false end
            self.data[key]=value; return true end''')
        self.f.drain()
        self.step(revision=0,now=1002)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),1)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).recoveries.crewHealItems)
        self.assertEqual(len(self.f.executor.calls),0)

    def test_false_scheduler_and_unload_still_records_definite_non_invocation(self):
        self.choose()
        self.h.lua.globals().itemScheduleApp = self.f.app
        self.f.executor.Schedule = self.h.lua.eval('''function(self,callback)
            self.queued[#self.queued+1]=callback; itemScheduleApp:Destroy(); return false end''')
        raw = self.raw()
        self.h.at(raw.capturedAt)
        self.f.app.Step(self.f.app,raw)
        self.f.restart()
        self.f.drain() # Adapter fenced even the callback queued by the refused schedule.
        self.step(revision=0,now=1002)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
        self.assertEqual(len(self.f.executor.calls),0)
