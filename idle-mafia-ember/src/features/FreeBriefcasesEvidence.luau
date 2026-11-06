-- Native reply source plus replicated same-board reveal/free decrement.
local FreeBriefcasesEvidence = {}

local function matching(a, b)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or a[field] ~= b[field] then return false end
    end
    return true
end

local function eventProof(raw)
    local p = type(raw) == "table" and raw.briefcaseProof
    if type(p) ~= "table" or type(p.header) ~= "table" or type(p.sourceKey) ~= "string"
        or #p.sourceKey ~= 64 or not p.sourceKey:match("^[%x]+$") or p.sourceKey ~= raw.catalogKey
        or type(p.sourceGeneration) ~= "number" or p.sourceGeneration % 1 ~= 0 or p.sourceGeneration < 1
        or type(raw.caseEvent) ~= "table" or p.season ~= raw.caseEvent.season or p.endAt ~= raw.caseEvent.endAt
        or type(raw.briefcaseRules) ~= "table" or p.version ~= raw.briefcaseRules.version then return nil end
    for _, k in ipairs({"session", "account", "place", "release", "revision", "capturedAt"}) do
        if p.header[k] ~= raw[k] then return nil end
    end
    return p
end

local function state(raw, baseline, expectedBoard, settlement)
    local native = type(raw) == "table" and raw.native
    local briefcase = type(native) == "table" and native.briefcase
    local board = type(briefcase) == "table" and briefcase.board
    local event = type(raw) == "table" and raw.caseEvent
    local rules = type(raw) == "table" and raw.briefcaseRules
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.serverNow) ~= "number"
        or native.serverNow ~= native.serverNow
        or native.serverNow < 0 or native.serverNow >= math.huge
        or type(briefcase) ~= "table" or type(board) ~= "table"
        or type(board.opened) ~= "table"
        or type(rules) ~= "table" or rules.cases ~= 12
        or board.cfg ~= rules.version
        or briefcase.season ~= baseline.season
        or board.n ~= (expectedBoard or baseline.board)
        or raw.catalogKey ~= baseline.catalogKey
        or type(briefcase.free) ~= "number"
        or briefcase.free ~= briefcase.free
        or briefcase.free % 1 ~= 0 or briefcase.free < 0 then return nil end
    local sameEvent = type(event) == "table" and event.season == baseline.season and event.endAt == baseline.endAt
    if settlement ~= true then
        if not sameEvent or event.endAt - native.serverNow <= 5 then return nil end
    elseif not sameEvent then
        -- Event attributes can disappear before the next genuine Sync. This
        -- observes an owned sent pick; it can never authorize another opening.
        local proof = eventProof(raw)
        if not proof or proof.active ~= false or baseline.eventSourceKey ~= proof.sourceKey
            or baseline.eventSourceKey ~= baseline.catalogKey or native.serverNow < baseline.endAt
            or (proof.season ~= 0 and proof.season ~= baseline.season)
            or (proof.endAt ~= 0 and proof.endAt ~= baseline.endAt) then return nil end
    end
    local prize = board.opened["c" .. baseline.index]
    if prize ~= nil and (type(prize) ~= "table"
        or type(prize.p) ~= "string" or #prize.p == 0) then return nil end
    local opened, count = {}, 0
    for key, row in pairs(board.opened) do
        local index = type(key) == "string"
            and tonumber(key:match("^c(%d+)$"))
        if type(index) ~= "number" or index % 1 ~= 0
            or index < 1 or index > 12 or key ~= "c" .. index
            or type(row) ~= "table" or type(row.p) ~= "string"
            or #row.p == 0 then return nil end
        opened[key] = row.p
        count = count + 1
        if count > 12 then return nil end
    end
    return true, briefcase.free, prize ~= nil, opened, count
end

function FreeBriefcasesEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "briefcases"
        or type(intent) ~= "table" or intent.kind ~= "freeBriefcasePick"
        or intent.command ~= "open" or type(intent.index) ~= "number"
        or intent.index % 1 ~= 0 or intent.index < 1 or intent.index > 12
        or type(intent.free) ~= "number" or intent.free < 1
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Free Briefcase baseline mismatch"
    end
    local valid, free, opened, prizes, count = state(before, intent)
    if not valid or free ~= intent.free or opened then
        return nil, "Selected free Briefcase is no longer ready"
    end
    local proof = eventProof(before)
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, index = intent.index,
        season = intent.season, board = intent.board,
        free = intent.free, endAt = intent.endAt,
        catalogKey = intent.catalogKey,
        eventSourceKey = proof and proof.active == true and proof.sourceKey or nil,
        priorPrizes = prizes, priorCount = count }, nil
end

function FreeBriefcasesEvidence.evaluate(proposal, beforeHeader, after,
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
        or proposal.intent.index ~= baseline.index
        or proposal.intent.season ~= baseline.season
        or proposal.intent.board ~= baseline.board
        or reply.pending == true or reply.code == "rate_limited" or reply.code == "busy"
        or reply.code == "presence" then return "pending" end
    local valid, free, opened, prizes, count = state(after, baseline, nil, true)
    -- Native BriefcasesTab treats an exact cleared reply as advancing to
    -- result.board + 1 (golden prizes can clear before the twelfth reveal).
    if not valid and reply.ok == true and reply.source == "free" and reply.cleared == true
        and reply.board == baseline.board and type(reply.prize) == "string" and #reply.prize > 0
        and #reply.prize <= 120 and not reply.prize:find("[%c]") then
        local nextValid, nextFree, nextOpened, _, nextCount = state(after, baseline, baseline.board + 1, true)
        if nextValid and nextFree == baseline.free - 1 and not nextOpened and nextCount == 0
            and type(after.revision) == "number" and after.revision > baseline.revision then return "confirmed" end
    end
    if not valid then return "pending" end
    local unchanged = type(baseline.priorPrizes) == "table"
        and type(baseline.priorCount) == "number"
        and count == baseline.priorCount + 1
    if unchanged then
        for key, prize in pairs(baseline.priorPrizes) do
            if prizes[key] ~= prize then unchanged = false; break end
        end
    end
    local advanced = type(after.revision) == "number"
        and after.revision > baseline.revision
        and free == baseline.free - 1 and opened and unchanged
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and reply.source == "free" and advanced then
        return "confirmed"
    end
    return "pending"
end

return FreeBriefcasesEvidence
