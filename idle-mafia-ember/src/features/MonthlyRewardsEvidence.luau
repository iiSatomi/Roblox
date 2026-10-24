-- Claim proof is the exact newer monthly marker within the same UTC day.
local MonthlyRewardsEvidence = {}

local function matching(a, b)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or a[field] ~= b[field] then return false end
    end
    return true
end

local function state(raw, month, today)
    local native = type(raw) == "table" and raw.native
    local record = type(native) == "table" and native.monthly
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.serverNow) ~= "number"
        or tonumber(os.date("!%Y%j", native.serverNow)) ~= today
        or os.date("!%Y-%m", native.serverNow) ~= month then return nil end
    if record == nil then return 0, nil end
    if type(record) ~= "table" then return nil end
    if record.month ~= month then return 0, nil end
    if type(record.claimed) ~= "number" or record.claimed < 0
        or record.claimed % 1 ~= 0 then return nil end
    return record.claimed, record.lastDay
end

function MonthlyRewardsEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "monthlyRewards"
        or type(intent) ~= "table" or intent.kind ~= "monthlyClaim"
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision
        or type(before.monthlyConfig) ~= "table"
        or before.monthlyConfig.enabled ~= true then
        return nil, "Monthly claim baseline mismatch"
    end
    local claimed, lastDay = state(before, intent.month, intent.today)
    if not claimed or claimed + 1 ~= intent.nextDay
        or lastDay == intent.today then
        return nil, "Monthly claim is no longer ready"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, month = intent.month,
        today = intent.today, claimed = claimed }, nil
end

function MonthlyRewardsEvidence.evaluate(proposal, beforeHeader, after,
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
        or proposal.intent.month ~= baseline.month
        or proposal.intent.today ~= baseline.today then return "pending" end
    local claimed, lastDay = state(after, baseline.month, baseline.today)
    if not claimed then return "pending" end
    local advanced = type(after.revision) == "number"
        and after.revision > baseline.revision
        and claimed == baseline.claimed + 1 and lastDay == baseline.today
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

return MonthlyRewardsEvidence
