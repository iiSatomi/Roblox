-- Durable one-dismiss/one-hire custody. No scheduler, services, retry loop or remote send.
-- Only SubmitCall after a successful write-ahead MarkSending can authorize one emission.
local CrewReplacementTransactions = {}
local Methods = {}
Methods.__index = Methods
local MAX = 9007199254740991
local writers = {}
local function number(v, low, high) return type(v) == "number" and v == v and v >= low and v <= high end
local function usageCopy(value)
    if type(value) ~= "table" or not number(value.attempted, 0, 1000) or value.attempted % 1 ~= 0
        or not number(value.spent, 0, MAX) or value.spent % 1 ~= 0
        or value.attempted == 0 and value.spent ~= 0 then return nil end
    for key in pairs(value) do if key ~= "attempted" and key ~= "spent" then return nil end end
    return {attempted = value.attempted, spent = value.spent}
end
local function usageMatches(record, usage)
    if not record then return true end
    local intent = record.funded
    local spent = intent.spentBefore
    if record.stage == "sentHire" or record.stage == "observedMember" then spent = spent + intent.cost end
    return usage.attempted == intent.attemptedBefore + 1 and usage.spent == spent
end
local function text(v, limit) return type(v) == "string" and #v > 0 and #v <= limit end
local function fresh(raw, now)
    return type(raw) == "table" and number(now, 0, MAX) and number(raw.capturedAt, 0, MAX)
        and raw.capturedAt <= now + 1 and now - raw.capturedAt <= 15
end
local stages = { preparedDismiss = true, sentDismiss = true, observedEmpty = true,
    preparedHire = true, sentHire = true, observedMember = true }
local function inScope(raw, scope)
    return type(raw) == "table" and raw.account == scope.account and raw.place == scope.place and raw.release == scope.release
end
local function validRecord(record, scope, helper)
    if type(record) ~= "table" or not stages[record.stage] or record.ownerId ~= scope.ownerId
        or not inScope(record.proposal, scope) or not helper.ValidBaseline(record.proposal, record.baseline)
        or type(record.funded) ~= "table" or record.funded.kind ~= "crewReplacementDismiss"
        or record.funded.ownerId ~= scope.ownerId or record.funded.sourceKey ~= helper.key then return false end
    local intent = record.proposal.intent
    for key, value in pairs(record.funded) do
        if key ~= "kind" and key ~= "rosterSignature" and key ~= "decreeRevision" and intent[key] ~= value then return false end
    end
    local hire = record.stage == "preparedHire" or record.stage == "sentHire" or record.stage == "observedMember"
    if intent.kind ~= (hire and "crewReplacementHire" or "crewReplacementDismiss") then return false end
    if not hire and not helper.Same(intent, record.funded) then return false end
    if hire then
        local origin = record.dismissal
        if type(origin) ~= "table" or not helper.Same(origin.proposal and origin.proposal.intent, record.funded)
            or not helper.ValidBaseline(origin.proposal, origin.baseline)
            or helper.reconcile(origin.proposal, origin.baseline, origin.observed, origin.reply, true) ~= "confirmed"
            or record.stage ~= "observedMember" and not helper.Same(record.observed, origin.observed) then return false end
    elseif record.dismissal ~= nil then return false end
    local sent = record.stage == "sentDismiss" or record.stage == "sentHire"
        or record.stage == "observedEmpty" or record.stage == "observedMember"
    if sent ~= (record.sentServerNow ~= nil) or sent and record.sentServerNow ~= record.baseline.before.native.serverNow then return false end
    if (record.stage == "observedEmpty" or hire)
        and (type(record.observed) ~= "table" or not inScope(record.observed, scope)
            or not helper.read(record.observed, record.observed)) then return false end
    if record.stage == "observedEmpty" or record.stage == "observedMember" then
        if helper.reconcile(record.proposal, record.baseline, record.observed, record.reply, true) ~= "confirmed" then return false end
    elseif record.reply ~= nil and not sent then return false end
    return true
