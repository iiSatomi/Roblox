-- Current runtime-load sends only. No persistent history, reset button or game IO.
local GlobalBossLoadUsage = {}
local function finite(v,low,high) return type(v)=="number" and v==v and v>=low and v<=high end
local function own(a,b)
    if type(a)~="table" then return false end
    for _,k in ipairs({"session","account","place","release"}) do if a[k]~=b[k] then return false end end
    return true
end
function GlobalBossLoadUsage.new(identity)
    local scope={}
    for _,k in ipairs({"session","account","place","release"}) do
        assert(type(identity[k])=="string" and #identity[k]>0,"Missing Global load owner")
        scope[k]=identity[k]
    end
    local counts={globalBossAttack=0,globalBossClaim=0}
    local tokens,lastAttack,closed={},nil,false
    local result={}
    function result:Proof(raw,now)
        if closed or not own(raw,scope) or not finite(now,0,9007199254740991) then return nil end
        return {session=scope.session,account=scope.account,place=scope.place,release=scope.release,
            revision=raw.revision,capturedAt=raw.capturedAt,now=now,
            attackAttempts=counts.globalBossAttack,claimAttempts=counts.globalBossClaim,lastAttackAt=lastAttack}
    end
    function result:Check(p,now)
        if type(p)~="table" or counts[p.feature]==nil then return true end
        local i=p.intent
        if closed or not own(p,scope) or type(i)~="table" or type(i.useLoadCap)~="boolean"
            or not finite(i.maxPerLoad,0,p.feature=="globalBossAttack" and 10000 or 10)
            or not finite(i.loadCountBefore,0,9007199254740991) or i.loadCountBefore%1~=0
            or not finite(now,0,9007199254740991) then return false,"Global load proof unavailable" end
        local token=tokens[p.feature]
        if token then
            return token.key==p.actionKey and token.count==i.loadCountBefore
                and token.id==(p.checkpointRequestId or p.requestId),"Global load charge changed"
        end
        if counts[p.feature]~=i.loadCountBefore or counts[p.feature]>=9007199254740991 then
            return false,"Global load count changed"
        end
        if i.useLoadCap and counts[p.feature]>=i.maxPerLoad then return false,"Global Boss per-load send cap reached" end
        if p.feature=="globalBossAttack" then
            if not finite(i.effectiveDelay,2,120) or i.loadLastAttackAt~=lastAttack
                or lastAttack and now<lastAttack+i.effectiveDelay then return false,"Global Boss per-load hit spacing" end
        end
        return true
    end
    function result:Charge(p,now)
        if counts[p.feature]==nil then return true end
        local ok,reason=self:Check(p,now)
        if not ok then return false,reason end
        if tokens[p.feature] then return true end
        if not finite(p.checkpointRequestId,1,9007199254740991) or p.checkpointRequestId%1~=0 then
            return false,"Global load checkpoint identity unavailable"
        end
        tokens[p.feature]={key=p.actionKey,id=p.checkpointRequestId,count=counts[p.feature],lastBefore=lastAttack}
        counts[p.feature]=counts[p.feature]+1
        if p.feature=="globalBossAttack" then lastAttack=now end
        return true
    end
    -- Caller must establish exact durable CP removal before a refund. A new load
    -- has no matching token, so recovering an old record never alters its counts.
    function result:Finish(p,refund,released)
        if type(p)~="table" or not own(p,scope) or counts[p.feature]==nil then return end
        local token=tokens[p.feature]
        if closed or not token or token.key~=p.actionKey
            or token.id~=(p.checkpointRequestId or p.requestId) then return end
        if refund then
            if released~=true or counts[p.feature]~=token.count+1 then return end
            counts[p.feature]=token.count
            if p.feature=="globalBossAttack" then lastAttack=token.lastBefore end
        end
        tokens[p.feature]=nil
    end
    function result:Status() return {attackAttempts=counts.globalBossAttack,claimAttempts=counts.globalBossClaim,lastAttackAt=lastAttack} end
    function result:Close() closed=true end
    return result
end
return GlobalBossLoadUsage
