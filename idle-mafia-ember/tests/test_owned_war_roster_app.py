"""Separate read-only native war source through the existing actual App scheduler."""
import unittest
import test_player_fight_app as app_fixture
from engine_harness import lua_table

class OwnedWarRosterAppTests(unittest.TestCase):
    def setUp(self):
        self.f=app_fixture.PlayerFightAppTests();self.f.include_war=True;self.f.setUp();self.h=self.f.h
        self.current=self.h.lua.execute('return {valid=true,Current=function(self) return self.valid end}')
        self.q=self.h.load('src/tabs/combat/HitListQuery.luau').new(lua_table(self.h.lua,self.h.session),'a'*64,self.current,'war')
        if self.f.tab.warRosterQuery:self.f.tab.warRosterQuery.Close(self.f.tab.warRosterQuery)
        self.f.tab.warRosterQuery=self.q
        self.f.tab.hitListQuery.Close(self.f.tab.hitListQuery)
        self.f.tab.hitListQuery=self.h.load('src/tabs/combat/HitListQuery.luau').new(lua_table(self.h.lua,self.h.session),'a'*64,self.current)
        self.h.lua.globals().warRaw=self.f.result.before
        self.h.lua.globals().warReply=lua_table(self.h.lua,{'ok':True,'warStatus':{'day':self.f.result.day,
            'serverNow':self.f.result.now,'targets':[]}})
        self.f.executor.InvokeOwned=self.h.lua.eval("""function(self,token,remote,method,arg)
            assert(remote=='GetHitList' and arg=='warStatus');self.calls=self.calls+1;return warReply end""")
        sources=self.f.tab.ReadSources(self.f.tab,self.f.f.reader)
        budget=self.h.load('src/engine/ReadBudget.luau').new(self.h.clock,lua_table(self.h.lua,[{'id':'combatWarRoster','interval':1}]),5,60)
        self.f.runtime.readSources=sources
        self.f.runtime.readCoordinator=self.h.load('src/transport/ReadCoordinator.luau').new(lua_table(self.h.lua,{
            'clock':self.h.clock,'lane':self.f.lane,'budget':budget,'executor':self.f.executor,'sources':sources,
            'currentSnapshot':self.h.lua.eval('function() return warRaw end')}))
    def start(self):
        self.assertTrue(self.f.app.Set(self.f.app,'warCombat.enabled',True)[0]);self.f.app.Resume(self.f.app);self.f.step()
        self.assertEqual(len(self.f.executor.queued),1)
    def test_all_off_has_no_war_read(self):
        self.f.step();self.assertEqual(len(self.f.executor.queued),0)
    def test_war_only_mode_commits_its_own_proof_without_ordinary_list_or_gameplay(self):
        self.start();self.f.executor.queued[1]();self.h.at(.25);self.f.step()
        raw=self.f.runtime.allowanceSnapshot
        self.assertIs(raw.warRosterProof.war.active,False);self.assertIsNone(raw.hitListProof)
        self.assertEqual(self.f.executor.calls,1);self.assertIsNone(self.f.source.callback)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
    def test_disable_or_unload_before_queue_never_calls_native_read(self):
        for unload in (False,True):
            if unload:self.tearDown();self.setUp()
            self.start()
            if unload:self.f.app.Destroy(self.f.app)
            else:self.f.app.Set(self.f.app,'warCombat.enabled',False);self.f.step()
            self.f.executor.queued[1]();self.assertEqual(self.f.executor.calls,0)
    def test_retired_source_refuses_reply_commit(self):
        self.start();self.current.valid=False;self.f.executor.queued[1]()
        self.assertIsNone(self.q.Read(self.q,self.f.result.before))
    def test_new_sync_fences_queued_native_read(self):
        self.start();self.f.result.before.revision+=1;self.f.executor.queued[1]()
        self.assertEqual(self.f.executor.calls,0);self.assertIsNone(self.q.Read(self.q,self.f.result.before))
    def test_polling_is_cached_instead_of_repeating_each_planner_tick(self):
        self.start();self.f.executor.queued[1]()
        for at in (.25,.5,.75,1):self.h.at(at);self.f.step()
        self.assertEqual(len(self.f.executor.queued),1)
    def test_caller_war_proof_is_cleared_without_owned_source(self):
        raw=self.f.result.before;raw.warRosterProof=lua_table(self.h.lua,{'war':{'active':True,'enemyFamilyId':'fake'}})
        self.f.step();self.assertIsNone(self.f.runtime.allowanceSnapshot.warRosterProof)
    def test_actual_war_descriptor_reads_its_own_inactive_source_without_proposing_an_attack(self):
        self.start();self.f.executor.queued[1]();self.h.at(.25);self.f.step()
        spec=next(row for row in self.f.tab.Descriptors(self.f.tab).values() if row.id=='warCombat')
        raw=self.f.runtime.allowanceSnapshot
        context=lua_table(self.h.lua,{key:raw[key] for key in ('session','account','place','release','revision','capturedAt')})
        context.serverNow=raw.native.serverNow
        view,why=spec.reader.read(raw,context);self.assertIsNotNone(view,why)
        self.assertIs(view.war.active,False)
        proposal,why=spec.planner.propose(view,lua_table(self.h.lua,{'enabled':True}))
        self.assertIsNone(proposal);self.assertIn('unverified',why)
    def test_yielding_read_cannot_commit_after_disable_or_unload(self):
        for unload in (False,True):
            if unload:self.tearDown();self.setUp()
            self.f.executor.InvokeOwned=self.h.lua.eval("""function(self,token,remote,method,arg)
                assert(remote=='GetHitList' and arg=='warStatus');self.calls=self.calls+1
                coroutine.yield('war read');return warReply end""")
            self.start();self.h.lua.globals().warJob=self.f.executor.queued[1]
            self.assertEqual(self.h.lua.execute('warThread=coroutine.create(warJob);local ok,value=coroutine.resume(warThread);assert(ok);return value'),'war read')
            if unload:self.f.app.Destroy(self.f.app)
            else:self.f.app.Set(self.f.app,'warCombat.enabled',False);self.f.step()
            self.h.lua.execute('assert(coroutine.resume(warThread))')
            self.assertIsNone(self.q.Read(self.q,self.f.result.before));self.assertEqual(self.f.executor.calls,1)
            self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
    def test_rejected_pending_or_challenged_read_stays_unknown_and_backs_off(self):
        for index,reply in enumerate(({'ok':False},{'ok':True,'pending':True},{'ok':True,'code':'rate_limited'},
                                      {'ok':True,'code':'presence','warStatus':{'day':self.f.result.day,'serverNow':self.f.result.now,'targets':[]}})):
            if index:self.tearDown();self.setUp()
            self.h.lua.globals().warReply=lua_table(self.h.lua,reply)
            self.start();self.f.executor.queued[1]();self.h.at(.25);self.f.step()
            self.assertIsNone(self.f.runtime.allowanceSnapshot.warRosterProof)
            self.h.at(1);self.f.step();self.assertEqual(len(self.f.executor.queued),1)
            self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
    def tearDown(self):self.f.tearDown()
