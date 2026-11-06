-- Read-only interpretation of settled Completion655 v1 producer records.
-- These are historical contracts, never current native ownership or a new baseline.
local Legacy = {}
local MAX = 9007199254740991
local function number(v,low) return type(v)=="number" and v==v and v>=(low or 0) and v<=MAX end
local function integer(v,low,high) return number(v,low) and v%1==0 and v<=(high or MAX) end
local function text(v,n) return type(v)=="string" and #v>0 and #v<=(n or 200) and not v:find("[%c]") end
local function id(v,n) return text(v,n) or integer(v,1) end
local function only(v,fields)
    if type(v)~="table" or getmetatable(v)~=nil then return false end
    for k in pairs(v) do if not fields[k] then return false end end
    return true
end
local function same(a,b)
    if type(a)~=type(b) then return false end
    if type(a)~="table" then return a==b end
    for k,v in pairs(a) do if not same(v,b[k]) then return false end end
    for k in pairs(b) do if a[k]==nil then return false end end
    return true
end
local function scope(v,i)
    return type(v)=="table" and v.account==i.account and v.place==i.place and v.release==i.release
end
local function header(v,i)
    return scope(v,i) and text(v.session) and integer(v.revision,0) and number(v.capturedAt)
end
local function summary(kind,i)
    return {kind=kind,legacyVersion=1,outcome="confirmed",receiptCountFloor=1,
        historicalOnly=true,nativeContinuityVerified=false,
        originalScope={account=i.account,place=i.place,release=i.release},affectedIntents={}}
end
local legacyFavorFields={"session","account","place","release","revision","rowId","heistId","ownerId",
    "helpsBefore","favorsBefore","favorCost","serverDay","usageAttemptsBefore"}
local function personal(row)
    if row.helpsUsed~=nil then return integer(row.helpsUsed,0) and row.helpsUsed or nil end
    if row.helped==true then return 1 end
    if row.helped==false or row.helped==nil then return 0 end
    return nil
end
local function favorAfter(raw,i,rowId)
    if not header(raw,i) or type(raw.native)~="table" or raw.native.fullSync~=true
        or not number(raw.native.serverNow) then return nil end
    local proof,usage=raw.heistBoardProof,raw.favorUsageProof
    local board=type(proof)=="table" and proof.board
    if type(board)~="table" or proof.query~=nil or proof.account~=raw.account
        or proof.capturedAt~=raw.capturedAt or board.ok~=true or type(board.rows)~="table"
        or not number(board.serverNow) or math.abs(board.serverNow-raw.native.serverNow)>2
        or not integer(board.favorsLeft,0) or type(usage)~="table" or usage.account~=raw.account
        or usage.capturedAt~=raw.capturedAt or not integer(usage.day,0) or not integer(usage.attempts,0)
        or usage.day~=math.floor(board.serverNow/86400) then return nil end
    local selected,seen,count=nil,{},0
    for index,row in ipairs(board.rows) do
        if type(row)~="table" or not id(row.id) or seen[row.id] then return nil end
        seen[row.id],count=true,index
        if row.id==rowId then selected=row end
    end
    for key in pairs(board.rows) do if not integer(key,1,count) then return nil end end
    return selected and board or nil,selected,usage
