-- Bind pending gear and cosmetic choices to one complete Sync.
local CollectionProtection = {}

local checked = {
    { id = "crewGear", empty = "No safe loose-inventory gear gain" },
    { id = "cosmetics", empty = "No safe loose cosmetic gain" },
}

local function integer(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge and value % 1 == 0
end

function CollectionProtection.derive(raw, context, settings, features)
    local native = type(raw) == "table" and raw.native
    if type(context) ~= "table" or type(settings) ~= "table"
        or type(features) ~= "table" or type(native) ~= "table"
        or native.fullSync ~= true
        or raw.session ~= context.session
        or raw.account ~= context.account
        or raw.place ~= context.place
        or raw.release ~= context.release
        or raw.revision ~= context.revision
        or raw.capturedAt ~= context.capturedAt
        or not integer(raw.revision) then
        return nil, "Fresh Collection protection input required"
    end
    local protected = {}
    for _, lane in ipairs(checked) do
        local config = settings[lane.id]
        if type(config) == "table" and config.enabled == true then
            local spec = features[lane.id]
            if type(spec) ~= "table" or type(spec.reader) ~= "table"
                or type(spec.planner) ~= "table" then
                return nil, "Gear or cosmetic planner missing"
            end
            local readOk, view = pcall(spec.reader.read, raw, context)
            if not readOk or type(view) ~= "table" then
                return nil, "Gear or cosmetic custody unknown"
            end
            local planOk, proposal, reason = pcall(spec.planner.propose,
                view, config)
            if not planOk then
                return nil, "Gear or cosmetic planner failed"
            end
            if proposal == nil then
                if reason ~= lane.empty then
                    return nil, "Gear or cosmetic plan unresolved"
                end
            else
                local intent = type(proposal) == "table"
                    and proposal.intent
                local id = type(intent) == "table"
                    and intent.itemId
                if proposal.feature ~= lane.id
                    or type(id) ~= "string" or #id == 0
                    or id:find("@", 1, true) then
                    return nil, "Gear or cosmetic plan invalid"
                end
                protected[id] = math.max(protected[id] or 0, 1)
            end
        end
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision,
        capturedAt = context.capturedAt,
        key = context.account .. ":" .. tostring(context.revision)
            .. ":" .. tostring(context.capturedAt),
        covers = { gear = true, cosmetics = true },
        protected = protected }, nil
end

return CollectionProtection
