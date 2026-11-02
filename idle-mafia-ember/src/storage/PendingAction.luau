-- Data for reconciliation only. Never serializes a callback, capability or replay arm.
local PendingAction = {}
local MAX = 9007199254740991
local identity = {"session", "account", "place", "release"}
local function finite(value) return type(value) == "number" and value == value and math.abs(value) <= MAX end
local function text(value) return type(value) == "string" and #value > 0 and #value <= 1000 end
local function convert(value, decode)
    local seen, nodes, bytes = {}, 0, 0
    local function walk(child, depth)
        nodes = nodes + 1
        if nodes > 24000 or depth > 12 then error("Recovery data exceeds node/depth limit") end
        local kind = type(child)
        if kind == "string" then
            bytes = bytes + #child
            if #child > 16384 then error("Recovery string too large") end
        elseif kind == "number" then
            if not finite(child) then error("Recovery number invalid") end
            bytes = bytes + #tostring(child)
        elseif kind ~= "boolean" and kind ~= "table" then error("Recovery value invalid") end
        if bytes > 262144 then error("Recovery data exceeds byte limit") end
        if kind ~= "table" then return child end
        if seen[child] or getmetatable(child) ~= nil then error("Recovery table invalid") end
        seen[child] = true
        local source, output = child, {}
        if decode then
            if type(child.entries) ~= "table" then error("Recovery encoding invalid") end
            for field in pairs(child) do if field ~= "entries" then error("Unknown recovery encoding field") end end
            source = child.entries
        end
        for key, entry in pairs(source) do
            local encoded, restored
            if decode then
                if type(key) ~= "string" or #key > 1002 then error("Invalid encoded recovery key") end
                local prefix, raw = key:sub(1, 2), key:sub(3)
                if prefix == "s:" then restored = raw
                elseif prefix == "n:" then
                    restored = tonumber(raw)
                    if not finite(restored) or restored % 1 ~= 0 or tostring(restored) ~= raw then error("Invalid numeric recovery key") end
                else error("Unknown recovery key kind") end
                encoded = key
            elseif type(key) == "string" and #key <= 1000 then encoded = "s:" .. key
            elseif finite(key) and key % 1 == 0 then encoded = "n:" .. tostring(key)
            else error("Recovery key invalid") end
            bytes = bytes + #encoded + 16 -- Includes conservative JSON wrapper overhead.
            if bytes > 262144 then error("Recovery data exceeds byte limit") end
            output[decode and restored or encoded] = walk(entry, depth + 1)
        end
        seen[child] = nil
        return decode and output or {entries = output}
    end
    local ok, result = pcall(walk, value, 0)
    return ok and result or nil
end
local function valid(data, record)
    if type(data) ~= "table" or type(data.proposal) ~= "table" or type(data.before) ~= "table"
        or type(data.baseline) ~= "table" then return false end
    for key in pairs(data) do if key ~= "proposal" and key ~= "before" and key ~= "baseline" and key ~= "reply" then return false end end
    if data.reply ~= nil and type(data.reply) ~= "table" then return false end
    local proposal, before = data.proposal, data.before
    if proposal.requestId ~= nil and (not finite(proposal.requestId)
        or proposal.requestId < 1 or proposal.requestId % 1 ~= 0) then return false end
    for _, key in ipairs(identity) do
        if not text(proposal[key]) or proposal[key] ~= before[key] then return false end
    end
    if not finite(proposal.revision) or proposal.revision < 0 or proposal.revision % 1 ~= 0
        or proposal.revision ~= before.revision or not finite(before.capturedAt) or before.capturedAt < 0
        or type(before.native) ~= "table" or before.native.fullSync ~= true
        or not text(proposal.feature) or not text(proposal.actionKey)
        or type(proposal.intent) ~= "table" or not text(proposal.intent.kind)
        or type(proposal.resources) ~= "table" then return false end
    for key, value in pairs(proposal.intent) do
        if not text(key) or (type(value) ~= "string" and type(value) ~= "boolean" and not finite(value)) then return false end
    end
    for key, amount in pairs(proposal.resources) do if not text(key) or not finite(amount) or amount < 0 then return false end end
    if record then
        if proposal.requestId ~= record.requestId then return false end
        for _, key in ipairs({"account", "place", "release", "feature", "actionKey"}) do
            if proposal[key] ~= record[key] then return false end
        end
        if type(record.resources) ~= "table" then return false end
        for key, amount in pairs(proposal.resources) do if record.resources[key] ~= amount then return false end end
        for key, amount in pairs(record.resources) do if proposal.resources[key] ~= amount then return false end end
    end
    return true
