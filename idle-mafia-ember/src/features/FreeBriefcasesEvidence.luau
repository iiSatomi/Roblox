-- Native reply source plus replicated same-board reveal/free decrement.
local FreeBriefcasesEvidence = {}

local function matching(a, b)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or a[field] ~= b[field] then return false end
    end
    return true
end

local function state(raw, baseline)
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
        or type(event) ~= "table" or event.season ~= baseline.season
        or event.endAt ~= baseline.endAt
        or event.endAt - native.serverNow <= 5
        or briefcase.season ~= baseline.season
        or board.n ~= baseline.board
        or raw.catalogKey ~= baseline.catalogKey
        or type(briefcase.free) ~= "number"
        or briefcase.free ~= briefcase.free
        or briefcase.free % 1 ~= 0 or briefcase.free < 0 then return nil end
    local prize = board.opened["c" .. baseline.index]
    if prize ~= nil and (type(prize) ~= "table"
        or type(prize.p) ~= "string" or #prize.p == 0) then return nil end
    return true, briefcase.free, prize ~= nil
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
    local valid, free, opened = state(before, intent)
    if not valid or free ~= intent.free or opened then
        return nil, "Selected free Briefcase is no longer ready"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, index = intent.index,
        season = intent.season, board = intent.board,
        free = intent.free, endAt = intent.endAt,
        catalogKey = intent.catalogKey }, nil
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
        or proposal.intent.board ~= baseline.board then return "pending" end
    local valid, free, opened = state(after, baseline)
    if not valid then return "pending" end
    local advanced = type(after.revision) == "number"
        and after.revision > baseline.revision
        and free == baseline.free - 1 and opened
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and reply.source == "free" and advanced then
        return "confirmed"
    end
    return "pending"
end

return FreeBriefcasesEvidence
