-- Native collect addresses the controller's exact current result, not a run ID.
local HeistCollect = {}
local MAX = 9007199254740991
local function integer(value, minimum)
    return type(value) == "number" and value == value and value >= minimum
        and value <= MAX and value % 1 == 0
end
local function text(value)
    return type(value) == "string" and #value > 0 and #value <= 120 and not value:find("[%c]")
end
local function hash(value)
    return type(value) == "string" and #value == 64 and value:match("^[%x]+$") ~= nil
end
local function rewards(result)
    if type(result) ~= "table" or not text(result.heistId) or type(result.ok) ~= "boolean" then return false end
    for _, field in ipairs({"cash", "xp", "gold", "crates", "bonusCrates"}) do
        local value = result[field]
        if result.ok then
            if not integer(value, 0) then return false end
        elseif value ~= nil and value ~= 0 then return false end
    end
    for _, pair in ipairs({{"crateId", "crates"}, {"bonusCrateId", "bonusCrates"}}) do
        local id, amount = result[pair[1]], result[pair[2]]
        if id ~= nil and not text(id) or amount ~= nil and amount > 0 and not text(id) then return false end
    end
    return true
end

function HeistCollect.propose(view, settings)
    if type(settings) ~= "table" or settings.enabled ~= true then
        return nil, "Heist result collection disabled"
    end
    if type(view) ~= "table" or view.state ~= "result" then
        return nil, "No personal Heist result ready"
    end
    if view.resultAddressable ~= true then
        return nil, "Result identity unverified; collect manually"
    end
    local protocol = view.protocol
    local quote = type(protocol) == "table" and protocol.quote
    if type(quote) ~= "table" or not integer(quote.sequence, 1)
        or not integer(protocol.controllerCounter, 0) or quote.sequence ~= protocol.controllerCounter + 1
        or not text(quote.nativeJob) or not text(quote.nativeEpoch) or not hash(quote.nativeSourceKey)
        or quote.nativeJob ~= protocol.nativeJob or quote.nativeEpoch ~= protocol.nativeEpoch
        or quote.nativeSourceKey ~= protocol.nativeSourceKey then
        return nil, "Heist mutation sequence ownership unverified"
    end
    if not hash(protocol.resultKey) or view.resultKey ~= protocol.resultKey then
        return nil, "Exact native Heist result identity required"
    end
    if not rewards(view.result) then return nil, "Complete native Heist reward quote required" end
    return {session = view.session, account = view.account, place = view.place,
        release = view.release, revision = view.revision, feature = "heistCollect",
        actionKey = "heistCollect:" .. #quote.nativeJob .. ":" .. quote.nativeJob .. ":"
            .. #quote.nativeEpoch .. ":" .. quote.nativeEpoch .. ":" .. tostring(quote.sequence)
            .. ":" .. protocol.resultKey,
        resources = {}, intent = {kind = "heistCollect", sequence = quote.sequence,
            nativeJob = quote.nativeJob, nativeEpoch = quote.nativeEpoch,
            nativeSourceKey = quote.nativeSourceKey, resultKey = protocol.resultKey}}, nil
end

return HeistCollect
