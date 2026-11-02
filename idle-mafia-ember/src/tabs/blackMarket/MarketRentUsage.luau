-- Independent one-period rental exposure. Only definite-unsent cleanup refunds.
local Usage = {}
local function integer(v, low, high) return type(v) == "number" and v == v and v % 1 == 0 and v >= low and v <= high end
function Usage.copy(raw)
    if raw == nil then return {version = 1, attempted = 0, spent = 0} end
    if type(raw) ~= "table" or raw.version ~= 1 or not integer(raw.attempted, 0, 20)
        or not integer(raw.spent, 0, 1000) or raw.spent < raw.attempted
        or (raw.attempted == 0 and raw.spent ~= 0) then return nil end
    for key in pairs(raw) do if key ~= "version" and key ~= "attempted" and key ~= "spent" then return nil end end
    return {version = 1, attempted = raw.attempted, spent = raw.spent}
end
function Usage.copyCharge(raw, feature, resources)
    if feature ~= "marketRent" or type(raw) ~= "table" or not integer(raw.price, 1, 1000)
        or not integer(raw.attemptedBefore, 0, 19) or not integer(raw.spentBefore, 0, 1000 - raw.price)
        or raw.spentBefore < raw.attemptedBefore or (raw.attemptedBefore == 0 and raw.spentBefore ~= 0)
        or type(resources) ~= "table" or resources.gold_bar ~= raw.price then return nil end
    for key in pairs(resources) do if key ~= "gold_bar" then return nil end end
    for key in pairs(raw) do if key ~= "price" and key ~= "attemptedBefore" and key ~= "spentBefore" then return nil end end
    return {price = raw.price, attemptedBefore = raw.attemptedBefore, spentBefore = raw.spentBefore}
end
function Usage.charge(raw, proposal)
    local usage = Usage.copy(raw)
    local intent = type(proposal) == "table" and proposal.intent
    if not usage or type(intent) ~= "table" or intent.kind ~= "marketRent" or intent.periods ~= 1
        or not integer(intent.maxAttempts, 0, 20) or not integer(intent.maxGoldSpend, 0, 1000) then
        return nil, nil, "Rental allowance intent invalid"
    end
    local charge = Usage.copyCharge({price = intent.cost, attemptedBefore = intent.attemptedBefore,
        spentBefore = intent.spentBefore}, proposal.feature, proposal.resources)
    if not charge or usage.attempted ~= charge.attemptedBefore or usage.spent ~= charge.spentBefore
        or usage.attempted >= intent.maxAttempts or usage.spent + charge.price > intent.maxGoldSpend then
        return nil, nil, "Rental allowance changed or cap reached"
    end
    return {version = 1, attempted = usage.attempted + 1, spent = usage.spent + charge.price}, charge, nil
end
function Usage.holds(raw, charge)
    local usage = Usage.copy(raw)
    return usage ~= nil and usage.attempted >= charge.attemptedBefore + 1 and usage.spent >= charge.spentBefore + charge.price
end
function Usage.rollback(raw, charge)
    local usage = Usage.copy(raw)
    if not usage or usage.attempted ~= charge.attemptedBefore + 1 or usage.spent ~= charge.spentBefore + charge.price then return nil end
    return {version = 1, attempted = charge.attemptedBefore, spent = charge.spentBefore}
end
return Usage
