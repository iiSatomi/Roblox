-- Reviewed external allowances are additional exposure, never retagged evidence.
local Carry = {DefaultSourceDirectory="IdleMafiaEmberCompletion655/checkpoints"}
local MAX = 9007199254740991
local fields = {"favorUsage", "bossUsage", "bossShopUsage", "marketRentUsage", "stationAttempts",
    "familyContributionUsage", "sabotageUsage", "globalClaimUsage", "globalAttackUsage",
    "familyClaimUsage", "familyAttackUsage", "eventShopUsage", "crewHireUsage", "playerFightUsage",
    "chestUsage", "shopUsage", "prestigeAttempts", "residencyAttempts"}
local family = {familyCash="cash",familyGold="gold_bar",familyStamina="stamina"}
local covered = {favors=true,bosses=true,bossShop=true,marketRent=true,station=true,
    familyCash=true,familyGold=true,familyStamina=true}
local function number(v) return type(v)=="number" and v==v and v>=0 and v<=MAX end
local function integer(v) return number(v) and v%1==0 end
local function text(v) return type(v)=="string" and #v>0 and #v<=512 and not v:find("[%c]") end
local function same(a,b)
    if type(a)~=type(b) then return false end
    if type(a)~="table" then return a==b end
    for k,v in pairs(a) do if not same(v,b[k]) then return false end end
    for k in pairs(b) do if a[k]==nil then return false end end
    return true
end
local function copy(v, seen, depth)
    if type(v)~="table" then return v end
    if getmetatable(v)~=nil or (depth or 0)>48 then error("Invalid carry table",0) end
    seen=seen or {};if seen[v] then error("Cyclic carry table",0) end;seen[v]=true
    local out={};for k,x in pairs(v) do out[k]=copy(x,seen,(depth or 0)+1) end
    seen[v]=nil;return out
end
local function tag(i) return #i.account..":"..i.account..#i.place..":"..i.place end
local function cpKey(i,r) return "idle-mafia-ember:checkpoint:v1:"..tag(i)..#r..":"..r end
local function belongs(key,kind,i,r)
    return key=="idle-mafia-ember:"..kind..":v1:"..tag(i)..#r..":"..r
end
local function targetValid(cp,i)
    return type(cp)=="table" and cp.fault==nil and type(cp.scope)=="table"
        and cp.scope.account==i.account and cp.scope.place==i.place and cp.scope.release==i.release
        and type(cp.Records)=="function" and type(cp.Recovery)=="function"
        and type(cp.FavorUsage)=="function" and type(cp.BossUsage)=="function"
end
local function baseline(cp)
    local out={version=1,records={},requestHighwater=cp.requestHighwater}
    for _,k in ipairs(fields) do if cp[k]~=nil then out[k]=copy(cp[k]) end end
    -- The persisted Family claim owner has a weeks envelope.
    out.familyClaimUsage={weeks=out.familyClaimUsage or {}}
    return out
end
local function checkpoint(deps,value,release)
    local m=deps.modules
    local read={strictRecovery=true,hash=deps.sha256,Read=function()return value end,Write=function()error("Carry review is read-only")end}
    local cp=m.Checkpoint.new(read,m.FamilyContributionUsage,m.ResourceReservations,m.PendingAction,
        m.EventShopUsage,m.MarketRentUsage,m.CrewHireUsage,m.PlayerFightUsage,m.Chests,m.ShopBuy)
    local records,why=cp:Load(deps.identity.account,deps.identity.place,release)
    if not records then error(why or "Invalid carry checkpoint",0) end
    return cp
end
local function nonzero(row)
    if type(row)=="number" then return row>0 end
    if type(row)~="table" then return false end
    for k,v in pairs(row) do if k~="version" and k~="day" and k~="week" and k~="session" and nonzero(v) then return true end end
    return false
