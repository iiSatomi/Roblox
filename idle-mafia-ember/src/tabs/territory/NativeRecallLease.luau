-- Source-owned Recall scheduling fields; never starts native workers or replays mutations.
local NativeRecallLease, Methods = {}, {}
Methods.__index = Methods
local MAX = 9007199254740991
local function integer(v, low) return type(v) == "number" and v == v and v >= low and v <= MAX and v % 1 == 0 end
local function text(v) return type(v) == "string" and #v > 0 and #v <= 200 and not v:find("[%c]") end
local function now(self)
    local ok, value = pcall(self.clock.Now, self.clock)
    return ok and type(value) == "number" and value == value and value >= 0 and value < math.huge and value or nil
end
local function read(self, current)
    if current then
        local ok, valid = pcall(self.port.Current, self.port)
        if not ok or valid ~= true then return nil, "Native Recall source changed" end
    end
    local ok, value = pcall(self.port.Read, self.port)
    if not ok or type(value) ~= "table" or not integer(value.counter, 0) then return nil, "Native Recall state unavailable" end
    if current and (self.epoch.retired or self.epoch.proven ~= true or value.counter ~= self.epoch.counterKnown) then
        if value.counter ~= self.epoch.counterKnown then self.epoch.retired = true end
        return nil, "Prior native Recall activity has no exclusive provenance"
    end
    return value
end
local function matches(self, p)
    local i = type(p) == "table" and p.intent
    return type(i) == "table" and p.feature == "station" and i.kind == "territoryRecall"
        and p.account == self.scope.account and p.place == self.scope.place and i.userId == self.scope.userId
        and i.nativeJob == self.scope.jobId and i.nativeEpoch == self.epoch.id
        and i.nativeSourceKey == self.scope.sourceKey and integer(i.requestId, 1)
end
function NativeRecallLease.new(port, clock, scope, epoch)
    if type(port) ~= "table" or type(port.Current) ~= "function" or port.Bound~=nil and type(port.Bound)~="function" or type(port.Read) ~= "function"
        or type(port.Write) ~= "function" or type(port.Clock) ~= "function" or type(clock) ~= "table" or type(clock.Now) ~= "function"
        or type(scope) ~= "table" or not text(scope.account) or not text(scope.place) or not integer(scope.userId, 1)
        or not text(scope.jobId) or type(scope.sourceKey) ~= "string" or #scope.sourceKey ~= 64 or not scope.sourceKey:match("^[%x]+$")
        or type(epoch) ~= "table" or not text(epoch.id) or not integer(epoch.counterKnown, 0) or type(epoch.proven) ~= "boolean" then
        return nil, "Source-owned Recall capabilities required"
    end
    if epoch.durableFence==nil then epoch.durableFence={owners={},writing={}} end
    if type(epoch.durableFence)~="table" or type(epoch.durableFence.owners)~="table" or type(epoch.durableFence.writing)~="table" then return nil,"Recall durable fence unavailable" end
    return setmetatable({port=port,clock=clock,scope=scope,epoch=epoch,closed=false},Methods), nil
end
local function expire(self)
    local live, time = self.epoch.live, now(self)
    if live and time and time >= live.deadline and type(live.release) == "function" then live.release() end
end
function Methods:Identity()
    if self.closed then return nil end
    -- Bind identity/storage while a human handles a native dialog. Readiness
    -- remains mandatory for Observe, Quote, Acquire, status and target checks.
    local ok, valid = pcall(self.port.Bound or self.port.Current, self.port)
    if not ok or valid ~= true then return nil end
    return {account=self.scope.account,userId=self.scope.userId,place=self.scope.place,
        nativeJob=self.scope.jobId,nativeEpoch=self.epoch.id,nativeSourceKey=self.scope.sourceKey}
end
function Methods:DurableFence() return self.epoch.durableFence end
function Methods:CheckTarget(p,baseline)
    if self.closed or not matches(self,p) or type(self.port.Target)~="function" then return false end
    local ok,valid=pcall(self.port.Target,self.port,p,baseline)
    return ok and valid==true
end
function Methods:Observe()
    if self.closed then return nil end
    expire(self)
    local state, why = read(self, true)
    if not state then return nil, why end
    local result = self:Identity()
    if result then result.counter = state.counter end
    return result, nil
