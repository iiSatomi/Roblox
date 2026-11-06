"""Source-pinned Combat port, pristine Scout proof and exact native cleanup."""
import unittest
import test_native_client_bindings as fixture
from engine_harness import lua_table


class NativeCombatBindingTests(unittest.TestCase):
    def setUp(self):
        self.h,self.game,self.state,self.probe,_,self.proposal=fixture.NativeClientBindingsTests().scout_client()
        h=self.h;h.lua.globals().combatBindingProbe=self.probe
        h.lua.execute('''local p=combatBindingProbe;local client=guardClient
            local attack=client.children.FightTab.Value.attack
            local ctx=p.upvalues(attack)[2];ctx.Remotes.ScoutPlayer=p.profileCtx.Remotes.ScoutPlayer
            local root={children={},GetChildren=function(s) local r={};for _,v in pairs(s.children) do r[#r+1]=v end;return r end,
                FindFirstChild=function(s,k) return s.children[k] end}
            local modal={Name='ConfirmModal',Visible=false,Parent=root,IsA=function(_,k) return k=='Frame' or k=='GuiObject' end}
            root.children.ConfirmModal=modal;ctx.gui={Root={Modals=root}}
            p.modal=modal;p.ctx=ctx;p.generation=0;p.target=nil
            local confirm=function() end;client.children.FightTab.Value.confirm=confirm;ctx.confirmDialog=confirm
            local previous=p.upvalues
            p.upvalues=function(fn)
                if fn==p.profileOpen then return {[1]=p.generation,[2]=p.target,[3]=p.profileBusy,[5]=ctx} end
                if fn==confirm then return {[1]=root,[3]=p.confirmation,[4]=ctx} end
                return previous(fn)
            end
            p.attack=attack;p.blocked=p.upvalues(attack)[1]
            guardGame.JobId='job-a';guardGame.PlaceId=73897506680154
        ''')
        self.source=h.load('src/transport/NativeClientBindings.luau').read(self.game,h.lua.eval('function(m) return m.Value end'),self.probe.upvalues)[0].currentFightNotifications
        self.module=h.load('src/tabs/combat/NativeCombatLease.luau')
        self.assertIsNotNone(self.source.CombatController,'Source-owned controller capability is missing')
        h.lua.globals().nativeBindingSource=self.source
        self.env=h.lua.execute('''local p=combatBindingProbe
            local env={crypt={},iscclosure=function() return true end}
            env.getupvalues=function(fn)
                local ok,value=pcall(p.upvalues,fn);if ok then return value end
                local out={};for index=1,100 do local name,value=debug.getupvalue(fn,index);if not name then break end;out[index]=value end;return out
            end
            env.setupvalue=function(fn,index,value)
                if fn==p.blocked and index==1 then p.busy=value;return end
                debug.setupvalue(fn,index,value)
            end
            env.decompile=function(module) return module.Name=='FightTab' and 'reviewed-fight' or 'reviewed-profile' end
            env.crypt.hash=function(bytes) if bytes=='reviewed-fight' then return 'c8999f2c92e903f6901ac22c6c5752a7993b04451faed081fda22d3daac7c9af' end
                if bytes=='reviewed-profile' then return '8329c1cff26a0cbd08e6aff6ef5919dded98e8fc9b69c189c7b5e98271a0475d' end;return string.rep('0',64) end
            return env''')
        self.source=h.load('src/transport/NativeClientBindings.luau').read(self.game,h.lua.eval('function(m) return m.Value end'),self.env.getupvalues)[0].currentFightNotifications
        self.registry=h.lua.table();self.owner=None
        self.proposal.session=h.session['session'];self.proposal.account=h.session['account']
        self.proposal.place=h.session['place'];self.proposal.release=h.session['release'];self.proposal.actionKey='scout:99'

    def bind(self):
        return self.module.bind(lua_table(self.h.lua,{'source':self.source,'env':self.env,'clock':self.h.clock,'identity':self.h.session,'registry':self.registry}))

    def make(self):
        self.owner,why=self.bind();self.assertIsNotNone(self.owner,why)

    def test_current_source_factory_exposes_owned_context_without_native_calls(self):
        controller,why=self.source.CombatController(self.source)
        self.assertIsNotNone(controller,why);self.assertTrue(controller.Current(controller))
        self.assertTrue(self.h.lua.eval('function(a,b) return a==b end')(controller.context,self.probe.ctx))
        self.assertFalse(self.probe.busy);self.assertFalse(self.probe.profileBusy)

    def test_binding_acquires_and_restores_shared_busy_cell_and_original_wrappers(self):
        self.make();self.assertTrue(self.owner.Acquire(self.owner,self.proposal,45)[0])
        self.assertEqual(self.h.lua.eval('type')(self.probe.busy),'table')
        self.assertIsNone(self.probe.ctx.Remotes.Attack.InvokeServer(self.probe.ctx.Remotes.Attack,99))
        self.owner.Close(self.owner);self.assertFalse(self.probe.busy)
        self.assertTrue(self.h.lua.eval('function(a,b) return a==b end')(self.probe.ctx.Remotes.ScoutPlayer,self.probe.profileCtx.Remotes.ScoutPlayer))

    def test_used_native_profile_is_unavailable_without_shadowing_gateways(self):
        original=self.probe.ctx.Remotes.ScoutPlayer;self.probe.generation=1;self.probe.target=99
        owner,why=self.bind();self.assertIsNone(owner);self.assertIsNotNone(why)
        self.assertFalse(self.probe.busy)
        self.assertTrue(self.h.lua.eval('function(a,b) return a==b end')(self.probe.ctx.Remotes.ScoutPlayer,original))

    def test_reviewed_646_fight_source_binds_and_keeps_manual_confirmation_guard(self):
        self.h.lua.globals().reviewedEnv=self.env
        self.h.lua.execute("""local old=reviewedEnv.crypt.hash
            reviewedEnv.crypt.hash=function(bytes)
                if bytes=='reviewed-fight' then return 'ae25c1d9065a7cbca1a75cc31bbcc6cbec3fa4c7c120a9fd7682c854ed79581f' end
                return old(bytes)
            end""")
        self.make()
        self.probe.confirmation=self.h.lua.table()
        allowed,why=self.owner.Acquire(self.owner,self.proposal,45)
        self.assertFalse(allowed);self.assertIsNotNone(why);self.assertFalse(self.probe.busy)
        self.probe.confirmation=None
        self.assertTrue(self.owner.Acquire(self.owner,self.proposal,45)[0])
        self.assertTrue(self.owner.Release(self.owner,self.proposal)[0])
        self.assertFalse(self.probe.busy)

    def test_unknown_source_hash_refuses_before_any_native_controller_write(self):
        self.env.decompile=self.h.lua.eval('function() return "changed" end')
        owner,why=self.bind();self.assertIsNone(owner);self.assertIsNotNone(why);self.assertFalse(self.probe.busy)

    def test_yielding_primitive_self_test_refuses_before_gateway_install(self):
        self.env.getupvalues=self.h.lua.eval('function() coroutine.yield("not_atomic");return {} end')
        owner,why=self.bind();self.assertIsNone(owner);self.assertIsNotNone(why);self.assertFalse(self.probe.busy)

    def test_job_change_sticky_retires_and_cleans_only_old_busy_token(self):
        self.make();self.assertTrue(self.owner.Acquire(self.owner,self.proposal,45)[0])
        self.game.JobId='job-b';self.assertFalse(self.owner.Owns(self.owner,self.proposal));self.assertFalse(self.probe.busy)
        self.game.JobId='job-a';self.assertFalse(self.owner.Acquire(self.owner,self.proposal,45)[0])

    def test_job_change_during_source_inspection_refuses_binding(self):
        self.h.lua.globals().bindingEnv=self.env
        self.h.lua.execute('local original=bindingEnv.decompile;bindingEnv.decompile=function(m) guardGame.JobId="job-b";return original(m) end')
        owner,why=self.bind();self.assertIsNone(owner);self.assertIsNotNone(why);self.assertFalse(self.probe.busy)

    def test_source_factory_preserves_pending_native_confirmation_and_refuses_lease(self):
        callback=self.h.lua.eval('function() error("A native challenge must stay manual") end');self.probe.confirmation=callback
        self.make();self.assertFalse(self.owner.Acquire(self.owner,self.proposal,45)[0])
        self.assertTrue(self.h.lua.eval('function(a,b) return a==b end')(self.probe.confirmation,callback));self.assertFalse(self.probe.busy)

    def test_source_and_primitive_readers_must_be_the_same_verified_function(self):
        self.h.lua.globals().bindingEnv=self.env
        self.h.lua.execute('local original=bindingEnv.getupvalues;bindingEnv.getupvalues=function(fn) return original(fn) end')
        owner,why=self.bind();self.assertIsNone(owner);self.assertIsNotNone(why);self.assertFalse(self.probe.busy)

    def test_owned_gateway_registration_preserves_normal_unleased_preflight(self):
        self.make();self.assertTrue(self.source.CanScout(self.source,self.proposal,99)[0])
        attack=self.proposal.intent;attack.kind='playerAttack';attack.expectedStaminaCost=2
        self.assertTrue(self.source.CanAttack(self.source,self.proposal,99)[0])

    def test_foreign_gateway_still_refuses_preflight_and_exact_cleanup_preserves_it(self):
        self.make();foreign=self.h.lua.table(Name='ScoutPlayer',Instance=self.probe.ctx.Remotes.ScoutPlayer.Instance,
            InvokeServer=self.h.lua.eval('function() return {ok=true} end'))
        self.probe.ctx.Remotes.ScoutPlayer=foreign
        self.assertFalse(self.source.CanScout(self.source,self.proposal,99)[0])
        self.owner.Close(self.owner)
        self.assertTrue(self.h.lua.eval('function(a,b) return a==b end')(self.probe.ctx.Remotes.ScoutPlayer,foreign))

    def test_actual_registered_proxy_forwards_only_owned_invocation_to_original_wrapper(self):
        self.h.lua.globals().bindingProbe=self.probe
        self.h.lua.execute('''bindingProbe.forwarded=0
            bindingProbe.ctx.Remotes.ScoutPlayer.InvokeServer=function(self,target)
                assert(target==99);bindingProbe.forwarded=bindingProbe.forwarded+1;return {ok=true,def=7} end''')
        self.source=self.h.load('src/transport/NativeClientBindings.luau').read(self.game,self.h.lua.eval('function(m) return m.Value end'),self.env.getupvalues)[0].currentFightNotifications
        self.make();self.assertTrue(self.owner.Acquire(self.owner,self.proposal,45)[0])
        self.assertIsNone(self.probe.ctx.Remotes.ScoutPlayer.InvokeServer(self.probe.ctx.Remotes.ScoutPlayer,99))
        reply=self.owner.Invoke(self.owner,self.proposal,self.h.lua.eval('function() return bindingProbe.ctx.Remotes.ScoutPlayer:InvokeServer(99) end'))
        self.assertTrue(reply.ok);self.assertEqual(reply['def'],7);self.assertEqual(self.probe.forwarded,1)

    def test_actual_silent_setter_refusal_retains_guard_until_confirmed_restoration(self):
        self.h.lua.globals().bindingEnv=self.env
        self.h.lua.execute('''local original=bindingEnv.setupvalue;bindingEnv.setupvalue=function(fn,index,value)
            if fn==combatBindingProbe.blocked and value==false and combatBindingProbe.refuseCleanup then return end
            return original(fn,index,value) end''')
        self.make();self.assertTrue(self.owner.Acquire(self.owner,self.proposal,45)[0]);self.probe.refuseCleanup=True
        self.assertFalse(self.owner.Release(self.owner,self.proposal)[0]);self.assertTrue(self.owner.Status(self.owner).active)
        self.probe.refuseCleanup=False;self.assertTrue(self.owner.Close(self.owner));self.assertFalse(self.probe.busy)

    def test_static_cleanup_retries_closed_proxy_restore_before_fresh_source_binding(self):
        self.make();self.h.lua.globals().cleanupOwner=self.owner
        self.h.lua.execute('''local port=cleanupOwner.port;local original=port.Restore
            port.Restore=function(s,token) if not s.allowRestore then return false end;return original(s,token) end''')
        self.assertFalse(self.owner.Close(self.owner));self.owner.port.allowRestore=True
        self.assertIsNotNone(self.module.cleanup,'Pre-binding exact cleanup capability is missing')
        freshModule=self.h.load('src/tabs/combat/NativeCombatLease.luau')
        self.assertTrue(freshModule.cleanup(self.registry)[0])
        self.source=self.h.load('src/transport/NativeClientBindings.luau').read(self.game,self.h.lua.eval('function(m) return m.Value end'),self.env.getupvalues)[0].currentFightNotifications
        self.owner=None;self.make();self.assertTrue(self.source.CanScout(self.source,self.proposal,99)[0])
        self.assertTrue(self.owner.Acquire(self.owner,self.proposal,45)[0])

    def test_static_cleanup_never_closes_an_active_owner(self):
        self.make();self.assertTrue(self.owner.Acquire(self.owner,self.proposal,45)[0])
        self.assertIsNotNone(self.module.cleanup,'Pre-binding exact cleanup capability is missing')
        ok,why=self.module.cleanup(self.registry)
        self.assertFalse(ok);self.assertIsNotNone(why);self.assertTrue(self.owner.Owns(self.owner,self.proposal))

    def test_missing_or_invalid_native_busy_readback_never_releases_opaque_guard_custody(self):
        self.make();self.assertTrue(self.owner.Acquire(self.owner,self.proposal,45)[0])
        self.h.lua.globals().bindingProbe=self.probe
        self.h.lua.execute('''local previous=bindingProbe.upvalues
            bindingProbe.upvalues=function(fn)
                local values=previous(fn)
                if fn==bindingProbe.blocked and bindingProbe.maskBusy then values[1]=bindingProbe.maskedBusy end
                return values
            end''')
        for invalid in (None,'unknown',17,self.h.lua.eval('function() end')):
            self.probe.maskBusy=True;self.probe.maskedBusy=invalid
            self.assertFalse(self.owner.Release(self.owner,self.proposal)[0])
            self.assertTrue(self.owner.Status(self.owner).active)
            self.assertEqual(self.h.lua.eval('type')(self.probe.busy),'table')
        self.probe.maskBusy=False
        self.assertTrue(self.owner.Close(self.owner));self.assertFalse(self.probe.busy)

    def tearDown(self):
        if self.owner:self.owner.Close(self.owner)
