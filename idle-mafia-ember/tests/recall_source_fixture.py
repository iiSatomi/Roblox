"""Captured CrewRecall executes only inside a fake offline client."""
import hashlib
import unittest
from engine_harness import Harness,lua_table,ROOT

def make_recall_client(provided_h=None):
    h=provided_h or Harness()
    # Exact 8904-byte capture from docs/native-remaining-contracts-2026-11-01.json.
    capture=ROOT/'tests/fixtures/native-recall-653.luau'
    if not capture.is_file():
        raise unittest.SkipTest('Private native Recall capture excluded from distributable archive')
    source=capture.read_bytes().decode('utf-8')
    h.lua.globals().recallCapturedSource=source
    h.lua.globals().recallHash=lambda value,kind:hashlib.sha256(value.encode()).hexdigest()
    f=h.lua.execute('''
        local function node(name,class)
            local n={Name=name,ClassName=class,children={},Visible=false}
            function n:IsA(k) return self.ClassName==k end
            function n:FindFirstChild(k) return self.children[k] end
            function n:WaitForChild(k) return assert(self.children[k],k) end
            function n:Add(child) child.Parent=self;self.children[child.Name]=child;return child end
            return n
        end
        local f={jobs={},writes=0,calls=0,presence=false,registry={}}
        local player=node('user-a','Player');player.UserId=42
        local scripts=player:Add(node('PlayerScripts','PlayerScripts'));local client=scripts:Add(node('MWClient','LocalScript'))
        local stateModule=client:Add(node('State','ModuleScript'));stateModule.Value={data={crew={}},latest=function() return stateModule.Value.data end}
        local replicated=node('ReplicatedStorage','ReplicatedStorage');local mw=replicated:Add(node('MW','Folder'))
        local remotes=mw:Add(node('Remotes','Folder'))
        local clockModule=mw:Add(node('ServerClock','ModuleScript'));clockModule.Value={now=function() return 1000 end}
        local action=remotes:Add(node('TerritoryAction','RemoteFunction'));local status=remotes:Add(node('TerritoryStatus','RemoteFunction'))
        local update=remotes:Add(node('TerritoryUpdate','RemoteEvent'));update.OnClientEvent={Connect=function(_,cb) f.update=cb;return {Disconnect=function()end} end}
        local gui=player:Add(node('PlayerGui','PlayerGui')):Add(node('MafiaWarsUI','ScreenGui'))
        local modals=gui:Add(node('Root','Frame')):Add(node('Modals','Frame'));local confirm=modals:Add(node('ConfirmModal','Frame'))
        local fightModule=client:Add(node('FightTab','ModuleScript'));fightModule.Value={confirm=function() error('native confirmation invoked') end}
        local presenceModule=client:Add(node('TerritoryPresence','ModuleScript'));presenceModule.Value={pending=function() return f.presence end}
        local function wrap(raw) return {Name=raw.Name,Instance=raw,InvokeServer=function() f.calls=f.calls+1;error('native worker invoked') end} end
        local wrapped={TerritoryAction=wrap(action),TerritoryStatus=wrap(status)}
        function wrapped:WaitForChild(name) return remotes:WaitForChild(name) end
        local ctx={player=player,State=stateModule.Value,Remotes=wrapped,gui=gui,confirmDialog=fightModule.Value.confirm,toast=function()end}
        local game={PlaceId=73897506680154,PlaceVersion=653,JobId='recall-job'}
        local guid=0
        function game:GetService(name)
            if name=='Players' then return {LocalPlayer=player} end
            if name=='ReplicatedStorage' then return replicated end
            if name=='HttpService' then return {GenerateGUID=function() guid=guid+1;return 'recall-epoch-'..guid end} end
            error(name)
        end
        -- Preserve object identities across service reads, matching Roblox services.
        local players=game:GetService('Players');local old=game.GetService
        function game:GetService(name) if name=='Players' then return players end return old(self,name) end
        local env=setmetatable({game=game,require=function(m) return m.Value end,
            warn=function()end,print=function()end,typeof=function() return 'Instance' end,
            task={spawn=function(fn) f.jobs[#f.jobs+1]=coroutine.create(fn) end,wait=function() coroutine.yield('wait') end}}, {__index=_G})
        local api=assert(load(recallCapturedSource,'CrewRecall','t',env))()
        local module=client:Add(node('CrewRecall','ModuleScript'));module.Value=api
        api.init(ctx);assert(coroutine.resume(f.jobs[1]))
        local maps={}
        maps[api.start]={'u3','u6','ServerClock','changed','finish','u2'}
        maps[api.init]={'u2','u3','finish'};maps[api.busy]={'u3'};maps[api.isPending]={'u3'}
        maps[api.targets]={'u2','u4'};maps[api.confirm]={'u3','u2','u1'};maps[api.onChanged]={'u7'}
        local function find(fn,name)
            for i=1,32 do local k,v=debug.getupvalue(fn,i);if k==nil then break end;if k==name then return i,v end end
        end
        local _,finish=find(api.start,'finish');local _,changed=find(api.start,'changed')
        maps[finish]={'u3','u2','u4','changed'};maps[changed]={'u7','u3'}
        local reflection={}
        function reflection.getupvalues(fn)
            local result={}
            if maps[fn] then for i,name in ipairs(maps[fn]) do local _,v=find(fn,name);result[i]=v end
            else for i=1,32 do local k,v=debug.getupvalue(fn,i);if k==nil then break end;result[i]=v end end
            return result
        end
        function reflection.setupvalue(fn,index,value)
            local actual=index
            if maps[fn] then actual=assert(find(fn,maps[fn][index])) end
            if fn==api.start then f.writes=f.writes+1 end
            assert(debug.setupvalue(fn,actual,value))
        end
        function reflection.iscclosure(fn) return type(fn)=='function' end
        function reflection.decompile(m) assert(m==module);return f.badSource and recallCapturedSource..' ' or recallCapturedSource end
        reflection.crypt={hash=function(bytes,kind) return recallHash(bytes,kind) end}
        f.env=reflection;f.game=game;f.player=player;f.module=module;f.api=api;f.ctx=ctx;f.modals=modals;f.confirm=confirm
        f.clockModule=clockModule;f.requireModule=env.require;f.maps=maps
        f.target={districtId='d1',userId=42,memberIndex=2,deploymentId='deployment-a',at=900,memberName='Guard',rarity=4}
        return f
    ''')
    return h,f