end
function Methods:Quote(highwater)
    if self.closed or not integer(highwater, 0) then return nil, "Recall highwater unavailable" end
    expire(self)
    local state, why = read(self, true)
    if not state then return nil, why end
    if state.pending ~= nil or self.epoch.live then return nil, "Native Recall controller busy" end
    local ok, serverNow = pcall(self.port.Clock, self.port)
    if not ok or type(serverNow) ~= "number" or serverNow ~= serverNow or serverNow < 0 or serverNow > (MAX - 1) / 1000
        or highwater >= MAX or state.counter >= MAX then return nil, "Native Recall clock or counter exhausted" end
    return {requestId=math.max(state.counter+1,highwater+1,math.floor(serverNow*1000)),nativeCounterBefore=state.counter,
        nativeJob=self.scope.jobId,nativeEpoch=self.epoch.id,nativeSourceKey=self.scope.sourceKey}, nil
end
local function acquire(self, p, deadline, status)
    local time = now(self)
    if self.closed or not time or type(deadline) ~= "number" or deadline ~= deadline or deadline <= time or deadline > time+45
        or not matches(self,p) then return false, "Recall lease scope or deadline changed" end
    local state, why = read(self,true)
    if not state then return false,why end
    local i = p.intent
    if self.lease or self.epoch.live or state.pending ~= nil
        or not status and (not integer(i.nativeCounterBefore,0) or state.counter ~= i.nativeCounterBefore or i.requestId <= state.counter)
        or status and i.requestId > state.counter then return false,"Native Recall controller contention" end
    local counter = status and state.counter or i.requestId
    -- Opaque ID prevents the native TerritoryUpdate listener from calling finish
    -- and clearing our token before the hub saves the exact terminal outcome.
    local token = {id={},targets={{districtId=i.districtId,userId=i.userId,memberIndex=i.memberIndex,
        deploymentId=i.deploymentId,at=i.at,memberName=i.memberName,rarity=i.rarity}},startedAt=time}
    local lease = {proposal=p,token=token,counter=counter,deadline=deadline,statusOnly=status == true}
    self.lease,self.epoch.live=lease,lease
    lease.release=function() return self:Release(p) end
    local ok = pcall(function()
        self.port:Write("pending",token)
        if not status then self.port:Write("counter",counter);self.epoch.counterKnown=counter end
    end)
    if not ok then self:Release(p);return false,"Recall lease write failed" end
    return true,nil
end
function Methods:Acquire(p,deadline) return acquire(self,p,deadline,false) end
function Methods:AcquireStatus(p,deadline) return acquire(self,p,deadline,true) end
function Methods:Owns(p)
    local live,time=self.lease,now(self)
    if self.closed or not live or live.proposal~=p or not time or time>=live.deadline or self.epoch.live~=live or not matches(self,p) then return false end
    local state=read(self,true)
    return state~=nil and state.pending==live.token and state.counter==live.counter
end
function Methods:Release(p)
    local live=self.lease
    if not live or live.proposal~=p then return true,nil,"absent" end
    local state,why=read(self,false)
    if not state then return false,why end
    if state.pending==live.token then
        local ok=pcall(self.port.Write,self.port,"pending",nil)
        if not ok then return false,"Recall token cleanup failed" end
    end
    self.lease=nil
    if self.epoch.live==live then self.epoch.live=nil end
    return true,nil
end
function Methods:Close()
    if self.lease then local ok=self:Release(self.lease.proposal);if not ok then return false end end
    self.closed=true
    return true
end

local SOURCE = "654dd04795595b750cfaae17169f846fc9975b08f54112f3051b07f75db781e1"
local REGISTRY = "__IDLE_MAFIA_EMBER_RECALL_EPOCH_V1"
local STORAGE = "__IDLE_MAFIA_EMBER_RECALL_STORAGE_V1"
local function child(parent,name,class)
    local value=parent and parent:FindFirstChild(name)
    return value and value.Parent==parent and value:IsA(class) and value or nil