end
local function project(cp,target)
    local floors,blocked={},{}
    for _,k in ipairs({"favorUsage","bossUsage","bossShopUsage","marketRentUsage","familyContributionUsage"}) do
        if cp[k] then floors[k]=copy(cp[k]) end
    end
    floors.stationAttempts=cp.stationAttempts or 0
    for feature in pairs(family) do
        local s=cp.familyContributionUsage and cp.familyContributionUsage.lanes[feature]
        local t=target.familyContributionUsage and target.familyContributionUsage.lanes[feature]
        if s and nonzero(s) and t and nonzero(t) then blocked[feature]="Imported Family allowance overlaps existing lineage" end
    end
    for feature,k in pairs({marketRent="marketRentUsage",station="stationAttempts",bossShop="bossShopUsage"}) do
        if nonzero(cp[k]) and nonzero(target[k]) then blocked[feature]="Imported allowance overlaps existing lineage" end
    end
    for feature,k in pairs({favors="favorUsage",bosses="bossUsage"}) do
        if cp[k] and target[k] and cp[k].day==target[k].day and nonzero(target[k]) then
            blocked[feature]="Imported daily allowance overlaps existing lineage"
        end
    end
    for feature,k in pairs({sabotage="sabotageUsage",globalBossClaim="globalClaimUsage",globalBossAttack="globalAttackUsage",
        familyBossClaims="familyClaimUsage",familyBossAttacks="familyAttackUsage",eventShop="eventShopUsage",
        crewHire="crewHireUsage",combat="playerFightUsage",warCombat="playerFightUsage",chests="chestUsage",
        shop="shopUsage",prestige="prestigeAttempts",residency="residencyAttempts"}) do
        if nonzero(cp[k]) then blocked[feature]="Imported allowance requires a typed feature adapter" end
    end
    return floors,blocked
