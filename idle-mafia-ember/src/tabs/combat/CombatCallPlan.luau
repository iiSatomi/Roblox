-- Saved native signatures for the six ordinary Boss controls.
local CombatCallPlan = {}
local function familyId(value)
    return type(value) == "string" and #value > 0 and #value <= 120
        and not value:find("[%c]")
        or type(value) == "number" and value == value and value >= 1
            and value <= 9007199254740991 and value % 1 == 0
end

local gear = { w_policebaton = true,
    a_commissionerjacket = true,
    v_policeresponsevan = true,
    w_warbringer = true,
    a_warlordarmor = true,
    v_warwagon = true }
local crates = { crate_loot = true, crate_ashport = true,
    crate_smuggler = true, crate_iron = true,
    crate_dragon = true, crate_sterling = true,
    crate_veilmont = true, crate_vespera = true,
    crate_exiles = true }

local function integer(value, low, high)
    return type(value) == "number" and value == value
        and value % 1 == 0 and value >= low and value <= high
end

local function key(value)
    return type(value) == "string" and #value > 0
        and #value <= 120
end

function CombatCallPlan.describe(proposal)
    local intent = type(proposal) == "table" and proposal.intent
    if type(intent) ~= "table" then
        return nil, "Missing Combat call intent"
    end
    if (proposal.feature == "combat" or proposal.feature == "warCombat") and (intent.kind == "playerAttack" or intent.kind == "playerScout")
        and integer(intent.target, 1, 9007199254740991) and key(intent.targetName) and integer(intent.targetLevel, 1, 1000000)
        and type(intent.sourceKey) == "string" and #intent.sourceKey == 64 and intent.sourceKey:match("^[%x]+$")
        and integer(intent.expectedStaminaCost, 1, 5) and integer(intent.maxStaminaExposure, intent.expectedStaminaCost, 5)
        and type(proposal.resources) == "table" and proposal.resources.stamina == intent.maxStaminaExposure
        and (intent.kind ~= "playerScout" or intent.allowScout == true)
        and (proposal.feature ~= "warCombat" or familyId(intent.warEnemyFamilyId)
            and intent.warEnemyFamilyId == intent.familyId and familyId(intent.warOwnFamilyId)
            and intent.warOwnFamilyId ~= intent.warEnemyFamilyId
            and integer(intent.warDay, 0, 1000000000)) then
        return {remote = intent.kind == "playerScout" and "ScoutPlayer" or "Attack", method = "InvokeServer",
            arity = 1, args = {intent.target}, source = "current native ordinary player target call"}, nil
    end
    if proposal.feature == "bosses"
        and intent.kind == "bossStageAttack"
        and integer(intent.stage, 1, 100000) then
        return { remote = "BossAction", method = "InvokeServer",
            arity = 2, args = { "stageAttack", intent.stage },
            source = "saved BossTab ordinary stage attack" }, nil
    end
    if proposal.feature == "globalBossAttack"
        and intent.kind == "globalBossAttack"
        and key(intent.runKey) then
        return { remote = "GlobalBossAction", method = "InvokeServer",
            arity = 1, args = { "attack" },
            source = "saved GlobalBossTab attack" }, nil
    end
    if proposal.feature == "globalBossClaim"
        and intent.kind == "globalBossClaim"
        and key(intent.runKey) then
        return { remote = "GlobalBossAction", method = "InvokeServer",
            arity = 1, args = { "claim" },
            source = "saved GlobalBossTab claim" }, nil
    end
    if proposal.feature == "familyBossAttacks"
        and intent.kind == "familyBossAttack"
        and integer(intent.week, 1, 1000000000)
        and familyId(intent.famId)
        and integer(intent.stage, 1, 6) then
        return { remote = "FamilyBossAction", method = "InvokeServer",
            arity = 1, args = { "attack" },
            source = "saved FamilyBossView attack" }, nil
    end
    if proposal.feature == "familyBossClaims"
        and intent.kind == "familyBossClaim"
        and integer(intent.week, 1, 1000000000)
        and integer(intent.stage, 0, 100) then
        return { remote = "FamilyBossAction", method = "InvokeServer",
            arity = 3, args = { "claim", intent.week, intent.stage },
            source = "saved FamilyBossView exact claim" }, nil
    end
    if proposal.feature == "bossShop"
        and intent.kind == "bossShopBuy" then
        if gear[intent.item] and intent.itemKind == "gear"
            and intent.quantity == 1 then
            return { remote = "BossAction", method = "InvokeServer",
                arity = 3, args = { "shopBuy", intent.item },
                source = "saved BossTab gear shopBuy call" }, nil
        end
        if crates[intent.item] and intent.itemKind == "crate"
            and (intent.quantity == 1 or intent.quantity == 10) then
            return { remote = "BossAction", method = "InvokeServer",
                arity = 3,
                args = { "shopBuy", intent.item, intent.quantity },
                source = "saved BossTab crate shopBuy call" }, nil
        end
    end
    return nil, "Unverified Combat call"
end

return CombatCallPlan