end
local function validResolution(value, active, usage, scope, helper)
    if value == nil then return true end
    if type(value) ~= "table" or value.kind ~= "known_unsent" and value.kind ~= "rejected"
        or not inScope(value.proposal, scope) or not helper.ValidBaseline(value.proposal, value.baseline)
        or value.proposal.feature ~= "crewRoll" or value.proposal.intent.ownerId ~= scope.ownerId then return false end
    for key in pairs(value) do
        if key ~= "kind" and key ~= "proposal" and key ~= "baseline" and key ~= "reply" then return false end
    end
    local intent = value.proposal.intent
    if value.kind == "known_unsent" then
        if value.reply ~= nil or usage.spent ~= intent.spentBefore then return false end
        if intent.kind == "crewReplacementDismiss" then return active == nil and usage.attempted == intent.attemptedBefore end
        return intent.kind == "crewReplacementHire" and usage.attempted == intent.attemptedBefore + 1
            and active ~= nil and active.stage == "observedEmpty" and active.funded.slot == intent.slot
            and active.funded.ownerId == intent.ownerId and active.funded.cost == intent.cost
    end
    return active == nil and intent.kind == "crewReplacementHire" and type(value.reply) == "table" and value.reply.ok == false
        and usage.attempted == intent.attemptedBefore + 1 and usage.spent == intent.spentBefore + intent.cost
end
function CrewReplacementTransactions.new(storage, scope, helper)
    if type(storage) ~= "table" or type(storage.Read) ~= "function" or type(storage.Write) ~= "function"
        or type(scope) ~= "table" or not text(scope.account, 200) or not text(scope.place, 200)
        or not text(scope.release, 200) or not text(scope.ownerId, 120) or type(helper) ~= "table"
        or type(helper.Copy) ~= "function" or type(helper.ValidBaseline) ~= "function"
        or type(helper.FundedHire) ~= "function" or helper.release ~= scope.release then
        return nil, "Durable Crew storage, exclusive owner scope and reviewed helper required"
    end
    local ownedScope = { account = scope.account, place = scope.place, release = scope.release, ownerId = scope.ownerId }
    local key = "idle-mafia-ember:crew-replacement:v1:" .. scope.account .. ":" .. scope.place .. ":" .. scope.release
    if writers[key] then return nil, "Crew replacement write already in flight" end
    local ok, envelope = pcall(storage.Read, storage, key)
    if not ok then return nil, "Crew replacement storage read failed" end
    if envelope ~= nil then
        envelope = helper.Copy(envelope)
        if not envelope or envelope.schema ~= 1 or not helper.Same(envelope.scope, ownedScope)
            or not usageCopy(envelope.usage) or not number(envelope.generation, 1, MAX) or envelope.generation % 1 ~= 0
            or envelope.active ~= nil and not validRecord(envelope.active, ownedScope, helper)
            or not usageMatches(envelope.active, envelope.usage)
            or not validResolution(envelope.resolution, envelope.active, envelope.usage, ownedScope, helper) then
            return nil, "Corrupt or mismatched Crew replacement record"
        end
        for field in pairs(envelope) do
            if field ~= "schema" and field ~= "scope" and field ~= "active" and field ~= "usage"
                and field ~= "generation" and field ~= "resolution" then return nil, "Unknown replacement envelope field" end
        end
    end
    return setmetatable({ storage = storage, scope = ownedScope, key = key, helper = helper,
        active = envelope and envelope.active or nil, usage = envelope and usageCopy(envelope.usage) or {attempted = 0, spent = 0},
        generation = envelope and envelope.generation or 0, resolution = envelope and helper.Copy(envelope.resolution) or nil,
        saved = envelope and helper.Copy(envelope) or nil,
        armed = false, preparedHere = false, closed = false }, Methods), nil
end
function Methods:save(record, usage, resolution)
    if self.closed or self.fault or writers[self.key] then return false, self.fault or "Crew replacement owner closed or busy" end
    usage = usageCopy(usage or self.usage)
    local envelope = usage and self.helper.Copy({ schema = 1, scope = self.scope, active = record,
        usage = usage, generation = self.generation + 1, resolution = resolution })
    if not envelope or record ~= nil and not validRecord(record, self.scope, self.helper) or not usageMatches(record, usage)
        or not validResolution(resolution, record, usage, self.scope, self.helper) then
        return false, "Invalid Crew replacement transition"
    end
    writers[self.key] = self
    local ok, accepted = pcall(function()
        local current = self.storage:Read(self.key)
        local copied = current and self.helper.Copy(current) or nil
        if current ~= nil and copied == nil or not self.helper.Same(copied, self.saved) then
            self.fault = "Crew replacement generation changed"
            return false
        end
        if self.closed then return false end
        return self.storage:Write(self.key, self.helper.Copy(envelope))
    end)
    writers[self.key] = nil
    if not ok or accepted ~= true then return false, "Crew replacement persistence failed" end
    self.active, self.usage, self.generation = envelope.active, envelope.usage, envelope.generation
    self.saved = self.helper.Copy(envelope)
    self.resolution = envelope.resolution
    return true, nil
