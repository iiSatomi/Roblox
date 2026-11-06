"""Only the exact source-owned Recall status signature enters the shared reader."""
import unittest
from engine_harness import Harness,lua_table

class RecallStatusReadTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness();self.h.lua.globals().current=self.h.snapshot(native={'fullSync':True,'serverNow':1000})
        self.lane=self.h.load('src/engine/RequestLane.luau').new(self.h.clock)
        self.executor=self.h.lua.execute("""return {queued={},calls=0,reply={ok=false,code='unknown_request'},
            Schedule=function(self,fn) self.queued[#self.queued+1]=fn;return true end,
            InvokeOwned=function(self,token,remote,method,...) self.calls=self.calls+1;return self.reply end}""")
        self.h.lua.globals().readCall=lua_table(self.h.lua,{'remote':'TerritoryStatus','method':'InvokeServer','arity':3,'kind':'statusOnly','args':['recallstatus',1000000]})
    def coordinator(self,status=True):
        source=self.h.lua.execute("""return {id='recall',prepare=function()return readCall end,
            accept=function(raw,request,reply) acceptedReply=reply;return {value=reply} end,
            commit=function(value) committedReply=value.value;return true end}""")
        source.statusOnly=status
        budget=self.h.load('src/engine/ReadBudget.luau').new(self.h.clock,lua_table(self.h.lua,[{'id':'recall','interval':3}]),5,60)
        return self.h.load('src/transport/ReadCoordinator.luau').new(lua_table(self.h.lua,{'clock':self.h.clock,'lane':self.lane,
            'budget':budget,'executor':self.executor,'sources':[source],'currentSnapshot':self.h.lua.eval('function()return current end')}))
    def step(self,coordinator):return coordinator.Step(coordinator,self.h.lua.globals().current,lua_table(self.h.lua,{'recall':True}))
    def test_exact_status_delivers_unknown_manual_and_pending_without_success_claim(self):
        for reply in ({'ok':False,'code':'unknown_request'},{'ok':False,'code':'presence'},{'ok':True,'pending':True}):
            with self.subTest(reply=reply):
                self.setUp();self.executor.reply=lua_table(self.h.lua,reply);coordinator=self.coordinator()
                self.assertEqual(self.step(coordinator),'queued');self.executor.queued[1]()
                self.assertEqual(dict(self.h.lua.globals().committedReply.items()),reply)
    def test_call_and_source_must_both_be_status_only(self):
        for source_status,call_kind in ((False,'statusOnly'),(True,None)):
            with self.subTest(source_status=source_status,call_kind=call_kind):
                self.setUp();self.h.lua.globals().readCall.kind=call_kind;coordinator=self.coordinator(source_status)
                self.assertEqual(self.step(coordinator),'blocked');self.assertEqual(len(self.executor.queued),0)
    def test_exact_numeric_request_identity_and_nil_third_argument_required(self):
        for request_id,third in ((None,None),(0,None),('1000',None),(1.5,None),(float('inf'),None),(1,'extra')):
            with self.subTest(request_id=request_id,third=third):
                self.setUp();self.h.lua.globals().readCall.args=lua_table(self.h.lua,{1:'recallstatus',2:request_id,3:third})
                coordinator=self.coordinator();self.assertEqual(self.step(coordinator),'blocked');self.assertEqual(len(self.executor.queued),0)
    def test_ordinary_reads_still_reject_pending_or_negative_replies(self):
        self.h.lua.globals().readCall=lua_table(self.h.lua,{'remote':'TerritoryView','method':'InvokeServer','arity':4,'args':['map']})
        coordinator=self.coordinator(False);self.assertEqual(self.step(coordinator),'queued');self.executor.queued[1]()
        self.assertIsNone(self.h.lua.globals().committedReply)
        self.assertEqual(coordinator.Status(coordinator).reasons.recall,'Read reply unavailable')
