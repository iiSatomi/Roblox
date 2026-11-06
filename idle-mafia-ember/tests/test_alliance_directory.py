import unittest
from engine_harness import Harness,lua_table

class AllianceDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness();self.m=self.h.load('src/tabs/alliance/FamilyDirectoryQuery.luau')
        self.source=self.h.lua.eval("{Current=function(_,name) return name=='FamilyAction' end}")
        self.q=self.m.new(self.source)
        self.raw=lua_table(self.h.lua,{**self.h.session,'revision':1,'capturedAt':0,'native':{'fullSync':True,'serverNow':1000}})
        self.q.Configure(self.q,lua_table(self.h.lua,{'browse':True,'query':''}))
    def reply(self):return lua_table(self.h.lua,{'ok':True,'browseReady':True,'families':[{'id':'family-a','name':'Same name'},{'id':'family-b','name':'Same name'}]})
    def test_native_read_shape_and_detached_identity_rows(self):
        request=self.q.Prepare(self.q,self.raw)[0]
        self.assertEqual((request.remote,request.arity,request.args[1],request.args[2]),('FamilyAction',2,'browse',''))
        reply=self.reply();staged=self.q.Accept(self.q,self.raw,request,reply)[0];self.assertTrue(self.q.Commit(self.q,staged))
        reply.families[1].id='evil';v=self.q.Read(self.q);self.assertEqual(v.rows[1].id,'family-a')
        v.rows[1].id='other';self.assertEqual(self.q.Read(self.q).rows[1].id,'family-a')
    def test_duplicate_sparse_oversize_and_failed_replies_are_not_directories(self):
        request=self.q.Prepare(self.q,self.raw)[0]
        for kind in ('duplicate','sparse','oversize','failed'):
            reply=self.reply()
            if kind=='duplicate':reply.families[2].id='family-a'
            if kind=='sparse':reply.families[1]=None
            if kind=='oversize':reply.families=lua_table(self.h.lua,[{'id':'f'+str(i),'name':'Family'} for i in range(513)])
            if kind=='failed':reply.ok=False
            self.assertIsNone(self.q.Accept(self.q,self.raw,request,reply)[0])
    def test_query_change_disable_source_change_and_close_reject_late_results(self):
        for kind in ('query','disable','source','close','revision'):
            self.setUp();request=self.q.Prepare(self.q,self.raw)[0]
            if kind=='query':self.q.Configure(self.q,lua_table(self.h.lua,{'browse':True,'query':'other'}))
            if kind=='disable':self.q.Configure(self.q,lua_table(self.h.lua,{'browse':False,'query':''}))
            if kind=='source':self.source.Current=self.h.lua.eval('function() return true end')
            if kind=='close':self.q.Close(self.q)
            if kind=='revision':self.raw.revision=2
            self.assertIsNone(self.q.Accept(self.q,self.raw,request,self.reply())[0])
    def test_forged_commit_and_partial_empty_directory(self):
        self.assertFalse(self.q.Commit(self.q,lua_table(self.h.lua,{'rows':[]})))
        request=self.q.Prepare(self.q,self.raw)[0];r=lua_table(self.h.lua,{'ok':True,'browseReady':False,'families':[]})
        staged=self.q.Accept(self.q,self.raw,request,r)[0];self.assertTrue(self.q.Commit(self.q,staged))
        self.assertFalse(self.q.Read(self.q).ready)

class AllianceDirectoryAppTests(unittest.TestCase):
    def setUp(self):
        import test_player_combat_planner_app as fixture
        self.b=fixture.PlayerCombatPlannerAppTests();self.b.setUp();self.f=self.b.f;self.h=self.b.h;self.app=self.b.app
        self.q=self.h.load('src/tabs/alliance/FamilyDirectoryQuery.luau').new(self.f.source);self.f.tab.familyDirectory=self.q
        sources=self.f.tab.ReadSources(self.f.tab,self.f.f.reader)
        budget=self.h.load('src/engine/ReadBudget.luau').new(self.h.clock,lua_table(self.h.lua,[{'id':s.id,'interval':s.interval} for s in sources.values()]),5,60)
        self.h.lua.globals().allianceRaw=self.f.result.before
        self.f.executor.InvokeOwned=self.h.lua.eval("""function(self,token,remote,method,command,query)
            assert(remote=='FamilyAction' and command=='browse' and query=='');self.calls=self.calls+1
            if self.hang then coroutine.yield('browse-return') end
            return {ok=true,browseReady=true,families={{id='family-a',name='Family A'}}}
        end""")
        self.f.runtime.readSources=sources
        self.f.runtime.readCoordinator=self.h.load('src/transport/ReadCoordinator.luau').new(lua_table(self.h.lua,{'clock':self.h.clock,
            'lane':self.f.lane,'budget':budget,'executor':self.f.executor,'sources':sources,
            'currentSnapshot':self.h.lua.eval('function() return allianceRaw end')}))
    def enable(self):
        self.app.Set(self.app,'alliance.browse',True);self.app.Resume(self.app);self.f.step()
    def tick(self,at):
        raw=self.f.result.before;raw.revision+=1;raw.capturedAt=at;raw.native.serverNow=1000+at;self.h.at(at);self.f.step()
    def test_only_read_call_without_gameplay_and_minute_spacing(self):
        self.enable();self.assertEqual(len(self.f.executor.queued),1);self.f.executor.queued[1]()
        self.assertEqual(self.f.executor.calls,1);self.assertEqual(self.f.runtime.Status(self.f.runtime).familyDirectory.rows[1].id,'family-a')
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
        self.tick(59);self.assertEqual(len(self.f.executor.queued),1)
        self.tick(60);self.assertEqual(len(self.f.executor.queued),2)
    def test_disable_and_unload_fence_queued_read(self):
        for close in (False,True):
            if close:self.tearDown();self.setUp()
            self.enable()
            if close:self.app.Destroy(self.app)
            else:self.app.Set(self.app,'alliance.browse',False);self.f.step()
            self.f.executor.queued[1]();self.assertEqual(self.f.executor.calls,0)
    def test_query_change_during_reply_discards_old_result(self):
        self.enable();self.f.executor.hang=True;self.h.lua.globals().allianceCallback=self.f.executor.queued[1]
        self.h.lua.execute('allianceThread=coroutine.create(allianceCallback);assert(coroutine.resume(allianceThread))')
        self.app.Set(self.app,'alliance.query','different');self.f.step()
        self.h.lua.execute('assert(coroutine.resume(allianceThread))');self.assertIsNone(self.q.Read(self.q))
    def tearDown(self):self.b.tearDown()