end
function Methods:Active() return self.active and self.helper.Copy(self.active) or nil end
function Methods:Usage() return not self.closed and not self.fault and usageCopy(self.usage) or nil end
function Methods:Resolution() return not self.closed and not self.fault and self.helper.Copy(self.resolution) or nil end
local function unsentEvidence(self, record)
    return self.helper.Copy({schema = 1, scope = self.scope, generation = self.generation,
        proposal = record.proposal, baseline = record.baseline})
end
local function unsentEvidenceKey(self)
    return self.key .. ":adapter-unsent:" .. string.format("%.0f", self.generation)
end
function Methods:RecordAbandonedUnsent(actionKey)
    local record = self.active
    if not record or record.proposal.actionKey ~= actionKey or record.reply ~= nil
        or record.stage ~= "sentDismiss" and record.stage ~= "sentHire" then return false end
    local key, evidence = unsentEvidenceKey(self), unsentEvidence(self, record)
    if not evidence or writers[key] then return false end
    writers[key] = self
    local ok, saved = pcall(function()
        local previous = self.storage:Read(key)
        if previous ~= nil then return self.helper.Same(self.helper.Copy(previous), evidence) end
        return self.storage:Write(key, evidence)
    end)
    writers[key] = nil
    return ok and saved == true
end
function Methods:KnownUnsent()
    local record, generation = self.active, self.generation
    if self.closed or self.fault or not record or record.reply ~= nil
        or record.stage ~= "sentDismiss" and record.stage ~= "sentHire" then return false end
    local evidence, key = unsentEvidence(self, record), unsentEvidenceKey(self)
    local ok, saved = pcall(self.storage.Read, self.storage, key)
    return ok and evidence ~= nil and self.generation == generation and self.helper.Same(record, self.active)
        and self.helper.Same(self.helper.Copy(saved), evidence)
end
function Methods:RecoverKnownUnsent()
    if not self:KnownUnsent() then return false, "No matching adapter proof of non-invocation" end
    local record = self.active
    local usage = {attempted = record.funded.attemptedBefore, spent = record.funded.spentBefore}
    local restored
    if record.stage == "sentHire" then
        if not record.dismissal then return false, "Original funded empty custody missing" end
        restored = self.helper.Copy(record.dismissal)
        restored.stage, restored.ownerId, restored.funded = "observedEmpty", self.scope.ownerId, self.helper.Copy(record.funded)
        restored.sentServerNow = restored.baseline.before.native.serverNow
        usage.attempted = usage.attempted + 1
    end
    self.armed, self.dispatchHere, self.preparedHere = false, false, false
    return self:save(restored, usage, {kind = "known_unsent", proposal = self.helper.Copy(record.proposal),
        baseline = self.helper.Copy(record.baseline)})
end
function Methods:ReservationClaims(reservationModule, raw)
    if self.closed or self.fault then return nil, self.fault or "Crew replacement owner closed" end
    local record = self.active
    if not record then return nil end
    if not validRecord(record, self.scope, self.helper) or type(reservationModule) ~= "table"
        or type(reservationModule.ForProposal) ~= "function" then return nil, "Crew replacement custody unavailable" end
    if record.stage == "observedMember" then return nil end
    local claims, reason = reservationModule.ForProposal(record.proposal, record.baseline.before)
    if not claims then return nil, reason end
    claims.funds.cash = record.funded.cost
    local actionKey = record.proposal.actionKey
    if record.stage == "observedEmpty" and raw ~= nil then
        local continuation = self.helper.FundedHire(raw, record.funded)
        if continuation then actionKey = continuation.actionKey end
    end
    return {account = self.scope.account, place = self.scope.place, release = self.scope.release,
        feature = "crewRoll", actionKey = actionKey, claims = claims}, nil
end
function Methods:IsPreparedHere()
    return not self.closed and self.preparedHere == true
end
function Methods:PrepareDismiss(proposal, before, now)
    if self.closed or self.active or not fresh(before, now) or not inScope(before, self.scope)
        or type(proposal) ~= "table" or type(proposal.intent) ~= "table"
        or proposal.intent.kind ~= "crewReplacementDismiss" or proposal.intent.ownerId ~= self.scope.ownerId then
        return false, "Fresh funded dismissal with exclusive empty transaction required"
    end
    local baseline, reason = self.helper.capture(proposal, before)
    if not baseline then return false, reason end
    if proposal.intent.attemptedBefore ~= self.usage.attempted or proposal.intent.spentBefore ~= self.usage.spent then
        return false, "Crew replacement allowance changed"
    end
    local ok, failure = self:save({ stage = "preparedDismiss", ownerId = self.scope.ownerId,
        proposal = self.helper.Copy(proposal), baseline = baseline, funded = self.helper.Copy(proposal.intent) },
        {attempted = self.usage.attempted + 1, spent = self.usage.spent})
    if ok then self.preparedHere = true end
    return ok, failure
