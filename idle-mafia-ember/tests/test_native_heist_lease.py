"""One source-owned native Heist counter, no native worker or RPC loop."""
import unittest
from engine_harness import Harness,lua_table

class NativeHeistLeaseTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness();h=self.h
        self.module=h.load('src/tabs/heists/NativeHeistLease.luau')
        self.port=h.lua.execute('''return {counter=4,running=false,valid=true,writes=0,workers=0,
            Current=function(self) return self.valid end,
            Read=function(self) return {counter=self.counter,pending=self.pending,running=self.running,inflight=self.inflight} end,
            Write=function(self,key,value) self.writes=self.writes+1;if self.fail==key then error('write failed') end;self[key]=value end,
            Refresh=function(self) self.refreshes=(self.refreshes or 0)+1 end,
            NativeAct=function(self) if not self.pending then self.counter=self.counter+1;self.pending={sequence=self.counter} end;if self.running then return end;self.running=true;self.workers=self.workers+1 end}''')
        self.epoch=lua_table(h.lua,{'id':'epoch-a','counterSeen':4})
        self.scope=lua_table(h.lua,{'account':'user-a','place':'73897506680154','jobId':'job-a','sourceKey':'a'*64})
        self.owner=self.module.new(self.port,h.clock,self.scope,self.epoch)[0]
        self.p=lua_table(h.lua,{**h.session,'feature':'heists','actionKey':'start:one','intent':{'kind':'heistStart','heistId':'h_a','sequence':5,'nativeJob':'job-a','nativeEpoch':'epoch-a','nativeSourceKey':'a'*64,'needsSequence':True}})
    def test_inspect_is_read_only_even_after_own_lease_deadline(self):
        self.assertIsNotNone(self.owner.Inspect)
        view,why=self.owner.Inspect(self.owner)
        self.assertIsNone(why)
        self.assertEqual((view.account,view.place,view.controllerCounter),('user-a',self.h.session['place'],4))
        self.assertEqual(self.port.writes,0)
        self.assertTrue(self.owner.Acquire(self.owner,self.p,45)[0])
        written=self.port.writes;token=self.port.pending
        self.h.at(46)
        view,why=self.owner.Inspect(self.owner)
        self.assertIsNone(why);self.assertEqual(view.controllerCounter,5)
        self.assertEqual(self.port.writes,written)
        self.assertTrue(self.h.lua.eval('function(a,b)return a==b end')(token,self.port.pending))

    def test_inspect_refuses_regressed_or_retired_native_source_without_writes(self):
        self.assertIsNotNone(self.owner.Inspect)
        self.port.counter=3
        self.assertIsNone(self.owner.Inspect(self.owner)[0])
        self.port.counter=4
        self.assertIsNone(self.owner.Inspect(self.owner)[0])
        self.assertEqual(self.port.writes,0)

    def test_inspect_distinguishes_fresh_controller_epoch_without_any_counter_write(self):
        self.port.counter=0
        epoch=lua_table(self.h.lua,{'id':'fresh-epoch','counterSeen':0})
        owner,why=self.module.new(self.port,self.h.clock,self.scope,epoch);self.assertIsNotNone(owner,why)
        inspected,why=owner.Inspect(owner);self.assertIsNone(why)
        self.assertEqual(inspected.sequenceScope,'nativeControllerEpoch')
        self.assertEqual(inspected.initialControllerCounter,0)
        self.assertTrue(inspected.controllerIdle)
        self.assertEqual(self.port.writes,0)
        q=owner.Quote(owner)[0];self.assertEqual(q.sequence,1)
        p=lua_table(self.h.lua,{**self.h.session,'feature':'heists','actionKey':'fresh:start',
            'intent':{'kind':'heistStart','heistId':'h_a',**{k:q[k] for k in q.keys()}}})
        self.assertTrue(owner.Acquire(owner,p,45)[0])
        inspected=owner.Inspect(owner)[0]
        self.assertEqual((inspected.controllerCounter,inspected.initialControllerCounter),(1,0))
        self.assertFalse(inspected.controllerIdle)
        self.assertTrue(owner.Release(owner,p)[0])
        restored,why=self.module.new(self.port,self.h.clock,self.scope,epoch);self.assertIsNotNone(restored,why)
        self.assertEqual(restored.Inspect(restored)[0].initialControllerCounter,0)
        self.assertEqual(restored.Quote(restored)[0].sequence,2)
        self.assertEqual(self.port.counter,1)

    def test_quote_is_read_only_and_acquire_advances_native_counter_once(self):
        q,why=self.owner.Quote(self.owner);self.assertIsNone(why);self.assertEqual(q.sequence,5);self.assertEqual(self.port.writes,0)
        self.assertTrue(self.owner.Acquire(self.owner,self.p,45)[0]);self.assertEqual(self.port.counter,5)
        self.assertTrue(self.owner.Owns(self.owner,self.p));self.port.NativeAct(self.port)
        self.assertEqual(self.port.counter,5);self.assertEqual(self.port.workers,0)
        self.assertTrue(self.owner.Release(self.owner,self.p)[0]);self.assertIsNone(self.port.pending);self.assertFalse(self.port.running);self.assertEqual(self.port.counter,5)
    def test_native_ui_winning_quote_race_is_untouched(self):
        self.port.NativeAct(self.port);native=self.port.pending
        self.assertFalse(self.owner.Acquire(self.owner,self.p,45)[0]);self.assertEqual(self.port.writes,0)
        self.assertTrue(self.h.lua.eval('function(a,b) return a==b end')(self.port.pending,native))
    def test_unfinished_native_invocation_cannot_be_adopted(self):
        self.port.inflight=self.h.lua.table();self.assertFalse(self.owner.Acquire(self.owner,self.p,45)[0]);self.assertEqual(self.port.writes,0)
    def test_expiry_and_broader_source_change_still_release_only_owned_token(self):
        self.assertTrue(self.owner.Acquire(self.owner,self.p,45)[0]);self.h.at(45);self.port.valid=False
        self.assertFalse(self.owner.Owns(self.owner,self.p));self.assertTrue(self.owner.Release(self.owner,self.p)[0])
        self.assertIsNone(self.port.pending);self.assertFalse(self.port.running);self.assertEqual(self.port.counter,5)
    def test_newer_native_owner_is_never_cleared(self):
        self.assertTrue(self.owner.Acquire(self.owner,self.p,45)[0]);other=self.h.lua.table();self.port.pending=other
        self.owner.Close(self.owner);self.assertTrue(self.h.lua.eval('function(a,b) return a==b end')(self.port.pending,other));self.assertTrue(self.port.running)
    def test_counter_reset_retires_the_old_epoch_without_guessing_highwater(self):
        self.port.counter=3;q,_=self.owner.Quote(self.owner);self.assertIsNone(q);self.assertTrue(self.epoch.retired);self.assertEqual(self.port.counter,3)
    def test_wrong_job_epoch_and_source_never_acquire(self):
        for k,value in [('nativeJob','other'),('nativeEpoch','other'),('nativeSourceKey','b'*64)]:
            old=self.p.intent[k];self.p.intent[k]=value;self.assertFalse(self.owner.Acquire(self.owner,self.p,45)[0]);self.p.intent[k]=old
        self.assertEqual(self.port.writes,0)
    def test_partial_write_failure_cleans_own_flags_without_counter_rollback(self):
        self.port.fail='counter';self.assertFalse(self.owner.Acquire(self.owner,self.p,45)[0]);self.assertIsNone(self.port.pending);self.assertFalse(self.port.running);self.assertEqual(self.port.counter,4)

    def test_cleanup_read_failure_retains_exact_ownership_for_retry(self):
        self.assertTrue(self.owner.Acquire(self.owner,self.p,45)[0]);old=self.port.Read
        self.port.Read=self.h.lua.eval("function() error('detached debug read') end")
        self.assertFalse(self.owner.Release(self.owner,self.p)[0]);self.assertIsNotNone(self.epoch.live)
        self.port.Read=old;self.assertTrue(self.owner.Release(self.owner,self.p)[0]);self.assertIsNone(self.port.pending)
    def test_cleanup_second_write_failure_can_retry_without_losing_its_token_proof(self):
        self.assertTrue(self.owner.Acquire(self.owner,self.p,45)[0]);self.port.fail='running'
        self.assertFalse(self.owner.Release(self.owner,self.p)[0]);self.assertIsNotNone(self.epoch.live)
        self.port.fail=None;self.assertTrue(self.owner.Release(self.owner,self.p)[0]);self.assertFalse(self.port.running);self.assertIsNone(self.epoch.live)


