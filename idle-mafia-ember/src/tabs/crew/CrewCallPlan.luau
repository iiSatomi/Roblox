-- Saved CrewTab call signatures; this module describes and never invokes.
local CrewCallPlan = {}

local function integer(value, low, high)
    return type(value) == "number" and value == value
        and value >= low and value <= high and value % 1 == 0
end

local function key(value)
    return type(value) == "string" and #value > 0 and #value <= 120
end

local function id(value)
    return key(value) and value:match("^[%w_]+$") ~= nil
end

local function memberId(value)
    return type(value) == "string" and #value > 0 and #value <= 128
end

function CrewCallPlan.describe(proposal)
    local intent = type(proposal) == "table" and proposal.intent
    if type(intent) ~= "table" then return nil, "Missing Crew intent" end
    if proposal.feature == "crew" and intent.kind == "crewAutoEquip" then
        return { remote = "AutoEquipCrew", method = "InvokeServer",
            arity = 0, args = {},
            source = "saved CrewTab Auto Equip call" }, nil
    end
    if proposal.feature == "crewSort" and intent.kind == "crewSort" then
        return { remote = "CrewAction", method = "InvokeServer",
            arity = 4, args = { "sort" },
            source = "saved CrewTab sort call" }, nil
    end
    if proposal.feature == "crewHeal" and intent.kind == "crewHeal"
        and integer(intent.slot, 2, 46) and memberId(intent.memberId)
        and integer(intent.expectedCost, 1, 100)
        and type(intent.injuredUntil) == "number" and intent.injuredUntil > 0
        and intent.injuredUntil < math.huge then
        return { remote = "CrewAction", method = "InvokeServer",
            arity = 3, args = { "heal", intent.slot,
                {memberId = intent.memberId, injuredUntil = intent.injuredUntil} },
            source = "saved CrewHealModal guarded stamina heal call" }, nil
    end
    if proposal.feature == "crewHealItems" and intent.kind == "crewHealItems"
        and integer(intent.slot, 2, 46) and memberId(intent.memberId)
        and (intent.itemId == "con_bandages" or intent.itemId == "con_medkit_small"
            or intent.itemId == "con_medkit_large")
        and type(intent.fromBound) == "boolean"
        and type(intent.injuredUntil) == "number" and intent.injuredUntil > 0
        and intent.injuredUntil < math.huge and integer(intent.sequence, 0, 9007199254740990) then
        return { remote = "CrewAction", method = "InvokeServer", arity = 3,
            args = { "healitem", intent.slot, { itemId = intent.itemId,
                fromBound = intent.fromBound, memberId = intent.memberId,
                injuredUntil = intent.injuredUntil, sequence = intent.sequence } },
            source = "saved CrewHealModal guarded item heal call" }, nil
    end
    if proposal.feature == "crewTrain" and intent.kind == "crewTrain"
        and integer(intent.slot, 2, 46)
        and integer(intent.quotedCost, 1, 9007199254740991)
        and key(intent.catalogKey) then
        return { remote = "CrewAction", method = "InvokeServer",
            arity = 4, args = { "train", intent.slot },
            source = "saved CrewTab training call" }, nil
    end
    if proposal.feature == "crewHire" and intent.kind == "crewHire"
        and id(intent.tier) and integer(intent.slot, 2, 46)
        and integer(intent.cost, 1, 9007199254740991)
        and key(intent.catalogKey) then
        return { remote = "CrewAction", method = "InvokeServer",
            arity = 4, args = { "hire", intent.tier, intent.cost },
            source = "saved CrewTab hire call" }, nil
    end
    if proposal.feature == "crewGear" and intent.kind == "crewGear"
        and integer(intent.slot, 1, 46)
        and (intent.gearKind == "weapon"
            or intent.gearKind == "armor"
            or intent.gearKind == "vehicle")
        and id(intent.itemId) and key(intent.sourceKey) then
        return { remote = "CrewEquip", method = "InvokeServer",
            arity = 3, args = { intent.slot, intent.gearKind,
                intent.itemId },
            source = "saved CrewTab gear equip call" }, nil
    end
    return nil, "No reviewed Crew call contract"
end

return CrewCallPlan
