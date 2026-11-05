-- Pure durable budget accounting. A charge is exposure, not proof of server spending.
local FamilyContributionUsage = {}
local resources = {familyCash = "cash", familyGold = "gold_bar", familyStamina = "stamina"}
local MAX_SPENT = 1000000000000000
local function integer(value, low, high)
    return type(value) == "number" and value == value and value >= low and value <= high and value % 1 == 0
end
function FamilyContributionUsage.copy(raw)
    if raw ~= nil and (type(raw) ~= "table" or raw.version ~= 1 or type(raw.lanes) ~= "table") then return nil end
    local copied = {version = 1, lanes = {}}
    if raw then
        for key in pairs(raw) do if key ~= "version" and key ~= "lanes" then return nil end end
        for feature in pairs(raw.lanes) do if not resources[feature] then return nil end end
    end
    for feature in pairs(resources) do
        local row
        if raw == nil then row = {attempted = 0, spent = 0} else row = raw.lanes[feature] end
        if type(row) ~= "table" or not integer(row.attempted, 0, 1000)
            or not integer(row.spent, 0, MAX_SPENT) then return nil end
        for key in pairs(row) do if key ~= "attempted" and key ~= "spent" then return nil end end
        copied.lanes[feature] = {attempted = row.attempted, spent = row.spent}
    end
    return copied
end
function FamilyContributionUsage.copyCharge(raw, feature, exposure)
    if not resources[feature] or type(raw) ~= "table" or raw.feature ~= feature
        or not integer(raw.amount, 1, MAX_SPENT) or not integer(raw.attemptedBefore, 0, 999)
        or not integer(raw.spentBefore, 0, MAX_SPENT - raw.amount)
        or type(exposure) ~= "table" or exposure[resources[feature]] ~= raw.amount then return nil end
    local count = 0
    for _ in pairs(exposure) do count = count + 1 end
    if count ~= 1 then return nil end
    for key in pairs(raw) do
        if key ~= "feature" and key ~= "amount" and key ~= "attemptedBefore" and key ~= "spentBefore" then return nil end
    end
    return {feature = feature, amount = raw.amount,
        attemptedBefore = raw.attemptedBefore, spentBefore = raw.spentBefore}
end
function FamilyContributionUsage.charge(raw, proposal)
    local usage = FamilyContributionUsage.copy(raw)
    local feature = type(proposal) == "table" and proposal.feature
    local intent = type(proposal) == "table" and proposal.intent
    if not usage or not resources[feature] or type(intent) ~= "table"
        or intent.kind ~= "familyContribution" or intent.resource ~= resources[feature]
        or not integer(intent.actorId, 1, 9007199254740991)
        or not (type(proposal.account) == "string" and #proposal.account > 0 and #proposal.account <= 200)
        or (intent.actorAccount ~= nil and intent.actorAccount ~= proposal.account)
        or (intent.actorAccount == nil and intent.actorId ~= tonumber(proposal.account))
        or not (type(intent.familyId) == "string" and #intent.familyId > 0 and #intent.familyId <= 160
            or integer(intent.familyId, 1, 9007199254740991))
        or not integer(intent.runBudget, 0, MAX_SPENT) or not integer(intent.maxAttempts, 0, 1000) then
        return nil, nil, "Invalid Family budget attempt"
    end
    local charge = FamilyContributionUsage.copyCharge({feature = feature, amount = intent.amount,
        attemptedBefore = intent.attemptsBefore, spentBefore = intent.spentBefore}, feature, proposal.resources)
    local current = usage.lanes[feature]
    if not charge or current.attempted ~= charge.attemptedBefore or current.spent ~= charge.spentBefore
        or current.attempted >= intent.maxAttempts or current.spent + charge.amount > intent.runBudget then
        return nil, nil, "Family budget cap or usage changed"
    end
    usage.lanes[feature] = {attempted = current.attempted + 1, spent = current.spent + charge.amount}
    return usage, charge, nil
end
function FamilyContributionUsage.holds(usage, charge)
    local row = type(usage) == "table" and type(usage.lanes) == "table" and usage.lanes[charge.feature]
    return type(row) == "table" and row.attempted >= charge.attemptedBefore + 1
        and row.spent >= charge.spentBefore + charge.amount
end
function FamilyContributionUsage.rollback(raw, charge)
    local usage = FamilyContributionUsage.copy(raw)
    if not usage or not FamilyContributionUsage.holds(usage, charge) then return nil end
    local row = usage.lanes[charge.feature]
    if row.attempted ~= charge.attemptedBefore + 1 or row.spent ~= charge.spentBefore + charge.amount then return nil end
    usage.lanes[charge.feature] = {attempted = charge.attemptedBefore, spent = charge.spentBefore}
    return usage
end
return FamilyContributionUsage
