"""Actual Prestige App dispatch requires the native reset owner on current clients."""
import unittest
import test_prestige_owned_app as fixture
from engine_harness import ROOT, lua_table
from prestige_source_fixture import make_prestige_client

class NativePrestigeAppTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.PrestigeOwnedAppTests();self.f.setUp();self.h=self.f.h
        self.owner=self.h.lua.execute("""return {active=false,calls=0,releases=0,closed=false,
            Acquire=function(s,p) if s.denied or s.closed then return false end;s.active=p;return true end,
            Owns=function(s,p)return s.active==p and not s.closed end,
            Invoke=function(s,p,invoke) if s.invokeDenied then return false end;assert(s:Owns(p));s.calls=s.calls+1;return invoke() end,
            Release=function(s,p) if s.active~=p then return false end;s.active=false;s.releases=s.releases+1;return true end,
            Status=function(s)return {closed=s.closed,active=s.active~=false,physical=s.physical==true}end,
            Close=function(s)s.closed=true;s.active=false;return true end}""")
        self.f.adapter.prestigeLease=self.owner;self.f.adapter.requirePrestigeLease=True
        self.f.tab.nativePrestigeLease=self.owner

    def test_owned_reset_invokes_once_and_releases_only_after_new_sync_confirmation(self):
        f=self.f;f.begin();f.send()
        self.assertEqual(self.owner.calls,1);self.assertTrue(self.owner.active)
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)),1)
        self.h.at(.25);f.app.Step(f.app,f.raw(rank=1,level=1,xp=0,revision=2,at=.25))
        self.assertEqual(f.runtime.Status(f.runtime).outcomes.prestige,'confirmed')
        self.assertFalse(self.owner.active);self.assertEqual(self.owner.releases,1)
        self.assertEqual(f.executor.calls,1)

    def test_missing_required_owner_refuses_before_pending_or_attempt_charge(self):
        f=self.f;f.adapter.prestigeLease=None;f.enable();f.app.Step(f.app,f.raw())
        self.assertEqual(len(f.executor.queued),0)
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)),0)
        self.assertEqual(f.runtime.checkpoint.PrestigeUsage(f.runtime.checkpoint,f.raw())[0].attempted,0)

    def test_native_manual_guard_or_owner_callback_denial_is_proven_unsent(self):
        for phase in ('denied','invokeDenied'):
            with self.subTest(phase=phase):
                if phase!='denied':self.tearDown();self.setUp()
                f=self.f;self.owner[phase]=True;f.begin();f.executor.queued[1]()
                self.assertEqual(f.executor.calls,0)
                self.assertFalse(self.owner.active)
                self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)),0)
                self.assertEqual(f.runtime.checkpoint.PrestigeUsage(f.runtime.checkpoint,f.raw())[0].attempted,0)

    def test_queued_disable_and_unload_do_not_acquire_or_invoke_native_owner(self):
        f=self.f;f.begin();f.app.Set(f.app,'prestige.enabled',False);f.executor.queued[1]()
        self.assertEqual(self.owner.calls,0);self.assertEqual(f.executor.calls,0)
        f.app.Destroy(f.app);self.assertTrue(self.owner.closed)

    def test_ambiguous_return_keeps_attempt_and_checkpoint_after_logical_expiry(self):
        f=self.f;f.begin();f.executor.fail=True;f.executor.queued[1]()
        self.assertEqual(f.executor.calls,1)
        self.h.at(45);f.app.Step(f.app,f.raw(revision=2,at=45))
        self.assertEqual(f.runtime.Status(f.runtime).outcomes.prestige,'skipped_unconfirmed')
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)),1)
        self.assertEqual(f.runtime.checkpoint.PrestigeUsage(f.runtime.checkpoint,f.raw())[0].attempted,1)
        self.assertFalse(self.owner.active)

    def attach_real_owner(self):
        f=self.f;h=self.h
        self.port=h.lua.execute("""return {nonYielding=true,busy=false,confirmationPending=false,modalOpen=false,
            Current=function()return true end,
            Read=function(s)return {busy=s.busy,confirmationPending=s.confirmationPending,modalOpen=s.modalOpen}end,
            Facts=function(s)local r={};for k,v in pairs(s.controller.frame)do r[k]=v end;return r end,
            CompareBusy=function(s,a,b)if s.busy~=a then return false end;s.busy=b;return true end}""")
        self.port.controller=f.controller
        self.epoch=h.lua.table()
        self.owner,why=h.load('src/tabs/prestige/NativePrestigeLease.luau').new(self.port,h.clock,lua_table(h.lua,h.session),self.epoch)
        self.assertIsNotNone(self.owner,why)
        f.adapter.prestigeLease=self.owner;f.tab.nativePrestigeLease=self.owner
        f.tab.controller=self.owner;f.tab.controllerRead=self.owner.Read;f.tab.controllerCurrent=self.owner.Current
        f.runtime.nativePrestigeController=self.owner;f.runtime.nativePrestigeRead=self.owner.Read;f.runtime.nativePrestigeCurrent=self.owner.Current

    @unittest.skipUnless((ROOT / "docs/native-source/2026-11-02/PrestigeModal.lua.txt").is_file(),
                         "Private native contract capture is intentionally excluded")
    def test_reviewed_654_source_owner_crosses_actual_app_and_preserves_attempt(self):
        h, native = make_prestige_client(self.h)
        native.game.PlaceVersion = 654
        native.state.data.xp = 1234
        owner, why = h.load('src/tabs/prestige/NativePrestigeLease.luau').bind(lua_table(h.lua, {
            'env': native.env, 'game': native.game, 'registry': native.registry,
            'requireModule': native.requireModule, 'clock': h.clock, 'identity': h.session}))
        self.assertIsNotNone(owner, why)
        self.owner = owner
        f = self.f
        f.adapter.prestigeLease = owner
        f.tab.nativePrestigeLease = owner
        f.tab.controller, f.tab.controllerRead, f.tab.controllerCurrent = owner, owner.Read, owner.Current
        f.runtime.nativePrestigeController = owner
        f.runtime.nativePrestigeRead, f.runtime.nativePrestigeCurrent = owner.Read, owner.Current
        h.lua.globals().prestige654 = native
        f.executor.InvokeOwned = h.lua.eval("""function(s, token, remote, method, arg)
            assert(prestigeLane:Owns(token))
            assert(remote=='PrestigeAction' and method=='InvokeServer' and arg=='prestige')
            s.calls=s.calls+1
            local d=prestige654.state.data;d.prestige=1;d.level=1;d.xp=0
            return {ok=true,rank=1}
        end""")
        f.begin(); f.send()
        self.assertEqual(h.lua.eval('type')(native.env.getupvalues(native.api.init)[5]), 'table')
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 1)
        h.at(.25)
        f.app.Step(f.app, f.raw(rank=1, level=1, xp=0, revision=2, at=.25))
        self.assertEqual(f.runtime.Status(f.runtime).outcomes.prestige, 'confirmed')
        self.assertFalse(native.env.getupvalues(native.api.init)[5])
        self.assertEqual(f.runtime.checkpoint.PrestigeUsage(f.runtime.checkpoint, f.raw())[0].attempted, 1)
        self.assertEqual((f.executor.calls, native.calls), (1, 0))
        f.restart_all_off()
        f.app.Step(f.app, f.raw(rank=1, level=1, xp=0, revision=2, at=.25))
        self.assertEqual(f.runtime.checkpoint.PrestigeUsage(f.runtime.checkpoint, f.raw())[0].attempted, 1)
        self.assertEqual(f.executor.calls, 0)

    def test_actual_native_owner_exposes_outcome_frame_while_busy_without_permitting_second_reset(self):
        self.attach_real_owner();f=self.f;f.begin();f.send()
        self.assertEqual(self.h.lua.eval('type')(self.port.busy),'table')
        frame=self.owner.Read(self.owner)
        self.assertEqual((frame.rank,frame.level,frame.xp),(1,1,0))
        self.assertFalse(frame.controllersClear)
        self.h.at(.25);f.app.Step(f.app,f.raw(rank=1,level=1,xp=0,revision=2,at=.25))
        self.assertEqual(f.runtime.Status(f.runtime).outcomes.prestige,'confirmed')
        self.assertFalse(self.port.busy);self.assertEqual(f.executor.calls,1)

    def test_actual_native_manual_dialog_at_dispatch_is_unsent_and_preserved(self):
        self.attach_real_owner();f=self.f;f.begin();self.port.confirmationPending=True
        f.executor.queued[1]()
        self.assertEqual(f.executor.calls,0);self.assertTrue(self.port.confirmationPending)
        self.assertFalse(self.port.busy)
        self.assertEqual(f.runtime.checkpoint.PrestigeUsage(f.runtime.checkpoint,f.raw())[0].attempted,0)

    def test_actual_owner_retains_busy_across_unload_until_physical_return(self):
        self.attach_real_owner();f=self.f;f.begin()
        f.executor.InvokeOwned=self.h.lua.eval("""function(s,...)s.calls=s.calls+1;coroutine.yield('native-reset');return {ok=true,rank=1}end""")
        self.h.lua.globals().prestigeQueued=f.executor.queued[1]
        self.h.lua.execute("prestigeNativeThread=coroutine.create(prestigeQueued);assert(coroutine.resume(prestigeNativeThread))")
        self.assertEqual(f.executor.calls,1)
        self.h.at(45);f.app.Step(f.app,f.raw(revision=2,at=45));f.app.Destroy(f.app)
        self.assertEqual(self.h.lua.eval('type')(self.port.busy),'table')
        self.assertTrue(self.owner.Status(self.owner).physical)
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)),1)
        self.h.lua.execute('assert(coroutine.resume(prestigeNativeThread))')
        self.assertFalse(self.port.busy);self.assertIsNone(self.epoch.binding)
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)),1)
        self.assertEqual(f.runtime.checkpoint.PrestigeUsage(f.runtime.checkpoint,f.raw())[0].attempted,1)

    def tearDown(self):self.f.tearDown()
