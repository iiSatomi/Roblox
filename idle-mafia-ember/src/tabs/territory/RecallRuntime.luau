-- One selected own deployment, shared request lane, no mutation replay.
local RecallRuntime, Methods = {}, {}
Methods.__index = Methods
local headers={"session","account","place","release","revision","capturedAt"}
local function integer(v,low,high) return type(v)=="number" and v==v and v%1==0 and v>=low and v<=(high or 9007199254740991) end
local function copy(v) local out={};for k,x in pairs(v) do out[k]=x end;return out end
local function recall(p) return type(p)=="table" and p.feature=="station" and type(p.intent)=="table" and p.intent.kind=="territoryRecall" end
local function bound(raw,identity)
    if type(raw)~="table" or type(raw.native)~="table" or raw.native.fullSync~=true then return false end
    for _,k in ipairs({"session","account","place","release"}) do if raw[k]~=identity[k] then return false end end
    return true
end
local function district(raw)
    local proof=type(raw)=="table" and raw.territoryDistrict
    local row=type(proof)=="table" and proof.district
    if type(proof)~="table" or type(proof.header)~="table" or type(row)~="table" or row.mine~=true
        or type(raw.native.family)~="table" or proof.familyId~=raw.native.family.id or row.holderId~=raw.native.family.id
        or type(row.id)~="string" or #row.id<1 or #row.id>120 or not integer(row.garrisonCount,0,1000000)
        or not integer(row.revision,0) or row.settling==true then return nil end
    for _,k in ipairs(headers) do if proof.header[k]~=raw[k] then return nil end end
    return row
end
function RecallRuntime.new(deps)
    if type(deps)~="table" or type(deps.lease)~="table" or type(deps.lease.Identity)~="function" or type(deps.lease.CheckTarget)~="function"
        or type(deps.transactions)~="table" or type(deps.clock)~="table" or type(deps.clock.Now)~="function" or type(deps.identity)~="table" then return nil,"Recall runtime dependencies unavailable" end
    local own=deps.lease:Identity()
    if not own or own.account~=deps.identity.account or own.place~=deps.identity.place then return nil,"Native Recall account mapping unavailable" end
    local scope={account=own.account,userId=own.userId,place=own.place,release=deps.identity.release}
    local owner,why=deps.transactions.new(deps.storage,scope,{release=scope.release,recallCooldownSeconds=deps.cooldownSeconds},deps.lease)
    if not owner then return nil,why end
    return setmetatable({lease=deps.lease,owner=owner,helper=deps.transactions,clock=deps.clock,identity=deps.identity,closed=false},Methods),nil
end
function Methods:BindCheckpoint(checkpoint,currentSnapshot)
    assert(not self.checkpoint or self.checkpoint==checkpoint,"Recall checkpoint already bound")
    self.checkpoint,self.currentSnapshot=checkpoint,currentSnapshot
end
function Methods:Ready() return not self.closed and self.checkpoint~=nil and not self.checkpoint.fault and not self.owner.fault end
function Methods:HasCheckpoint(key)
    if not self.checkpoint then return true end
    for _,r in ipairs(self.checkpoint:Records()) do if r.actionKey==key then return true end end
    return false
end
function Methods:Unresolved()
    if not self:Ready() or self.owner:Active() then return true end
    for _,r in ipairs(self.checkpoint:Records()) do if r.feature=="station" then return true end end
    return false
end
function Methods:Enrich(raw)
    local out=copy(raw);out.recallOwnerProof=nil
    self.latest=out
    if not self:Ready() or not bound(raw,self.identity) then return out end
    local active=self.owner:Active()
    if active and not self.preparing and not self.active and not self:HasCheckpoint(active.actionKey) then
        if active.stage=="prepared" then self.owner:DiscardPrepared()
        elseif active.stage=="observed" or active.stage=="rejectedObserved" then self.owner:ClearObserved() end
    end
    local observed=self.lease:Observe()
    if not observed then return out end
    local proof=copy(observed)
    for _,k in ipairs(headers) do proof[k]=raw[k] end
    proof.attempted=self.owner:Usage().attempted
    if not self:Unresolved() then proof.quote=self.lease:Quote(self.owner:LastRequestId()) end
    out.recallOwnerProof=proof
    return out