end
-- Target catalogs are selection data, not durable outcome evidence. Keep only
-- this action's high-only membership; current full history stays in the live owner.
local function recoveryBefore(proposal, before)
    local ledger = type(before) == "table" and before.playerFightHistoryProof
    if type(ledger) ~= "table" or ledger.highValue == nil or getmetatable(before) ~= nil or getmetatable(ledger) ~= nil then return before end
    local saved, history = {}, {}
    for key, value in pairs(before) do saved[key] = value end
    for key, value in pairs(ledger) do if key ~= "highValue" then history[key] = value end end
    saved.playerFightHistoryProof = history
    local intent, high = proposal.intent, ledger.highValue
    if proposal.feature == "combat" and type(intent) == "table" and intent.highValueOnly == true
        and (intent.kind == "playerAttack" or intent.kind == "playerScout")
        and finite(intent.target) and intent.target >= 1 and intent.target % 1 == 0 then
        local targets = type(high) == "table" and high.targets
        local target = type(targets) == "table" and targets[tostring(intent.target)]
        history.highValue = {known = type(high) == "table" and high.known == true, targets = {}}
        if type(target) == "table" then history.highValue.targets[tostring(intent.target)] = {userId = target.userId} end
    end
    return saved
end
function PendingAction.Capture(proposal, before, baseline, reply)
    if type(proposal) ~= "table" then return nil, "Recovery proposal required" end
    local request = {}
    for _, key in ipairs({"session", "account", "place", "release", "revision", "feature", "actionKey", "resources", "intent", "requestId"}) do
        request[key] = proposal[key]
    end
    local data = {proposal = request, before = recoveryBefore(request, before), baseline = baseline, reply = reply}
    if not valid(data) then return nil, "Complete recovery intent and baseline required" end
    local encoded = convert(data, false)
    if not encoded then return nil, "Recovery data invalid or exceeds bounded storage" end
    return {version = 1, payload = encoded}, nil
end
function PendingAction.Decode(raw, record)
    if type(raw) ~= "table" or raw.version ~= 1 then return nil end
    for key in pairs(raw) do if key ~= "version" and key ~= "payload" then return nil end end
    local data = convert(raw.payload, true)
    if not data or not valid(data, record) then return nil end
    return data
end
function PendingAction.Copy(raw, record)
    local data = PendingAction.Decode(raw, record)
    if not data then return nil end
    return PendingAction.Capture(data.proposal, data.before, data.baseline, data.reply)
end
local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not equal(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
function PendingAction.WithReply(raw, record, reply)
    local data = PendingAction.Decode(raw, record)
    if not data or type(reply) ~= "table" then return nil, "Original pending data and table result required" end
    -- Validate/copy before comparison so cycles and capabilities cannot enter it.
    local encoded, reason = PendingAction.Capture(data.proposal, data.before, data.baseline, reply)
    if not encoded then return nil, reason end
    local candidate = PendingAction.Decode(encoded, record)
    if not candidate then return nil, "Returned result could not be decoded" end
    if data.reply ~= nil and not equal(data.reply, candidate.reply) then return nil, "A different result is already recorded" end
    return encoded, nil
end
function PendingAction.Same(first, second, record)
    local a, b = PendingAction.Decode(first, record), PendingAction.Decode(second, record)
    return a ~= nil and b ~= nil and equal(a, b)
end
return PendingAction
