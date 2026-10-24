-- Shared request headers only. Feature readers own game-specific state.
local Contracts = {}

local identityKeys = { "session", "account", "place", "release" }

local function finite(value)
    return type(value) == "number" and value == value
        and value > -math.huge and value < math.huge
end

local function nonempty(value)
    return type(value) == "string" and #value > 0
end

local function revision(value)
    return finite(value) and value >= 0 and value % 1 == 0
end

function Contracts.validateSnapshot(raw, expectedSession)
    if type(raw) ~= "table" or type(expectedSession) ~= "table" then
        return nil, "Missing snapshot or expected session"
    end
    local view = {}
    for _, key in ipairs(identityKeys) do
        if not nonempty(raw[key]) or raw[key] ~= expectedSession[key] then
            return nil, "Snapshot " .. key .. " mismatch"
        end
        view[key] = raw[key]
    end
    if not revision(raw.revision) then return nil, "Invalid snapshot revision" end
    if not finite(raw.capturedAt) or raw.capturedAt < 0 then
        return nil, "Invalid snapshot capture time"
    end
    view.revision, view.capturedAt = raw.revision, raw.capturedAt
    return view, nil
end

function Contracts.validateProposal(raw, snapshot)
    if type(raw) ~= "table" or type(snapshot) ~= "table" then
        return nil, "Missing proposal or snapshot"
    end
    local view = {}
    for _, key in ipairs(identityKeys) do
        if not nonempty(raw[key]) or raw[key] ~= snapshot[key] then
            return nil, "Proposal " .. key .. " mismatch"
        end
        view[key] = raw[key]
    end
    if not revision(raw.revision) or raw.revision ~= snapshot.revision then
        return nil, "Proposal revision is stale"
    end
    if not nonempty(raw.feature) or not nonempty(raw.actionKey) then
        return nil, "Proposal feature or action key missing"
    end
    if type(raw.resources) ~= "table" then
        return nil, "Proposal resource exposure missing"
    end
    if type(raw.intent) ~= "table" or not nonempty(raw.intent.kind) then
        return nil, "Proposal intent missing"
    end
    local resources = {}
    for resource, amount in pairs(raw.resources) do
        if not nonempty(resource) or not finite(amount) or amount < 0 then
            return nil, "Invalid proposal resource exposure"
        end
        resources[resource] = amount
    end
    local intent = {}
    for key, value in pairs(raw.intent) do
        local valueType = type(value)
        if not nonempty(key) or (valueType ~= "string" and valueType ~= "boolean"
            and not (valueType == "number" and finite(value))) then
            return nil, "Invalid proposal intent"
        end
        intent[key] = value
    end
    view.revision = raw.revision
    view.feature = raw.feature
    view.actionKey = raw.actionKey
    view.resources = resources
    view.intent = intent
    return view, nil
end

return Contracts
