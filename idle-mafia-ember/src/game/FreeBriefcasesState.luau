-- First unopened Briefcase only when native free picks are replicated.
local FreeBriefcasesState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function openedMap(opened, cases)
    if type(opened) ~= "table" then return nil end
    local selected = nil
    local occupied = {}
    for key, prize in pairs(opened) do
        local index = type(key) == "string" and tonumber(key:match("^c(%d+)$"))
        if not integer(index, 1) or index > cases or key ~= "c" .. index
            or type(prize) ~= "table" or type(prize.p) ~= "string"
            or #prize.p == 0 then return nil end
        occupied[index] = true
    end
    for index = 1, cases do
        if not occupied[index] then selected = index; break end
    end
    return selected
end

function FreeBriefcasesState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Briefcase state or context"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Briefcase snapshot header changed"
        end
    end
    local native = raw.native
    local rules, event = raw.briefcaseRules, raw.caseEvent
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.briefcase) ~= "table"
        or type(rules) ~= "table" or rules.cases ~= 12
        or not integer(rules.version, 0)
        or type(event) ~= "table"
        or not integer(event.season, 1)
        or not integer(event.endAt, 1)
        or type(raw.catalogKey) ~= "string" or #raw.catalogKey == 0 then
        return nil, "Current Briefcase rules and event required"
    end
    local now = context.serverNow
    local state, board = native.briefcase, native.briefcase.board
    if not integer(now, 0) or native.serverNow ~= now
        or event.endAt - now <= 5
        or state.season ~= event.season
        or not integer(state.free, 1)
        or type(board) ~= "table" or not integer(board.n, 1)
        or board.cfg ~= rules.version then
        return nil, "Replicated active free Briefcase board required"
    end
    local index = openedMap(board.opened, rules.cases)
    if not index then return nil, "No unopened Briefcase on current board" end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        catalogKey = raw.catalogKey, season = event.season,
        board = board.n, free = state.free, index = index,
        endAt = event.endAt }, nil
end

return FreeBriefcasesState
