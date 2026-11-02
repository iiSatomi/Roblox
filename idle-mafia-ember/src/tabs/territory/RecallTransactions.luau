-- One durable OWN deployment recall. No scheduler, nonce generator or transport.
-- Source: CrewRecall-805e20839f28 / TerritoryTab-12325359dd27, build 0.26.530.
local RecallTransactions = {}
local Methods = {}
Methods.__index = Methods
local MAX = 9007199254740991

local function number(value, low, high)
    return type(value) == "number" and value == value
        and value >= low and value <= high
end
local function integer(value, low, high)
    return number(value, low, high) and value % 1 == 0
end
local function text(value, limit)
    return type(value) == "string" and #value > 0 and #value <= limit
end
local function id(value)
    return text(value, 160) or integer(value, 1, MAX)
end
local function copy(value)
    local seen, nodes = {}, 0
    local function clone(current, depth)
        nodes = nodes + 1
        if nodes > 3000 or depth > 7 then error("Recall record exceeds bounds") end
        if type(current) ~= "table" then
            if type(current) == "number" and number(current, 0, MAX)
                or type(current) == "string" and #current <= 200
                or type(current) == "boolean" then return current end
            error("Invalid recall record value")
        end
        if seen[current] then error("Cyclic recall record") end
        seen[current] = true
        local result, count = {}, 0
        for key, child in pairs(current) do
            count = count + 1
            if count > 64 or not text(key, 200) then error("Invalid recall record key") end
            result[key] = clone(child, depth + 1)
        end
        seen[current] = nil
        return result
    end
    local ok, result = pcall(clone, value, 0)
    return ok and result or nil