class NativeHeistBoundEpochTests(unittest.TestCase):
    """Synthetic reflection boundary; never executes or embeds native game source."""
    def setUp(self):
        self.h=Harness();self.module=self.h.load('src/tabs/heists/NativeHeistLease.luau')
        self.f=self.h.lua.execute("""
            local function node(name,class)
                local n={Name=name,ClassName=class,children={}}
                function n:IsA(k)return self.ClassName==k end
                function n:FindFirstChild(k)return self.children[k]end
                function n:Add(c)c.Parent=self;self.children[c.Name]=c;return c end
                return n
            end
            local f={registry={},writes=0,calls=0,guids=0}
            local player=node('user-a','Player')
            local scripts=player:Add(node('PlayerScripts','PlayerScripts'))
            local client=scripts:Add(node('MWClient','LocalScript'))
            local module=client:Add(node('HeistsTab','ModuleScript'))
            local stateModule=client:Add(node('State','ModuleScript'));stateModule.Value={data={}}
            local replicated=node('ReplicatedStorage','ReplicatedStorage')
            local mw=replicated:Add(node('MW','Folder'));local remotes=mw:Add(node('Remotes','Folder'))
            local remote=remotes:Add(node('HeistAction','RemoteFunction'))
            local wrapper={Instance=remote,InvokeServer=function()f.calls=f.calls+1;error('No native worker')end}
            local context={player=player,State=stateModule.Value,Remotes={HeistAction=wrapper}}
            local actor=function()end;local helper=function()end
            local values={[2]=0,[3]=false,[4]=function()end,[5]=helper,[6]=context,[7]=function()end}
            local players={LocalPlayer=player}
            local game={PlaceId=73897506680154,PlaceVersion=654,JobId='same-native-job'}
            function game:GetService(name)
                if name=='Players'then return players end
                if name=='ReplicatedStorage'then return replicated end
                if name=='HttpService'then return {GenerateGUID=function()f.guids=f.guids+1;return 'native-epoch-'..f.guids end}end
                error(name)
            end
            local env={filtergc=function()return {actor}end,getfenv=function()return {script=module}end,
                -- Digest stub isolates binding identity logic, not source-hash verification.
                decompile=function(m)assert(m==module);return string.rep('x',69223)end,
                crypt={hash=function()return '11e1d4138dcf5db66aa9b1f4f69d0298bd3b66f8173e13ee4b81dba8f104ec8a'end},
                iscclosure=function(fn)return type(fn)=='function'end}
            function env.getupvalues(fn)
                if fn==actor then return values end
                if fn==helper then return {[2]=context}end
                local result={};for i=1,32 do local name,v=debug.getupvalue(fn,i);if not name then break end;result[i]=v end
                return result
            end
            function env.setupvalue(fn,index,value)
                if fn==actor then values[index]=value;f.writes=f.writes+1
                else assert(debug.setupvalue(fn,index,value))end
            end
            f.game=game;f.env=env;f.values=values;f.requireModule=function(m)return m.Value end
            return f
        """)
        self.deps=lua_table(self.h.lua,{'game':self.f.game,'env':self.f.env,'registry':self.f.registry,
            'requireModule':self.f.requireModule,'clock':self.h.clock,'account':'user-a'})
    def bind(self):return self.module.bind(self.deps)
    def test_same_controller_rebind_keeps_original_zero_and_next_sequence(self):
        owner,why=self.bind();self.assertIsNotNone(owner,why)
        self.assertEqual(owner.Inspect(owner)[0].initialControllerCounter,0)
        q=owner.Quote(owner)[0]
        p=lua_table(self.h.lua,{**self.h.session,'feature':'heists','actionKey':'new:one',
            'intent':{'kind':'heistStart','heistId':'h_a',**dict(q.items())}})
        self.assertTrue(owner.Acquire(owner,p,45)[0]);self.assertTrue(owner.Release(owner,p)[0]);owner.Close(owner)
        rebound,why=self.bind();self.assertIsNotNone(rebound,why)
        self.assertEqual(rebound.Inspect(rebound)[0].initialControllerCounter,0)
        self.assertEqual(rebound.Quote(rebound)[0].sequence,2)
        self.assertEqual(self.f["values"][2],1);self.assertEqual(self.f.guids,1);self.assertEqual(self.f.calls,0)
    def test_retired_same_actor_context_job_cannot_rebind_as_a_fresh_epoch(self):
        owner,why=self.bind();self.assertIsNotNone(owner,why)
        self.f["values"][2]=1;self.assertIsNotNone(owner.Inspect(owner)[0])
        self.f["values"][2]=0;self.assertIsNone(owner.Inspect(owner)[0])
        rebound,why=self.bind()
        self.assertIsNone(rebound);self.assertIn('retired',why)
        self.assertEqual(self.f.guids,1);self.assertEqual(self.f.writes,0);self.assertEqual(self.f.calls,0)
