-- Attach weekend and cached membership facts from a trusted native source.
local RewardsProofProducer = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

function RewardsProofProducer.derive(raw, context, source)
    local native = type(raw) == "table" and raw.native
    if type(context) ~= "table" or type(source) ~= "table"
        or type(native) ~= "table" or native.fullSync ~= true
        or source.release ~= context.release
        or raw.session ~= context.session
        or raw.account ~= context.account
        or raw.place ~= context.place
        or raw.release ~= context.release
        or raw.revision ~= context.revision
        or raw.capturedAt ~= context.capturedAt then
        return nil, "Fresh Rewards source required"
    end
    local result = {}
    if integer(native.serverNow, 0)
        and type(source.IsWeekend) == "function" then
        local ok, active = pcall(source.IsWeekend,
            source, native.serverNow)
        local dateOk, textDay = pcall(function()
            return os.date("!%Y%j", native.serverNow)
        end)
        local day = dateOk and tonumber(textDay)
        if ok and type(active) == "boolean" and integer(day, 1) then
            result.weekendBuff = { active = active, day = day }
        end
    end
    local config = raw.groupConfig
    local groupId = type(config) == "table" and config.id
    if integer(groupId, 1)
        and type(source.Membership) == "function" then
        local ok, member, checkedAt = pcall(source.Membership,
            source, context.account, groupId)
        if ok and type(member) == "boolean"
            and type(checkedAt) == "number"
            and checkedAt == checkedAt
            and checkedAt >= 0
            and checkedAt <= context.capturedAt
            and context.capturedAt - checkedAt <= 30 then
            result.groupMembership = { session = context.session,
                account = context.account, place = context.place,
                release = context.release,
                groupId = groupId, isMember = member,
                checkedAt = checkedAt }
        end
    end
    return result, nil
end

return RewardsProofProducer
