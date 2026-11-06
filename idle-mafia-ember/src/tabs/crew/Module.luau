-- Crew owns its independent controls and read-only roster boundary.
local CrewTab = {}
local Methods = {}
Methods.__index = Methods

local known = { crew = true, crewGear = true, crewRoll = true,
    crewSort = true, crewHeal = true, crewTrain = true,
    crewHire = true, crewHealItems = true }
local blocked = {
    crewRoll = "Durable replacement ownership, funding reservations and recovery are not connected",
}

local function positiveInteger(value)
    return type(value) == "number" and value == value
        and value > 0 and value < math.huge and value % 1 == 0
end

function CrewTab.BuildUI(section, feature, bind, numeric, recovery)
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
        Description = "Select this activity; the status below shows whether this entry can run it.",
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
    -- Availability text follows constructed runtime/recovery capability.
    -- This changes no selection, budget, dismissal consent or dispatch guard.
    if feature.id == "crewRoll" and type(recovery) == "table" and recovery.available == true then reason = nil end
    local row = { feature = feature, tabOwned = true,
        alwaysShowCustom = feature.id == "crewRoll",
        blockedReason = reason and ("Unavailable: " .. reason) or nil,
        status = group:Status({ Text = "Activity",
            Default = reason and ("Blocked — " .. reason)
                or "Off — UI only" }) }
    if #feature.custom > 0 then
        row.custom = group:Group({ Text = "Custom limits", Open = false })
        for _, field in ipairs(feature.custom) do
            assert((field.type == "number"
                and (feature.id == "crewHeal"
                or feature.id == "crewTrain"
                or feature.id == "crewHire"
                or feature.id == "crewHealItems")) or (feature.id == "crewRoll"
                and (field.type == "number" or field.type == "select" or field.type == "boolean")),
                "Unsupported Crew custom control")
            local key = feature.id .. ".custom." .. field.id
            if field.type == "select" then
                bind(row.custom, "Dropdown", key, {Text = field.label,
                    Options = field.options, Default = field.value})
            elseif field.type == "boolean" then
                bind(row.custom, "Toggle", key, {Text = field.label, Default = false,
                    RevertOnClose = true, RevertTo = false})
            else
                numeric[key] = true
                bind(row.custom, "Input", key, {Text = field.label,
                    Default = tostring(field.value), FireOnBlur = true})
            end
        end
    end
    if feature.id == "crewRoll" then
        local available = type(recovery) == "table" and recovery.available == true
        local controls = group:Group({Text = "Saved replacement recovery", Open = false,
            Disabled = not available, DisabledReason = "Recovery needs a compatible runtime"})
        controls:Description({Text = "Pause first. Review the saved request, then confirm local cleanup. This does not dismiss, hire or retry a game action."})
        row.recoveryStatus = controls:Status({Text = "Saved Crew record", Save = false, FireOnStart = false,
            Default = available and "Pause and review a saved request" or "Recovery controls unavailable in this entry"})
        local function user(origin)
            return not origin or not (origin.initial or origin.restored or origin.reapplied or origin.reverted)
        end
        local function alive() return available and type(recovery.alive) == "function" and recovery.alive() end
        row.recoveryReview = controls:Button({Text = "Review saved replacement", ButtonText = "Review", FireOnStart = false,
            Callback = function(_, _, origin)
                if not alive() or not user(origin) then return end
                local ok, preview, why = pcall(recovery.preview)
                if not alive() then return end
                row.recoveryStatus:Set(ok and type(preview) == "table" and ("Slot " .. tostring(preview.slot) .. ": " .. preview.description)
                    or (ok and (why or "No reviewable saved request") or "Recovery review failed"), true)
            end})
        row.recoveryConfirm = controls:Button({Text = "Confirm saved-record cleanup", ButtonText = "Confirm cleanup", Danger = true, FireOnStart = false,
            Callback = function(_, _, origin)
                if not alive() or not user(origin) then return end
                local ok, saved, why = pcall(recovery.confirm)
                if not alive() then return end
                row.recoveryStatus:Set(ok and saved == true and "Local recovery saved; automation remains paused"
                    or (ok and (why or "Recovery refused") or "Recovery save failed"), true)
            end})
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
    local territory = type(deps.config) == "table"
        and deps.config.TERRITORY
    assert(type(territory) == "table"
        and positiveInteger(territory.healStaminaCost)
        and positiveInteger(territory.healSeconds),
        "Missing reviewed Crew heal rules")
    local trainingCatalog = deps.NativeTrainingCatalog.new(
        deps.config, deps.fingerprint, deps.release)
    local hireCatalog = deps.NativeHireCatalog.new(
        deps.config, deps.fingerprint, deps.release)
    local healItemCatalog = deps.NativeHealItemCatalog.new(
        deps.gameData, deps.config, deps.fingerprint, deps.release)
    local gear = deps.CrewGear.new(deps.gameData, deps.gearSets,
        deps.fingerprint, deps.release)
    local replacement
    if deps.CrewReplacement ~= nil then
        assert(type(deps.CrewReplacement) == "table" and type(deps.CrewReplacement.new) == "function",
            "Invalid Crew replacement helper")
        local reason
        replacement, reason = deps.CrewReplacement.new(deps.config, deps.fingerprint, deps.release)
        assert(replacement, reason or "Invalid Crew replacement source")
    end
    local self = setmetatable({ id = "crew", roster = deps.RosterState,
        autoEquip = deps.AutoEquipCrew, sort = deps.CrewSort,
        heal = deps.CrewHeal, train = deps.CrewTrain,
        hire = deps.CrewHire, healItems = deps.CrewHealItems,
        gear = gear, roll = deps.CrewRollState, replacement = replacement,
        replacementTransactions = deps.CrewReplacementTransactions,
        reservationModule = deps.ResourceReservations,
        healRules = { release = deps.release,
            healStaminaCost = territory.healStaminaCost,
            healSeconds = territory.healSeconds },
        trainingCatalog = trainingCatalog,
        hireCatalog = hireCatalog,
        healItemCatalog = healItemCatalog }, Methods)
    if replacement and deps.CrewReplacementRuntime and deps.storage and deps.identity and deps.clock then
        self.replacementRuntime, self.replacementFault = deps.CrewReplacementRuntime.new({
            helper = replacement, transactions = deps.CrewReplacementTransactions,
            storage = deps.storage, identity = deps.identity, clock = deps.clock, review = deps.CrewRecoveryReview})
        if self.replacementRuntime then self.replacementOwner = self.replacementRuntime.owner end
        self.ownedProofs = {"crewReplacementUsageProof", "crewReplacementOwnerProof"}
    end
    return self
