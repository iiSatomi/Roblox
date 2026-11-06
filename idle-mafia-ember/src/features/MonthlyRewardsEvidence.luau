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
        or native.serverNow ~= native.serverNow
        or native.serverNow < 0 or native.serverNow >= math.huge then
        return nil
    end
    local dateOk, dayText, monthText = pcall(function()
        local second = math.floor(native.serverNow)
        return os.date("!%Y%j", second),
            os.date("!%Y-%m", second)
    end)
    if not dateOk or tonumber(dayText) ~= today
        or monthText ~= month then return nil end
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
        revision = proposal.revision, serverNow = before.native.serverNow, month = intent.month,
        today = intent.today, claimed = claimed, lastDay = lastDay }, nil
end

local function reconcile(proposal, beforeHeader, after, reply, baseline, restart)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table"
        or type(after) ~= "table" or type(reply) ~= "table"
        or type(baseline) ~= "table"
        or not matching(proposal, beforeHeader)
        or after.account ~= proposal.account or after.place ~= proposal.place or after.release ~= proposal.release
        or (not restart and after.session ~= proposal.session)
        or type(after.revision) ~= "number" or after.revision % 1 ~= 0
        or type(after.native) ~= "table" or type(after.native.serverNow) ~= "number"
        or type(baseline.serverNow) ~= "number" or after.native.serverNow < baseline.serverNow
        or not (after.session == baseline.session and after.revision > baseline.revision
            or restart and after.session ~= baseline.session and after.native.serverNow > baseline.serverNow)
        or reply.pending == true or reply.code == "pending" or reply.code == "busy"
        or reply.code == "rate_limited" or reply.code == "presence"
        or not matching(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision
        or type(proposal.intent) ~= "table"
        or proposal.intent.month ~= baseline.month
        or proposal.intent.today ~= baseline.today then return "pending" end
    local claimed, lastDay = state(after, baseline.month, baseline.today)
    if not claimed then return "pending" end
    local advanced = claimed == baseline.claimed + 1 and lastDay == baseline.today
    if reply.ok == false then return claimed == baseline.claimed and lastDay == baseline.lastDay and "rejected" or "pending" end
    if reply.ok == true and reply.pending ~= true and reply.code ~= "rate_limited"
        and advanced then return "confirmed" end
    return "pending"
end

function MonthlyRewardsEvidence.evaluate(proposal, before, after, reply, baseline)
    return reconcile(proposal, before, after, reply, baseline, false)
end
function MonthlyRewardsEvidence.recoverSaved(data, after)
    if type(data) ~= "table" or type(data.reply) ~= "table" or type(data.baseline) ~= "table" then return nil end
    local baseline = MonthlyRewardsEvidence.capture(data.proposal, data.before)
    if not baseline then return nil end
    for key, value in pairs(baseline) do if data.baseline[key] ~= value then return nil end end
    for key in pairs(data.baseline) do if baseline[key] == nil then return nil end end
    local outcome = reconcile(data.proposal, data.before, after, data.reply, baseline, true)
    return (outcome == "confirmed" or outcome == "rejected") and outcome or nil
end

return MonthlyRewardsEvidence
