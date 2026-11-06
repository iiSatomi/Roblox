-- Inputs for the native shared act owner. Sequence allocation stays inside the game.
local Plan = {}
local function integer(value, low)
    return type(value) == "number" and value == value and value % 1 == 0
        and value >= low and value <= 9007199254740991
end
local function key(value)
    return type(value) == "string" and #value > 0 and #value <= 120 and not value:find("[%c]")
end
local function resources(value, expected)
    if type(value) ~= "table" then return false end
    for field, amount in pairs(expected) do if value[field] ~= amount or not integer(amount, 0) then return false end end
    for field in pairs(value) do if expected[field] == nil then return false end end
    return true
end
function Plan.describe(proposal)
    local intent = type(proposal) == "table" and proposal.intent
    if type(intent) ~= "table" or intent.needsSequence ~= true then return nil, "Native Heist sequence contract required" end
    local action, arg1
    if proposal.feature == "heists" and intent.kind == "heistStart" and key(intent.heistId)
        and resources(proposal.resources, {cash = intent.expectedStake, energy = intent.expectedEnergy})
        and integer(intent.expectedStake, 0) and integer(intent.expectedEnergy, 0) then
        action, arg1 = "start", intent.heistId
    elseif proposal.feature == "heistCollect" and intent.kind == "heistCollect"
        and type(intent.resultKey) == "string" and #intent.resultKey == 64 and intent.resultKey:match("^[%x]+$")
        and resources(proposal.resources, {}) then
        action = "collect"
    elseif ((proposal.feature == "favors" and intent.kind == "favorHelp")
        or (proposal.feature == "sabotage" and intent.kind == "heistSabotage"))
        and (key(intent.rowId) or integer(intent.rowId, 1))
        and integer(intent.expectedFavorCost, 0) and integer(intent.expectedEnergyCost, 0)
        and resources(proposal.resources, {favors = intent.expectedFavorCost, energy = intent.expectedEnergyCost}) then
        action, arg1 = proposal.feature == "favors" and "help" or "sabotage", intent.rowId
    end
    if not action then return nil, "Exact ordinary native Heist action required" end
    return {remote = "HeistAction", method = "InvokeServer", arity = 2,
        args = {action, arg1}, nativeAct = true, source = "reviewed native HeistsTab act owner"}, nil
end
return Plan
