-- Chooses one eligible proposal. It never sends or changes game state.
local Scheduler = {}
local Methods = {}
Methods.__index = Methods

local priority = { heists = 1, favors = 2, collect = 3, operations = 4 }
local nativeControllerFeatures = {
    jobs = true, shop = true, crewRoll = true, bosses = true,
}

local function finite(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

function Scheduler.new()
    return setmetatable({ lastKey = {} }, Methods)
end

local function hasResources(context, desired, proposal)
    if type(proposal.resources) ~= "table" then return false end
    for resource, amount in pairs(proposal.resources) do
        local current = context.resources and context.resources[resource]
        local reserved = desired.reservations and desired.reservations[resource] or 0
        local uncertain = desired.uncertain and desired.uncertain[resource] or 0
        if not finite(amount) or not finite(current)
            or not finite(reserved) or not finite(uncertain)
            or amount > current - reserved - uncertain then
            return false
        end
    end
    return true
end

function Methods:Choose(context, desired, brokerStatus, now)
    if type(context) ~= "table" or type(desired) ~= "table"
        or type(brokerStatus) ~= "table" or not finite(now) then
        return nil, "Missing scheduler context"
    end
    if now < context.capturedAt or now - context.capturedAt > context.maxAge then
        return nil, "Native state is stale"
    end
    if brokerStatus.active then return nil, "Broker busy" end
    if type(brokerStatus.nextSendAt) == "number" and now < brokerStatus.nextSendAt then
        return nil, "Waiting for send spacing"
    end
    local proposals = desired.proposals
    if type(proposals) ~= "table" then return nil, "No eligible proposals" end
    local eligible, resourceBlocked = {}, false
    for _, proposal in ipairs(proposals) do
        local feature = proposal.feature
        if desired.enabled and desired.enabled[feature] == true then
            local owner = context.owners and context.owners[feature]
            local activity = owner and owner.activity or "unknown"
            local nativeBlocked = nativeControllerFeatures[feature]
                and activity ~= "inactive"
            local cooldown = brokerStatus.cooldownUntil
                and brokerStatus.cooldownUntil[feature] or 0
            if not nativeBlocked and now >= cooldown then
                if hasResources(context, desired, proposal) then
                    eligible[#eligible + 1] = proposal
                else
                    resourceBlocked = true
                end
            end
        end
    end
    if #eligible == 0 then
        return nil, resourceBlocked and "Resource unavailable" or "No eligible proposals"
    end
    table.sort(eligible, function(a, b)
        local pa, pb = priority[a.feature] or 5, priority[b.feature] or 5
        if pa ~= pb then return pa < pb end
        return a.actionKey < b.actionKey
    end)
    local firstPriority = priority[eligible[1].feature] or 5
    local chosen = eligible[1]
    local last = self.lastKey[firstPriority]
    if last then
        for _, proposal in ipairs(eligible) do
            if (priority[proposal.feature] or 5) ~= firstPriority then break end
            if proposal.actionKey > last then
                chosen = proposal
                break
            end
        end
    end
    self.lastKey[firstPriority] = chosen.actionKey
    return chosen, nil
end

return Scheduler
