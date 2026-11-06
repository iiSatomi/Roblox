-- Source-owned, read-only Config.hireCost / DecreeRules.pctFor evidence.
local NativeHireQuoteSource = {}
local Methods = {}
Methods.__index = Methods
local headers = {"session", "account", "place", "release", "revision", "capturedAt"}
local MAX = 9007199254740991
local function finite(v, minimum) return type(v)=="number" and v==v and v>=minimum and v<=MAX end
local function integer(v, minimum) return finite(v,minimum) and v%1==0 end
local function text(v) return type(v)=="string" and #v>0 and #v<=200 and not v:find("%c") end
local function child(parent,name,class)
    local value=parent and parent:FindFirstChild(name)
    return value and value.Parent==parent and value:IsA(class) and value or nil
end
local function equal(a,b)
    if type(a)~=type(b) then return false end
    if type(a)~="table" then return a==b end
    for k,v in pairs(a) do if not equal(v,b[k]) then return false end end
    for k in pairs(b) do if a[k]==nil then return false end end
    return true
end
local function family(native)
    if type(native)~="table" then return nil,false end
    if native.family==nil then return nil,true end
    if type(native.family)~="table" then return nil,false end
    local id=native.family.id
    return id,id==nil or text(id)
end

function NativeHireQuoteSource.bind(deps)
    if type(deps)~="table" or deps.placeVersion~=654 or deps.game.PlaceVersion~=654
        or type(deps.requireModule)~="function" then return nil,"Unreviewed native hire source" end
    local game,requireModule=deps.game,deps.requireModule
    local players,replicated=game:GetService("Players"),game:GetService("ReplicatedStorage")
    local player=players.LocalPlayer
    local scripts=child(player,"PlayerScripts","PlayerScripts")
    local client=child(scripts,"MWClient","LocalScript")
    local stateModule=child(client,"State","ModuleScript")
    local mw=child(replicated,"MW","Folder")
    local configModule=child(mw,"Config","ModuleScript")
    local decreeModule=child(mw,"DecreeRules","ModuleScript")
    local clockModule=child(mw,"ServerClock","ModuleScript")
    if not stateModule or not configModule or not decreeModule or not clockModule
        or not text(player.Name) or not integer(player.UserId,1)
        or tostring(game.PlaceId)=="nil" then return nil,"Native hire modules unavailable" end
    local state,config,decree,clock=requireModule(stateModule),requireModule(configModule),requireModule(decreeModule),requireModule(clockModule)
    if state~=deps.nativeState or config~=deps.config or type(state)~="table" or type(state.latest)~="function"
        or type(config)~="table" or type(config.hireCost)~="function"
        or type(config.CREW)~="table" or type(config.CREW.hireTiers)~="table"
        or type(config.DECREES)~="table" or type(config.DECREES.hire)~="table"
        or type(decree)~="table" or type(decree.BY_KEY)~="table" or type(decree.BY_KEY.hire)~="table"
        or type(clock)~="table" or type(clock.now)~="function" then return nil,"Native hire helpers unavailable" end
    local crew,tiers,ranges,range=config.CREW,config.CREW.hireTiers,config.DECREES,config.DECREES.hire
    if range.min~=-25 or range.max~=25 or range.default~=0 or decree.BY_KEY.hire.attr~="DecreeHirePct" then
        return nil,"Unreviewed native hire range"
    end
    local functions={}
    for _,key in ipairs({"pctFor","pct","isPenalty","inRulingFamily","default"}) do
        if type(decree[key])~="function" then return nil,"Native decree helper unavailable" end
        functions[key]=decree[key]
    end
    local latest,hireCost,now,getAttribute=state.latest,config.hireCost,clock.now,mw.GetAttribute
    if type(getAttribute)~="function" then return nil,"Native decree attributes unavailable" end
    local byKey,hireKind=decree.BY_KEY,decree.BY_KEY.hire
    local rows,ids={},{}
    if #tiers<1 or #tiers>8 then return nil,"Native hire tiers unavailable" end
    for i,row in ipairs(tiers) do
        if type(row)~="table" or not text(row.id) or ids[row.id] or not integer(row.cost,1) then return nil,"Invalid native hire tiers" end
        rows[i]={row=row,id=row.id,cost=row.cost};ids[row.id]=true
    end
    local place,account,userId=tostring(game.PlaceId),player.Name,player.UserId
    local retired=false
    local function current()
        if retired then return false end
        local ok,valid=pcall(function()
            if game.PlaceVersion~=654 or tostring(game.PlaceId)~=place or players.LocalPlayer~=player
                or player.Name~=account or player.UserId~=userId or child(player,"PlayerScripts","PlayerScripts")~=scripts
                or child(scripts,"MWClient","LocalScript")~=client or child(client,"State","ModuleScript")~=stateModule
                or child(replicated,"MW","Folder")~=mw or child(mw,"Config","ModuleScript")~=configModule
                or child(mw,"DecreeRules","ModuleScript")~=decreeModule or child(mw,"ServerClock","ModuleScript")~=clockModule
                or state.latest~=latest or config.hireCost~=hireCost or clock.now~=now or mw.GetAttribute~=getAttribute
                or config.CREW~=crew or crew.hireTiers~=tiers or #tiers~=#rows or config.DECREES~=ranges or ranges.hire~=range
                or range.min~=-25 or range.max~=25 or range.default~=0 or decree.BY_KEY~=byKey or byKey.hire~=hireKind
                or hireKind.attr~="DecreeHirePct" then return false end
            for key,value in pairs(functions) do if decree[key]~=value then return false end end
            for i,saved in ipairs(rows) do if tiers[i]~=saved.row or saved.row.id~=saved.id or saved.row.cost~=saved.cost then return false end end
            return true
        end)
        if not ok or valid~=true then retired=true end
        return not retired
    end
    local function attributes()
        local result={}
        for _,key in ipairs({"DecreeHirePct","DecreeHireAt","DecreeHirePrev","DecreeHireFam","DecreeRulerId"}) do
            local value=getAttribute(mw,key)
            if value~=nil and not (type(value)=="string" and #value<=200 or finite(value,-MAX)) then return nil end
            result[key]=value
        end
        return result
    end
    local function matches(native)
        local data=latest()
        local original,valid=family(native)
        local live,liveValid=family(data)
        return type(data)=="table" and valid and liveValid and live==original
            and data.cityId==native.cityId and (data.userId==nil or data.userId==userId)
            and (native.userId==nil or native.userId==userId)
            and finite(native.cash,0) and finite(data.cash,native.cash)
            and type(native.crew)=="table" and #native.crew<=46
            and type(data.crew)=="table" and #data.crew<=46 and equal(native.crew,data.crew)
    end
    if not current() then return nil,"Native hire source changed during binding" end
    return {account=account,place=place,Current=current,Read=function(native)
        if not current() or type(native)~="table" or not text(native.cityId)
            or not finite(native.serverNow,0) or not matches(native) then return nil end
        local first=attributes()
        local clockNow=now()
        if not first or not finite(clockNow,0) or clockNow<native.serverNow or clockNow-native.serverNow>2 then return nil end
        local familyId=family(native)
        local pct=functions.pctFor(mw,"hire",familyId)
        if not integer(pct,-25) or pct>25 then return nil end
        local quotes={}
        for _,saved in ipairs(rows) do
            local cost=hireCost(saved.row,pct)
            if not integer(cost,1) or cost~=math.max(1,math.floor(saved.cost*(100+pct)/100+0.5)) then return nil end
            quotes[saved.id]=cost
        end
        local afterNow=now()
        if not current() or not matches(native) or not equal(first,attributes()) or not finite(afterNow,clockNow)
            or afterNow-native.serverNow>2 then return nil end
        local ruler=first.DecreeRulerId
        if ruler~=nil and not text(ruler) then return nil end
        return {city=native.cityId,familyId=familyId or "",rulerId=ruler or "",hirePct=pct,
            attributes=first,quotes=quotes}
    end},nil
end

local function frameCopy(frame)
    local result = {city=frame.city,familyId=frame.familyId,rulerId=frame.rulerId,hirePct=frame.hirePct,quotes={},attributes={}}
    for key,value in pairs(frame.quotes) do result.quotes[key]=value end
    for key,value in pairs(frame.attributes) do result.attributes[key]=value end
    return result
end
function NativeHireQuoteSource.new(current,identity,sourceKey,readNative)
    if type(current)~="table" or type(current.Current)~="function" or type(current.Read)~="function"
        or type(identity)~="table" or current.account~=identity.account or current.place~=identity.place
        or type(readNative)~="function" or type(sourceKey)~="string" or #sourceKey~=64 or not sourceKey:match("^%x+$") then
        return nil,"Current owned hire quote source required"
    end
    local bound={}
    for _,key in ipairs({"session","account","place","release"}) do
        if not text(identity[key]) then return nil,"Hire quote identity unavailable" end
        bound[key]=identity[key]
    end
    return setmetatable({identity=bound,account=bound.account,release=bound.release,sourceKey=sourceKey:lower(),
        current=current,read=current.Read,isCurrent=current.Current,call=readNative,proofs={},order={}},Methods),nil
end
function Methods:Frame(raw)
    if self.closed or type(raw)~="table" or type(raw.native)~="table" or raw.native.fullSync~=true
        or not integer(raw.revision,0) or not finite(raw.capturedAt,0) then return nil end
    for key,value in pairs(self.identity) do if raw[key]~=value then return nil end end
    if self.current.Read~=self.read or self.current.Current~=self.isCurrent then return nil end
    local ok,value=self.call(function()
        if self.isCurrent()~=true then return nil end
        local frame=self.read(raw.native)
        if self.isCurrent()~=true then return nil end
        return frame
    end)
    if not ok or self.current.Read~=self.read or self.current.Current~=self.isCurrent
        or type(value)~="table" or not text(value.city) or value.city~=raw.native.cityId
        or type(value.familyId)~="string" or type(value.rulerId)~="string" or not integer(value.hirePct,-25) or value.hirePct>25
        or type(value.quotes)~="table" or type(value.attributes)~="table" then return nil end
    local familyId,valid=family(raw.native)
    if not valid or value.familyId~=(familyId or "") then return nil end
    local count=0
    for tier,cost in pairs(value.quotes) do
        count=count+1
        if count>8 or not text(tier) or not integer(cost,1) then return nil end
    end
    if count==0 then return nil end
    count=0
    for key,attribute in pairs(value.attributes) do
        count=count+1
        if count>8 or not text(key) or not (type(attribute)=="string" and #attribute<=200 or finite(attribute,-MAX)) then return nil end
    end
    return frameCopy(value)
end
function Methods:Enrich(raw)
    local frame=self:Frame(raw)
    if not frame then return nil,"Current native hire quote unavailable" end
    local saved=self.proofs[raw.revision]
    if saved and (saved.capturedAt~=raw.capturedAt or not equal(saved.frame,frame)) then return nil,"Hire quote changed within this Sync" end
    if not saved then
        self.proofs[raw.revision]={capturedAt=raw.capturedAt,frame=frameCopy(frame)}
        self.order[#self.order+1]=raw.revision
        if #self.order>8 then self.proofs[table.remove(self.order,1)]=nil end
    end
    local result,proof={},{}
    for key,value in pairs(raw) do result[key]=value end
    for _,key in ipairs(headers) do proof[key]=raw[key] end
    proof.sourceKey,proof.city=self.sourceKey,frame.city
    proof.familyId,proof.rulerId,proof.hirePct=frame.familyId,frame.rulerId,frame.hirePct
    proof.quotes,proof.attributes=frame.quotes,frame.attributes
    result.economyProof=proof
    return result,nil
end
function Methods:CanDispatch(proposal,raw)
    local intent=type(proposal)=="table" and proposal.intent
    local saved=type(proposal)=="table" and self.proofs[proposal.revision]
    if not saved or type(intent)~="table" or type(raw)~="table" or raw.revision~=proposal.revision
        or raw.capturedAt~=saved.capturedAt then return false end
    for key,value in pairs(self.identity) do if proposal[key]~=value then return false end end
    local frame=self:Frame(raw)
    if not frame or not equal(frame,saved.frame) or intent.decreeRevision~=proposal.revision
        or intent.cost~=frame.quotes[intent.tier] or intent.hirePct~=frame.hirePct
        or intent.cityId~=nil and intent.cityId~=frame.city
        or intent.familyId~=nil and intent.familyId~=frame.familyId
        or intent.rulerId~=nil and intent.rulerId~=frame.rulerId then return false end
    return proposal.feature=="crewHire" and intent.kind=="crewHire"
        or proposal.feature=="crewRoll" and (intent.kind=="crewReplacementHire" or intent.kind=="crewReplacementDismiss")
end
function Methods:Close() self.closed=true;self.proofs={};self.order={} end
return NativeHireQuoteSource
