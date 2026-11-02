-- Earned-medal run exposure survives reload; only known-unsent charges refund.
local EventShopUsage = {}
local function integer(value, low, high)
    return type(value) == "number" and value == value and value % 1 == 0 and value >= low and value <= high
end
function EventShopUsage.copy(raw)
    if raw == nil then return {version = 1, attempted = 0, spent = 0} end
    if type(raw) ~= "table" or raw.version ~= 1 or not integer(raw.attempted, 0, 1000)
        or not integer(raw.spent, 0, 1000000000) or raw.spent < raw.attempted
        or (raw.attempted == 0 and raw.spent ~= 0) then return nil end
    for key in pairs(raw) do if key ~= "version" and key ~= "attempted" and key ~= "spent" then return nil end end
    return {version = 1, attempted = raw.attempted, spent = raw.spent}
end
function EventShopUsage.copyCharge(raw, feature, resources)
    if feature ~= "eventShop" or type(raw) ~= "table" or not integer(raw.price, 1, 1000000000)
        or not integer(raw.attemptedBefore, 0, 999) or not integer(raw.spentBefore, 0, 1000000000 - raw.price)
        or raw.spentBefore < raw.attemptedBefore or (raw.attemptedBefore == 0 and raw.spentBefore ~= 0)
        or type(resources) ~= "table" or resources.event_medal ~= raw.price then return nil end
    for key in pairs(resources) do if key ~= "event_medal" then return nil end end
    for key in pairs(raw) do if key ~= "price" and key ~= "attemptedBefore" and key ~= "spentBefore" then return nil end end
    return {price = raw.price, attemptedBefore = raw.attemptedBefore, spentBefore = raw.spentBefore}
end
function EventShopUsage.charge(raw, proposal)
    local usage = EventShopUsage.copy(raw)
    local intent = type(proposal) == "table" and proposal.intent
    if not usage or type(intent) ~= "table" or intent.kind ~= "eventShopBuy" or intent.quantity ~= 1
        or not integer(intent.maxAttempts, 0, 1000) or not integer(intent.maxSpend, 0, 1000000000) then
        return nil, nil, "Event Shop usage intent invalid"
    end
    local charge = EventShopUsage.copyCharge({price = intent.price, attemptedBefore = intent.attemptedBefore,
        spentBefore = intent.spentBefore}, proposal.feature, proposal.resources)
    if not charge or usage.attempted ~= charge.attemptedBefore or usage.spent ~= charge.spentBefore
        or usage.attempted >= intent.maxAttempts or usage.spent + charge.price > intent.maxSpend then
        return nil, nil, "Event Shop usage changed or cap reached"
    end
    return {version = 1, attempted = usage.attempted + 1, spent = usage.spent + charge.price}, charge, nil
end
function EventShopUsage.holds(usage, charge)
    return type(usage) == "table" and usage.attempted >= charge.attemptedBefore + 1
        and usage.spent >= charge.spentBefore + charge.price
end
function EventShopUsage.rollback(raw, charge)
    local usage = EventShopUsage.copy(raw)
    if not usage or not EventShopUsage.holds(usage, charge)
        or usage.attempted ~= charge.attemptedBefore + 1 or usage.spent ~= charge.spentBefore + charge.price then return nil end
    return {version = 1, attempted = charge.attemptedBefore, spent = charge.spentBefore}
end
return EventShopUsage
