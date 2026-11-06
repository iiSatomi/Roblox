-- Durable claims for a sequence allocated by native act. This owner never sends or increments a sequence.
local Transactions, Methods, writers = {}, {}, {}
Methods.__index = Methods
local MAX = 9007199254740991
local fields = {"session", "account", "place", "release", "revision", "feature", "actionKey"}
local function number(value) return type(value) == "number" and value == value and value >= 0 and value <= MAX end
local function integer(value, low) return number(value) and value % 1 == 0 and value >= low end
local function text(value) return type(value) == "string" and #value > 0 and #value <= 200 and not value:find("[%c]") end
local function same(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not same(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
local function proposalMatches(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, key in ipairs(fields) do if a[key] ~= b[key] then return false end end
    return same(a.intent, b.intent) and same(a.resources, b.resources)
end
local function only(value, allowed)
    for key in pairs(value) do if not allowed[key] then return false end end
    return true
end
local function dataOf(self, record)
    return type(record) == "table" and self.pending.Decode(record.data) or nil
end
local function outcomeOf(self, data, after, recovering)
    local evidence = self.evidence[data.proposal.feature]
    if recovering and type(evidence.recoverSaved) == "function" then return evidence.recoverSaved(data, after) end
    return evidence.evaluate(data.proposal, data.before, after, data.reply, data.baseline)
end
local function copyRecord(self, raw)
    if type(raw) ~= "table" or not integer(raw.sequence, 1) or type(raw.sent) ~= "boolean"
        or raw.sent and not number(raw.sentAt) or not raw.sent and raw.sentAt ~= nil
        or not only(raw, {sequence = true, actionName = true, arg1 = true, sent = true,
            sentAt = true, data = true}) then return nil end
    local data = dataOf(self, raw)
    local proposal = data and data.proposal
    if not proposal then return nil end
    for _, field in ipairs({"account", "place", "release"}) do if proposal[field] ~= self.scope[field] then return nil end end
    local evidence = self.evidence[proposal.feature]
    local call = self.plan.describe(proposal)
    if type(evidence) ~= "table" or type(evidence.capture) ~= "function" or type(evidence.evaluate) ~= "function"
        or not call or call.nativeAct ~= true or raw.actionName ~= call.args[1] or raw.arg1 ~= call.args[2] then return nil end
    local baseline = evidence.capture(proposal, data.before)
    if not baseline or not same(baseline, data.baseline) or not raw.sent and data.reply ~= nil then return nil end
    local copied = self.pending.Copy(raw.data)
    if not copied then return nil end
    return {sequence = raw.sequence, actionName = raw.actionName, arg1 = raw.arg1,
        sent = raw.sent, sentAt = raw.sentAt, data = copied}
end
local function copyReceipt(self, raw)
    if raw == nil then return nil, true end
    if type(raw) ~= "table" or not only(raw, {record = true, outcome = true, observation = true})
        or raw.outcome ~= "confirmed" and raw.outcome ~= "rejected" and raw.outcome ~= "known_unsent" then return nil, false end
    local record = copyRecord(self, raw.record)
    if not record then return nil, false end
    local data = dataOf(self, record)
    local observation
    if raw.outcome == "known_unsent" then
        if data.reply ~= nil or raw.observation ~= nil then return nil, false end
    else
        observation = self.pending.Copy(raw.observation)
        local decoded = observation and self.pending.Decode(observation)
        if not decoded or not same(decoded.baseline, {kind = "heistObservation"})
            or not same(decoded.reply, data.reply) then return nil, false end
        -- The observation keeps its actual session/revision. Only the durable
        -- action identity is shared with the original proposal.
        for _, field in ipairs({"account", "place", "release", "feature", "actionKey"}) do
            if decoded.proposal[field] ~= data.proposal[field] then return nil, false end
        end
        if not same(decoded.proposal.intent, data.proposal.intent)
            or not same(decoded.proposal.resources, data.proposal.resources)
            or outcomeOf(self, data, decoded.before, true) ~= raw.outcome then return nil, false end
    end
    return {record = record, outcome = raw.outcome, observation = observation}, true
end
local function copyState(self, raw)
    if type(raw) ~= "table" or raw.version ~= 1 or not integer(raw.generation, 1)
        or not only(raw, {version = true, generation = true, account = true, place = true,
            release = true, active = true, receipt = true}) then return nil end
    for _, field in ipairs({"account", "place", "release"}) do if raw[field] ~= self.scope[field] then return nil end end
    local active = raw.active and copyRecord(self, raw.active)
    local receipt, valid = copyReceipt(self, raw.receipt)
    if raw.active ~= nil and not active or not valid then return nil end
    return {version = 1, generation = raw.generation, account = self.scope.account,
        place = self.scope.place, release = self.scope.release, active = active, receipt = receipt}
end
function Transactions.new(storage, scope, pending, plan, evidence)
    if type(storage) ~= "table" or storage.strictRecovery ~= true or type(storage.Read) ~= "function"
        or type(storage.Write) ~= "function" or type(scope) ~= "table" or type(pending) ~= "table"
        or type(pending.Capture) ~= "function" or type(pending.Decode) ~= "function" or type(pending.Copy) ~= "function"
        or type(plan) ~= "table" or type(plan.describe) ~= "function" or type(evidence) ~= "table" then return nil, "Durable Heist dependencies required" end
    local owned, key = {}, "idle-mafia-ember:heist-sequences:v1:"
    for _, field in ipairs({"account", "place", "release"}) do
        if not text(scope[field]) then return nil, "Invalid Heist scope" end
        owned[field], key = scope[field], key .. #scope[field] .. ":" .. scope[field]
    end
    if writers[key] then return nil, "Heist save in flight" end
    local self = setmetatable({storage = storage, scope = owned, key = key,
        pending = pending, plan = plan, evidence = evidence}, Methods)
    local ok, raw = pcall(storage.Read, storage, key)
    if not ok then return nil, "Heist storage read failed" end
    local state = raw ~= nil and copyState(self, raw) or nil
    if raw ~= nil and not state then return nil, "Invalid Heist sequence ledger" end
    self.state, self.expected = state, state and copyState(self, state) or nil
    return self, nil
end
function Methods:save(active, receipt)
    if self.closed or self.fault or writers[self.key] then return false, self.fault or "Heist owner unavailable" end
    writers[self.key] = self
    local ok, saved = pcall(function()
        local raw = self.storage:Read(self.key)
        local current = raw ~= nil and copyState(self, raw) or nil
        if raw ~= nil and not current or not same(current, self.expected) or self.closed then return false end
        local nextState = copyState(self, {version = 1, generation = current and current.generation + 1 or 1,
            account = self.scope.account, place = self.scope.place, release = self.scope.release,
            active = active, receipt = receipt})
        if not nextState or self.storage:Write(self.key, nextState) == false then return false end
        local observed = copyState(self, self.storage:Read(self.key))
        if not observed or not same(observed, nextState) then return false end
        self.state, self.expected = observed, copyState(self, observed)
        return not self.closed
    end)
    if writers[self.key] == self then writers[self.key] = nil end
    if not ok or saved ~= true then self.fault = "Heist durable write refused"; return false, self.fault end
    return true, nil
end
function Methods:Active()
    if self.fault or self.closed then return nil end
    local record = self.state and self.state.active
    if not record then return nil end
    local result = copyRecord(self, record)
    local data = dataOf(self, result)
    result.actionKey, result.account, result.place, result.release = data.proposal.actionKey,
        self.scope.account, self.scope.place, self.scope.release
    result.recovery = data
    return result
end
function Methods:Receipt()
    local receipt = self.state and self.state.receipt
    if not receipt then return nil end
    local result = self:recordView(receipt.record)
    result.outcome = receipt.outcome
    return result
end
function Methods:recordView(record)
    local result = copyRecord(self, record)
    local data = dataOf(self, result)
    result.actionKey, result.account, result.place, result.release = data.proposal.actionKey,
        self.scope.account, self.scope.place, self.scope.release
    result.recovery = data
    return result
end
function Methods:Prepare(proposal, before, baseline, native, now)
    if self.state and self.state.active or type(native) ~= "table" or native.controllersClear ~= true
        or not integer(native.sequence, 0) or native.sequence >= MAX or not number(now)
        or type(before) ~= "table" or not number(before.capturedAt) or before.capturedAt > now
        or now - before.capturedAt > 2 then return false, "Current clear native Heist owner required" end
    local call = self.plan.describe(proposal)
    local encoded = self.pending.Capture(proposal, before, baseline)
    if not call or not encoded then return false, "Exact Heist baseline required" end
    local record = copyRecord(self, {sequence = native.sequence + 1, actionName = call.args[1],
        arg1 = call.args[2], sent = false, data = encoded})
    if not record then return false, "Invalid Heist claim" end
    local saved, why = self:save(record, self.state and self.state.receipt)
    if saved then self.preparedHere = record.sequence end
    return saved, why
end
function Methods:MarkSending(proposal, native, now)
    local record = self.state and self.state.active
    local data = dataOf(self, record)
    if not record or record.sent or self.preparedHere ~= record.sequence or not data
        or not proposalMatches(data.proposal, proposal) or type(native) ~= "table"
        or native.controllersClear ~= true or native.sequence ~= record.sequence - 1 or not number(now)
        or now < data.before.capturedAt or now - data.before.capturedAt > 2 then return nil, "Heist claim or native counter changed" end
    local nextRecord = copyRecord(self, record)
    nextRecord.sent, nextRecord.sentAt = true, now
    local saved, why = self:save(nextRecord, self.state.receipt)
    if not saved then return nil, why end
    self.sendingHere = record.sequence
    local call = self.plan.describe(proposal)
    call.nativeSequence = record.sequence
    return call, nil
end
function Methods:AcceptReply(actionKey, sequence, reply)
    local record = self.state and self.state.active
    local data = dataOf(self, record)
    if not record or not record.sent or record.sequence ~= sequence or not data or data.proposal.actionKey ~= actionKey
        or type(reply) ~= "table" or type(reply.ok) ~= "boolean" or reply.pending == true
        or reply.code == "rate_limited" or reply.code == "no_pending" or reply.code == "busy"
        or reply.code == "presence" then return false, "Exact terminal Heist reply required" end
    if data.reply ~= nil then return same(data.reply, reply), "Heist reply already recorded" end
    local nextRecord = copyRecord(self, record)
    nextRecord.data = self.pending.Capture(data.proposal, data.before, data.baseline, reply)
    if not nextRecord.data then return false, "Invalid Heist reply" end
    return self:save(nextRecord, self.state.receipt)
end
function Methods:Resolve(actionKey, sequence, outcome, after, recovering)
    local record = self.state and self.state.active
    local data = dataOf(self, record)
    if not record or not record.sent or record.sequence ~= sequence or not data or data.proposal.actionKey ~= actionKey
        or outcome ~= "confirmed" and outcome ~= "rejected"
        or outcomeOf(self, data, after, recovering == true) ~= outcome then return false, "Heist outcome remains uncertain" end
    local observedProposal = {}
    for key, value in pairs(data.proposal) do observedProposal[key] = value end
    for _, field in ipairs({"session", "account", "place", "release", "revision"}) do observedProposal[field] = after[field] end
    -- Use canonical snapshot projection for both halves of the receipt.
    local observation = self.pending.Capture(observedProposal, after, {kind = "heistObservation"}, data.reply)
    if not observation then return false, "Heist observation too large" end
    return self:save(nil, {record = record, outcome = outcome, observation = observation})
end
function Methods:CancelUnsent(actionKey, sequence)
    local record = self.state and self.state.active
    if not record then
        local receipt = self:Receipt()
        return receipt ~= nil and receipt.outcome == "known_unsent" and receipt.actionKey == actionKey
            and receipt.sequence == sequence, nil
    end
    local data = dataOf(self, record)
    if not record or record.sequence ~= sequence or not data or data.proposal.actionKey ~= actionKey
        or data.reply ~= nil or self.preparedHere ~= sequence or record.sent and self.sendingHere ~= sequence then return false, "Known local unsent Heist claim required" end
    return self:save(nil, {record = record, outcome = "known_unsent"})
end
function Methods:RecoverPrepared()
    local record = self.state and self.state.active
    if not record or record.sent or self.preparedHere ~= nil then return false, "No restored unsent Heist preparation" end
    -- Only MarkSending can precede entry into act. A restored preparation
    -- therefore cannot have emitted; a stale previous owner is fenced by CAS.
    return self:save(nil, {record = record, outcome = "known_unsent"})
end
function Methods:RecoveryRecord()
    local active = self:Active()
    return active and active.sent and active or nil
end
function Methods:Close() self.closed = true end
return Transactions
