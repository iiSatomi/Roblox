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
        or proposal.intent.reset ~= baseline.reset then return "pending" end
    local valid, claimed = state(after, baseline)
    if not valid then return "pending" end
    local advanced = type(after.revision) == "number"
        and after.revision > baseline.revision and claimed
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

return ContractBonusesEvidence
