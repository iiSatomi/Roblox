-- Durable attempted Stamina allowances; ordinary/war and Attack/Scout stay separate.
local Usage = {}
local LIMIT = 1000000
local features = {combat = true, warCombat = true}
local modes = {attack = true, scout = true}
local function integer(v, low, high)
    return type(v) == "number" and v == v and v % 1 == 0 and v >= low and v <= high
end
local function only(raw, allowed)
    for k in pairs(raw) do if not allowed[k] then return false end end
    return true
end
local function row(raw)
    if type(raw) ~= "table" or not only(raw, {attempted = true, spent = true})
        or not integer(raw.attempted, 0, LIMIT) or not integer(raw.spent, 0, LIMIT)
        or raw.spent < raw.attempted or raw.spent > raw.attempted * 5 then return nil end
    return {attempted = raw.attempted, spent = raw.spent}
end
function Usage.copy(raw)
    if raw == nil then
        raw = {version = 1, lanes = {combat = {attack = {attempted = 0, spent = 0}, scout = {attempted = 0, spent = 0}},
            warCombat = {attack = {attempted = 0, spent = 0}, scout = {attempted = 0, spent = 0}}}}
    end
    if type(raw) ~= "table" or raw.version ~= 1 or not only(raw, {version = true, lanes = true})
        or type(raw.lanes) ~= "table" or not only(raw.lanes, features) then return nil end
    local out = {version = 1, lanes = {}}
    for feature in pairs(features) do
        local lane = raw.lanes[feature]
        if type(lane) ~= "table" or not only(lane, modes) then return nil end
        local attack, scout = row(lane.attack), row(lane.scout)
        if not attack or not scout then return nil end
        out.lanes[feature] = {attack = attack, scout = scout}
    end
    return out
end
function Usage.copyCharge(raw, feature, resources)
    if not features[feature] or type(raw) ~= "table" or raw.feature ~= feature or not modes[raw.mode]
        or not only(raw, {feature = true, mode = true, cost = true, quoteCost = true, attemptedBefore = true, spentBefore = true})
        or not integer(raw.cost, 1, 5) or not row({attempted = raw.attemptedBefore, spent = raw.spentBefore})
        or raw.spentBefore > LIMIT - raw.cost or type(resources) ~= "table"
        or resources.stamina ~= raw.cost or not only(resources, {stamina = true})
        or raw.quoteCost ~= nil and not integer(raw.quoteCost, 1, raw.cost) then return nil end
    return {feature = feature, mode = raw.mode, cost = raw.cost, quoteCost = raw.quoteCost,
        attemptedBefore = raw.attemptedBefore, spentBefore = raw.spentBefore}
end
function Usage.charge(raw, proposal)
    local usage = Usage.copy(raw)
    local feature = type(proposal) == "table" and proposal.feature
    local intent = type(proposal) == "table" and proposal.intent
    if not usage or not features[feature] or type(intent) ~= "table"
        or not integer(intent.maxAttackSpend, 0, LIMIT) or not integer(intent.maxScoutSpend, 0, LIMIT) then
        return nil, nil, "Explicit independent player Stamina limits required"
    end
    local mode = intent.kind == "playerAttack" and "attack" or intent.kind == "playerScout" and "scout" or nil
    if not mode then return nil, nil, "Unknown player Stamina action" end
    local cost, quote = intent.expectedStaminaCost, nil
    if intent.maxStaminaExposure ~= nil then
        if not integer(intent.expectedStaminaCost, 1, 5) or not integer(intent.maxStaminaExposure, intent.expectedStaminaCost, 5) then
            return nil, nil, "Quoted cost and maximum Stamina exposure required"
        end
        cost, quote = intent.maxStaminaExposure, intent.expectedStaminaCost
    end
    local charge = Usage.copyCharge({feature = feature, mode = mode, cost = cost, quoteCost = quote,
        attemptedBefore = intent.attemptedBefore, spentBefore = intent.spentBefore}, feature, proposal.resources)
    local current = usage.lanes[feature][mode]
    local cap = mode == "attack" and intent.maxAttackSpend or intent.maxScoutSpend
    if not charge or current.attempted ~= charge.attemptedBefore or current.spent ~= charge.spentBefore
        or current.spent + charge.cost > cap then return nil, nil, "Player Stamina allowance changed or cap reached" end
    usage.lanes[feature][mode] = {attempted = current.attempted + 1, spent = current.spent + charge.cost}
    return Usage.copy(usage), charge, nil
end
function Usage.holds(raw, charge)
    local usage = Usage.copy(raw)
    local copied = type(charge) == "table" and Usage.copyCharge(charge, charge.feature, {stamina = charge.cost})
    if not usage or not copied then return false end
    local current = usage.lanes[copied.feature][copied.mode]
    return current.attempted >= copied.attemptedBefore + 1 and current.spent >= copied.spentBefore + copied.cost
end
function Usage.rollback(raw, charge)
    local usage = Usage.copy(raw)
    if not usage or not Usage.holds(usage, charge) then return nil end
    local current = usage.lanes[charge.feature][charge.mode]
    if current.attempted ~= charge.attemptedBefore + 1 or current.spent ~= charge.spentBefore + charge.cost then return nil end
    usage.lanes[charge.feature][charge.mode] = {attempted = charge.attemptedBefore, spent = charge.spentBefore}
    return Usage.copy(usage)
end
function Usage.summary(raw, feature)
    local usage = Usage.copy(raw)
    if not usage or not features[feature] then return nil end
    local lane = usage.lanes[feature]
    return {attempted = lane.attack.attempted + lane.scout.attempted, spent = lane.attack.spent + lane.scout.spent,
        attackAttempted = lane.attack.attempted, attackSpent = lane.attack.spent,
        scoutAttempted = lane.scout.attempted, scoutSpent = lane.scout.spent}
end
function Usage.reset(raw, feature)
    local usage = Usage.copy(raw)
    if not usage or not features[feature] then return nil end
    usage.lanes[feature] = {attack = {attempted = 0, spent = 0}, scout = {attempted = 0, spent = 0}}
    return usage
end
return Usage
