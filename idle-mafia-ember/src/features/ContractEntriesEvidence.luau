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
        or proposal.intent.reset ~= baseline.reset then return "pending" end
    local _, claimed = rowState(after, baseline)
    if claimed == nil then return "pending" end
    local advanced = type(after.revision) == "number"
        and after.revision > baseline.revision and claimed == true
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

return ContractEntriesEvidence