end
local function heist(value,deps)
    local i,m=deps.identity,deps.modules
    if not only(value,{version=true,generation=true,account=true,place=true,release=true,receipt=true,active=true})
        or value.version~=1 or not integer(value.generation,1) or not scope(value,i) or value.active~=nil then
        return nil,"Inactive legacy Heist scope required"
    end
    local receipt=value.receipt
    if not only(receipt,{record=true,outcome=true,observation=true}) or receipt.outcome~="confirmed" then
        return nil,"Confirmed legacy Heist receipt required"
    end
    local record=receipt.record
    if not only(record,{sequence=true,actionName=true,arg1=true,sent=true,sentAt=true,data=true})
        or not integer(record.sequence,1) or record.sent~=true or not number(record.sentAt)
        or record.actionName~="help" then return nil,"Legacy Heist feature adapter unavailable" end
    if type(m.PendingAction)~="table" or type(m.PendingAction.Decode)~="function"
        or type(m.FavorHelpEvidence)~="table" or type(m.FavorHelpEvidence.capture)~="function" then
        return nil,"Legacy Heist evidence dependencies unavailable"
    end
    local data=m.PendingAction.Decode(record.data)
    local observed=m.PendingAction.Decode(receipt.observation)
    local p=data and data.proposal
    if not p or p.feature~="favors" or type(p.intent)~="table" or p.intent.kind~="favorHelp"
        or not scope(p,i) or p.intent.needsSequence~=true or p.intent.sequence~=nil
        or p.intent.nativeJob~=nil or p.intent.nativeEpoch~=nil or p.intent.nativeSourceKey~=nil
        or p.intent.rowId~=record.arg1 or not header(data.before,i)
        or data.before.session~=p.session or data.before.revision~=p.revision
        or record.sentAt<data.before.capturedAt or type(data.before.native)~="table"
        or data.before.native.fullSync~=true or not number(data.before.native.serverNow)
        or type(data.reply)~="table" or data.reply.ok~=true or data.reply.pending==true
        or data.reply.code=="rate_limited" or data.reply.code=="busy" or data.reply.code=="presence"
        or data.reply.code=="no_pending" or not observed then return nil,"Exact original Favor receipt required" end
    -- The current capture revalidates the original admission. Compare only the
    -- exact published v1 baseline fields; never write a reconstructed baseline.
    local captured=m.FavorHelpEvidence.capture(p,data.before)
    if not captured then return nil,"Original Favor admission is invalid" end
    local original={}
    for _,field in ipairs(legacyFavorFields) do original[field]=captured[field] end
    if not same(original,data.baseline) or not same(observed.baseline,{kind="heistObservation"})
        or not same(observed.reply,data.reply) or type(observed.proposal)~="table"
        or observed.proposal.feature~=p.feature or observed.proposal.actionKey~=p.actionKey
        or not same(observed.proposal.intent,p.intent) or not same(observed.proposal.resources,p.resources)
        or not header(observed.before,i) or not scope(observed.proposal,i)
        or observed.proposal.session~=observed.before.session or observed.proposal.revision~=observed.before.revision
        or observed.before.native.serverNow<data.before.native.serverNow
        or observed.before.session==p.session and observed.before.revision<=p.revision then
        return nil,"Original Favor observation changed"
    end
    local board,row,usage=favorAfter(observed.before,i,p.intent.rowId)
    if not board or row.heistId~=original.heistId or row.ownerId~=original.ownerId
        or personal(row)~=original.helpsBefore+1 or board.favorsLeft~=original.favorsBefore-original.favorCost
        or usage.day~=original.serverDay or usage.attempts<original.usageAttemptsBefore+1 then
        return nil,"Legacy Favor settlement remains unproven"
    end
    local result=summary("heist",i)
    result.sequenceFloor=record.sequence
    result.affectedIntents={heistStart=true,heistCollect=true,favorHelp=true,heistSabotage=true}
    return result,nil
end
local memberFields={key=true,name=true,rarity=true,train=true,duty=true,token=true,at=true,stationed=true,
    injured=true,recalled=true,training=true,rolling=true,pending=true,weapon=true,armor=true,vehicle=true}
local function member(row)
    if not only(row,memberFields) or not text(row.key) or not row.key:match("^id:.+") and not row.key:match("^deployment:.+")
        or not text(row.name,64) or not integer(row.rarity,1,20) or not integer(row.train,0,1000000)
        or not (row.duty==false or text(row.duty,120)) or not (row.token==false or id(row.token,160))
        or not (row.at==false or number(row.at)) or not number(row.injured) or not number(row.recalled)
        or type(row.stationed)~="boolean" or type(row.training)~="boolean" or type(row.rolling)~="boolean"
        or type(row.pending)~="boolean" then return false end
    for _,field in ipairs({"weapon","armor","vehicle"}) do
        if row[field]~=false and not text(row[field],120) then return false end
    end
    return not row.key:match("^deployment:") or text(row.duty,120) and id(row.token,160)
        and row.key=="deployment:"..tostring(row.token)
