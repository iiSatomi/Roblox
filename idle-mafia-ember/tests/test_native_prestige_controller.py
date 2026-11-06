"""Read-only native Prestige busy/confirmation preflight; never open, confirm or reset."""
import unittest
import test_native_client_bindings as fixture
from engine_harness import lua_table

class NativePrestigeControllerTests(unittest.TestCase):
    def setUp(self):
        self.h,self.game,self.state,self.probe,_,_=fixture.NativeClientBindingsTests().fight_client()
        self.remotes=self.game.GetService(self.game,'ReplicatedStorage').children.MW.children.Remotes
        self.state_module=self.game.GetService(self.game,'Players').LocalPlayer.children.PlayerScripts.children.MWClient.children.State
        self.h.lua.globals().prestigeGame=self.game;self.h.lua.globals().prestigeState=self.state
        self.h.lua.globals().prestigeRemotes=self.remotes;self.h.lua.globals().prestigeModule=self.state_module
        # The existing fake upvalue reader remains authoritative for other native controllers.
        self.h.lua.globals().prestigeReadUpvalues=self.probe.upvalues
        # Reuse the fixture construction above after its original reader is installed.
        self.p=self.h.lua.execute(PRESTIGE_FIXTURE)
        self.bindings=self.h.load('src/transport/NativeClientBindings.luau')
        self.found=self.bindings.read(self.game,self.h.lua.eval('function(m) return m.Value end'),self.p.read)[0]
        self.assertIsNotNone(self.found)
        self.source=self.found.currentPrestigeController
    def read(self):
        self.assertIsNotNone(self.source,'Native Prestige controller source is missing')
        value=self.source.Read(self.source);self.assertIsNotNone(value);return value
    def test_verified_build_653_reads_clear_state_and_retires_on_build_transition(self):
        for version,changed in ((648,653),(653,648)):
            self.setUp();self.game.PlaceVersion=version
            self.found=self.bindings.read(self.game,self.h.lua.eval('function(m) return m.Value end'),self.p.read)[0]
            self.source=self.found.currentPrestigeController
            self.assertTrue(self.read().controllersClear)
            self.game.PlaceVersion=changed
            self.assertIsNone(self.source.Read(self.source))
            self.game.PlaceVersion=version
            self.assertIsNone(self.source.Read(self.source))

    def test_known_build_transition_during_any_required_module_is_not_recaptured(self):
        for version,changed in ((648,653),(653,648)):
            for module in ('State','RemoteLink','PrestigeModal','FightTab','Prestige'):
                self.setUp();self.game.PlaceVersion=version
                self.h.lua.globals().prestigeLoadGame=self.game
                require=self.h.lua.eval("function(m) if m.Name=='"+module+"' then prestigeLoadGame.PlaceVersion="+str(changed)+" end;return m.Value end")
                found,why=self.bindings.read(self.game,require,self.p.read)
                self.assertIsNotNone(found,why);self.assertIsNone(found.currentPrestigeController)

    def test_build_653_retains_native_busy_and_confirmation_shape_guards(self):
        self.game.PlaceVersion=653
        self.found=self.bindings.read(self.game,self.h.lua.eval('function(m) return m.Value end'),self.p.read)[0]
        self.source=self.found.currentPrestigeController
        self.assertTrue(self.read().controllersClear)
        self.p.busy=True;self.assertFalse(self.read().controllersClear);self.p.busy=False
        self.p.pending=42;self.assertIsNone(self.source.Read(self.source))

    def test_idle_native_state_is_observed_without_invoking_ui_or_remote(self):
        value=self.read();self.assertTrue(value.controllersClear)
        self.assertEqual((value.rank,value.level,value.xp,value.ready),(0,200,10,True))
    def test_busy_pending_callback_or_any_native_modal_refuses_clear(self):
        for field in ('busy','pending','modal','confirm','other','root'):
            self.setUp()
            if field=='busy':self.p.busy=True
            elif field=='pending':self.p.pending=self.h.lua.eval('function() error("do not call") end')
            else:self.p[field].Visible=True
            self.assertFalse(self.read().controllersClear)
    def test_changed_native_module_context_or_gui_retires_source(self):
        self.read();client=self.state_module.Parent;old=client.children.PrestigeModal;client.children.PrestigeModal=None
        self.assertIsNone(self.source.Read(self.source));client.children.PrestigeModal=old
        self.assertIsNone(self.source.Read(self.source))
    def test_changed_rules_or_native_link_refuses_source(self):
        self.read();self.p.rules.canPrestige=self.h.lua.eval('function() return true end')
        self.assertIsNone(self.source.Read(self.source))
    def test_corrupt_busy_or_callback_shapes_are_unknown(self):
        for field,value in (('busy','false'),('pending',42)):
            self.setUp();self.p[field]=value
            self.assertIsNotNone(self.source,'Missing controller source');self.assertIsNone(self.source.Read(self.source))
    def test_read_postcheck_rejects_scope_change_inside_native_rules(self):
        self.h.lua.globals().prestigeFixtureGame=self.game
        self.p.rules.canPrestige=self.h.lua.eval('function() prestigeFixtureGame.PlaceVersion=649;return true end')
        self.found=self.bindings.read(self.game,self.h.lua.eval('function(m) return m.Value end'),self.p.read)[0]
        self.source=self.found.currentPrestigeController
        self.assertIsNotNone(self.source,'Missing controller source');self.assertIsNone(self.source.Read(self.source))
    def test_close_fences_observations_without_changing_native_flags(self):
        self.read();self.source.Close(self.source);self.assertIsNone(self.source.Read(self.source))
        self.assertFalse(self.p.busy);self.assertIsNone(self.p.pending);self.assertFalse(self.p.root.Visible)
    def test_unverified_place_version_cannot_create_a_controller_source(self):
        self.game.PlaceVersion=649
        found,why=self.bindings.read(self.game,self.h.lua.eval('function(m) return m.Value end'),self.p.read)
        self.assertIsNotNone(found,why);self.assertIsNone(found.currentPrestigeController)
    def test_replaced_confirmation_frame_retires_existing_source(self):
        self.read();self.h.lua.globals().prestigeRoot=self.p.root
        self.h.lua.execute("""local root=prestigeRoot;local old=root.children.ConfirmModal
            root.children.ConfirmModal={Name='ConfirmModal',Parent=root,Visible=false,IsA=old.IsA,ClassName='Frame'}""")
        self.assertIsNone(self.source.Read(self.source))

    def test_present_native_user_identity_must_match_current_player(self):
        self.read();self.state.data.userId=999
        self.assertIsNone(self.source.Read(self.source))
    def test_native_state_owner_or_values_changed_during_rules_are_not_projected(self):
        for field,value in (('userId',999),('level',201),('xp',11)):
            self.setUp();self.state.data.userId=42
            self.h.lua.globals().prestigeFixtureState=self.state
            self.p.rules.canPrestige=self.h.lua.eval('function() prestigeFixtureState.data.'+field+'='+str(value)+';return true end')
            found=self.bindings.read(self.game,self.h.lua.eval('function(m) return m.Value end'),self.p.read)[0]
            self.source=found.currentPrestigeController;self.assertIsNotNone(self.source)
            self.assertIsNone(self.source.Read(self.source))
    def test_mutated_wrapper_name_or_instance_retires_source_without_invocation(self):
        for field in ('Name','Instance'):
            self.setUp();self.read()
            linked=self.p.ctx.Remotes.PrestigeAction
            linked[field]='Changed' if field=='Name' else self.h.lua.table()
            self.assertIsNone(self.source.Read(self.source))

    def test_place_version_change_during_module_loading_cannot_be_recaptured(self):
        self.h.lua.globals().prestigeLoadGame=self.game
        require=self.h.lua.eval('function(m) if m.Name=="PrestigeModal" then prestigeLoadGame.PlaceVersion=649 end;return m.Value end')
        found,why=self.bindings.read(self.game,require,self.p.read)
        self.assertIsNotNone(found,why);self.assertIsNone(found.currentPrestigeController)