end
function Methods:Read(raw,context)
    if not bound(raw,self.identity) or type(context)~="table" then return nil,"Current own Recall snapshot required" end
    for _,k in ipairs(headers) do if raw[k]~=context[k] then return nil,"Recall snapshot changed" end end
    local proof=raw.recallOwnerProof
    if type(proof)~="table" then return nil,"Source-owned Recall controller required" end
    for _,k in ipairs(headers) do if proof[k]~=raw[k] then return nil,"Recall proof changed" end end
    local state=self.owner:ReadState(raw);local row=district(raw)
    local reservations=raw.stationReservationProof
    if not state or not row or type(reservations)~="table" or type(reservations.members)~="table" then return nil,"Current own deployment, district and member custody required" end
    for _,k in ipairs(headers) do if reservations[k]~=raw[k] then return nil,"Recall reservation scope changed" end end
    return {raw=raw,state=state,district=row,proof=proof,reserved=reservations.members},nil
end
function Methods:Propose(view,settings)
    if type(settings)~="table" or settings.enabled~=true or settings.mode~="Recall" then return nil,"Recall disabled" end
    if type(view)~="table" or type(view.proof.quote)~="table" or not integer(settings.memberSlot,2,46)
        or not integer(settings.minGarrison,0,1000000) or not integer(settings.maxAttempts,1,1000)
        or view.proof.attempted>=settings.maxAttempts or settings.districtId~=view.district.id then return nil,"Explicit Recall target, limits and current controller required" end
    local row=view.state.members[tostring(settings.memberSlot)]
    local key=row and (row.healId==false and "slot:"..settings.memberSlot or "id:"..row.healId)
    if not row or row.duty~=view.district.id or row.training or row.rolling or row.pending
        or row.injured>view.state.serverNow or row.recalled>view.state.serverNow or view.reserved[key]
        or view.district.garrisonCount-1<settings.minGarrison then return nil,"Member custody or district defender reserve blocks Recall" end
    local raw,q=view.raw,view.proof.quote
    local p={feature="station",revision=raw.revision,resources={},actionKey="recall:"..q.requestId..":"..key,
        intent={kind="territoryRecall",districtId=row.duty,userId=view.proof.userId,memberIndex=settings.memberSlot,
            deploymentId=row.token~=false and row.token or nil,at=row.at~=false and row.at or nil,memberName=row.name,rarity=row.rarity,
            memberKey=key,attemptedBefore=view.proof.attempted,maxAttempts=settings.maxAttempts,
            familyId=view.state.familyId,districtRevision=view.district.revision,minGarrison=settings.minGarrison}}
    for _,k in ipairs({"session","account","place","release"}) do p[k]=raw[k] end
    for k,v in pairs(q) do p.intent[k]=v end
    return p,nil
end
function Methods:Policy(p,raw)
    if not recall(p) or not bound(raw,self.identity) or p.revision~=raw.revision then return false end
    local i,row=p.intent,district(raw)
    return row~=nil and row.id==i.districtId and row.revision==i.districtRevision and raw.native.family.id==i.familyId
        and integer(i.minGarrison,0,1000000) and row.garrisonCount-1>=i.minGarrison
end
function Methods:Capture(p,raw)
    if not self:Policy(p,raw) then return nil,"Recall defender/identity proof changed" end
    local baseline=self.owner:Capture(p,raw)
    return baseline,baseline==nil and "Exact source-owned Recall baseline required" or nil
end
function Methods:Describe(p)
    if not recall(p) then return nil,"Not an owned Recall" end
    local call,why=self.owner:Describe(p)
    if call then
        self.calls=self.calls or setmetatable({},{__mode="k"})
        local prior=self.calls[p]
        if prior and not self.helper.same(prior.args,call.args) then return nil,"Recall call changed" end
        if not prior then self.calls[p]=call end
        return self.calls[p],nil
    end
    return nil,why
end
function Methods:CanDispatch(p)
    if not self:Ready() or not self.lease:Owns(p) or not self.active or self.active.proposal~=p then return false end
    local raw=self.currentSnapshot and self.currentSnapshot() or self.latest
    local baseline=self.owner:Capture(p,raw)
    if not baseline or not self:Policy(p,raw) or not self.owner:Matches(p,baseline) then return false end
    return self.lease:CheckTarget(p,baseline) and self.lease:Owns(p)
end
function Methods:Release(p)
    local ok,why=self.lease:Release(p)
    if ok and self.active and self.active.proposal==p then self.active=nil end
    return ok,why
end
function Methods:Terminal(p,reply) return self.owner:ReplyKind(p,reply)~=nil end
function Methods:Returned(p,reply,deliver)
    local active=self.active
    if self.closed or not active or active.proposal~=p or not self.lease:Owns(p) then return false end
    if type(deliver)=="function" and active.deliver==nil then active.deliver=deliver end
    if active.terminal or not self:Terminal(p,reply) or not active.deliver then return true end
    active.terminal=reply;active.deliver(reply)
    return true
