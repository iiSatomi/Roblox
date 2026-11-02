-- A newer same-day claimed-tier marker confirms the selected ladder claim.
local PlaytimeEvidence = {}

local function matching(a, b)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or a[field] ~= b[field] then return false end
    end
    return true
end

local function state(raw, index, day)
    local native = type(raw) == "table" and raw.native
    local playtime = type(native) == "table" and native.playtime
    local claimed = type(playtime) == "table"
        and (playtime.laddersClaimed or {})
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.serverNow) ~= "number"
        or native.serverNow ~= native.serverNow
        or native.serverNow < 0 or native.serverNow >= math.huge
        or type(playtime) ~= "table"
        or type(playtime.todaySeconds) ~= "number"
        or playtime.todaySeconds < 0
        or playtime.todaySeconds >= math.huge
        or type(claimed) ~= "table" then return nil end
    local dateOk, dateText = pcall(os.date, "!%Y%j",
        math.floor(native.serverNow))
    if not dateOk or tonumber(dateText) ~= day then return nil end
    local marker = claimed[tostring(index)]
    if marker ~= nil and (type(marker) ~= "number" or marker < 1
        or marker > 4 or marker % 1 ~= 0) then return nil end
    return true, marker, playtime.todaySeconds
end

function PlaytimeEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "playtime"
        or type(intent) ~= "table" or intent.kind ~= "playtimeClaim"
        or type(intent.index) ~= "number" or intent.index % 1 ~= 0
        or intent.index < 1 or intent.index > 7
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision
        or intent.catalogKey ~= before.catalogKey then
        return nil, "Playtime claim baseline mismatch"
    end
    local valid, marker, seconds = state(before, intent.index, intent.day)
    local rung = type(before.ladderCatalog) == "table"
        and before.ladderCatalog[intent.index]
    if not valid or marker ~= nil or type(rung) ~= "table"
        or type(rung.seconds) ~= "number" or seconds < rung.seconds then
        return nil, "Selected ladder rung is not replicated ready"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, serverNow = before.native.serverNow, catalogKey = intent.catalogKey,
        day = intent.day, index = intent.index }, nil
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
        or reply.pending == true or reply.code == "rate_limited" or reply.code == "presence"
        or not matching(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision
        or type(proposal.intent) ~= "table"
        or proposal.intent.index ~= baseline.index
        or proposal.intent.day ~= baseline.day
        or after.catalogKey ~= baseline.catalogKey then return "pending" end
    local valid, marker = state(after, baseline.index, baseline.day)
    if not valid then return "pending" end
    local advanced = marker ~= nil
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and reply.pending ~= true and reply.code ~= "rate_limited"
        and advanced then return "confirmed" end
    return "pending"
end

function PlaytimeEvidence.evaluate(proposal, before, after, reply, baseline)
    return reconcile(proposal, before, after, reply, baseline, false)
end
function PlaytimeEvidence.recoverSaved(data, after)
    if type(data) ~= "table" or type(data.reply) ~= "table" or type(data.baseline) ~= "table" then return nil end
    local baseline = PlaytimeEvidence.capture(data.proposal, data.before)
    if not baseline then return nil end
    for key, value in pairs(baseline) do if data.baseline[key] ~= value then return nil end end
    for key in pairs(data.baseline) do if baseline[key] == nil then return nil end end
    local outcome = reconcile(data.proposal, data.before, after, data.reply, baseline, true)
    return (outcome == "confirmed" or outcome == "rejected") and outcome or nil
end

return PlaytimeEvidence
