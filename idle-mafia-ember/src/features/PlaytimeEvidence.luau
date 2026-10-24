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
        or tonumber(os.date("!%Y%j", native.serverNow)) ~= day
        or type(playtime) ~= "table"
        or type(playtime.todaySeconds) ~= "number"
        or playtime.todaySeconds < 0
        or playtime.todaySeconds >= math.huge
        or type(claimed) ~= "table" then return nil end
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
        revision = proposal.revision, catalogKey = intent.catalogKey,
        day = intent.day, index = intent.index }, nil
end

function PlaytimeEvidence.evaluate(proposal, beforeHeader, after, reply, baseline)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table"
        or type(after) ~= "table" or type(reply) ~= "table"
        or type(baseline) ~= "table"
        or not matching(proposal, beforeHeader)
        or not matching(proposal, after)
        or not matching(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision
        or type(proposal.intent) ~= "table"
        or proposal.intent.index ~= baseline.index
        or proposal.intent.day ~= baseline.day
        or after.catalogKey ~= baseline.catalogKey then return "pending" end
    local valid, marker = state(after, baseline.index, baseline.day)
    if not valid then return "pending" end
    local advanced = type(after.revision) == "number"
        and after.revision > baseline.revision and marker ~= nil
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

return PlaytimeEvidence
