-- Exact bonus marker and unchanged prerequisite rows, before reset.
local ContractBonusesEvidence = {}

local function matching(a, b)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or a[field] ~= b[field] then return false end
    end
    return true
end

local function state(raw, baseline)
    local native = type(raw) == "table" and raw.native
    local contracts = type(native) == "table" and native.contracts
    local derived = type(native) == "table" and native.derived
    if type(native) ~= "table" or native.fullSync ~= true
        or type(contracts) ~= "table" or type(derived) ~= "table"
        or type(native.serverNow) ~= "number"
        or native.serverNow ~= native.serverNow
        or native.serverNow < 0 or native.serverNow >= math.huge
        or raw.catalogKey ~= baseline.catalogKey then return nil end
    local reset = baseline.period == "daily" and derived.contractDayReset
        or derived.contractWeekReset
    if reset ~= baseline.reset or reset - native.serverNow <= 5 then return nil end
    local rows = contracts[baseline.period]
    if baseline.period == "weekly" and type(rows) == "table"
        and rows.id ~= nil then rows = { rows } end
    if type(rows) ~= "table" then return nil end
    local rowKey = tostring(#rows) .. ":"
    for index = 1, #rows do
        local row = rows[index]
        if type(row) ~= "table" or type(row.id) ~= "string"
            or #row.id == 0 or row.claimed ~= true then return nil end
        rowKey = rowKey .. #row.id .. ":" .. row.id .. ";"
    end
    if rowKey ~= baseline.rowKey then return nil end
    local marker
    if baseline.period == "daily" then marker = contracts.bonusClaimed
    else marker = contracts.weeklyBonusClaimed end
    if marker ~= nil and type(marker) ~= "boolean" then return nil end
    return true, marker == true
end

function ContractBonusesEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "bonuses"
        or type(intent) ~= "table" or intent.kind ~= "contractBonusClaim"
        or (intent.period ~= "daily" and intent.period ~= "weekly")
        or intent.command ~= (intent.period == "daily" and "claimbonus"
            or "claimweeklybonus")
        or type(intent.rowKey) ~= "string" or #intent.rowKey == 0
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Contract bonus baseline mismatch"
    end
    local valid, claimed = state(before, intent)
    if not valid or claimed then
        return nil, "Contract bonus is not replicated ready"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, period = intent.period,
        reset = intent.reset, catalogKey = intent.catalogKey,
        rowKey = intent.rowKey }, nil
end

function ContractBonusesEvidence.evaluate(proposal, beforeHeader, after,
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
        or proposal.intent.reset ~= baseline.reset
        or type(after.revision) ~= "number" or after.revision ~= after.revision
        or after.revision >= math.huge or after.revision % 1 ~= 0
        or after.revision <= baseline.revision
        or reply.pending == true or reply.code == "pending" or reply.code == "no_pending"
        or reply.code == "rate_limited" or reply.code == "busy" or reply.code == "presence" then return "pending" end
    local valid, claimed = state(after, baseline)
    if not valid then return "pending" end
    local advanced = type(after.revision) == "number"
        and after.revision > baseline.revision and claimed
    if reply.ok == false then return advanced and "pending" or "rejected" end
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
local function clock(value) return type(value) == "number" and value == value and value >= 0 and value < math.huge end

-- The whole original Contract set must remain identical except for this
-- successful bonus marker; a new row/reset cannot settle an old receipt.
function ContractBonusesEvidence.recoverSaved(data, after)
    local reply = type(data) == "table" and data.reply
    if type(reply) ~= "table" or type(reply.ok) ~= "boolean" or reply.pending == true
        or reply.code == "pending" or reply.code == "no_pending" or reply.code == "rate_limited"
        or reply.code == "busy" or reply.code == "presence" or type(after) ~= "table" then return nil end
    local p, before = data.proposal, data.before
    local baseline = ContractBonusesEvidence.capture(p, before)
    if not baseline or not equal(baseline, data.baseline) or not matching(p, before)
        or type(after.session) ~= "string" or #after.session == 0
        or type(after.native) ~= "table" or not clock(before.native.serverNow)
        or not clock(after.native.serverNow) or after.native.serverNow <= before.native.serverNow
        or not clock(after.revision) or after.revision % 1 ~= 0
        or after.session == baseline.session and (after.revision <= baseline.revision
            or not clock(after.capturedAt) or after.capturedAt < before.capturedAt)
        or type(p.resources) ~= "table"
        or p.actionKey ~= "contract-bonus:" .. baseline.period .. ":" .. baseline.reset then return nil end
    for _, field in ipairs({"account", "place", "release"}) do if after[field] ~= p[field] then return nil end end
    for _, amount in pairs(p.resources) do if amount ~= 0 then return nil end end
    local valid, claimed = state(after, baseline)
    if not valid or claimed ~= reply.ok then return nil end
    local expected = {}
    for key, value in pairs(before.native.contracts) do expected[key] = value end
    if reply.ok then expected[baseline.period == "daily" and "bonusClaimed" or "weeklyBonusClaimed"] = true end
    if not equal(expected, after.native.contracts) then return nil end
    return reply.ok and "confirmed" or "rejected"
end

return ContractBonusesEvidence
