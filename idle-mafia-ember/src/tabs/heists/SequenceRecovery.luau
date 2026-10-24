-- Read-only recovery description for a previously sent, durably owned action.
local SequenceRecovery = {}

local actions = { start = true, collect = true, sabotage = true }

local function nonempty(value)
    return type(value) == "string" and #value > 0 and #value <= 120
end

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value <= 9007199254740991
        and value % 1 == 0
end

function SequenceRecovery.statusCall(record, identity)
    if type(record) ~= "table" or type(identity) ~= "table"
        or not nonempty(identity.account) or not nonempty(identity.place)
        or not nonempty(identity.release)
        or record.account ~= identity.account
        or record.place ~= identity.place
        or record.release ~= identity.release
        or record.sent ~= true or not actions[record.actionName]
        or not integer(record.sequence, 1)
        or not nonempty(record.actionKey)
        or not integer(record.sentAt, 0)
        or (record.actionName == "collect" and record.arg1 ~= nil)
        or (record.actionName ~= "collect" and not nonempty(record.arg1)) then
        return nil, "No owned sent Heist sequence to recover"
    end
    return { kind = "statusOnly", remote = "HeistAction",
        method = "InvokeServer", arity = 3,
        args = { "status", record.arg1, record.sequence },
        actionKey = record.actionKey,
        source = "saved HeistsTab status poll" }, nil
end

function SequenceRecovery.classify(reply)
    if type(reply) ~= "table" then return "unresolved" end
    if reply.pending == true or reply.code == "rate_limited" then
        return "waiting"
    end
    if reply.code == "no_pending" then return "unresolved" end
    if type(reply.ok) == "boolean" then return "reported" end
    return "unresolved"
end

return SequenceRecovery