end
local targetFields={districtId=true,userId=true,memberIndex=true,memberName=true,rarity=true,deploymentId=true,at=true}
local function recall(value,deps)
    local i=deps.identity
    if not only(value,{version=true,lastRequestId=true,receipt=true,transaction=true}) or value.version~=1
        or value.transaction~=nil or not integer(value.lastRequestId,1) then return nil,"Inactive legacy Recall required" end
    local receipt=value.receipt
    if not only(receipt,{outcome=true,record=true}) or receipt.outcome~="confirmed" then
        return nil,"Confirmed legacy Recall receipt required"
    end
    local r=receipt.record
    if not only(r,{account=true,place=true,release=true,userId=true,requestId=true,actionKey=true,cooldownSeconds=true,
        replyReceived=true,stage=true,target=true,baseline=true,sentServerNow=true,settled=true})
        or not scope(r,i) or not integer(r.userId,1) or not integer(r.requestId,1,value.lastRequestId)
        or not text(r.actionKey) or not integer(r.cooldownSeconds,1,86400)
        or r.replyReceived~=true or r.stage~="observed" then return nil,"Observed original Recall identity required" end
    local t,b=r.target,r.baseline
    if not only(t,targetFields) or not text(t.districtId,120) or t.userId~=r.userId
        or not integer(t.memberIndex,2,46) or not text(t.memberName,64) or not integer(t.rarity,1,20)
        or t.deploymentId~=nil and not id(t.deploymentId,160) or t.at~=nil and not number(t.at)
        or t.deploymentId==nil and not number(t.at,1) or not same(r.settled,t)
        or not only(b,{session=true,revision=true,capturedAt=true,serverNow=true,familyId=true,size=true,members=true})
        or not text(b.session) or not integer(b.revision,0) or not number(b.capturedAt) or not number(b.serverNow)
        or not id(b.familyId,160) or not integer(b.size,2,46) or type(b.members)~="table"
        or r.sentServerNow~=b.serverNow or r.requestId<math.floor(b.serverNow*1000) then
        return nil,"Original Recall target or baseline changed"
    end
    local seen,tokens,count={},{},0
    for key,row in pairs(b.members) do
        local slot=tonumber(key)
        if not integer(slot,2,b.size) or tostring(slot)~=key or not member(row) or seen[row.key]
            or row.token~=false and tokens[tostring(row.token)] then return nil,"Legacy Recall roster identity is ambiguous" end
        seen[row.key],count=true,count+1
        if row.token~=false then tokens[tostring(row.token)]=true end
    end
    local selected=b.members[tostring(t.memberIndex)]
    if count~=b.size-1 or not selected or not selected.key:match("^id:.+") or selected.name~=t.memberName
        or selected.rarity~=t.rarity or selected.duty~=t.districtId
        or (selected.token~=false and selected.token or nil)~=t.deploymentId
        or (selected.at~=false and selected.at or nil)~=t.at
        or selected.training or selected.rolling or selected.pending or selected.injured>b.serverNow
        or selected.recalled>b.serverNow then return nil,"Legacy selected Recall deployment changed" end
    local result=summary("recall",i)
    result.requestFloor=value.lastRequestId
    result.originalScope.userId=r.userId
    result.affectedIntents={territoryRecall=true}
    return result,nil
end
function Legacy.Inspect(kind,value,deps)
    local ok,result,reason=pcall(function()
        local i=type(deps)=="table" and deps.identity
        if type(i)~="table" or not text(i.account) or not text(i.place) or not text(i.release)
            or type(deps.modules)~="table" then return nil,"Legacy source scope unavailable" end
        if kind=="heist" then return heist(value,deps) end
        if kind=="recall" then return recall(value,deps) end
        return nil,"Unsupported legacy receipt kind"
    end)
    return ok and result or nil,not ok and "Legacy receipt inspection failed" or reason
end
return Legacy
