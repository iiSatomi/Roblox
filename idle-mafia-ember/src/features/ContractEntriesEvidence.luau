-- Selected entry must become claimed before its same reset; reply alone is weak.
local ContractEntriesEvidence = {}

local function matching(a, b)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or a[field] ~= b[field] then return false end
    end
    return true
end

local function rowState(raw, intent)
    local native = type(raw) == "table" and raw.native
    local contracts = type(native) == "table" and native.contracts
    local derived = type(native) == "table" and native.derived
    if type(native) ~= "table" or native.fullSync ~= true
        or type(contracts) ~= "table" or type(derived) ~= "table"
        or type(native.serverNow) ~= "number"
        or native.serverNow ~= native.serverNow
        or native.serverNow >= math.huge
        or native.serverNow < 0
        or raw.catalogKey ~= intent.catalogKey then return nil end
    local reset = intent.period == "daily" and derived.contractDayReset
        or derived.contractWeekReset
    if reset ~= intent.reset or reset - native.serverNow <= 5 then return nil end
    local rows = contracts[intent.period]
    if intent.period == "weekly" and type(rows) == "table"
        and rows.id ~= nil then rows = { rows } end
    local row = type(rows) == "table" and rows[intent.index]
    if type(row) ~= "table" or row.id ~= intent.rowId
        or type(row.done) ~= "boolean"
        or type(row.claimed) ~= "boolean" then return nil end
    return row.done, row.claimed
end

function ContractEntriesEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "contracts"
        or type(intent) ~= "table" or intent.kind ~= "contractEntryClaim"
        or (intent.period ~= "daily" and intent.period ~= "weekly")
        or type(intent.index) ~= "number" or intent.index % 1 ~= 0
        or intent.index < 1 or intent.index > 5
        or type(intent.rowId) ~= "string" or #intent.rowId == 0
        or intent.command ~= (intent.period == "daily" and "claim" or "claimweekly")
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Contract claim baseline mismatch"
    end
    local done, claimed = rowState(before, intent)
    if done ~= true or claimed ~= false then
        return nil, "Selected Contract row is not replicated ready"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, period = intent.period,
        index = intent.index, rowId = intent.rowId,
        reset = intent.reset, catalogKey = intent.catalogKey }, nil
end

function ContractEntriesEvidence.evaluate(proposal, beforeHeader, after,
    reply, baseline)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table"
        or type(after) ~= "table" or type(reply) ~= "table"
        or type(baseline) ~= "table"
        or not matching(proposal, beforeHeader)
        or not matching(proposal, after)
        or not matching(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision
        or type(proposal.intent) ~= "table"
        or proposal.intent.period ~= baseline.period
        or proposal.intent.index ~= baseline.index
        or proposal.intent.rowId ~= baseline.rowId
        or proposal.intent.reset ~= baseline.reset
        or type(after.revision) ~= "number" or after.revision ~= after.revision
        or after.revision >= math.huge or after.revision % 1 ~= 0
        or after.revision <= baseline.revision
        or reply.pending == true or reply.code == "pending" or reply.code == "no_pending"
        or reply.code == "rate_limited" or reply.code == "busy" or reply.code == "presence" then return "pending" end
    local done, claimed = rowState(after, baseline)
    if claimed == nil then return "pending" end
    local advanced = type(after.revision) == "number"
        and after.revision > baseline.revision and claimed == true
    if reply.ok == false then return done == true and claimed == false and "rejected" or "pending" end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

local function equal(a, b, depth)
    if type(a) ~= type(b) or (depth or 0) > 16 then return false end
    if type(a) ~= "table" then return a == b end
    if getmetatable(a) ~= nil or getmetatable(b) ~= nil then return false end
    local count = 0
    for key, value in pairs(a) do
        count = count + 1
        if count > 512 or not equal(value, b[key], (depth or 0) + 1) then return false end
    end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
local function copy(value) local out = {}; for key, child in pairs(value) do out[key] = child end; return out end
local function clock(value) return type(value) == "number" and value == value and value >= 0 and value < math.huge end

-- Reuse the immutable original row and baseline; never infer a claim from a
-- replacement Contract set or change the saved session/revision to this load.
function ContractEntriesEvidence.recoverSaved(data, after)
    local reply = type(data) == "table" and data.reply
    if type(reply) ~= "table" or type(reply.ok) ~= "boolean" or reply.pending == true
        or reply.code == "pending" or reply.code == "no_pending" or reply.code == "rate_limited"
        or reply.code == "busy" or reply.code == "presence" or type(after) ~= "table" then return nil end
    local p, before = data.proposal, data.before
    local baseline = ContractEntriesEvidence.capture(p, before)
    if not baseline or not equal(baseline, data.baseline) or not matching(p, before)
        or type(after.session) ~= "string" or #after.session == 0
        or type(after.native) ~= "table" or not clock(before.native.serverNow)
        or not clock(after.native.serverNow) or after.native.serverNow <= before.native.serverNow
        or not clock(after.revision) or after.revision % 1 ~= 0
        or after.session == baseline.session and (after.revision <= baseline.revision
            or not clock(after.capturedAt) or after.capturedAt < before.capturedAt)
        or type(p.resources) ~= "table"
        or p.actionKey ~= "contract:" .. baseline.period .. ":" .. baseline.reset .. ":"
            .. baseline.index .. ":" .. #baseline.rowId .. ":" .. baseline.rowId then return nil end
    for _, field in ipairs({"account", "place", "release"}) do if after[field] ~= p[field] then return nil end end
    for _, amount in pairs(p.resources) do if amount ~= 0 then return nil end end
    local done, claimed = rowState(after, baseline)
    if done ~= true or claimed ~= reply.ok then return nil end
    local expected = copy(before.native.contracts)
    if reply.ok then
        local rows = expected[baseline.period]
        if baseline.period == "weekly" and rows.id ~= nil then
            rows = copy(rows); rows.claimed = true
        else
            rows = copy(rows); local row = copy(rows[baseline.index]); row.claimed = true
            rows[baseline.index] = row
        end
        expected[baseline.period] = rows
    end
    if not equal(expected, after.native.contracts) then return nil end
    return reply.ok and "confirmed" or "rejected"
end

return ContractEntriesEvidence