end
function Methods:WrapTransport(base)
    local owner=self
    local wrapper={}
    for _,name in ipairs({"Validate","InFlight","ReadLease"}) do wrapper[name]=function(_,...) return base[name](base,...) end end
    function wrapper:Send(p,onReturn,canDispatch,token,onUnsent,authorize)
        return base:Send(p,recall(p) and function(reply) owner:Returned(p,reply,onReturn) end or onReturn,canDispatch,token,onUnsent,authorize)
    end
    for _,name in ipairs({"ReleaseResolved","ReleaseExpired"}) do
        wrapper[name]=function(_,p,...)
            if recall(p) then local ok=owner:Release(p);if not ok then return false end end
            return base[name](base,p,...)
        end
    end
    return wrapper
end
function Methods:StatusCall()
    if not self:Ready() or not self.lease:Observe() then return nil end
    local record=self.owner:Active()
    if not record or (record.stage~="sent" and record.stage~="settled" and record.stage~="rejected") then return nil end
    local data=self.checkpoint:Recovery(record.actionKey)
    local p=data and data.proposal
    if not p or data.reply~=nil or not self.owner:Origin(p) or not self.owner:Matches(p,data.baseline) then return nil end
    if self.active and (not self.active.deliver or self.active.terminal) then return nil end
    return self.owner:StatusCall()
end
function Methods:ReadSources()
    local owner=self
    return {{id="territoryRecallStatus",interval=3,statusOnly=true,confirmFeatures={station=true},
        enabled=function() return owner:StatusCall()~=nil end,
        prepare=function()
            local request=owner:StatusCall();if not request then return nil,"No owned Recall status pending" end
            local data=owner.checkpoint:Recovery(request.actionKey);local p=data and data.proposal
            if not p then return nil end
            local held=owner.active and owner.active.proposal or nil
            if not held then
                local ok=owner.lease:AcquireStatus(p,owner.clock:Now()+5)
                if not ok then return nil,"Native Recall status contention" end
                owner.statusHold=p
            end
            owner.statusRequest=request
            return request
        end,
        accept=function(_,request,reply) return {request=request,reply=reply} end,
        commit=function(staged)
            if owner.closed or owner.statusRequest~=staged.request then return false end
            local request,reply=staged.request,staged.reply
            local ok=true
            local data=owner.checkpoint:Recovery(request.actionKey)
            if data and owner:Terminal(data.proposal,reply) then
                if owner.active then ok=owner:Returned(owner.active.proposal,reply)
                else
                    local record=owner.owner:Active()
                    if not record or not owner.owner:AcceptReply(record.requestId,reply) then ok=false
                    else ok=owner.checkpoint:RecordReply(request.actionKey,reply) end
                end
            end
            if owner.statusHold then local released=owner.lease:Release(owner.statusHold);owner.statusHold=nil;ok=released and ok end
            owner.statusRequest=nil
            return ok
        end}}
end
function Methods:RecoverSaved(data,after)
    if not self:Ready() or type(data)~="table" or not recall(data.proposal) or not self.owner:Matches(data.proposal,data.baseline) then return nil end
    for _,record in ipairs(self.checkpoint:Records()) do
        if record.actionKey==data.proposal.actionKey and self.checkpoint:KnownUnsent(record) then
            if self.owner:CancelRecoveredUnsent(data.proposal,data.baseline,true) then return "known_unsent" end
            return nil
        end
    end
    if not self:Terminal(data.proposal,data.reply) then return nil end
    local active=self.owner:Active()
    if active and (active.stage=="observed" or active.stage=="rejectedObserved") and self.owner:AcceptReply(active.requestId,data.reply) then
        return active.stage=="observed" and "confirmed" or "rejected"
    end
    local status=self.owner:Evaluate(data.proposal,data.before,after,data.reply,data.baseline)
    if status~="confirmed" and status~="rejected" then return nil end
    if not self.owner:AcceptReply(data.proposal.intent.requestId,data.reply) then return nil end
    local reconciled=self.owner:Reconcile(after)
    return (reconciled=="observed" and status=="confirmed" or reconciled=="rejected" and status=="rejected") and status or nil