end
local function primitives(get,set,isC)
    if type(get)~="function" or type(set)~="function" or type(isC)~="function" or not isC(get) or not isC(set) then return false end
    local cell=nil
    local function dummy(value,write) if write then cell=value end;return cell end
    local marker={}
    local thread=coroutine.create(function()
        if type(get(dummy))~="table" then return false end
        for _,value in ipairs({17,true,marker}) do set(dummy,1,value);if dummy()~=value or get(dummy)[1]~=value then return false end end
        set(dummy,1,nil)
        return dummy()==nil and get(dummy)[1]==nil
    end)
    local ok,valid=coroutine.resume(thread)
    return ok and valid==true and coroutine.status(thread)=="dead"
end
function NativeRecallLease.bind(deps)
    if type(deps)~="table" or type(deps.env)~="table" or type(deps.registry)~="table" or type(deps.requireModule)~="function"
        or type(deps.clock)~="table" or not text(deps.account) then return nil,"Native Recall bind capabilities unavailable" end
    local env,game=deps.env,deps.game
    local get,set=env.getupvalues,env.setupvalue
    if type(env.decompile)~="function" or type(env.crypt)~="table" or type(env.crypt.hash)~="function"
        or not primitives(get,set,env.iscclosure) then return nil,"Non-yielding Recall reflection unavailable" end
    local ok,result,reason=pcall(function()
        local build,jobId=game.PlaceVersion,game.JobId
        if game.PlaceId~=73897506680154 or (build~=648 and build~=653 and build~=654 and build~=655) or not text(jobId) then return nil,"Unreviewed Recall build" end
        local players,replicated=game:GetService("Players"),game:GetService("ReplicatedStorage")
        local player=players.LocalPlayer
        local userId=player and player.UserId
        if not player or player.Name~=deps.account or not integer(player.UserId,1) then return nil,"Recall account binding unavailable" end
        local scripts=child(player,"PlayerScripts","PlayerScripts")
        local client=child(scripts,"MWClient","LocalScript")
        local module,stateModule=child(client,"CrewRecall","ModuleScript"),child(client,"State","ModuleScript")
        local fightModule,presenceModule=child(client,"FightTab","ModuleScript"),child(client,"TerritoryPresence","ModuleScript")
        local mw=child(replicated,"MW","Folder")
        local remotes,clockModule=child(mw,"Remotes","Folder"),child(mw,"ServerClock","ModuleScript")
        local action,status,update=child(remotes,"TerritoryAction","RemoteFunction"),child(remotes,"TerritoryStatus","RemoteFunction"),child(remotes,"TerritoryUpdate","RemoteEvent")
        if not module or not stateModule or not fightModule or not presenceModule or not clockModule or not action or not status or not update then return nil,"Recall instances unavailable" end
        local bytes=env.decompile(module)
        if type(bytes)~="string" or #bytes~=8904 or env.crypt.hash(bytes,"sha256"):lower()~=SOURCE then return nil,"Native Recall source changed" end
        local api,state,serverClock=deps.requireModule(module),deps.requireModule(stateModule),deps.requireModule(clockModule)
        local fight,presence=deps.requireModule(fightModule),deps.requireModule(presenceModule)
        if type(api)~="table" or type(state)~="table" or type(serverClock)~="table" or type(serverClock.now)~="function"
            or type(fight)~="table" or type(fight.confirm)~="function" or type(presence)~="table" or type(presence.pending)~="function" then return nil,"Recall native APIs unavailable" end
        local exports={}
        for _,key in ipairs({"start","init","busy","isPending","targets","confirm","onChanged"}) do
            if type(api[key])~="function" then return nil,"Recall exports changed" end
            exports[key]=api[key]
        end
        local actor=exports.start
        local values=get(actor)
        local clock,changed,finish,ctx=values[3],values[4],values[5],values[6]
        if not integer(values[2],0) or clock~=serverClock or type(changed)~="function" or type(finish)~="function" or type(ctx)~="table"
            or ctx.player~=player or ctx.State~=state or ctx.confirmDialog~=fight.confirm or type(ctx.Remotes)~="table" then return nil,"Recall context/layout changed" end
        local linkedAction,linkedStatus=ctx.Remotes.TerritoryAction,ctx.Remotes.TerritoryStatus
        if type(linkedAction)~="table" or linkedAction.Instance~=action or type(linkedAction.InvokeServer)~="function"
            or type(linkedStatus)~="table" or linkedStatus.Instance~=status or type(linkedStatus.InvokeServer)~="function" then return nil,"Native Recall wrapper changed" end
        local gui=ctx.gui
        local modals=child(child(gui,"Root","Frame"),"Modals","Frame")
        local confirm=child(modals,"ConfirmModal","Frame")
        if not modals or not confirm or type(modals.Visible)~="boolean" or type(confirm.Visible)~="boolean" then return nil,"Native Recall confirmation state unavailable" end
        local clockNow,confirmFn,presenceFn=serverClock.now,fight.confirm,presence.pending
        local invokeAction,invokeStatus=linkedAction.InvokeServer,linkedStatus.InvokeServer
        local retired=false
        local function layout()
            local v=get(actor);local init=get(exports.init);local done=get(finish);local notice=get(changed)
            local target=get(exports.targets);local confirmation=get(exports.confirm)
            if v[3]~=serverClock or v[4]~=changed or v[5]~=finish or v[6]~=ctx or not integer(v[2],0)
                or init[1]~=ctx or init[2]~=v[1] or init[3]~=finish or done[1]~=v[1] or done[2]~=ctx
                or done[3]~=target[2] or done[4]~=changed or target[1]~=ctx or type(target[2])~="table"
                or notice[2]~=v[1] or notice[1]~=get(exports.onChanged)[1]
                or get(exports.busy)[1]~=v[1] or get(exports.isPending)[1]~=v[1]
                or confirmation[1]~=v[1] or confirmation[2]~=ctx or confirmation[3]~=api then error("Recall shared scheduling cells changed") end
            return {pending=v[1],counter=v[2]}
        end
        layout()
        local port={}
        function port:Bound()
            if game.PlaceVersion~=build or game.JobId~=jobId then retired=true end
            if retired or players.LocalPlayer~=player or player.Name~=deps.account or player.UserId~=userId
                or child(player,"PlayerScripts","PlayerScripts")~=scripts or child(scripts,"MWClient","LocalScript")~=client
                or child(client,"CrewRecall","ModuleScript")~=module or child(client,"State","ModuleScript")~=stateModule
                or child(client,"FightTab","ModuleScript")~=fightModule or child(client,"TerritoryPresence","ModuleScript")~=presenceModule
                or child(replicated,"MW","Folder")~=mw or child(mw,"Remotes","Folder")~=remotes or child(mw,"ServerClock","ModuleScript")~=clockModule
                or child(remotes,"TerritoryAction","RemoteFunction")~=action or child(remotes,"TerritoryStatus","RemoteFunction")~=status
                or child(remotes,"TerritoryUpdate","RemoteEvent")~=update or env.getupvalues~=get or env.setupvalue~=set
                or serverClock.now~=clockNow or fight.confirm~=confirmFn or presence.pending~=presenceFn
                or ctx.player~=player or ctx.State~=state or ctx.gui~=gui or ctx.confirmDialog~=confirmFn
                or ctx.Remotes.TerritoryAction~=linkedAction or ctx.Remotes.TerritoryStatus~=linkedStatus
                or linkedAction.Instance~=action or linkedStatus.Instance~=status or linkedAction.InvokeServer~=invokeAction or linkedStatus.InvokeServer~=invokeStatus
                or child(child(gui,"Root","Frame"),"Modals","Frame")~=modals or child(modals,"ConfirmModal","Frame")~=confirm then retired=true;return false end
            for key,fn in pairs(exports) do if api[key]~=fn then retired=true;return false end end
            local intact=pcall(layout)
            if not intact then retired=true;return false end
            return true
        end
        function port:Current()
            return port:Bound() and modals.Visible==false and confirm.Visible==false and presenceFn()==false
        end
        function port:Target(p,baseline)
            if not port:Current() or type(p)~="table" or type(p.intent)~="table" then return false end
            local i,data=p.intent,ctx.State.data
            local row=type(data)=="table" and type(data.crew)=="table" and data.crew[i.memberIndex]
            local at=clockNow()
            if type(row)~="table" then return false end
            local key=row.healId==nil and "slot:"..i.memberIndex or type(row.healId)=="string" and "id:"..row.healId
            if row.healId==nil then
                -- An unkeyed target reserves the whole roster. Compare the
                -- source's current cards to the exact durable baseline before
                -- invoking, even if the copied Sync has not advanced yet.
                if type(baseline)~="table" or type(baseline.members)~="table" or not integer(baseline.size,2) or baseline.size>46
                    or type(data.crew)~="table" or #data.crew~=baseline.size then return false end
                local count=0
                local function absent(value,fallback) if value==nil then return fallback end;return value end
                for slot,card in pairs(data.crew) do
                    count=count+1
                    if not integer(slot,1) or slot>#data.crew or type(card)~="table" then return false end
                    if slot>1 then
                        local saved=baseline.members[tostring(slot)]
                        if type(saved)~="table" or card.healId~=nil and (type(card.healId)~="string" or #card.healId<1
                            or #card.healId>128 or card.healId:find("[%c]")) or card.training~=nil and type(card.training)~="table"
                            or card.rolling~=nil and type(card.rolling)~="boolean" or card.dutyPending~=nil and type(card.dutyPending)~="boolean"
                            or card.dutyRemapPending~=nil and type(card.dutyRemapPending)~="boolean" then return false end
                        local current={name=card.name,rarity=card.rarity,healId=absent(card.healId,false),train=absent(card.train,0),
                            duty=card.duty or false,token=card.dutyToken or false,at=card.dutyAt or false,
                            injured=absent(card.injuredUntil,0),recalled=absent(card.recalledUntil,0),training=card.training~=nil,
                            rolling=card.rolling==true,pending=card.dutyPending==true or card.dutyRemapPending==true,
                            weapon=card.weapon or false,armor=card.armor or false,vehicle=card.vehicle or false}
                        for field,value in pairs(saved) do if current[field]~=value then return false end end
                    end
                end
                if count~=#data.crew then return false end
            end
            return type(row)=="table" and data.userId==userId and i.userId==userId
                and type(data.family)=="table" and data.family.id==i.familyId
                and row.name==i.memberName and row.rarity==i.rarity and key==i.memberKey
                and row.duty==i.districtId and row.dutyToken==i.deploymentId and row.dutyAt==i.at
                and row.training==nil and row.rolling~=true and row.dutyPending~=true and row.dutyRemapPending~=true
                and type(at)=="number" and at==at and (row.injuredUntil==nil or type(row.injuredUntil)=="number" and row.injuredUntil<=at)
                and (row.recalledUntil==nil or type(row.recalledUntil)=="number" and row.recalledUntil<=at)
        end
        function port:Read() return layout() end
        function port:Clock() if not port:Current() then error("Recall clock source changed") end;return clockNow() end
        function port:Write(key,value)
            local index=key=="pending" and 1 or key=="counter" and 2
            assert(index,"Unsupported Recall scheduling field")
            set(actor,index,value)
        end
        local previous=rawget(deps.registry,REGISTRY)
        local epoch
        if type(previous)=="table" and previous.actor==actor and previous.context==ctx and previous.module==module
            and previous.jobId==jobId and previous.account==player.Name and previous.userId==player.UserId then epoch=previous end
        if not epoch then
            epoch={id=game:GetService("HttpService"):GenerateGUID(false),counterKnown=values[2],proven=values[2]==0,
                actor=actor,context=ctx,module=module,jobId=jobId,account=player.Name,userId=player.UserId}
            rawset(deps.registry,REGISTRY,epoch)
        end
        local fence=rawget(deps.registry,STORAGE)
        if fence==nil then fence={owners={},writing={}};rawset(deps.registry,STORAGE,fence) end
        if type(fence)~="table" or type(fence.owners)~="table" or type(fence.writing)~="table" then return nil,"Recall durable ownership registry changed" end
        epoch.durableFence=fence
        return NativeRecallLease.new(port,deps.clock,{account=player.Name,userId=player.UserId,place=tostring(game.PlaceId),jobId=jobId,sourceKey=SOURCE},epoch)
    end)
    if not ok then return nil,"Native Recall binding inspection failed" end
    return result,reason
end
return NativeRecallLease