end

function Methods:ReadRoster(raw, context)
    return self.roster.read(raw, context)
end

function Methods:Enrich(snapshot, settings)
    local trained, reason = self.trainingCatalog:Enrich(snapshot)
    if not trained then return nil, reason end
    local hired, hireReason = self.hireCatalog:Enrich(trained)
    if not hired then return nil, hireReason end
    local healed, healReason = self.healItemCatalog:Enrich(hired)
    if not healed then return nil, healReason end
    local result = {}
    for key, value in pairs(healed) do result[key] = value end
    result.gearSourceKey = self.gear.sourceKey
    result.healRules = { release = self.healRules.release,
        healStaminaCost = self.healRules.healStaminaCost,
        healSeconds = self.healRules.healSeconds }
    if self.replacement then
        result = self.replacement:Enrich(result)
        if self.replacementRuntime then return self.replacementRuntime:Enrich(result, settings) end
    end
    return result, nil
end

function CrewTab.ReplacementSettings(settings)
    if type(settings) ~= "table" then return nil end
    local custom = type(settings.custom) == "table" and settings.custom or settings
    local result = {enabled = settings.enabled, policy = "Bounded replacement"}
    for _, key in ipairs({"slot", "tier", "targetRarity", "maxDismissRarity", "allowDismiss",
        "cashReserve", "minHome", "maxCost", "maxSpend", "maxAttempts"}) do result[key] = custom[key] end
    if settings.policy == "Legendary or better" then result.targetRarity = 5
    elseif settings.policy == "Mythic or better" then result.targetRarity = 6
    elseif settings.policy ~= nil and settings.policy ~= "Custom" and settings.policy ~= "Bounded replacement" then
        return nil
    end
    return result
end

function Methods:NewReplacementTransactions(storage, scope)
    if not self.replacement or type(self.replacementTransactions) ~= "table"
        or type(self.replacementTransactions.new) ~= "function" then
        return nil, "Crew replacement transaction modules unavailable"
    end
    return self.replacementTransactions.new(storage, scope, self.replacement)
