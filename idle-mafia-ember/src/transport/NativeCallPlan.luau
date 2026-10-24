-- Saved-client call descriptions only. This module never obtains or invokes a Remote.
local NativeCallPlan = {}

local gear = {
    w_policebaton = true, a_commissionerjacket = true,
    v_policeresponsevan = true, w_warbringer = true,
    a_warlordarmor = true, v_warwagon = true,
}
local crates = {
    crate_loot = true, crate_ashport = true,
    crate_smuggler = true, crate_iron = true,
    crate_dragon = true, crate_sterling = true,
    crate_veilmont = true, crate_vespera = true,
    crate_exiles = true,
}
local stats = { energy = true, stamina = true, health = true,
    attack = true, defense = true, property = true }

local function id(value)
    return type(value) == "string" and #value > 0
        and #value <= 120 and value:match("^[%w_]+$") ~= nil
end

local function key(value)
    return type(value) == "string" and #value > 0
        and #value <= 120
end

local function integer(value, low, high)
    return type(value) == "number" and value == value
        and value >= low and value <= high and value % 1 == 0
end

function NativeCallPlan.describe(proposal)
    local intent = type(proposal) == "table" and proposal.intent
    if type(intent) ~= "table" then
        return nil, "Missing native call intent"
    end
    if proposal.feature == "jobs" and intent.kind == "job" then
        if not id(intent.targetId) then
            return nil, "Invalid Job ID"
        end
        return { remote = "DoJob", method = "InvokeServer",
            arity = 1, args = { intent.targetId },
            source = "saved JobsTab DoJob call" }, nil
    end
    if proposal.feature == "operations"
        and intent.kind == "operationStart"
        and id(intent.targetId) then
        return { remote = "StartOperation", method = "InvokeServer",
            arity = 1, args = { intent.targetId },
            source = "saved OpsTab start call" }, nil
    end
    if proposal.feature == "collect"
        and intent.kind == "operationCollect"
        and integer(intent.index, 1, 16) then
        return { remote = "CollectOperation", method = "InvokeServer",
            arity = 1, args = { intent.index },
            source = "saved OpsTab collect call" }, nil
    end
    if proposal.feature == "contracts"
        and intent.kind == "contractEntryClaim"
        and integer(intent.index, 1, 5) then
        local command = intent.period == "daily" and "claim"
            or intent.period == "weekly" and "claimweekly" or nil
        if command and intent.command == command then
            return { remote = "ContractAction",
                method = "InvokeServer", arity = 3,
                args = { command, intent.index },
                source = "saved ContractsTab entry claim" }, nil
        end
    end
    if proposal.feature == "bonuses"
        and intent.kind == "contractBonusClaim" then
        local command = intent.period == "daily" and "claimbonus"
            or intent.period == "weekly" and "claimweeklybonus" or nil
        if command and intent.command == command then
            return { remote = "ContractAction",
                method = "InvokeServer", arity = 3,
                args = { command },
                source = "saved ContractsTab bonus claim" }, nil
        end
    end
    if proposal.feature == "briefcases"
        and intent.kind == "freeBriefcasePick"
        and intent.command == "open"
        and integer(intent.index, 1, 12) then
        return { remote = "BriefcaseAction", method = "InvokeServer",
            arity = 2, args = { "open", intent.index },
            source = "saved BriefcasesTab open call" }, nil
    end
    if proposal.feature == "skills"
        and intent.kind == "skillAllocation"
        and stats[intent.stat]
        and integer(intent.count, 1, 100) then
        return { remote = "AllocateSkillPoint",
            method = "InvokeServer", arity = 2,
            args = { intent.stat, intent.count },
            source = "saved Hud skill allocation" }, nil
    end
    if proposal.feature == "bank"
        and intent.kind == "bankDeposit"
        and integer(intent.amount, 1, 9007199254740991) then
        return { remote = "BankDeposit", method = "InvokeServer",
            arity = 1, args = { intent.amount },
            source = "saved BankTab deposit" }, nil
    end
    if proposal.feature == "withdraw"
        and intent.kind == "purposeWithdrawal"
        and integer(intent.amount, 1, 9007199254740991) then
        return { remote = "Withdraw", method = "InvokeServer",
            arity = 1, args = { intent.amount },
            source = "saved BankTab withdrawal" }, nil
    end
    if proposal.feature == "safehouse"
        and intent.kind == "safehouseUpgrade"
        and integer(intent.nextTier, 2, 18) then
        return { remote = "UpgradeSafehouse", method = "InvokeServer",
            arity = 0, args = {},
            source = "saved SafehouseTab upgrade" }, nil
    end
    if proposal.feature == "groupBonus"
        and intent.kind == "groupBonusClaim"
        and integer(intent.groupId, 1, 9007199254740991) then
        return { remote = "ClaimGroupBonus", method = "InvokeServer",
            arity = 0, args = {},
            source = "saved PropsTab group claim" }, nil
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
        and integer(intent.famId, 1, 9007199254740991)
        and integer(intent.stage, 1, 5) then
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
    if proposal.feature == "properties"
        and intent.kind == "propertyBuild"
        and id(intent.propId)
        and intent.optionalSlot == nil then
        -- The no-slot planner matches the saved BuyProperty(id, nil) call.
        return { remote = "BuyProperty", method = "InvokeServer",
            arity = 2, args = { intent.propId },
            source = "saved PropertyBlock no-slot buy" }, nil
    end
    if proposal.feature == "shop"
        and intent.kind == "shopCashBuy"
        and id(intent.itemId)
        and integer(intent.slot, 0, 1000000000)
        and integer(intent.expectedCost, 1, 1000000000000000) then
        return { remote = "BuyShopItem", method = "InvokeServer",
            arity = 3, args = { intent.itemId, nil,
                intent.expectedCost },
            source = "saved ShopTab cash-only buy" }, nil
    end
    if proposal.feature == "trophies"
        and intent.kind == "earnedTrophyClaim"
        and (intent.targetId == "t_eldersignet"
            or intent.targetId == "t_grudgeledger") then
        return { remote = "ClaimTrophy", method = "InvokeServer",
            arity = 1, args = { intent.targetId },
            source = "saved InventoryTab trophy claim" }, nil
    end
    if proposal.feature == "monthlyRewards"
        and intent.kind == "monthlyClaim"
        and integer(intent.month, 1, 12)
        and integer(intent.nextDay, 1, 31) then
        return { remote = "ClaimMonthly", method = "InvokeServer",
            arity = 0, args = {},
            source = "saved MonthlyCalendar claim" }, nil
    end
    if proposal.feature == "playtime"
        and intent.kind == "playtimeClaim"
        and integer(intent.index, 1, 7)
        and integer(intent.day, 1, 999999999) then
        return { remote = "ClaimLadder", method = "InvokeServer",
            arity = 1, args = { intent.index },
            source = "saved SafehouseTab ladder claim" }, nil
    end
    if proposal.feature == "marketManage"
        and intent.kind == "marketCollectEarnings"
        and integer(intent.earningsBefore, 1, 9007199254740991)
        and integer(intent.goldBefore, 0, 9007199254740991) then
        return { remote = "MarketAction", method = "InvokeServer",
            arity = 4, args = { "collect" },
            source = "saved MarketTab sold-earnings claim" }, nil
    end
    if proposal.feature == "bossShop"
        and intent.kind == "bossShopBuy" then
        if gear[intent.item] and intent.itemKind == "gear"
            and intent.quantity == 1 then
            -- The saved gear handler passes an explicit nil quantity.
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
        return nil, "Unverified Boss Shop item or quantity"
    end
    return nil, "No saved native call contract for feature"
end

return NativeCallPlan