end
function Methods:Wrap(spec,ordinaryCall)
    local owner,result=self,copy(spec)
    result.reader={read=function(raw,context)
        local ordinary,ordinaryWhy=spec.reader.read(raw,context)
        local own,why=owner:Read(raw,context)
        if not own and not ordinary then
            return nil,"Station: "..(ordinaryWhy or "unavailable").."; Recall: "..(why or "unavailable")
        end
        return {ordinary=ordinary,recall=own,ordinaryReason=ordinaryWhy,recallReason=why},nil
    end}
    result.planner={propose=function(view,settings,reservations)
        if type(settings)=="table" and settings.mode=="Recall" then
            if not view.recall then return nil,view.recallReason or "Recall snapshot unavailable" end
            return owner:Propose(view.recall,settings)
        end
        if not view.ordinary then return nil,view.ordinaryReason or "Station snapshot unavailable" end
        return spec.planner.propose(view.ordinary,settings,reservations)
    end}
    result.evidence={capture=function(p,raw) if recall(p) then return owner:Capture(p,raw) end;return spec.evidence.capture(p,raw) end,
        evaluate=function(p,before,after,reply,baseline) if recall(p) then return owner.owner:Evaluate(p,before,after,reply,baseline) end;return spec.evidence.evaluate(p,before,after,reply,baseline) end}
    result.canDispatch=function(p) if recall(p) then return owner:CanDispatch(p) end;return not spec.canDispatch or spec.canDispatch(p)==true end
    result.recoverSaved=function(data,after) if data and recall(data.proposal) then return owner:RecoverSaved(data,after) end;return spec.recoverSaved and spec.recoverSaved(data,after) end
    result.lifecycle={
        prepare=function(p,raw,baseline,at)
            if not recall(p) then return true end
            if owner:Unresolved() then return false,"Unresolved Recall/member custody","controller_wait" end
            local acquired,why=owner.lease:Acquire(p,at+45)
            if not acquired then return false,why,"controller_wait" end
            owner.preparing=true
            local saved,reason=owner.owner:Prepare(p,raw,at)
            owner.preparing=nil
            if not saved then owner.lease:Release(p);return false,reason,not owner.owner.fault and "controller_wait" or nil end
            owner.active={proposal=p,before=raw,baseline=baseline}
            return true
        end,
        authorize=function(p,raw,at)
            if not recall(p) then return ordinaryCall(p) end
            if not owner:CanDispatch(p) then return nil,"Recall dispatch guard changed" end
            local saved,why=owner.owner:MarkSending(raw,at)
            if not saved then return nil,why end
            local call,reason=owner.owner:SubmitCall(raw,at)
            local expected=owner.calls and owner.calls[p]
            if not call or not expected or call.remote~=expected.remote or call.method~=expected.method
                or call.arity~=expected.arity or not owner.helper.same(call.args,expected.args) then return nil,reason or "Recall authorized call changed" end
            return expected
        end,
        returned=function(p,reply)
            if not recall(p) then return true end
            if owner.closed or not owner.active or owner.active.proposal~=p or owner.active.terminal~=reply then return false,"Recall terminal owner changed" end
            return owner.owner:AcceptReply(p.intent.requestId,reply)
        end,
        resolve=function(p,outcome,after)
            if not recall(p) then return true end
            local state=owner.owner:Reconcile(after)
            if outcome=="confirmed" and state~="observed" or outcome=="rejected" and state~="rejected" then return false,"Recall effect remains unconfirmed" end
            return owner:Release(p)
        end,
        unsent=function(p)
            if not recall(p) then return true end
            if owner.closed then return false,"Recall owner closed" end
            local ok,why=owner.owner:CancelUnsent(p.actionKey)
            local released=owner:Release(p)
            return ok and released,why
        end,
        abandonedUnsent=function(p)
            local active=owner.active
            return recall(p) and active and active.proposal==p and owner.checkpoint and owner.checkpoint:RecordUnsent(p,active.before,active.baseline) or false
        end}
    return result
end
function Methods:Reservations()
    if self.owner.fault then return nil,"Recall durable member custody unavailable" end
    local record=self.owner:Active()
    if not record then return nil end
    return {account=self.identity.account,place=self.identity.place,release=self.identity.release,feature="station",actionKey=record.actionKey,
        claims={members={["slot:"..record.target.memberIndex]=true,[record.memberKey]=true},items={},funds={},allCrew=record.memberKey=="slot:"..record.target.memberIndex,allItems=false}}
end
function Methods:Close()
    if self.closed then return true end
    self.closed=true
    local ok=self.lease:Close()
    self.owner:Close()
    return ok
end
return RecallRuntime
