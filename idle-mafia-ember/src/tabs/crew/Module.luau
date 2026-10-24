-- Crew owns its independent controls and read-only roster boundary.
local CrewTab = {}
local Methods = {}
Methods.__index = Methods

local known = { crew = true, crewGear = true, crewRoll = true,
    crewSort = true, crewHeal = true, crewTrain = true,
    crewHire = true, crewHealItems = true }
local blocked = {
    crewRoll = "Native Auto Roll stop-on-disable and server spending contract unverified",
}

function CrewTab.BuildUI(section, feature, bind, numeric)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "crew" and known[feature.id]
        and type(bind) == "function"
        and type(numeric) == "table"
        and type(feature.policies) == "table"
        and type(feature.custom) == "table", "Invalid Crew UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", feature.id .. ".enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity for the prototype.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    if #feature.policies > 0 then
        bind(group, "Dropdown", feature.id .. ".policy", {
            Text = "Goal", Options = feature.policies,
            Default = feature.policies[1],
        })
    end
    if feature.limits then group:Description({ Text = feature.limits }) end
    local reason = blocked[feature.id]
    local row = { feature = feature, tabOwned = true,
        blockedReason = reason and ("Unavailable: " .. reason) or nil,
        status = group:Status({ Text = "Activity",
            Default = reason and ("Blocked — " .. reason)
                or "Off — UI only" }) }
    if #feature.custom > 0 then
        row.custom = group:Group({ Text = "Custom limits", Open = false })
        for _, field in ipairs(feature.custom) do
            assert(field.type == "number"
                and (feature.id == "crewHeal"
                or feature.id == "crewTrain"
                or feature.id == "crewHire"
                or feature.id == "crewHealItems"),
                "Unsupported Crew custom control")
            local key = feature.id .. ".custom." .. field.id
            numeric[key] = true
            bind(row.custom, "Input", key, {
                Text = field.label, Default = tostring(field.value),
                FireOnBlur = true,
            })
        end
    end
    return row
end

function CrewTab.new(deps)
    assert(type(deps) == "table" and type(deps.RosterState) == "table"
        and type(deps.RosterState.read) == "function"
        and type(deps.AutoEquipCrew) == "table"
        and type(deps.AutoEquipCrew.read) == "function"
        and type(deps.AutoEquipCrew.propose) == "function"
        and type(deps.AutoEquipCrew.capture) == "function"
        and type(deps.AutoEquipCrew.evaluate) == "function"
        and type(deps.CrewSort) == "table"
        and type(deps.CrewSort.read) == "function"
        and type(deps.CrewSort.propose) == "function"
        and type(deps.CrewSort.capture) == "function"
        and type(deps.CrewSort.evaluate) == "function"
        and type(deps.CrewHeal) == "table"
        and type(deps.CrewHeal.read) == "function"
        and type(deps.CrewHeal.propose) == "function"
        and type(deps.CrewHeal.capture) == "function"
        and type(deps.CrewHeal.evaluate) == "function"
        and type(deps.NativeTrainingCatalog) == "table"
        and type(deps.NativeTrainingCatalog.new) == "function"
        and type(deps.CrewTrain) == "table"
        and type(deps.CrewTrain.read) == "function"
        and type(deps.CrewTrain.propose) == "function"
        and type(deps.CrewTrain.capture) == "function"
        and type(deps.CrewTrain.evaluate) == "function",
        "Missing Crew modules")
    assert(type(deps.NativeHireCatalog) == "table"
        and type(deps.NativeHireCatalog.new) == "function"
        and type(deps.CrewHire) == "table"
        and type(deps.CrewHire.read) == "function"
        and type(deps.CrewHire.propose) == "function"
        and type(deps.CrewHire.capture) == "function"
        and type(deps.CrewHire.evaluate) == "function",
        "Missing Crew modules")
    assert(type(deps.NativeHealItemCatalog) == "table"
        and type(deps.NativeHealItemCatalog.new) == "function"
        and type(deps.CrewHealItems) == "table"
        and type(deps.CrewHealItems.read) == "function"
        and type(deps.CrewHealItems.propose) == "function"
        and type(deps.CrewHealItems.capture) == "function"
        and type(deps.CrewHealItems.evaluate) == "function",
        "Missing Crew item healing modules")
    assert(type(deps.CrewGear) == "table"
        and type(deps.CrewGear.new) == "function"
        and type(deps.gearSets) == "table",
        "Missing Crew gear source")
    assert(type(deps.CrewRollState) == "table"
        and type(deps.CrewRollState.read) == "function"
        and type(deps.CrewRollState.propose) == "function"
        and type(deps.CrewRollState.capture) == "function"
        and type(deps.CrewRollState.evaluate) == "function",
        "Missing Crew Auto Roll status")
    local trainingCatalog = deps.NativeTrainingCatalog.new(
        deps.config, deps.fingerprint, deps.release)
    local hireCatalog = deps.NativeHireCatalog.new(
        deps.config, deps.fingerprint, deps.release)
    local healItemCatalog = deps.NativeHealItemCatalog.new(
        deps.gameData, deps.config, deps.fingerprint, deps.release)
    local gear = deps.CrewGear.new(deps.gameData, deps.gearSets,
        deps.fingerprint, deps.release)
    return setmetatable({ id = "crew", roster = deps.RosterState,
        autoEquip = deps.AutoEquipCrew, sort = deps.CrewSort,
        heal = deps.CrewHeal, train = deps.CrewTrain,
        hire = deps.CrewHire, healItems = deps.CrewHealItems,
        gear = gear, roll = deps.CrewRollState,
        trainingCatalog = trainingCatalog,
        hireCatalog = hireCatalog,
        healItemCatalog = healItemCatalog }, Methods)
end

function Methods:ReadRoster(raw, context)
    return self.roster.read(raw, context)
end

function Methods:Enrich(snapshot)
    local trained, reason = self.trainingCatalog:Enrich(snapshot)
    if not trained then return nil, reason end
    local hired, hireReason = self.hireCatalog:Enrich(trained)
    if not hired then return nil, hireReason end
    local healed, healReason = self.healItemCatalog:Enrich(hired)
    if not healed then return nil, healReason end
    local result = {}
    for key, value in pairs(healed) do result[key] = value end
    result.gearSourceKey = self.gear.sourceKey
    return result, nil
end

function Methods:Descriptors()
    return { { id = "crew", reader = self.autoEquip,
        planner = self.autoEquip, evidence = self.autoEquip },
        { id = "crewGear", reader = self.gear,
            planner = self.gear, evidence = self.gear },
        { id = "crewRoll", reader = self.roll,
            planner = self.roll, evidence = self.roll },
        { id = "crewSort", reader = self.sort,
            planner = self.sort, evidence = self.sort },
        { id = "crewHeal", reader = self.heal,
            planner = self.heal, evidence = self.heal },
        { id = "crewTrain", reader = self.train,
            planner = self.train, evidence = self.train },
        { id = "crewHire", reader = self.hire,
            planner = self.hire, evidence = self.hire },
        { id = "crewHealItems", reader = self.healItems,
            planner = self.healItems, evidence = self.healItems } }
end

return CrewTab
