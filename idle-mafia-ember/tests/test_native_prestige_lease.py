"""Atomic Prestige busy ownership and retained physical custody, without live Reset."""
import unittest
from engine_harness import Harness, ROOT, lua_table
from prestige_source_fixture import make_prestige_client

PATH = 'src/tabs/prestige/NativePrestigeLease.luau'


def proposal(h):
    return lua_table(h.lua, {**h.session, 'revision':1, 'feature':'prestige', 'actionKey':'prestige:0:1', 'resources':{},
        'intent':{'kind':'prestigeReset','rankBefore':0,'nextRank':1,'levelBefore':200,'xpBefore':10,
                  'requiredLevel':200,'catalogKey':'a'*64,'allowReset':True,'targetRank':1,'maxResets':1,'attemptedBefore':0}})


class NativePrestigeLeaseTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / PATH).is_file(), 'Atomic native Prestige ownership is missing')
        self.h=Harness();self.module=self.h.load(PATH)
        self.port=self.h.lua.execute('''local p={nonYielding=true,valid=true,busy=false,writes=0,modalOpen=false,confirmationPending=false}
            function p:Current() return self.valid end
            function p:Read() if self.failRead then error('read failed') end;return {busy=self.busy,modalOpen=self.modalOpen,confirmationPending=self.confirmationPending} end
            function p:Facts() return {rank=0,level=200,xp=10,ready=true} end
            function p:CompareBusy(expected,value)
                if self.race then self.busy=true;return false end
                if self.busy~=expected or self.failCompare then return false end
                self.busy=value;self.writes=self.writes+1
                if self.failAfterWrite then self.failRead=true;error('after write') end
                return true
            end
            return p''')
        self.epoch=self.h.lua.table();self.p=proposal(self.h);self.owner=None
    def make(self):
        self.owner,why=self.module.new(self.port,self.h.clock,lua_table(self.h.lua,self.h.session),self.epoch)
        self.assertIsNotNone(self.owner,why);return self.owner
    def acquire(self):
        if self.owner is None:self.make()
        self.assertTrue(self.owner.Acquire(self.owner,self.p,45)[0])
    def same(self,a,b):return self.h.lua.eval('function(a,b) return a==b end')(a,b)
    def start_physical(self):
        self.h.lua.globals().prestigeOwner=self.owner;self.h.lua.globals().prestigeProposal=self.p
        self.h.lua.execute('''prestigeSent=0;prestigeThread=coroutine.create(function()
            prestigeResult=prestigeOwner:Invoke(prestigeProposal,function() prestigeSent=prestigeSent+1;coroutine.yield('rpc');return {ok=true,rank=1} end)
        end);assert(coroutine.resume(prestigeThread))''')
    def finish_physical(self):
        self.h.lua.execute('assert(coroutine.resume(prestigeThread))')
    def test_claims_opaque_shared_cell_and_projects_facts_until_exact_release(self):
        self.acquire();self.assertEqual(self.h.lua.eval('type')(self.port.busy),'table')
        self.assertTrue(self.owner.Owns(self.owner,self.p));frame=self.owner.Read(self.owner)
        self.assertEqual((frame.rank,frame.level,frame.xp,frame.ready),(0,200,10,True));self.assertFalse(frame.controllersClear)
        self.assertTrue(self.owner.Release(self.owner,self.p)[0]);self.assertFalse(self.port.busy)
        self.assertTrue(self.owner.Read(self.owner).controllersClear)
    def test_native_busy_pending_confirmation_and_any_modal_never_get_overwritten(self):
        for field in ('busy','confirmationPending','modalOpen'):
            self.setUp();self.port[field]=True;self.make()
            self.assertFalse(self.owner.Acquire(self.owner,self.p,45)[0]);self.assertTrue(self.port[field]);self.assertEqual(self.port.writes,0)
    def test_native_claim_winning_compare_race_is_preserved(self):
        self.make();self.port.race=True;self.assertFalse(self.owner.Acquire(self.owner,self.p,45)[0])
        self.assertTrue(self.port.busy);self.assertEqual(self.port.writes,0)
    def test_changed_proposal_or_scope_cannot_invoke_callback(self):
        for field,value in (('actionKey','other'),('account','other'),('release','other'),('revision',2)):
            self.setUp();self.acquire();self.p[field]=value
            self.assertFalse(self.owner.Owns(self.owner,self.p));self.assertFalse(self.owner.Invoke(self.owner,self.p,self.h.lua.eval('function() error("callback entered") end'))[0])
        self.setUp();self.acquire();self.p.intent.xpBefore=11;self.assertFalse(self.owner.Owns(self.owner,self.p))
    def test_modal_opening_after_claim_refuses_before_executor_entered(self):
        self.acquire();self.port.modalOpen=True
        self.assertFalse(self.owner.Invoke(self.owner,self.p,self.h.lua.eval('function() error("callback entered") end'))[0])
    def test_physical_return_preserves_reply_tuple_and_keeps_logical_guard(self):
        self.acquire();value,middle,last=self.owner.Invoke(self.owner,self.p,self.h.lua.eval('function() return {ok=true,rank=1},nil,"tail" end'))
        self.assertTrue(value.ok);self.assertIsNone(middle);self.assertEqual(last,'tail');self.assertTrue(self.owner.Owns(self.owner,self.p))
    def test_timeout_releases_admission_but_keeps_busy_until_physical_return(self):
        self.acquire();token=self.port.busy;self.start_physical();self.h.at(45)
        self.assertFalse(self.owner.Owns(self.owner,self.p));self.owner.Release(self.owner,self.p)
        status=self.owner.Status(self.owner);self.assertFalse(status.active);self.assertTrue(status.physical)
        self.assertTrue(self.same(token,self.port.busy));self.assertFalse(self.owner.Acquire(self.owner,self.p,90)[0])
        self.finish_physical();self.assertFalse(self.port.busy);self.assertFalse(self.owner.Status(self.owner).physical)
    def test_close_does_not_clear_a_physically_unresolved_reset(self):
        self.acquire();token=self.port.busy;self.start_physical();self.assertFalse(self.owner.Close(self.owner))
        self.assertTrue(self.same(token,self.port.busy));self.assertIsNotNone(self.epoch.binding)
        self.finish_physical();self.assertFalse(self.port.busy);self.assertTrue(self.owner.Close(self.owner));self.assertIsNone(self.epoch.binding)
    def test_false_cleanup_compare_or_incomplete_read_retains_exact_custody(self):
        self.acquire();token=self.port.busy;self.port.failCompare=True
        self.assertFalse(self.owner.Release(self.owner,self.p)[0]);self.assertTrue(self.same(token,self.port.busy));self.assertIsNotNone(self.epoch.binding)
        self.port.failCompare=False;self.port.failRead=True
        self.assertFalse(self.owner.Release(self.owner,self.p)[0]);self.port.failRead=False
        self.assertTrue(self.owner.Release(self.owner,self.p)[0]);self.assertFalse(self.port.busy)
    def test_write_error_after_claim_retains_retryable_token_when_cleanup_read_fails(self):
        self.make();self.port.failAfterWrite=True;self.assertFalse(self.owner.Acquire(self.owner,self.p,45)[0])
        self.assertIsNotNone(self.epoch.binding);self.assertEqual(self.h.lua.eval('type')(self.port.busy),'table')
        self.port.failRead=False;self.port.failAfterWrite=False;self.assertTrue(self.owner.Release(self.owner,self.p)[0]);self.assertFalse(self.port.busy)
    def test_foreign_busy_token_is_never_cleared(self):
        self.acquire();foreign=self.h.lua.table();self.port.busy=foreign;self.owner.Close(self.owner)
        self.assertTrue(self.same(foreign,self.port.busy))
    def test_source_retirement_allows_only_captured_exact_cleanup_and_stays_retired(self):
        self.acquire();self.port.valid=False;self.assertFalse(self.owner.Current(self.owner));self.assertFalse(self.port.busy)
        self.port.valid=True;self.assertFalse(self.owner.Current(self.owner));self.assertFalse(self.owner.Acquire(self.owner,self.p,45)[0])
    def test_expired_or_overlong_deadline_never_claims(self):
        self.make()
        for deadline in (0,46,float('nan')):self.assertFalse(self.owner.Acquire(self.owner,self.p,deadline)[0])
        self.assertEqual(self.port.writes,0)

    def test_returned_owned_action_cannot_invoke_a_second_callback(self):
        self.acquire();self.owner.Invoke(self.owner,self.p,self.h.lua.eval('function() return {ok=true} end'))
        self.assertFalse(self.owner.Invoke(self.owner,self.p,self.h.lua.eval('function() error("second callback entered") end'))[0])
    def test_missing_explicit_reset_consent_or_invalid_reset_limits_cannot_claim(self):
        for field,value in (('allowReset',False),('targetRank',0),('maxResets',0),('attemptedBefore',1)):
            self.setUp();self.make();self.p.intent[field]=value
            self.assertFalse(self.owner.Acquire(self.owner,self.p,45)[0]);self.assertEqual(self.port.writes,0)


