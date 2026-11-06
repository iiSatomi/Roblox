"""Existing actual App + existing read coordinator; player gameplay stays blocked."""
import unittest
import test_player_fight_app as app_fixture
from engine_harness import lua_table

class OwnedHitListAppTests(unittest.TestCase):
    def setUp(self):
        self.f=app_fixture.PlayerFightAppTests();self.f.setUp();self.h=self.f.h
        self.currentSource=self.h.lua.execute('return {valid=true,Current=function(self) return self.valid end}')
        self.q=self.h.load('src/tabs/combat/HitListQuery.luau').new(lua_table(self.h.lua,self.h.session),'a'*64,self.currentSource)
        self.f.tab.hitListQuery.Close(self.f.tab.hitListQuery);self.f.tab.hitListQuery=self.q
        blocked=self.h.load('src/tabs/combat/BlockedFight.luau').new('combat')
        self.f.spec.reader=self.f.spec.planner=blocked
        self.h.lua.globals().hitRaw=self.f.result.before
        self.h.lua.globals().hitReply=lua_table(self.h.lua,{'ok':True,'list':[{'userId':42,'name':'Target B',
            'level':128,'stamina':2,'familyId':'foreign-family','shielded':False}],
            'warStatus':{'day':self.f.result.before.native.attackDaily.day,'serverNow':self.f.result.before.native.serverNow,'targets':[]}})
        self.f.executor.InvokeOwned=self.h.lua.eval("""function(self,token,remote,method,refresh)
            assert(remote=='GetHitList' and refresh==false);self.calls=self.calls+1;if hitReply.warStatus then hitReply.warStatus.serverNow=hitRaw.native.serverNow end;return hitReply end""")
        sources=self.f.tab.ReadSources(self.f.tab,self.f.f.reader)
        budget=self.h.load('src/engine/ReadBudget.luau').new(self.h.clock,lua_table(self.h.lua,[{'id':'combatHitList','interval':1}]),5,60)
        reads=self.h.load('src/transport/ReadCoordinator.luau').new(lua_table(self.h.lua,{'clock':self.h.clock,
            'lane':self.f.lane,'budget':budget,'executor':self.f.executor,'sources':sources,
            'currentSnapshot':self.h.lua.eval('function() return hitRaw end')}))
        self.f.runtime.readSources=sources;self.f.runtime.readCoordinator=reads
    def start(self):
        self.f.app.Set(self.f.app,'combat.enabled',True);self.f.app.Resume(self.f.app);self.f.step()
        self.assertEqual(len(self.f.executor.queued),1)
    def test_all_off_has_no_target_read_or_subscription(self):
        self.f.step();self.assertEqual(len(self.f.executor.queued),0)
        self.assertIsNone(self.f.runtime.allowanceSnapshot.hitListProof)
    def test_owned_native_read_reaches_app_with_exact_cost_and_family_no_attack(self):
        self.start();self.f.executor.queued[1]();self.h.at(.25);self.f.step()
        row=self.f.runtime.allowanceSnapshot.hitListProof.rows[1]
        self.assertEqual((row.stamina,row.familyId),(2,'foreign-family'))
        self.assertEqual(self.f.executor.calls,1);self.assertIsNone(self.f.source.callback)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
    def test_disable_before_scheduled_read_cancels_without_game_call(self):
        self.start();self.f.app.Set(self.f.app,'combat.enabled',False);self.f.step();self.f.executor.queued[1]()
        self.assertEqual(self.f.executor.calls,0);self.assertIsNone(self.q.Read(self.q,self.f.result.before))
    def test_new_sync_or_unload_fences_queued_read(self):
        self.start();self.f.result.before.revision=2;self.f.executor.queued[1]()
        self.assertEqual(self.f.executor.calls,0);self.assertIsNone(self.q.Read(self.q,self.f.result.before))
        self.f.app.Destroy(self.f.app);self.assertIsNone(self.q.Prepare(self.q,self.f.result.before)[0])
    def test_poll_budget_does_not_repeat_for_each_planner_tick_or_enable_war_reads(self):
        self.start();self.f.executor.queued[1]();self.h.at(.25);self.f.step();self.h.at(.5);self.f.step()
        self.assertEqual(len(self.f.executor.queued),1)
        self.f.app.Set(self.f.app,'combat.enabled',False);self.f.app.Set(self.f.app,'warCombat.enabled',True)
        self.h.at(10);self.f.result.before.capturedAt=10;self.f.step();self.assertEqual(len(self.f.executor.queued),1)
    def test_retired_source_during_rpc_cannot_commit_against_unchanged_cached_snapshot(self):
        self.h.lua.globals().hitCurrent=self.currentSource
        self.f.executor.InvokeOwned=self.h.lua.eval('function(self) self.calls=self.calls+1;hitCurrent.valid=false;return hitReply end')
        self.start();self.f.executor.queued[1]();self.h.at(.25);self.f.step()
        self.assertIsNone(self.f.runtime.allowanceSnapshot.hitListProof)
    def test_retired_source_hides_previously_committed_proof(self):
        self.start();self.f.executor.queued[1]();self.assertIsNotNone(self.q.Read(self.q,self.f.result.before))
        self.currentSource.valid=False;self.h.at(.25);self.f.step()
        self.assertIsNone(self.f.runtime.allowanceSnapshot.hitListProof)
    def test_own_price_change_refreshes_once_without_waiting_for_cache_expiry(self):
        self.start();self.f.executor.queued[1]()
        raw=self.f.result.before;raw.revision=2;raw.capturedAt=1;raw.native.serverNow+=1;raw.native.respect=100
        self.h.at(1);self.f.step();self.assertEqual(len(self.f.executor.queued),2)
        self.f.executor.queued[2]();self.h.at(1.25);self.f.step()
        self.assertEqual(len(self.f.executor.queued),2);self.assertIsNotNone(self.q.Read(self.q,raw))
    def tearDown(self):
        self.f.tearDown()
