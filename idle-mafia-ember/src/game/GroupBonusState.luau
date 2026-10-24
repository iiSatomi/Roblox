-- Ordinary claim eligibility for a currently verified group member.
local GroupBonusState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

function GroupBonusState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Group bonus state or context"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Group bonus snapshot header changed"
        end
    end
    local native = raw.native
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.groupBonus) ~= "boolean" then
        return nil, "Complete Group bonus Sync required"
    end
    if native.groupBonus then return nil, "Group bonus already claimed" end
    local config, membership = raw.groupConfig, raw.groupMembership
    local groupId = type(config) == "table" and config.id
    if not integer(groupId, 1) or type(membership) ~= "table"
        or membership.groupId ~= groupId
        or membership.session ~= context.session
        or membership.account ~= context.account
        or membership.place ~= context.place
        or membership.release ~= context.release
        or membership.isMember ~= true
        or type(membership.checkedAt) ~= "number"
        or membership.checkedAt ~= membership.checkedAt
        or membership.checkedAt > context.capturedAt
        or context.capturedAt - membership.checkedAt > 30 then
        return nil, "Current matching Group membership proof required"
    end
    return {
        session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        groupId = groupId,
    }, nil
end

return GroupBonusState