@unittest.skipUnless((ROOT / "docs/native-source/2026-11-02/PrestigeModal.lua.txt").is_file(),
                     "Private native contract capture is intentionally excluded from this package")
class NativePrestigeBindTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / PATH).is_file(), 'Atomic native Prestige ownership is missing')
        self.h,self.f=make_prestige_client();self.module=self.h.load(PATH);self.p=proposal(self.h)
    def bind(self):
        return self.module.bind(lua_table(self.h.lua,{'env':self.f.env,'game':self.f.game,'registry':self.f.registry,
            'requireModule':self.f.requireModule,'clock':self.h.clock,'identity':self.h.session}))
    def make(self):
        owner,why=self.bind();self.assertIsNotNone(owner,why);return owner
    def busy(self):return self.f.env.getupvalues(self.f.api.init)[5]
    def test_reviewed_build_654_preserves_atomic_native_ownership_and_cleanup(self):
        self.f.game.PlaceVersion = 654
        owner = self.make()
        self.assertEqual(self.f.writes, 0)
        self.assertTrue(owner.Read(owner).controllersClear)
        self.assertTrue(owner.Acquire(owner, self.p, 45)[0])
        self.f.press()
        self.assertEqual((self.f.calls, len(self.f.jobs), self.f.confirmCalls), (0, 0, 0))
        self.assertEqual(self.h.lua.eval('type')(self.busy()), 'table')
        self.assertTrue(owner.Release(owner, self.p)[0])
        self.assertFalse(self.busy())
        self.assertTrue(owner.Close(owner))
        self.assertTrue(self.module.cleanup(self.f.registry)[0])
        self.assertIsNotNone(self.bind()[0])

    def test_654_source_mismatch_and_unreviewed_future_build_refuse_without_native_write(self):
        self.f.game.PlaceVersion = 654
        self.f.badSource = True
        self.assertIsNone(self.bind()[0])
        self.assertEqual(self.f.writes, 0)
        for build in (655, 656, 999):
            self.setUp()
            self.f.game.PlaceVersion = build
            self.assertIsNone(self.bind()[0])
            self.assertEqual(self.f.writes, 0)

    def test_654_cleanup_refuses_unresolved_physical_custody(self):
        self.f.game.PlaceVersion = 654
        owner = self.make()
        self.assertTrue(owner.Acquire(owner, self.p, 45)[0])
        self.h.lua.globals().prestigeOwner = owner
        self.h.lua.globals().prestigeProposal = self.p
        self.h.lua.execute('prestigeThread=coroutine.create(function() prestigeOwner:Invoke(prestigeProposal,function() coroutine.yield("rpc");return {} end) end);assert(coroutine.resume(prestigeThread))')
        self.assertFalse(owner.Close(owner))
        self.assertFalse(self.module.cleanup(self.f.registry)[0])
        self.assertIsNone(self.bind()[0])
        self.assertEqual(self.h.lua.eval('type')(self.busy()), 'table')
        self.h.lua.execute('assert(coroutine.resume(prestigeThread))')
        self.assertFalse(self.busy())
        self.assertTrue(self.module.cleanup(self.f.registry)[0])

    def test_exact_capture_token_blocks_native_button_and_already_queued_confirmation(self):
        # A native confirm handler may have cleared its callback immediately before our atomic claim.
        self.f.press();saved=self.f.pending;self.f.pending=None
        owner=self.make();self.assertTrue(owner.Acquire(owner,self.p,45)[0]);self.f.press();saved()
        self.assertEqual((len(self.f.jobs),self.f.calls,self.f.confirmCalls),(0,0,1));self.assertTrue(owner.Owns(owner,self.p))
        self.assertEqual((owner.Read(owner).rank,owner.Read(owner).xp),(0,10));owner.Release(owner,self.p);self.assertFalse(self.busy())
    def test_native_sets_busy_before_spawn_and_only_return_makes_reset_available(self):
        self.f.press();saved=self.f.pending;self.f.pending=None;saved();self.assertTrue(self.busy())
        owner=self.make();self.assertFalse(owner.Acquire(owner,self.p,45)[0]);self.assertEqual(self.f.calls,0)
        self.h.lua.globals().prestigeNativeFixture=self.f;self.h.lua.execute('assert(coroutine.resume(prestigeNativeFixture.jobs[1]))')
        self.assertFalse(self.busy());self.assertEqual(self.f.calls,1);self.assertTrue(owner.Acquire(owner,self.p,45)[0])
    def test_pending_native_callback_and_modal_are_observed_without_being_invoked_or_changed(self):
        self.f.press();saved=self.f.pending;owner=self.make();self.assertFalse(owner.Acquire(owner,self.p,45)[0])
        self.assertTrue(self.h.lua.eval('function(a,b) return a==b end')(saved,self.f.pending));self.assertEqual(len(self.f.jobs),0)
        self.f.pending=None;self.f.other.Visible=True;self.assertFalse(owner.Acquire(owner,self.p,45)[0]);self.assertTrue(self.f.other.Visible)
    def test_changed_source_or_yielding_or_nonwriting_reflection_refuses_before_native_write(self):
        self.f.badSource=True;self.assertIsNone(self.bind()[0]);self.assertEqual(self.f.writes,0)
        self.setUp();self.f.env.getupvalues=self.h.lua.eval('function() coroutine.yield("read") end');self.assertIsNone(self.bind()[0]);self.assertEqual(self.f.writes,0)
        self.setUp();self.f.env.setupvalue=self.h.lua.eval('function() end');self.assertIsNone(self.bind()[0]);self.assertEqual(self.f.writes,0)
    def test_source_job_context_gui_or_wrapper_transition_is_sticky_even_if_restored(self):
        for field in ('job','context','gui','wrapper','build','player'):
            self.setUp();owner=self.make();self.assertTrue(owner.Acquire(owner,self.p,45)[0])
            if field=='job':old=self.f.game.JobId;self.f.game.JobId='other';restore=lambda:setattr(self.f.game,'JobId',old)
            elif field=='build':old=self.f.game.PlaceVersion;self.f.game.PlaceVersion=648;restore=lambda:setattr(self.f.game,'PlaceVersion',old)
            elif field=='context':old=self.f.ctx.State;self.f.ctx.State=self.h.lua.table();restore=lambda:setattr(self.f.ctx,'State',old)
            elif field=='gui':old=self.f.modal.Parent;self.f.modal.Parent=self.h.lua.table();restore=lambda:setattr(self.f.modal,'Parent',old)
            elif field=='player':old=self.f.player.UserId;self.f.player.UserId=43;restore=lambda:setattr(self.f.player,'UserId',old)
            else:old=self.f.wrapper.Name;self.f.wrapper.Name='Other';restore=lambda:setattr(self.f.wrapper,'Name',old)
            self.assertFalse(owner.Current(owner));self.assertFalse(self.busy());restore();self.assertFalse(owner.Current(owner))
    def test_load_time_build_or_job_change_cannot_be_adopted_after_source_capture(self):
        for field,value in (('PlaceVersion',648),('JobId','other')):
            self.setUp();self.h.lua.globals().prestigeBindingFixture=self.f
            self.h.lua.execute("local f=prestigeBindingFixture;local original=f.env.decompile;f.env.decompile=function(m) f.game."+field+"="+(str(value) if isinstance(value,int) else "'"+value+"'")+";return original(m) end")
            self.assertIsNone(self.bind()[0]);self.assertEqual(self.f.writes,0)
    def test_registry_refuses_active_unknown_and_physically_unresolved_owner(self):
        owner=self.make();self.assertIsNone(self.bind()[0]);self.assertFalse(self.module.cleanup(self.f.registry)[0])
        self.assertTrue(owner.Close(owner));self.assertTrue(self.module.cleanup(self.f.registry)[0]);newer=self.make()
        self.assertTrue(newer.Acquire(newer,self.p,45)[0]);self.h.lua.globals().prestigeOwner=newer;self.h.lua.globals().prestigeProposal=self.p
        self.h.lua.execute('prestigeThread=coroutine.create(function() prestigeOwner:Invoke(prestigeProposal,function() coroutine.yield("rpc");return {} end) end);assert(coroutine.resume(prestigeThread))')
        newer.Close(newer);self.assertFalse(self.module.cleanup(self.f.registry)[0]);self.assertIsNone(self.bind()[0]);self.assertEqual(self.h.lua.eval('type')(self.busy()),'table')
        self.h.lua.execute('assert(coroutine.resume(prestigeThread))');self.assertTrue(self.module.cleanup(self.f.registry)[0]);self.assertFalse(self.busy())

    def test_ambiguous_registry_record_is_refused_without_native_write(self):
        self.f.registry['__IDLE_MAFIA_EMBER_PRESTIGE_OWNER_V1']=self.h.lua.table()
        self.assertFalse(self.module.cleanup(self.f.registry)[0]);self.assertIsNone(self.bind()[0]);self.assertEqual(self.f.writes,0)
    def test_replied_reset_frame_stays_readable_under_own_token_before_sync_resolution(self):
        owner=self.make();owner.Acquire(owner,self.p,45);self.h.lua.globals().prestigeOwnedFixture=self.f
        reply=owner.Invoke(owner,self.p,self.h.lua.eval('function() local f=prestigeOwnedFixture;f.state.data.prestige=1;f.state.data.level=1;f.state.data.xp=0;return {ok=true,rank=1} end'))
        self.assertTrue(reply.ok);self.assertTrue(owner.Owns(owner,self.p));frame=owner.Read(owner)
        self.assertEqual((frame.rank,frame.level,frame.xp,frame.ready),(1,1,0,False));self.assertFalse(frame.controllersClear)

    def test_registry_replacement_retires_old_owner_and_cleans_only_its_token(self):
        owner=self.make();owner.Acquire(owner,self.p,45)
        self.f.registry['__IDLE_MAFIA_EMBER_PRESTIGE_OWNER_V1']=self.h.lua.table()
        self.assertFalse(owner.Current(owner));self.assertFalse(self.f.env.getupvalues(self.f.api.init)[5])
        self.assertIsNone(self.bind()[0])
    def test_same_controller_cannot_adopt_a_new_job_or_build_after_retirement(self):
        for field,value in (('JobId','other'),('PlaceVersion',648)):
            self.setUp();owner=self.make();self.f.game[field]=value;self.assertFalse(owner.Current(owner))
            self.assertIsNone(self.bind()[0])
