"""Lookup admission cooldown must not cancel an already-authorized owned read."""
import unittest
import test_saved_search_app as app_fixture
import test_owned_saved_search as query_fixture
from engine_harness import lua_table

class SavedSearchLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.b=app_fixture.SavedSearchAppTests();self.b.setUp();self.f=self.b.f;self.h=self.b.h;self.app=self.b.app
    def test_unchanged_tick_before_queued_dispatch_preserves_authorized_read(self):
        self.b.enable();self.f.step();self.f.executor.queued[1]()
        self.assertEqual(len(self.f.executor.log),1)
        self.assertEqual(len(self.f.tab.hitListQuery.Read(self.f.tab.hitListQuery,self.b.raw).rows),1)
    def test_unchanged_tick_while_reply_yields_preserves_the_valid_result(self):
        self.b.enable();self.f.executor.yieldReply=True;self.h.lua.globals().lookupCallback=self.f.executor.queued[1]
        value=self.h.lua.execute('lookupThread=coroutine.create(lookupCallback);local ok,v=coroutine.resume(lookupThread);assert(ok);return v')
        self.assertEqual(value,'lookup-return');self.f.step();self.h.lua.execute('assert(coroutine.resume(lookupThread))')
        self.assertEqual(len(self.f.tab.hitListQuery.Read(self.f.tab.hitListQuery,self.b.raw).rows),1)
    def test_revoked_native_source_cannot_dispatch_an_owned_queued_lookup(self):
        self.b.enable();self.f.source.Current=self.h.lua.eval('function() return false end');self.f.step()
        self.f.executor.queued[1]();self.assertEqual(len(self.f.executor.log),0)
    def test_changed_source_or_threshold_while_reply_yields_still_refuses_attachment(self):
        for key,value in [('targetSource','Saved only + lookup'),('minimumPayout',1000000000)]:
            if key!='targetSource':self.tearDown();self.setUp()
            self.b.enable();self.f.executor.yieldReply=True;self.h.lua.globals().lookupCallback=self.f.executor.queued[1]
            self.h.lua.execute('lookupThread=coroutine.create(lookupCallback);assert(coroutine.resume(lookupThread))')
            self.app.Set(self.app,'combat.custom.'+key,value);self.f.step();self.h.lua.execute('assert(coroutine.resume(lookupThread))')
            self.assertEqual(len(self.f.tab.hitListQuery.Read(self.f.tab.hitListQuery,self.b.raw).rows),0)
    def tearDown(self):
        if hasattr(self,'b'):self.b.tearDown()

class SavedSearchScopeFairnessTests(unittest.TestCase):
    def test_alternating_groups_do_not_starve_later_ids_after_retry_window_opens(self):
        f=query_fixture.OwnedSavedSearchTests();f.setUp();h=f.h;q=f.q;raw=f.raw
        high=lua_table(h.lua,[{'userId':i,'name':'High_'+str(i)} for i in range(2,22)])
        ordinary=lua_table(h.lua,[{'userId':i,'name':'Ordinary_'+str(i)} for i in range(1001,1021)])
        seen={'high':set(),'ordinary':set()};last=None
        for round in range(80):
            raw.capturedAt=round*60;raw.native.serverNow=1000+round*60;raw.revision=round+1;h.at(round*60)
            call=q.Prepare(q,raw)[0];self.assertTrue(q.Commit(q,q.Accept(q,raw,call,f.f.reply)[0]))
            a=q.PickSavedSearch(q,raw,high,128,'high');b=q.PickSavedSearch(q,raw,ordinary,32,'ordinary')
            chosen=a if a is not None and (b is None or last!='high') else b
            self.assertIsNotNone(chosen);scope='high' if chosen.userId<1000 else 'ordinary';chosen.lookupScope=scope
            request,why=q.PrepareSavedSearch(q,raw,chosen);self.assertIsNotNone(request,why)
            reply=lua_table(h.lua,{'ok':True,'search':chosen.name,'list':[]})
            staged,why=q.AcceptSavedSearch(q,raw,request,reply);self.assertIsNotNone(staged,why);self.assertTrue(q.CommitSavedSearch(q,staged))
            seen[scope].add(chosen.userId);last=scope
        self.assertEqual(seen['high'],set(range(2,22)));self.assertEqual(seen['ordinary'],set(range(1001,1021)))