end
function Methods:PrepareHire(before, now)
    local record = self.active
    if self.closed or not record or record.stage ~= "observedEmpty" or not fresh(before, now)
        or not inScope(before, self.scope) then return nil, "Fresh observed-empty custody required" end
    local view = self.helper.read(before, before)
    local observed = self.helper.read(record.observed, record.observed)
    if not view or not observed or view.serverNow < observed.serverNow or view.rosterSignature ~= observed.rosterSignature then
        return nil, "Observed empty target or roster changed"
    end
    local proposal, reason = self.helper.FundedHire(before, record.funded)
    if not proposal then return nil, reason end
    local baseline = self.helper.capture(proposal, before)
    if not baseline then return nil, "Current funded hire baseline required" end
    local nextRecord = self.helper.Copy(record)
    nextRecord.dismissal = { proposal = self.helper.Copy(record.proposal), baseline = self.helper.Copy(record.baseline),
        reply = self.helper.Copy(record.reply), observed = self.helper.Copy(record.observed) }
    nextRecord.stage, nextRecord.proposal, nextRecord.baseline = "preparedHire", proposal, baseline
    nextRecord.reply, nextRecord.sentServerNow = nil, nil
    local ok, failure = self:save(nextRecord)
    if not ok then return nil, failure end
    self.preparedHere = true
    return self.helper.Copy(proposal), nil
end
function Methods:MarkSending(before, now)
    local record = self.active
    if self.closed or not self.preparedHere or not record or (record.stage ~= "preparedDismiss" and record.stage ~= "preparedHire")
        or not fresh(before, now) or not inScope(before, self.scope) then return false, "Fresh known-unsent stage required" end
    local baseline = self.helper.capture(record.proposal, before)
    if not baseline or not self.helper.Same(baseline, record.baseline) then return false, "Prepared Crew baseline changed" end
    local nextRecord = self.helper.Copy(record)
    nextRecord.stage = record.stage == "preparedDismiss" and "sentDismiss" or "sentHire"
    nextRecord.sentServerNow = baseline.before.native.serverNow
    local usage = usageCopy(self.usage)
    if record.stage == "preparedHire" then usage.spent = usage.spent + record.funded.cost end
    local ok, reason = self:save(nextRecord, usage)
    if ok and not self.closed then self.armed, self.preparedHere, self.dispatchHere = true, false, true end
    return ok, reason
end
function Methods:SubmitCall(before, now)
    local armed, record = self.armed, self.active
    self.armed = false -- A failed preflight also consumes the single live emission arm.
    if self.closed or not armed or not record or (record.stage ~= "sentDismiss" and record.stage ~= "sentHire")
        or record.reply ~= nil or not fresh(before, now) or not inScope(before, self.scope) then
        return nil, "No live write-ahead Crew emission arm"
    end
    local baseline = self.helper.capture(record.proposal, before)
    if not baseline or not self.helper.Same(baseline, record.baseline) then return nil, "Crew changed before direct emission" end
    local intent = record.proposal.intent
    return { remote = "CrewAction", method = "InvokeServer", arity = 4,
        args = intent.kind == "crewReplacementDismiss" and { "dismiss", intent.slot }
            or { "hire", intent.tier, intent.cost }, actionKey = record.proposal.actionKey,
        source = "durable ordinary Crew replacement; no server-side dismissal identity guard" }, nil
end
function Methods:AcceptReply(actionKey, reply)
    local record = self.active
    if self.closed or not record or (record.stage ~= "sentDismiss" and record.stage ~= "sentHire")
        or actionKey ~= record.proposal.actionKey or type(reply) ~= "table" or type(reply.ok) ~= "boolean" then
        return false, "Reply does not match this sent Crew action"
    end
    self.armed = false
    self.dispatchHere = false
    local saved = { ok = reply.ok, pending = reply.pending, code = reply.code, index = reply.index }
    if reply.member ~= nil then
        if type(reply.member) ~= "table" then return false, "Invalid hired member reply" end
        saved.member = {}
        for _, field in ipairs({ "name", "rarity", "atk", "def", "healId" }) do saved.member[field] = reply.member[field] end
    end
    saved = self.helper.Copy(saved)
    if not saved then return false, "Malformed Crew reply" end
    if record.reply ~= nil then return self.helper.Same(record.reply, saved), "Crew callback already recorded" end
    local nextRecord = self.helper.Copy(record)
    nextRecord.reply = saved
    return self:save(nextRecord)