end

function Methods:AttachReplacementOwner(owner)
    if not self.replacement or type(owner) ~= "table" or owner.helper ~= self.replacement
        or type(owner.Active) ~= "function" or type(owner.IsPreparedHere) ~= "function"
        or type(owner.scope) ~= "table" or owner.scope.release ~= self.replacement.release then
        return false, "Matching durable Crew replacement owner required"
    end
    self.replacementOwner = owner
    return true, nil
end

function Methods:ReservationSources()
    return {{id = "crewReplacement", read = function(raw)
        if self.closed then return nil, "Crew tab closed" end
        if self.replacementFault then return nil, self.replacementFault end
        if not self.replacementOwner then return nil end
        if type(self.replacementOwner.ReservationClaims) ~= "function" then return nil, "Crew custody source missing" end
        return self.replacementOwner:ReservationClaims(self.reservationModule, raw)
    end}}
end

function Methods:Close()
    self.closed = true
    if self.replacementRuntime then self.replacementRuntime:Close() end
    if self.replacementOwner and type(self.replacementOwner.Close) == "function" then self.replacementOwner:Close() end
end

function Methods:PlanReplacement(view, settings)
    local mapped = CrewTab.ReplacementSettings(settings)
    if not mapped then return nil, "Unknown Crew replacement policy" end
    if mapped.enabled ~= true then return nil, "Crew replacement disabled" end
    local owner = self.replacementOwner
    if not owner or owner.closed or type(view) ~= "table" or owner.scope.account ~= view.account
        or owner.scope.place ~= view.place or owner.scope.release ~= view.release
        or owner.scope.ownerId ~= view.ownerId then return nil, "Durable Crew replacement owner not connected" end
    local active = owner:Active()
    if not active then return self.replacement.propose(view, mapped) end
    for _, key in ipairs({"slot", "tier", "targetRarity", "maxDismissRarity", "allowDismiss",
        "cashReserve", "minHome", "maxCost", "maxSpend", "maxAttempts"}) do
        if mapped[key] ~= active.funded[key] then return nil, "Replacement choices changed; review saved custody" end
    end
    if active.stage == "sentDismiss" or active.stage == "sentHire" or active.stage == "observedMember" then
        return nil, "Saved replacement requires outcome reconciliation"
    end
    if active.stage ~= "observedEmpty" and not owner:IsPreparedHere() then
        return nil, "Recovered prepared replacement is held for review"
    end
    local proposal, reason
    if active.stage == "observedEmpty" or active.stage == "preparedHire" then
        proposal, reason = self.replacement.FundedHire(view.raw, active.funded)
    else proposal, reason = self.replacement.propose(view, mapped) end
    if proposal and active.stage ~= "observedEmpty" and (proposal.revision ~= active.proposal.revision
        or proposal.actionKey ~= active.proposal.actionKey) then
        return nil, "Prepared replacement snapshot changed; review saved custody"
    end
    return proposal, reason
end

function Methods:Descriptors()
    local roll = self.replacement or self.roll
    local planner = self.replacement and {propose = function(view, settings)
        return self:PlanReplacement(view, settings)
    end} or self.roll
    return { { id = "crew", reader = self.autoEquip,
        planner = self.autoEquip, evidence = self.autoEquip,recoverSaved=self.autoEquip.recoverSaved },
        { id = "crewGear", reader = self.gear,
            planner = self.gear, evidence = self.gear,recoverSaved=self.gear.recoverSaved },
        { id = "crewRoll", reader = roll,
            planner = planner, evidence = roll,
            lifecycle = self.replacementRuntime and self.replacementRuntime.lifecycle or nil },
        { id = "crewSort", reader = self.sort,
            planner = self.sort, evidence = self.sort,recoverSaved=self.sort.recoverSaved },
        { id = "crewHeal", reader = self.heal,
            planner = self.heal, evidence = self.heal,recoverSaved=self.heal.recoverSaved },
        { id = "crewTrain", reader = self.train,
            planner = self.train, evidence = self.train,recoverSaved=self.train.recoverSaved },
        { id = "crewHire", reader = self.hire,
            planner = self.hire, evidence = self.hire,recoverSaved=self.hire.recoverSaved },
        { id = "crewHealItems", reader = self.healItems,
            planner = self.healItems, evidence = self.healItems, recoverSaved = self.healItems.recoverSaved } }
end

return CrewTab