PRESTIGE_FIXTURE = r"""local game,state,remotes,smod=prestigeGame,prestigeState,prestigeRemotes,prestigeModule
            game.PlaceId=73897506680154
            local function add(parent,name,class,value)
                local n={Name=name,ClassName=class,Value=value,children={},Visible=false}
                n.Add=parent.Add;n.FindFirstChild=parent.FindFirstChild;n.GetChildren=parent.GetChildren;n.GetAttribute=parent.GetAttribute
                function n:IsA(kind) return kind==self.ClassName or kind=='GuiObject' and self.ClassName=='Frame' end
                return parent:Add(n)
            end
            local player=game:GetService('Players').LocalPlayer
            local gui=add(add(player,'PlayerGui','PlayerGui'),'MWGui','ScreenGui')
            local root=add(add(gui,'Root','Frame'),'Modals','Frame')
            local modal=add(root,'PrestigeModal','Frame');local confirm=add(root,'ConfirmModal','Frame')
            local other=add(root,'PresenceModal','Frame');add(root,'Backdrop','TextButton')
            local mw=game:GetService('ReplicatedStorage').children.MW
            local cfg=mw.children.Config.Value
            local rules={canPrestige=function(d) return d.level>=200 and d.prestige<6 end,rankOf=function(d) return d.prestige end}
            local ruleModule=add(mw,'Prestige','ModuleScript',rules)
            local pmod=add(smod.Parent,'PrestigeModal','ModuleScript',{})
            local raw=add(remotes,'PrestigeAction','RemoteFunction');function raw:InvokeServer() error('Reset forbidden') end
            local function forbidden() error('Native callback must never be invoked') end
            local fight=smod.Parent.children.FightTab.Value;fight.confirm=forbidden
            pmod.Value.open=function() error('Native open forbidden') end;pmod.Value.init=function() error('Native init forbidden') end
            local link=smod.Parent.children.RemoteLink.Value.wrap(remotes)
            local ctx={player=player,State=state,Config=cfg,gui=gui,confirmDialog=fight.confirm,
                Remotes={PrestigeAction=link:FindFirstChild('PrestigeAction')}}
            local paint=function() end;local close=function() end;local any=function() end
            local p={root=root,modal=modal,confirm=confirm,other=other,ctx=ctx,rules=rules,module=pmod,
                busy=false,pending=nil,latest=state.latest}
            state.data={level=200,xp=10,prestige=0};state.latest=function() return state.data end
            local old=prestigeReadUpvalues
            p.read=function(fn)
                if fn==pmod.Value.init then return {ctx,root,modal,close,p.busy,rules,any,paint} end
                if fn==pmod.Value.open then return {ctx,rules,paint,root,modal} end
                if fn==fight.confirm then return {[1]=root,[2]='fixture-color',[3]=p.pending,[4]=ctx} end
                return old(fn)
            end
            return p

"""
