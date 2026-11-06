"""Conditional native ownership; physical calls never become canceled by expiry."""
import unittest

from engine_harness import Harness, ROOT, lua_table


class NativeCombatLeaseTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / 'src/tabs/combat/NativeCombatLease.luau').exists(),
            'The native Combat owner is not implemented')
        self.h = Harness(); h = self.h
        self.module = h.load('src/tabs/combat/NativeCombatLease.luau')
        self.port = h.lua.execute('''local p={valid=true,nonYielding=true,attackBusy=false,
            scoutBusy=false,scoutGeneration=0,scoutTarget=nil,calls=0,writes=0,modalOpen=false}
            function p:Current() return self.valid end
            function p:Read() return {attackBusy=self.attackBusy,scoutBusy=self.scoutBusy,
                scoutGeneration=self.scoutGeneration,scoutTarget=self.scoutTarget,
                confirmationPending=self.confirmation~=nil,modalOpen=self.modalOpen} end
            function p:CompareAttackBusy(expected,value)
                if self.attackBusy~=expected then return false end
                self.attackBusy=value;self.writes=self.writes+1;return true
            end
            local function forward(...) p.calls=p.calls+1;if p.hang then coroutine.yield('native_wait') end;return {ok=true,value=7},nil,'tail' end
            p.originalAttack=function(...) return forward(...) end
            p.originalScout=function(...) return forward(...) end
            p.nativeAttack=p.originalAttack;p.nativeScout=p.originalScout
            function p:Install(gateway)
                local token={};self.gate=token
                token.attack=function(...) return gateway('Attack',self.originalAttack,...) end
                token.scout=function(...) return gateway('ScoutPlayer',self.originalScout,...) end
                self.nativeAttack=token.attack;self.nativeScout=token.scout
                return token
            end
            function p:Restore(token)
                if self.nativeAttack==token.attack then self.nativeAttack=self.originalAttack end
                if self.nativeScout==token.scout then self.nativeScout=self.originalScout end
                if self.gate==token then self.gate=nil end
                return true
            end
            return p''')
        self.epoch = h.lua.table()
        self.identity = lua_table(h.lua, h.session)
        self.p = lua_table(h.lua, {**h.session, 'feature':'combat', 'actionKey':'fight:42',
            'intent':{'kind':'playerAttack','target':42}})
        self.owner = None

    def make(self):
        self.owner, reason = self.module.new(self.port,self.h.clock,self.identity,self.epoch)
        self.assertIsNotNone(self.owner, reason)
        return self.owner

    def acquire(self, deadline=45):
        self.make() if self.owner is None else None
        ok, why = self.owner.Acquire(self.owner,self.p,deadline)
        self.assertTrue(ok, why)

    def test_pristine_owner_leases_shared_attack_guard_and_restores_exact_token(self):
        self.acquire(); self.assertEqual(self.h.lua.eval('type')(self.port.attackBusy),'table')
        self.assertTrue(self.owner.Owns(self.owner,self.p))
        self.assertTrue(self.owner.Release(self.owner,self.p)[0])
        self.assertFalse(self.port.attackBusy); self.assertEqual(self.port.calls,0)

    def test_used_or_busy_scout_cannot_be_adopted_despite_false_busy_reset(self):
        for generation,target,busy in [(1,42,False),(1,None,False),(0,42,False),(0,None,True)]:
            with self.subTest(generation=generation,target=target,busy=busy):
                self.port.scoutGeneration=generation;self.port.scoutTarget=target;self.port.scoutBusy=busy
                owner, reason = self.module.new(self.port,self.h.clock,self.identity,self.h.lua.table())
                self.assertIsNone(owner);self.assertIsNotNone(reason)
                self.assertIsNone(self.port.gate);self.assertEqual(self.port.writes,0)

    def test_native_attack_already_running_cannot_be_adopted(self):
        self.port.attackBusy=True
        owner,why=self.module.new(self.port,self.h.clock,self.identity,self.epoch)
        self.assertIsNone(owner);self.assertIsNotNone(why);self.assertIsNone(self.port.gate)

    def test_pending_confirmation_and_visible_modal_are_preserved(self):
        self.make(); callback=self.h.lua.eval('function() error("Never answer a native prompt") end')
        self.port.confirmation=callback
        self.assertFalse(self.owner.Acquire(self.owner,self.p,45)[0])
        self.assertTrue(self.h.lua.eval('function(a,b) return a==b end')(self.port.confirmation,callback))
        self.port.confirmation=None;self.port.modalOpen=True
        self.assertFalse(self.owner.Acquire(self.owner,self.p,45)[0])
        self.assertTrue(self.port.modalOpen);self.assertEqual(self.port.calls,0)

    def test_both_native_gateways_refuse_mutations_during_hub_lease(self):
        self.acquire()
        self.assertIsNone(self.port.nativeAttack(42));self.assertIsNone(self.port.nativeScout(42))
        self.assertEqual(self.port.calls,0)
        self.port.scoutGeneration=1;self.port.scoutTarget=43;self.port.scoutBusy=False
        self.assertIsNone(self.port.nativeScout(43));self.assertEqual(self.port.calls,0)

    def test_native_calls_are_forwarded_once_with_all_return_values_when_unleased(self):
        self.make();reply,middle,last=self.port.nativeScout(42)
        self.assertTrue(reply.ok);self.assertIsNone(middle);self.assertEqual(last,'tail')
        self.assertEqual(self.port.calls,1)

    def test_prospective_native_physical_call_blocks_hub_despite_busy_flag_reset(self):
        self.make();self.port.hang=True;self.h.lua.globals().nativePort=self.port
        thread=self.h.lua.eval('coroutine.create(function() return nativePort.nativeScout(42) end)').coroutine()
        self.assertEqual(next(thread),'native_wait')
        self.port.scoutGeneration=1;self.port.scoutTarget=43;self.port.scoutBusy=False
        self.assertFalse(self.owner.Acquire(self.owner,self.p,45)[0])
        self.assertEqual(self.port.calls,1)
        next(thread)
        self.assertTrue(self.owner.Acquire(self.owner,self.p,45)[0])

    def test_hub_invoke_retains_physical_ambiguity_after_45_second_logical_release(self):
        self.acquire();self.h.lua.globals().combatOwner=self.owner;self.h.lua.globals().combatProposal=self.p
        thread=self.h.lua.eval('coroutine.create(function() return combatOwner:Invoke(combatProposal,function() coroutine.yield("hub_wait");return {ok=true} end) end)').coroutine()
        self.assertEqual(next(thread),'hub_wait');self.h.at(45)
        self.assertFalse(self.owner.Owns(self.owner,self.p));self.assertFalse(self.port.attackBusy)
        self.assertTrue(self.owner.Status(self.owner).physical)
        self.assertIsNone(self.port.nativeScout(42));self.assertEqual(self.port.calls,0)
        self.assertFalse(self.owner.Acquire(self.owner,self.p,90)[0])
        next(thread);self.assertFalse(self.owner.Status(self.owner).physical)
        self.assertTrue(self.owner.Acquire(self.owner,self.p,90)[0])

    def test_queued_disable_or_unload_never_runs_the_supplied_invocation(self):
        for closing in (False,True):
            with self.subTest(closing=closing):
                self.setUp();self.acquire()
                self.owner.Close(self.owner) if closing else self.owner.Release(self.owner,self.p)
                self.h.lua.globals().neverCalled=0
                callback=self.h.lua.eval('function() neverCalled=neverCalled+1 end')
                ok,why=self.owner.Invoke(self.owner,self.p,callback)
                self.assertFalse(ok);self.assertIsNotNone(why);self.assertEqual(self.h.lua.globals().neverCalled,0)
                self.assertFalse(self.port.attackBusy)

    def test_close_restores_only_its_own_native_gateway_fields(self):
        self.acquire();foreign=self.h.lua.eval('function() return "foreign" end')
        self.port.nativeScout=foreign;self.owner.Close(self.owner)
        self.assertEqual(self.port.nativeScout(),'foreign');self.assertFalse(self.port.attackBusy)
        self.assertTrue(self.h.lua.eval('function(a,b) return a==b end')(self.port.nativeAttack,self.port.originalAttack))

    def test_source_change_retires_and_cleans_exact_busy_token(self):
        self.acquire();self.port.valid=False
        self.assertFalse(self.owner.Owns(self.owner,self.p));self.assertFalse(self.port.attackBusy)
        self.port.valid=True;self.assertFalse(self.owner.Acquire(self.owner,self.p,45)[0])

    def test_changed_busy_token_is_never_cleared_and_owner_cannot_resume(self):
        self.acquire();foreign=self.h.lua.table();self.port.attackBusy=foreign
        self.assertFalse(self.owner.Owns(self.owner,self.p));self.owner.Close(self.owner)
        self.assertTrue(self.h.lua.eval('function(a,b) return a==b end')(self.port.attackBusy,foreign))

    def test_late_old_invocation_cannot_clear_newer_physical_identity(self):
        self.acquire();self.h.lua.globals().combatOwner=self.owner;self.h.lua.globals().combatProposal=self.p
        thread=self.h.lua.eval('coroutine.create(function() return combatOwner:Invoke(combatProposal,function() coroutine.yield("hub_wait");return true end) end)').coroutine()
        self.assertEqual(next(thread),'hub_wait');foreign=self.h.lua.table();self.epoch.physical=foreign
        next(thread)
        self.assertTrue(self.h.lua.eval('function(a,b) return a==b end')(self.epoch.physical,foreign))
        self.owner.Close(self.owner)

    def test_scope_kind_and_deadline_changes_are_refused_without_flag_write(self):
        self.make()
        for deadline in (0,46,float('inf'),float('nan')):
            self.assertFalse(self.owner.Acquire(self.owner,self.p,deadline)[0])
        for key,value in [('account','other'),('session','other'),('place','other'),('release','other'),('feature','jobs')]:
            old=self.p[key];self.p[key]=value;self.assertFalse(self.owner.Acquire(self.owner,self.p,45)[0]);self.p[key]=old
        self.p.intent.kind='job';self.assertFalse(self.owner.Acquire(self.owner,self.p,45)[0])
        self.assertEqual(self.port.writes,0)

    def test_unproven_yielding_port_cannot_install_native_gateways(self):
        self.port.nonYielding=False
        owner,why=self.module.new(self.port,self.h.clock,self.identity,self.epoch)
        self.assertIsNone(owner);self.assertIsNotNone(why);self.assertIsNone(self.port.gate)

    def test_partial_guard_write_failure_restores_its_exact_token(self):
        self.make()
        self.port.CompareAttackBusy=self.h.lua.eval('''function(s,expected,value)
            if s.attackBusy~=expected then return false end;s.attackBusy=value
            if type(value)=='table' then error('setter raised after writing') end;return true end''')
        self.assertFalse(self.owner.Acquire(self.owner,self.p,45)[0])
        self.assertFalse(self.port.attackBusy);self.assertFalse(self.owner.Status(self.owner).active)

    def test_throwing_physical_call_clears_only_its_marker_and_preserves_error(self):
        self.acquire()
        with self.assertRaisesRegex(Exception,'native failed'):
            self.owner.Invoke(self.owner,self.p,self.h.lua.eval('function() error("native failed") end'))
        self.assertFalse(self.owner.Status(self.owner).physical)
        self.assertTrue(self.owner.Owns(self.owner,self.p))

    def test_new_manual_prompt_between_acquisition_and_invoke_remains_manual(self):
        self.acquire();self.port.confirmation=self.h.lua.eval('function() error("Do not answer") end')
        self.h.lua.globals().neverCalled=0
        ok,why=self.owner.Invoke(self.owner,self.p,self.h.lua.eval('function() neverCalled=neverCalled+1;return true,"invoked" end'))
        self.assertFalse(ok);self.assertIsNotNone(why);self.assertEqual(self.h.lua.globals().neverCalled,0)
        self.assertIsNotNone(self.port.confirmation)

    def test_cleanup_error_retains_exact_custody_until_a_retry_succeeds(self):
        self.acquire();self.h.lua.globals().cleanupPort=self.port
        self.h.lua.execute('''local original=cleanupPort.CompareAttackBusy
            cleanupPort.CompareAttackBusy=function(s,expected,value)
                if value==false and not s.failedCleanup then s.failedCleanup=true;error('cleanup interrupted') end
                return original(s,expected,value) end''')
        self.assertFalse(self.owner.Release(self.owner,self.p)[0])
        self.assertTrue(self.owner.Status(self.owner).active)
        self.assertTrue(self.owner.Release(self.owner,self.p)[0]);self.assertFalse(self.port.attackBusy)

    def test_unload_while_invocation_yields_fences_the_old_positive_return(self):
        self.acquire();self.h.lua.globals().combatOwner=self.owner;self.h.lua.globals().combatProposal=self.p
        thread=self.h.lua.eval('coroutine.create(function() local reply,why=combatOwner:Invoke(combatProposal,function() coroutine.yield("hub_wait");return {ok=true} end);return type(reply)=="table",reply==false,why end)').coroutine()
        self.assertEqual(next(thread),'hub_wait');self.owner.Close(self.owner)
        result=next(thread);self.assertFalse(result[0]);self.assertTrue(result[1]);self.assertIsNotNone(result[2])
        self.assertFalse(self.port.attackBusy);self.assertFalse(self.owner.Status(self.owner).physical)

    def test_owned_invoke_can_enter_the_exact_native_gateway_once(self):
        self.acquire();self.h.lua.globals().nativePort=self.port
        result=self.owner.Invoke(self.owner,self.p,self.h.lua.eval('function() return nativePort.nativeAttack(42) end'))
        self.assertIsInstance(result,tuple);reply,middle,last=result
        self.assertTrue(reply.ok);self.assertIsNone(middle);self.assertEqual(last,'tail');self.assertEqual(self.port.calls,1)

    def test_invoke_permit_refuses_other_remote_target_extra_args_and_second_call(self):
        self.acquire();self.h.lua.globals().nativePort=self.port
        result=self.owner.Invoke(self.owner,self.p,self.h.lua.eval('''function()
            assert(nativePort.nativeScout(42)==nil)
            assert(nativePort.nativeAttack(43)==nil)
            assert(nativePort.nativeAttack(42,nil)==nil)
            local first=nativePort.nativeAttack(42)
            assert(nativePort.nativeAttack(42)==nil)
            return first
        end'''))
        self.assertIsNotNone(result);self.assertTrue(result.ok);self.assertEqual(self.port.calls,1)

    def test_invoke_permit_is_not_consumable_by_another_coroutine(self):
        self.acquire();self.h.lua.globals().nativePort=self.port
        result=self.owner.Invoke(self.owner,self.p,self.h.lua.eval('''function()
            local other=coroutine.create(function() return nativePort.nativeAttack(42) end)
            local ok,value=coroutine.resume(other);assert(ok and value==nil)
            return nativePort.nativeAttack(42)
        end'''))
        self.assertIsNotNone(result);self.assertTrue(result[0].ok);self.assertEqual(self.port.calls,1)

    def test_unleased_native_scouts_forward_unchanged_and_out_of_order_completion_retains_custody(self):
        self.make();self.port.hang=True;self.h.lua.globals().nativePort=self.port
        create=self.h.lua.eval('function(target) return coroutine.create(function() return nativePort.nativeScout(target) end) end')
        first=create(42).coroutine();second=create(43).coroutine()
        self.assertEqual(next(first),'native_wait');self.assertEqual(next(second),'native_wait')
        self.assertEqual(self.port.calls,2);self.assertFalse(self.owner.Acquire(self.owner,self.p,45)[0])
        next(second);self.assertTrue(self.owner.Status(self.owner).physical)
        self.assertFalse(self.owner.Acquire(self.owner,self.p,45)[0])
        next(first);self.assertFalse(self.owner.Status(self.owner).physical)
        self.assertTrue(self.owner.Acquire(self.owner,self.p,45)[0]);self.assertEqual(self.port.calls,2)

    def test_native_tracking_capacity_preserves_calls_and_keeps_unknown_admission_blocked(self):
        self.make();self.port.hang=True;self.h.lua.globals().nativePort=self.port
        create=self.h.lua.eval('function() return coroutine.create(function() return nativePort.nativeScout(42) end) end')
        threads=[create().coroutine() for _ in range(130)]
        for thread in threads:self.assertEqual(next(thread),'native_wait')
        self.assertEqual(self.port.calls,130);self.assertEqual(self.epoch.nativeCalls.retained,128)
        for thread in reversed(threads):next(thread)
        self.assertEqual(self.epoch.nativeCalls.retained,0)
        self.assertFalse(self.owner.Acquire(self.owner,self.p,45)[0]);self.assertTrue(self.owner.Status(self.owner).physical)

    def test_silent_guard_cleanup_refusal_retains_exact_token_for_close_retry(self):
        self.acquire();self.h.lua.globals().cleanupPort=self.port
        self.h.lua.execute('''local original=cleanupPort.CompareAttackBusy
            cleanupPort.CompareAttackBusy=function(s,expected,value)
                if value==false and not s.allowCleanup then return false end;return original(s,expected,value) end''')
        self.assertFalse(self.owner.Release(self.owner,self.p)[0])
        self.assertTrue(self.owner.Status(self.owner).active);self.assertIsNot(self.port.attackBusy,False)
        self.port.allowCleanup=True;self.assertTrue(self.owner.Close(self.owner));self.assertFalse(self.port.attackBusy)

    def test_failed_gateway_restore_retains_closed_owner_for_later_retry(self):
        for failure in ('false','error'):
            with self.subTest(failure=failure):
                self.setUp();self.acquire();self.h.lua.globals().cleanupPort=self.port;self.port.failure=failure
                self.h.lua.execute('''local original=cleanupPort.Restore
                    cleanupPort.Restore=function(s,token)
                        if not s.allowRestore then if s.failure=='error' then error('restore interrupted') end;return false end
                        return original(s,token) end''')
                self.assertFalse(self.owner.Close(self.owner));self.assertIsNotNone(self.port.gate)
                self.assertTrue(self.h.lua.eval('function(a,b) return a==b end')(self.epoch.binding,self.owner))
                self.port.allowRestore=True;self.assertTrue(self.owner.Close(self.owner))
                self.assertIsNone(self.port.gate);self.assertIsNone(self.epoch.binding);self.assertFalse(self.port.attackBusy)

    def tearDown(self):
        if self.owner:self.owner.Close(self.owner)