end
function Carry.new(deps)
    local i=type(deps)=="table" and deps.identity
    local s=type(deps)=="table" and deps.sourceStore
    if type(i)~="table" or not text(i.account) or not text(i.place) or not text(i.release)
        or not text(deps.sourceRelease) or not text(deps.sourceDirectory) or type(s)~="table"
        or s.strictRecovery~=true or type(s.Current)~="function" or type(s.Read)~="function" or type(s.ListKeys)~="function"
        or type(deps.codec)~="table" or type(deps.codec.Decode)~="function" or type(deps.sha256)~="function"
        or type(deps.modules)~="table" or type(deps.modules.Checkpoint)~="table" then
        return nil,"Typed carry dependencies unavailable"
    end
    local identity={account=i.account,place=i.place,release=i.release,session=i.session}
    local storeCurrent,storeRead,storeList=s.Current,s.Read,s.ListKeys
    local engine={}
    local function hash(bytes)
        local value=deps.sha256(bytes)
        if type(value)~="string" or #value~=64 or not value:match("^[%x]+$") then error("Carry hash unavailable",0) end
        return value:lower()
    end
    local function sourceSnapshot()
        if s.Current~=storeCurrent or s.Read~=storeRead or s.ListKeys~=storeList then error("Carry source methods changed",0) end
        local ownerKey="idle-mafia-ember:release-owner:v1:"..tag(identity)
        local ownerSlot=s:Current(ownerKey)
        local owner=ownerSlot and ownerSlot.value
        if type(owner)~="table" or owner.version~=1 or owner.account~=identity.account
            or owner.place~=identity.place or owner.release~=deps.sourceRelease then error("Carry source owner changed",0) end
        local keys,why=s:ListKeys();if not keys then error(why or "Carry discovery failed",0) end
        if #keys>256 then error("Carry key limit",0) end
        table.sort(keys)
        local sources,anchors={},{}
        local sourceCPKey=cpKey(identity,deps.sourceRelease)
        local checkpointSlot=s:Current(sourceCPKey)
        local raw=checkpointSlot and checkpointSlot.value
        if type(raw)~="table" then error("External checkpoint missing",0) end
        local allowed={version=true,records=true,requestHighwater=true,chestUsageInitialized=true,shopUsageInitialized=true}
        for _,field in ipairs(fields) do allowed[field]=true end
        for field in pairs(raw) do if not allowed[field] then error("Unsupported external allowance field",0) end end
        local cp=checkpoint(deps,raw,deps.sourceRelease)
        if #cp:Records()>0 then error("Foreign active custody requires recovery",0) end
        local receiptBlocks={}
        local totalPayload,seen=0,{}
        for _,key in ipairs(keys) do
            if not text(key) or seen[key] then error("Invalid carry source inventory",0) end
            seen[key]=true
            local current=key==ownerKey and ownerSlot or key==sourceCPKey and checkpointSlot or s:Current(key)
            if not current or not integer(current.generation) or current.generation<1 or type(current.payload)~="string"
                or #current.payload>1048576 then error("Carry source unavailable",0) end
            totalPayload=totalPayload+#current.payload
            if totalPayload>16777216 then error("Carry archive byte limit",0) end
            local value=current.value
            if key~=ownerKey and key~=sourceCPKey then
                if belongs(key,"heist-sequences",identity,deps.sourceRelease) then
                    if type(value)~="table" or value.active~=nil then error("Foreign Heist custody requires recovery",0) end
                    for _,f in ipairs({"heists","heistCollect","favors","sabotage"}) do
                        receiptBlocks[f]="Preserved legacy Heist receipt requires a typed native continuity adapter"
                    end
                elseif belongs(key,"territory-recall",identity,deps.sourceRelease) then
                    if type(value)~="table" or value.transaction~=nil then error("Foreign Recall custody requires recovery",0) end
                    receiptBlocks.territoryRecall="Preserved legacy Recall receipt requires a typed native continuity adapter"
                elseif belongs(key,"payouts",identity,deps.sourceRelease) then
                    local m=deps.modules.MarketPayoutLedger
                    if type(m)~="table" or type(m.new)~="function" then
                        receiptBlocks.marketManage="Preserved payout history requires its typed ledger adapter"
                    else
                        local scope={account=identity.account,place=identity.place,release=deps.sourceRelease}
                        local ledger,reason=m.new(s,scope,{recoverSaved=function()return nil end})
                        if not ledger then error(reason or "Invalid preserved payout ledger",0) end
                        ledger:Close()
                    end
                elseif key:sub(1,#"idle-mafia-ember:adapter-unsent:v1:")=="idle-mafia-ember:adapter-unsent:v1:" then
                    local p=type(value)=="table" and deps.modules.PendingAction.Decode(value.recovery)
                    if not p or value.version~=1 or not integer(value.requestId) or value.requestId<1
                        or value.requestId>cp.requestHighwater or p.reply~=nil
                        or value.account~=identity.account or value.place~=identity.place or value.release~=deps.sourceRelease
                        or key~=cp:UnsentKey(value.requestId) then error("Invalid preserved unsent receipt",0) end
                else error("Unsupported external storage owner",0) end
            end
            anchors[#anchors+1]={key=key,generation=current.generation,sha256=hash(current.payload)}
            sources[#sources+1]={key=key,generation=current.generation,payload=current.payload}
        end
        if not seen[ownerKey] or not seen[sourceCPKey] then error("Carry inventory omitted its owner or checkpoint",0) end
        local finalKeys,finalReason=s:ListKeys()
        if not finalKeys then error(finalReason or "Carry discovery failed",0) end
        table.sort(finalKeys)
        if not same(keys,finalKeys) then error("Carry source inventory changed during capture",0) end
        for index,row in ipairs(anchors) do
            local current=s:Current(row.key)
            if not current or current.generation~=row.generation or current.payload~=sources[index].payload then
                error("Carry source changed during capture",0)
            end
        end
        if s.Current~=storeCurrent or s.Read~=storeRead or s.ListKeys~=storeList then error("Carry source methods changed",0) end
        return cp,anchors,sources,receiptBlocks
    end
    local function derive(target)
        if not targetValid(target,identity) then error("Canonical checkpoint unavailable",0) end
        local source,anchors,sources,receiptBlocks=sourceSnapshot()
        local floors,blocked=project(source,target)
        local blockedIntents={}
        for f,why in pairs(receiptBlocks) do
            if f=="territoryRecall" then blockedIntents[f]=why else blocked[f]=why end
        end
        local review={version=1,sourceDirectory=deps.sourceDirectory,sourceRelease=deps.sourceRelease,
            account=identity.account,place=identity.place,targetStorageRelease=identity.release,
            sources=anchors,targetBaseline=baseline(target),floors=floors,blockedFeatures=blocked,blockedIntents=blockedIntents,
            requestHighwaterFloor=source.requestHighwater,preserveOriginalEvidence=true}
        return review,sources
    end
    function engine:Preview(target)
        local ok,review,sources=pcall(derive,target)
        return ok and review or nil,ok and sources or tostring(review)
    end
    function engine:Verify(review,target)
        local ok,current=pcall(derive,target)
        return ok and same(current,review),not ok and tostring(current) or not same(current,review) and "Carry review changed" or nil
    end
    function engine:Adopt(review,sources,targetCheckpoint)
        local ok,result=pcall(function()
            if type(review)~="table" or type(review.targetBaseline)~="table" then error("Exact carry review required",0) end
            local originalTarget=checkpoint(deps,review.targetBaseline,identity.release)
            local exact,archived=derive(originalTarget)
            if not same(exact,review) or not same(archived,sources) then error("Carry archive or review changed",0) end
            local saved=copy(exact)
            -- Historical parsers provide no current native authority. Their
            -- detached summaries never alter the already-issued review/certificate.
            local legacy,intrinsicBlocks={},{}
            local inspector=deps.modules.LegacyCompletionReceipts
            local inspect=type(inspector)=="table" and inspector.Inspect
            for _,row in ipairs(sources) do
                local kind=belongs(row.key,"heist-sequences",identity,deps.sourceRelease) and "heist"
                    or belongs(row.key,"territory-recall",identity,deps.sourceRelease) and "recall" or nil
                if kind and type(inspect)=="function" then
                    local decoded=deps.codec:Decode(row.payload)
                    local valid,summary=pcall(inspect,kind,decoded,{identity={account=identity.account,
                        place=identity.place,release=deps.sourceRelease},modules=deps.modules})
                    if valid and type(summary)=="table" and summary.kind==kind and summary.historicalOnly==true
                        and summary.nativeContinuityVerified==false and summary.outcome=="confirmed" then
                        legacy[kind]=copy(summary)
                    end
                elseif row.key==cpKey(identity,deps.sourceRelease) then
                    local originalSource=checkpoint(deps,deps.codec:Decode(row.payload),deps.sourceRelease)
                    local _;_,intrinsicBlocks=project(originalSource,originalTarget)
                end
            end
            local bound,methods,nativeBound
            local nativeSources={}
            local guard={requestHighwaterFloor=saved.requestHighwaterFloor}
            function guard:BindNativeSources(sourcesByKind)
                if type(sourcesByKind)~="table" then return false,"Native carry sources unavailable" end
                for key in pairs(sourcesByKind) do
                    if key~="heist" and key~="recall" then return false,"Unknown native carry source" end
                end
                for _,kind in ipairs({"heist","recall"}) do
                    local source=sourcesByKind[kind]
                    if nativeBound and nativeSources[kind].source~=source then return false,"Native carry source cannot be rebound" end
                end
                if not nativeBound then
                    for _,kind in ipairs({"heist","recall"}) do
                        local source=sourcesByKind[kind]
                        nativeSources[kind]={source=source,inspect=type(source)=="table" and source.Inspect,
                            owns=type(source)=="table" and source.Owns}
                    end
                    nativeBound=true
                end
                return true,nil
            end
            local function nativePermission(kind,p)
                local summary,source=legacy[kind],nativeSources[kind]
                if not summary or not source or source.retired or type(source.source)~="table"
                    or type(source.inspect)~="function" or type(source.owns)~="function" then return false end
                local function methodsCurrent()
                    return source.source.Inspect==source.inspect and source.source.Owns==source.owns
                end
                if not methodsCurrent() then source.retired=true;return false end
                local ok,first=pcall(source.inspect,source.source)
                local ownsOk,owned=pcall(source.owns,source.source,p)
                local afterOk,last=pcall(source.inspect,source.source)
                if not ok or not afterOk or not ownsOk or type(owned)~="boolean"
                    or type(first)~="table" or type(last)~="table" or not same(first,last) or not methodsCurrent() then
                    source.retired=true;return false
                end
                local counter=kind=="heist" and first.controllerCounter or first.counter
                if first.account~=identity.account or first.place~=identity.place or not integer(counter)
                    or not text(first.nativeJob) or not text(first.nativeEpoch) or not text(first.nativeSourceKey)
                    or #first.nativeSourceKey~=64 or not first.nativeSourceKey:match("^[%x]+$") then
                    source.retired=true;return false
                end
                local signature={account=first.account,place=first.place,nativeJob=first.nativeJob,
                    nativeEpoch=first.nativeEpoch,nativeSourceKey=first.nativeSourceKey,
                    userId=kind=="recall" and first.userId or nil}
                if source.signature and not same(signature,source.signature)
                    or source.counter~=nil and counter<source.counter then source.retired=true;return false end
                source.signature,source.counter=signature,counter
                local i=p.intent
                for _,key in ipairs({"nativeJob","nativeEpoch","nativeSourceKey"}) do if i[key]~=first[key] then return false end end
                if type(summary.affectedIntents)~="table" or summary.affectedIntents[i.kind]~=true
                    or intrinsicBlocks[p.feature] and not (p.feature=="station" and i.kind=="territoryRecall") then return false end
                if kind=="heist" then
                    if not integer(summary.sequenceFloor) or not integer(i.sequence) or i.sequence<=summary.sequenceFloor
                        or counter<summary.sequenceFloor then return false end
                    return counter==(owned and i.sequence or i.sequence-1)
                end
                local original=summary.originalScope
                return type(original)=="table" and integer(original.userId) and original.userId>=1
                    and i.userId==original.userId and first.userId==original.userId
                    and integer(summary.requestFloor) and integer(i.requestId) and i.requestId>summary.requestFloor
                    and integer(i.nativeCounterBefore) and i.requestId>i.nativeCounterBefore
                    and counter==(owned and i.requestId or i.nativeCounterBefore)
            end
            local function retained(cp)
                local old=saved.targetBaseline
                if not integer(cp.requestHighwater) or cp.requestHighwater<old.requestHighwater then return false end
                for _,k in ipairs({"stationAttempts","prestigeAttempts","residencyAttempts"}) do
                    if not integer(cp[k]) or cp[k]<(old[k] or 0) then return false end
                end
                local current=cp.familyContributionUsage
                for f in pairs(family) do
                    local base=old.familyContributionUsage and old.familyContributionUsage.lanes[f]
                    local row=current and current.lanes[f]
                    if base and (not row or not integer(row.attempted) or not integer(row.spent)
                        or row.attempted<base.attempted or row.spent<base.spent) then return false end
                end
                if old.marketRentUsage then
                    local row=cp.marketRentUsage
                    if not row or row.attempted<old.marketRentUsage.attempted or row.spent<old.marketRentUsage.spent then return false end
                end
                for _,k in ipairs({"favorUsage","bossUsage"}) do
                    local base,row=old[k],cp[k]
                    if base then
                        if not row or row.day<base.day then return false end
                        if row.day==base.day then
                            for _,field in ipairs(k=="favorUsage" and {"attempts"} or {"hits","stamina","lastServerNow"}) do
                                if not number(row[field]) or row[field]<base[field] then return false end
                            end
                        end
                    end
                end
                local base,row=old.bossShopUsage,cp.bossShopUsage
                if base and (not row or row.session==base.session and row.attempts<base.attempts) then return false end
                return true
            end
            function guard:BindCheckpoint(cp)
                if bound and bound~=cp then return false,"Carry checkpoint owner cannot be replaced" end
                if not targetValid(cp,identity) or not retained(cp) then return false,"Carry checkpoint unavailable or reviewed usage regressed" end
                if not bound then
                    bound=cp;methods={Records=cp.Records,Recovery=cp.Recovery,FavorUsage=cp.FavorUsage,BossUsage=cp.BossUsage}
                end
                return true,nil
            end
            function guard:Summary() return copy(saved) end
            local function check(p,raw)
                if type(p)~="table" or type(raw)~="table" then return false,"Carry proposal unavailable" end
                if not covered[p.feature] and not saved.blockedFeatures[p.feature] then return true,nil end
                if not bound or not targetValid(bound,identity) or bound.Records~=methods.Records or bound.Recovery~=methods.Recovery
                    or bound.FavorUsage~=methods.FavorUsage or bound.BossUsage~=methods.BossUsage or not retained(bound) then
                    return false,"Imported allowance checkpoint unavailable"
                end
                for _,k in ipairs({"account","place","release"}) do
                    if p[k]~=identity[k] or raw[k]~=identity[k] then return false,"Imported allowance scope changed" end
                end
                if p.session~=raw.session or identity.session~=nil and raw.session~=identity.session then return false,"Imported allowance session changed" end
                local i=p.intent
                if type(i)~="table" then return false,"Carry intent unavailable" end
                local recall=p.feature=="station" and i.kind=="territoryRecall"
                local featureBlock=not recall and saved.blockedFeatures[p.feature]
                if featureBlock then
                    local heist=p.feature=="heists" or p.feature=="heistCollect" or p.feature=="favors" or p.feature=="sabotage"
                    if not heist or not nativePermission("heist",p) then return false,featureBlock end
                end
                if saved.blockedIntents[i.kind] then
                    if not recall or not nativePermission("recall",p) then return false,saved.blockedIntents[i.kind] end
                end
                local native=raw.native
                if type(native)~="table" or native.fullSync~=true or not number(native.serverNow) then
                    return false,"Current native clock required for preserved allowances"
                end
                if p.feature=="station" and i.kind=="territoryRecall" then return true,nil end
                local own=false
                for _,r in ipairs(bound:Records()) do
                    if r.feature==p.feature and r.actionKey==p.actionKey then
                        local data=bound:Recovery(r.actionKey)
                        if not data or data.reply~=nil or r.requestId~=p.checkpointRequestId
                            or data.proposal.session~=p.session or data.proposal.revision~=p.revision
                            or not same(data.proposal.intent,i) or not same(data.proposal.resources,p.resources) then
                            return false,"Imported allowance prepared identity changed"
                        end
                        own=true
                    end
                end
                if p.checkpointRequestId~=nil and not own then return false,"Prepared carry action no longer exists" end
                local function cap(current,before,amount,maximum,floor)
                    return integer(current) and integer(before) and integer(amount) and integer(maximum) and integer(floor)
                        and current==before+(own and amount or 0) and before+amount+floor<=maximum
                end
                local f=saved.floors
                if family[p.feature] then
                    local lane=bound.familyContributionUsage and bound.familyContributionUsage.lanes[p.feature]
                    local imported=f.familyContributionUsage and f.familyContributionUsage.lanes[p.feature] or {attempted=0,spent=0}
                    if not lane or i.kind~="familyContribution" or i.resource~=family[p.feature]
                        or not cap(lane.attempted,i.attemptsBefore,1,i.maxAttempts,imported.attempted)
                        or not cap(lane.spent,i.spentBefore,i.amount,i.runBudget,imported.spent) then
                        return false,"Preserved Family allowance is included in this cap"
                    end
                elseif p.feature=="bossShop" then
                    local localUsage=bound.bossShopUsage
                    local attempts=localUsage and localUsage.session==p.session and localUsage.attempts or 0
                    if i.kind~="bossShopBuy" or not cap(attempts,i.attemptsBefore,1,i.maxSends,f.bossShopUsage and f.bossShopUsage.attempts or 0) then
                        return false,"Preserved private-session Boss Shop attempts count toward this cap"
                    end
                elseif p.feature=="marketRent" then
                    local u=bound.marketRentUsage or {attempted=0,spent=0};local old=f.marketRentUsage or {attempted=0,spent=0}
                    if i.kind~="marketRent" or not cap(u.attempted,i.attemptedBefore,1,i.maxAttempts,old.attempted)
                        or not cap(u.spent,i.spentBefore,i.cost,i.maxGoldSpend,old.spent) then return false,"Preserved rental allowance is included in this cap" end
                elseif p.feature=="station" then
                    if i.kind~="territoryStation" or not cap(bound.stationAttempts,i.attemptedBefore,1,i.maxAttempts,f.stationAttempts) then
                        return false,"Preserved Station attempts count toward this cap"
                    end
                elseif p.feature=="favors" then
                    local old=f.favorUsage
                    if not integer(i.serverDay) or i.serverDay~=math.floor(native.serverNow/86400) or old and i.serverDay<old.day then return false,"Imported Favor day regressed" end
                    local current=bound:FavorUsage(i.serverDay,raw.capturedAt)
                    local floor=old and old.day==i.serverDay and old.attempts or 0
                    if i.kind~="favorHelp" or not current or not cap(current.attempts,i.usageAttemptsBefore,1,i.maxDailyAttempts,floor) then
                        return false,"Preserved Favor attempts count toward this day"
                    end
                elseif p.feature=="bosses" then
                    local old=f.bossUsage
                    local dateOk,date=pcall(os.date,"!%Y%j",math.floor(native.serverNow))
                    if not dateOk or not integer(i.dayStamp) or i.dayStamp~=tonumber(date) or old and i.dayStamp<old.day then return false,"Imported Boss day regressed" end
                    local current=bound:BossUsage(i.dayStamp,raw.capturedAt)
                    local floor=old and old.day==i.dayStamp and old or {hits=0,stamina=0,lastServerNow=0}
                    if i.kind~="bossStageAttack" or not current or not cap(current.hits,i.hitsBefore,1,100,floor.hits)
                        or not cap(current.stamina,i.staminaBefore,i.expectedStaminaCost,100,floor.stamina)
                        or not number(i.serverNow) or i.serverNow>native.serverNow or floor.hits>0 and i.serverNow<floor.lastServerNow+5 then
                        return false,"Preserved Boss sends and spacing count toward this day"
                    end
                end
                return true,nil
            end
            function guard:Check(p,raw)
                local safe,allowed,why=pcall(check,p,raw)
                return safe and allowed==true,not safe and "Imported allowance inspection failed" or why
            end
            if targetCheckpoint~=nil and (not targetValid(targetCheckpoint,identity) or not retained(targetCheckpoint)) then
                error("Reviewed canonical usage regressed",0)
            end
            return guard
        end)
        return ok and result or nil,not ok and tostring(result) or nil
    end
    return engine,nil
end
return Carry
