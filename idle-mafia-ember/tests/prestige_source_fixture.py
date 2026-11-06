"""Exact PrestigeModal source runs only in an offline client with queued tasks."""
import hashlib
from engine_harness import Harness, ROOT


def make_prestige_client(h=None):
    h = h if h is not None else Harness()
    h.lua.globals().prestigeCapturedSource = (ROOT / 'docs/native-source/2026-11-02/PrestigeModal.lua.txt').read_bytes().decode('utf-8')
    h.lua.globals().prestigeSourceHash = lambda value, kind: hashlib.sha256(value.encode()).hexdigest()
    f = h.lua.execute('''
        local function node(name,class)
            local n={Name=name,ClassName=class,children={},Visible=false}
            function n:IsA(k) return self.ClassName==k or k=='GuiObject' and (self.ClassName=='Frame' or self.ClassName=='TextButton') end
            function n:FindFirstChild(k) return self.children[k] end
            function n:WaitForChild(k) return assert(self.children[k],k) end
            function n:GetChildren() local result={};for _,v in pairs(self.children) do result[#result+1]=v end;return result end
            function n:Add(c) c.Parent=self;self.children[c.Name]=c;self[c.Name]=c;return c end
            return n
        end
        local f={jobs={},calls=0,writes=0,confirmCalls=0,registry={}}
        local player=node('user-a','Player');player.UserId=42
        local scripts=player:Add(node('PlayerScripts','PlayerScripts'));local client=scripts:Add(node('MWClient','LocalScript'))
        local stateModule=client:Add(node('State','ModuleScript'))
        local state={data={userId=42,prestige=0,level=200,xp=10}}
        state.latest=function() return state.data end;state.onChanged=function(cb) f.changed=cb end;stateModule.Value=state
        local replicated=node('ReplicatedStorage','ReplicatedStorage');local mw=replicated:Add(node('MW','Folder'))
        local rules={rankOf=function(d) return d.prestige end,canPrestige=function(d) return d.level>=200 and d.prestige<6 end}
        mw:Add(node('Prestige','ModuleScript')).Value=rules
        local config=mw:Add(node('Config','ModuleScript'));config.Value={PRESTIGE={crewSlotsPerRank=1}}
        local remotes=mw:Add(node('Remotes','Folder'));local raw=remotes:Add(node('PrestigeAction','RemoteFunction'))
        local wrapper={Name='PrestigeAction',Instance=raw,InvokeServer=function(_,kind)
            assert(kind=='prestige');f.calls=f.calls+1;if f.hang then coroutine.yield('native-wait') end;return {ok=false,msg='offline fixture'} end}
        local gui=player:Add(node('PlayerGui','PlayerGui')):Add(node('MWGui','ScreenGui'))
        local root=gui:Add(node('Root','Frame')):Add(node('Modals','Frame'))
        local modal=root:Add(node('PrestigeModal','Frame'));local confirmation=root:Add(node('ConfirmModal','Frame'))
        root:Add(node('Backdrop','TextButton'));local other=root:Add(node('OtherModal','Frame'))
        modal.CloseButton={Activated={Connect=function(_,cb) f.close=cb end}}
        modal.PrestigeButton={Activated={Connect=function(_,cb) f.press=cb end}}
        local ctx={player=player,State=state,Config=config.Value,gui=gui,Remotes={PrestigeAction=wrapper},
            toast=function() end,Sfx={play=function() end}}
        local confirm=function(_,_,_,cb) f.confirmCalls=f.confirmCalls+1;f.pending=cb end
        ctx.confirmDialog=confirm;local fight=client:Add(node('FightTab','ModuleScript'));fight.Value={confirm=confirm}
        local badge=client:Add(node('PrestigeBadge','ModuleScript'));badge.Value={apply=function() end}
        local module=client:Add(node('PrestigeModal','ModuleScript'))
        local players={LocalPlayer=player};local game={PlaceId=73897506680154,PlaceVersion=653,JobId='prestige-job'}
        function game:GetService(k) if k=='Players' then return players elseif k=='ReplicatedStorage' then return replicated end;error(k) end
        local native=setmetatable({game=game,script=module,require=function(m) return m.Value end,
            task={spawn=function(fn) f.jobs[#f.jobs+1]=coroutine.create(fn) end}}, {__index=_G})
        local api=assert(load(prestigeCapturedSource,'PrestigeModal','t',native))();module.Value=api;api.init(ctx)
        local maps={[api.init]={'u2','u3','u4','close','u5','Prestige','anyModalOpen','paint'},
            [api.open]={'u2','Prestige','paint','u3','u4'}}
        local function find(fn,name)
            for i=1,32 do local k,v=debug.getupvalue(fn,i);if k==nil then break end;if k==name then return i,v end end
        end
        local reflection={}
        function reflection.getupvalues(fn)
            if f.failRead and fn==api.init then error('read failed') end
            if fn==confirm then return {[1]=root,[2]='fixture-color',[3]=f.pending,[4]=ctx} end
            local out={};if maps[fn] then for i,name in ipairs(maps[fn]) do local _,v=find(fn,name);out[i]=v end
            else for i=1,32 do local k,v=debug.getupvalue(fn,i);if k==nil then break end;out[i]=v end end;return out
        end
        function reflection.setupvalue(fn,index,value)
            if fn==api.init then f.writes=f.writes+1;if f.failWrite then error('write failed') end end
            local actual=maps[fn] and assert(find(fn,maps[fn][index])) or index
            assert(debug.setupvalue(fn,actual,value))
        end
        function reflection.iscclosure(fn) return type(fn)=='function' end
        function reflection.decompile(m) assert(m==module);return f.badSource and prestigeCapturedSource..' ' or prestigeCapturedSource end
        reflection.crypt={hash=function(value,kind) return prestigeSourceHash(value,kind) end}
        f.env=reflection;f.game=game;f.player=player;f.api=api;f.module=module;f.ctx=ctx;f.root=root;f.modal=modal
        f.confirm=confirmation;f.other=other;f.rules=rules;f.wrapper=wrapper;f.state=state;f.requireModule=native.require;f.players=players
        return f
    ''')
    return h, f