end
local function same(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for key, value in pairs(a) do
        if type(value) == "table" then
            if not same(value, b[key]) then return false end
        elseif b[key] ~= value then return false end
    end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
local function own(scope)
    return type(scope) == "table" and text(scope.account, 200)
        and text(scope.place, 200) and text(scope.release, 200)
        and integer(scope.userId, 1, MAX)
        and scope.account == string.format("%.0f", scope.userId)
end
local function header(raw, scope)
    return type(raw) == "table" and text(raw.session, 200)
        and raw.account == scope.account and raw.place == scope.place
        and raw.release == scope.release and integer(raw.revision, 0, MAX)
        and number(raw.capturedAt, 0, MAX)
end
local function targetValid(target, userId)
    return type(target) == "table" and text(target.districtId, 120)
        and integer(target.userId, 1, MAX) and target.userId == userId
        and integer(target.memberIndex, 2, 46) and text(target.memberName, 64)
        and integer(target.rarity, 1, 20)
        and (target.deploymentId == nil or id(target.deploymentId))
        and (target.at == nil or number(target.at, 0, MAX))
        and (target.deploymentId ~= nil or number(target.at, 1, MAX))
end
local memberFields = { "name", "rarity", "train", "duty", "token", "at",
    "injured", "recalled", "training", "rolling", "pending", "weapon", "armor", "vehicle" }
local function memberValid(row)
    if type(row) ~= "table" or not text(row.name, 64)
        or not integer(row.rarity, 1, 20) or not integer(row.train, 0, 1000000)
        or not (row.duty == false or text(row.duty, 120))
        or not (row.token == false or id(row.token))
        or not (row.at == false or number(row.at, 0, MAX))
        or not number(row.injured, 0, MAX) or not number(row.recalled, 0, MAX)
        or type(row.training) ~= "boolean" or type(row.rolling) ~= "boolean"
        or type(row.pending) ~= "boolean" then return false end
    for _, field in ipairs({ "weapon", "armor", "vehicle" }) do
        if row[field] ~= false and not text(row[field], 120) then return false end
    end
    return true
end
local function absent(value, fallback)
    if value == nil then return fallback end
    return value
end
local function state(raw, scope)
    if not header(raw, scope) or type(raw.native) ~= "table"
        or raw.native.fullSync ~= true or not number(raw.native.serverNow, 0, MAX)
        or type(raw.native.family) ~= "table" or not id(raw.native.family.id)
        or type(raw.native.crew) ~= "table"
        or #raw.native.crew < 2 or #raw.native.crew > 46 then return nil end
    local members, count, seen = {}, 0, {}
    for slot, row in pairs(raw.native.crew) do
        count = count + 1
        if not integer(slot, 1, #raw.native.crew) or type(row) ~= "table" then return nil end
        if slot > 1 then
            if row.training ~= nil and type(row.training) ~= "table"
                or row.rolling ~= nil and type(row.rolling) ~= "boolean"
                or row.dutyPending ~= nil and type(row.dutyPending) ~= "boolean"
                or row.dutyRemapPending ~= nil and type(row.dutyRemapPending) ~= "boolean" then return nil end
            local saved = { name = row.name, rarity = row.rarity, train = absent(row.train, 0),
                duty = row.duty or false, token = row.dutyToken or false, at = row.dutyAt or false,
                injured = absent(row.injuredUntil, 0), recalled = absent(row.recalledUntil, 0),
                training = row.training ~= nil, rolling = row.rolling == true,
                pending = row.dutyPending == true or row.dutyRemapPending == true,
                weapon = row.weapon or false, armor = row.armor or false, vehicle = row.vehicle or false }
            if not memberValid(saved) then return nil end
            local key = #saved.name .. ":" .. saved.name .. ":" .. saved.rarity
            if seen[key] then return nil end
            seen[key], members[tostring(slot)] = true, saved
        end
    end
    if count ~= #raw.native.crew then return nil end
    return { session = raw.session, revision = raw.revision, capturedAt = raw.capturedAt,
        serverNow = raw.native.serverNow, familyId = raw.native.family.id,
        members = members, size = count }
end
local function targetFor(member, slot, userId)
    return { districtId = member.duty, userId = userId, memberIndex = slot,
        deploymentId = member.token ~= false and member.token or nil,
        at = member.at ~= false and member.at or nil,
        memberName = member.name, rarity = member.rarity }
end
local function targetMatches(target, settled)
    if type(settled) ~= "table" or settled.districtId ~= target.districtId
        or settled.userId ~= target.userId or settled.memberIndex ~= target.memberIndex
        or (settled.memberName ~= nil and settled.memberName ~= target.memberName)
        or (settled.rarity ~= nil and settled.rarity ~= target.rarity) then return false end
    if target.deploymentId ~= nil then
        return settled.deploymentId == target.deploymentId
            and (settled.at == nil or settled.at == target.at)
    end
    return settled.deploymentId == nil and settled.at == target.at
        and settled.memberName == target.memberName
end
local function baselineValid(baseline, target)
    if type(baseline) ~= "table" or not text(baseline.session, 200)
        or not integer(baseline.revision, 0, MAX) or not number(baseline.capturedAt, 0, MAX)
        or not number(baseline.serverNow, 0, MAX) or not id(baseline.familyId)
        or not integer(baseline.size, 2, 46) or type(baseline.members) ~= "table" then return false end
    local count, seen = 0, {}
    for key, row in pairs(baseline.members) do
        count = count + 1
        local slot = tonumber(key)
        if not integer(slot, 2, baseline.size) or tostring(slot) ~= key
            or not memberValid(row) then return false end
        local stable = #row.name .. ":" .. row.name .. ":" .. row.rarity
        if seen[stable] then return false end
        seen[stable] = true
    end
    local selected = baseline.members[tostring(target.memberIndex)]
    return count == baseline.size - 1 and selected ~= nil
        and same(targetFor(selected, target.memberIndex, target.userId), target)
        and not selected.training and not selected.rolling and not selected.pending
        and selected.injured <= baseline.serverNow and selected.recalled <= baseline.serverNow
end
local function recordValid(record, scope, highwater)
    return type(record) == "table" and record.account == scope.account
        and record.place == scope.place and record.release == scope.release
        and record.userId == scope.userId and integer(record.requestId, 1, highwater)
        and record.requestId == highwater and text(record.actionKey, 200)
        and integer(record.cooldownSeconds, 1, 86400)
        and (record.stage == "prepared" or record.stage == "sent"
            or record.stage == "settled" or record.stage == "observed")
        and targetValid(record.target, scope.userId) and baselineValid(record.baseline, record.target)
        and record.requestId >= math.floor(record.baseline.serverNow * 1000)
        and (record.stage == "prepared" and record.sentServerNow == nil and record.settled == nil
            or record.stage == "sent" and record.sentServerNow == record.baseline.serverNow and record.settled == nil
            or (record.stage == "settled" or record.stage == "observed")
                and record.sentServerNow == record.baseline.serverNow
                and same(record.settled, record.target))
end
local function envelopeValid(value, scope)
    return type(value) == "table" and value.version == 1
        and integer(value.lastRequestId, 0, MAX)
        and (value.transaction == nil or recordValid(value.transaction, scope, value.lastRequestId))
end
local function key(scope)
    return "idle-mafia-ember:territory-recall:v1:" .. #scope.account .. ":" .. scope.account
        .. #scope.place .. ":" .. scope.place .. #scope.release .. ":" .. scope.release
end

function RecallTransactions.new(storage, scope, terms)
    if type(storage) ~= "table" or storage.strictRecovery ~= true
        or type(storage.Read) ~= "function" or type(storage.Write) ~= "function"
        or not own(scope) or type(terms) ~= "table" or terms.release ~= scope.release
        or not integer(terms.recallCooldownSeconds, 1, 86400) then
        return nil, "Strict own-account recall storage and reviewed cooldown required"
    end
    local ownScope = { account = scope.account, place = scope.place,
        release = scope.release, userId = scope.userId }
    local storageKey = key(ownScope)
    local ok, value = pcall(storage.Read, storage, storageKey)
    if not ok then return nil, "Recall transaction read failed" end
    if value == nil then value = { version = 1, lastRequestId = 0 } else value = copy(value) end
    if not envelopeValid(value, ownScope)
        or (value.transaction and value.transaction.cooldownSeconds ~= terms.recallCooldownSeconds) then
        return nil, "Corrupt recall transaction"
    end
    return setmetatable({ storage = storage, scope = ownScope, key = storageKey,
        cooldownSeconds = terms.recallCooldownSeconds, saved = value, emission = false }, Methods), nil
end
local function persist(self, transaction, highwater)
    local value = { version = 1, lastRequestId = highwater or self.saved.lastRequestId,
        transaction = transaction }
    value = copy(value)
    if not envelopeValid(value, self.scope) then return false, "Invalid recall transaction" end
    local ok, written = pcall(self.storage.Write, self.storage, self.key, copy(value))
    if not ok or written ~= true then return false, "Recall persistence failed" end
    self.saved, self.emission = value, false
    return true, nil
end
function Methods:Active()
    return self.saved.transaction and copy(self.saved.transaction) or nil
end
-- A read-only floor for Task 24's shared allocator; this does not allocate an ID.
function Methods:LastRequestId()
    return self.saved.lastRequestId
end

local intentKeys = { kind = true, requestId = true, districtId = true, userId = true,
    memberIndex = true, deploymentId = true, at = true, memberName = true, rarity = true }
function RecallTransactions.describe(proposal)
    local intent = type(proposal) == "table" and proposal.intent
    if type(intent) ~= "table" or proposal.feature ~= "station"
        or intent.kind ~= "territoryRecall" or not integer(intent.requestId, 1, MAX)
        or not targetValid(intent, intent.userId)
        or proposal.account ~= string.format("%.0f", intent.userId)
        or type(proposal.resources) ~= "table" or next(proposal.resources) ~= nil then
        return nil, "Reviewed own-member recall intent required"
    end
    for field in pairs(intent) do
        if not intentKeys[field] then return nil, "Recall intent must contain only target primitives" end
    end
    local target = { districtId = intent.districtId, userId = intent.userId,
        memberIndex = intent.memberIndex, deploymentId = intent.deploymentId,
        at = intent.at, memberName = intent.memberName, rarity = intent.rarity }
    return { remote = "TerritoryAction", method = "InvokeServer", arity = 3,
        args = { "recallcrew", intent.requestId, { target } },
        source = "saved CrewRecall single own target" }, nil
end
function Methods:Prepare(proposal, before, now)
    if self.saved.transaction then return false, "Unresolved own-member recall exists" end
    local call = RecallTransactions.describe(proposal)
    local baseline = state(before, self.scope)
    if not call or not baseline or not number(now, 0, MAX)
        or now - baseline.capturedAt > 15 or baseline.capturedAt > now + 1
        or proposal.session ~= baseline.session or proposal.revision ~= baseline.revision
        or proposal.place ~= self.scope.place or proposal.release ~= self.scope.release
        or proposal.intent.userId ~= self.scope.userId or not text(proposal.actionKey, 200)
        or proposal.intent.requestId <= self.saved.lastRequestId
        or proposal.intent.requestId < math.floor(baseline.serverNow * 1000) then
        return false, "Fresh own deployment and shared epoch-ms request identity required"
    end
    local target = call.args[3][1]
    if not baselineValid(baseline, target) then return false, "Exact own deployment custody required" end
    return persist(self, { account = self.scope.account, place = self.scope.place,
        release = self.scope.release, userId = self.scope.userId,
        actionKey = proposal.actionKey, requestId = proposal.intent.requestId,
        target = target, baseline = baseline, stage = "prepared",
        cooldownSeconds = self.cooldownSeconds }, proposal.intent.requestId)
end
function Methods:MarkSending(before, now)
    local record = self.saved.transaction
    local baseline = state(before, self.scope)
    if not record or record.stage ~= "prepared" or not baseline
        or not number(now, 0, MAX) or now - baseline.capturedAt > 15
        or baseline.capturedAt > now + 1 or not same(record.baseline, baseline) then
        return false, "Fresh unchanged prepared recall custody required"
    end
    local nextRecord = copy(record)
    nextRecord.stage, nextRecord.sentServerNow = "sent", baseline.serverNow
    local ok, reason = persist(self, nextRecord)
    if ok then self.emission = true end
    return ok, reason
end
function Methods:SubmitCall(before, now)
    local record = self.saved.transaction
    if not self.emission or not record or record.stage ~= "sent" then
        return nil, "Recall submission unavailable; recovered sent requests are status-only"
    end
    self.emission = false
    local baseline = state(before, self.scope)
    if not baseline or not number(now, 0, MAX)
        or now - baseline.capturedAt > 15 or baseline.capturedAt > now + 1
        or not same(record.baseline, baseline) then
        return nil, "Recall submission custody expired or changed; status only"
    end
    return { remote = "TerritoryAction", method = "InvokeServer", arity = 3,
        args = { "recallcrew", record.requestId, { copy(record.target) } },
        actionKey = record.actionKey, source = "saved CrewRecall after durable sent gate" }, nil
end
function Methods:StatusCall()
    local record = self.saved.transaction
    if not record or (record.stage ~= "sent" and record.stage ~= "settled") then
        return nil, "No owned sent recall to query"
    end
    return { kind = "statusOnly", remote = "TerritoryStatus", method = "InvokeServer", arity = 3,
        args = { "recallstatus", record.requestId }, actionKey = record.actionKey,
        source = "saved CrewRecall status query; unknown_request never resubmits" }, nil
end
function Methods:AcceptReply(requestId, reply)
    local record = self.saved.transaction
    if record and requestId == record.requestId then self.emission = false end
    if not record or record.stage == "prepared" or requestId ~= record.requestId
        or type(reply) ~= "table" or reply.ok ~= true or reply.pending == true
        or reply.code == "unknown_request" or reply.code == "rate_limited"
        or type(reply.settled) ~= "table" or #reply.settled ~= 1
        or not targetMatches(record.target, reply.settled[1]) then
        return false, "Exact settled own deployment reply required; do not resubmit"
    end
    local count = 0
    for slot in pairs(reply.settled) do
        count = count + 1
        if slot ~= 1 then return false, "Ambiguous recall settlements" end
    end
    if count ~= 1 then return false, "Ambiguous recall settlements" end
    if record.stage == "settled" or record.stage == "observed" then return true, nil end
    local nextRecord = copy(record)
    nextRecord.stage, nextRecord.settled = "settled", copy(record.target)
    return persist(self, nextRecord)
end
local function returned(record, current)
    local baseline, slot = record.baseline, tostring(record.target.memberIndex)
    if current.familyId ~= baseline.familyId or current.size ~= baseline.size then return false end
    for index, member in pairs(baseline.members) do
        local after = current.members[index]
        if not after then return false end
        if index ~= slot then
            -- Other features may run after the broker releases its 45s gate.
            -- Preserve roster identity, without attributing their activity to recall.
            if after.name ~= member.name or after.rarity ~= member.rarity then return false end
        else
            for _, field in ipairs(memberFields) do
                if field ~= "duty" and field ~= "token" and field ~= "at"
                    and field ~= "injured" and field ~= "recalled"
                    and after[field] ~= member[field] then return false end
            end
            if after.duty ~= false or after.token ~= false or after.at ~= false then return false end
            if after.recalled > record.sentServerNow then
                if after.injured ~= after.recalled
                    or after.recalled < record.sentServerNow + record.cooldownSeconds
                    or after.recalled > current.serverNow + record.cooldownSeconds then return false end
            elseif (after.recalled ~= 0 and after.recalled ~= member.recalled)
                or (after.injured ~= 0 and after.injured ~= member.injured) then
                return false
            end
        end
    end
    return true
end
function Methods:Reconcile(after)
    local record = self.saved.transaction
    if not record then return "idle", nil end
    if record.stage == "prepared" then return "prepared", "Recall was not durably sent" end
    if record.stage == "observed" then return "observed", nil end
    if record.stage ~= "settled" then return "uncertain", "Settled own deployment reply required; status only" end
    local current = state(after, self.scope)
    local baseline = record.baseline
    if not current or current.serverNow < baseline.serverNow
        or (current.session == baseline.session and current.revision <= baseline.revision)
        or (current.session ~= baseline.session and current.serverNow <= baseline.serverNow) then
        return "waiting", "Newer full own Crew Sync required"
    end
    if not returned(record, current) then return "uncertain", "Recall custody or cooldown ambiguous; do not resubmit" end
    local nextRecord = copy(record)
    nextRecord.stage = "observed"
    local ok, reason = persist(self, nextRecord)
    return ok and "observed" or "uncertain", reason
end
function Methods:ClearObserved()
    if not self.saved.transaction or self.saved.transaction.stage ~= "observed" then
        return false, "Only a final observed recall may be cleared"
    end
    return persist(self, nil)
end

function Methods:DiscardPrepared()
    if not self.saved.transaction or self.saved.transaction.stage ~= "prepared" then
        return false, "Only a known-unsent prepared recall may be discarded"
    end
    return persist(self, nil)
end

return RecallTransactions