end
function Methods:Reconcile(after, now)
    local record = self.active
    if self.closed or not record or (record.stage ~= "sentDismiss" and record.stage ~= "sentHire")
        or not fresh(after, now) or not inScope(after, self.scope) then return false, "Fresh sent Crew custody required" end
    local outcome = self.helper.reconcile(record.proposal, record.baseline, after, record.reply, true)
    if outcome ~= "confirmed" then return false, "Crew action is " .. outcome .. "; no replay authorized" end
    local view = self.helper.read(after, after)
    local nextRecord = self.helper.Copy(record)
    nextRecord.stage = record.stage == "sentDismiss" and "observedEmpty" or "observedMember"
    nextRecord.observed = self.helper.Copy(view.raw)
    return self:save(nextRecord)
end
function Methods:DiscardPrepared()
    if self.closed or not self.active or self.active.stage ~= "preparedDismiss" then
        return false, "Only the known-unsent dismissal can be discarded"
    end
    return self:save(nil, {attempted = self.active.funded.attemptedBefore, spent = self.active.funded.spentBefore},
        {kind = "known_unsent", proposal = self.helper.Copy(self.active.proposal), baseline = self.helper.Copy(self.active.baseline)})
end
-- Only the adapter's known-unsent path may call this for a live sent stage.
-- Reloaded/successfully returned stages never carry this process-local permission.
function Methods:CancelUnsent(actionKey)
    local record = self.active
    if self.closed or not record or record.proposal.actionKey ~= actionKey or record.reply ~= nil
        or not (self.preparedHere or self.dispatchHere) then return false, "No live known-unsent Crew stage" end
    self.armed = false
    local usage = {attempted = record.funded.attemptedBefore + 1, spent = record.funded.spentBefore}
    local nextRecord
    if record.stage == "preparedDismiss" or record.stage == "sentDismiss" then
        usage.attempted = record.funded.attemptedBefore
    elseif record.stage == "preparedHire" or record.stage == "sentHire" then
        local origin = record.dismissal
        if not origin then return false, "Original observed empty custody unavailable" end
        nextRecord = self.helper.Copy(origin)
        nextRecord.stage, nextRecord.ownerId, nextRecord.funded = "observedEmpty", self.scope.ownerId, self.helper.Copy(record.funded)
        nextRecord.sentServerNow = origin.baseline.before.native.serverNow
    else return false, "Crew stage is not an unsent command" end
    local saved, reason = self:save(nextRecord, usage, {kind = "known_unsent",
        proposal = self.helper.Copy(record.proposal), baseline = self.helper.Copy(record.baseline)})
    if saved then self.dispatchHere, self.preparedHere = false, false end
    return saved, reason
end
function Methods:ClearObserved()
    if self.closed or not self.active or self.active.stage ~= "observedMember" then
        return false, "Intermediate empty or uncertain Crew custody cannot be cleared"
    end
    return self:save(nil)
end
function Methods:RestorePreparedHire()
    local record = self.active
    if self.closed or not record or record.stage ~= "preparedHire" or not record.dismissal then
        return false, "Only a known-unsent prepared hire can restore funding"
    end
    local origin = self.helper.Copy(record.dismissal)
    origin.stage, origin.ownerId, origin.funded = "observedEmpty", self.scope.ownerId, self.helper.Copy(record.funded)
    origin.sentServerNow = origin.baseline.before.native.serverNow
    self.armed, self.dispatchHere = false, false
    return self:save(origin, self.usage, {kind = "known_unsent", proposal = self.helper.Copy(record.proposal),
        baseline = self.helper.Copy(record.baseline)})
end
function Methods:ReleaseRejectedHire(after, now)
    local record = self.active
    if self.closed or not record or record.stage ~= "sentHire" or not fresh(after, now)
        or not inScope(after, self.scope) or type(record.reply) ~= "table" or record.reply.pending == true
        or self.helper.reconcile(record.proposal, record.baseline, after, record.reply, true) ~= "rejected" then
        return false, "Exact newer rejected-hire state required"
    end
    return self:save(nil, self.usage, {kind = "rejected", proposal = self.helper.Copy(record.proposal),
        baseline = self.helper.Copy(record.baseline), reply = self.helper.Copy(record.reply)})
end
function Methods:Close() self.closed, self.armed, self.dispatchHere = true, false, false end
return CrewReplacementTransactions
