-- Ordered, inert composition map for implemented offline feature slices.
local FeatureRegistry = {}

local definitions = {
    { "heists", "HeistBoardState", "HeistStart", "HeistStartEvidence" },
    { "heistCollect", "HeistBoardState", "HeistCollect", "HeistCollectEvidence" },
    { "favors", "FavorsState", "FavorHelp", "FavorHelpEvidence" },
    { "sabotage", "SabotageState", "Sabotage", "SabotageEvidence" },
    { "jobs", "JobsState", "Jobs", "JobsEvidence" },
    { "bosses", "BossesState", "Bosses", "BossesEvidence" },
    { "globalBossAttack", "GlobalBossAttackState", "GlobalBossAttack", "GlobalBossAttackEvidence" },
    { "globalBossClaim", "GlobalBossClaimState", "GlobalBossClaim", "GlobalBossClaimEvidence" },
    { "familyBossAttacks", "FamilyBossAttackState", "FamilyBossAttacks", "FamilyBossAttacksEvidence" },
    { "familyBossClaims", "FamilyBossClaimState", "FamilyBossClaims", "FamilyBossClaimsEvidence" },
    { "bossShop", "BossShopBuyState", "BossShopBuy", "BossShopBuyEvidence" },
    { "operations", "OperationsState", "OperationsStart", "OperationsEvidence" },
    { "collect", "OperationsState", "OperationsCollect", "OperationsCollectEvidence" },
    { "skills", "SkillsState", "Skills", "SkillsEvidence" },
    { "groupBonus", "GroupBonusState", "GroupBonus", "GroupBonusEvidence" },
    { "monthlyRewards", "MonthlyRewardsState", "MonthlyRewards", "MonthlyRewardsEvidence" },
    { "trophies", "EarnedTrophiesState", "EarnedTrophies", "EarnedTrophiesEvidence" },
    { "playtime", "PlaytimeState", "Playtime", "PlaytimeEvidence" },
    { "contracts", "ContractEntriesState", "ContractEntries", "ContractEntriesEvidence" },
    { "bonuses", "ContractBonusesState", "ContractBonuses", "ContractBonusesEvidence" },
    { "briefcases", "FreeBriefcasesState", "FreeBriefcases", "FreeBriefcasesEvidence" },
    { "bank", "BankState", "BankDeposits", "BankDepositsEvidence" },
    { "safehouse", "SafehouseState", "SafehouseUpgrades", "SafehouseUpgradesEvidence" },
    { "withdraw", "WithdrawalState", "PurposeWithdrawals", "PurposeWithdrawalsEvidence" },
    { "properties", "PropertiesState", "Properties", "PropertiesEvidence" },
    { "prestige", "PrestigeState", "PrestigeBlocked", "PrestigeBlocked" },
    { "shop", "ShopState", "ShopBuy", "ShopBuyEvidence" },
    { "familyCash", "FamilyState", "FamilyBlocked", "FamilyBlocked" },
    { "familyStamina", "FamilyState", "FamilyBlocked", "FamilyBlocked" },
    { "familyGold", "FamilyState", "FamilyBlocked", "FamilyBlocked" },
    { "marketManage", "MarketEarningsState", "MarketEarnings", "MarketEarningsEvidence" },
}

local function name(value)
    return type(value) == "string" and #value > 0
end

local function dense(value, maximum)
    if type(value) ~= "table" then return false end
    local length, count = #value, 0
    if length < 1 or length > maximum then return false end
    for key in pairs(value) do
        if type(key) ~= "number" or key % 1 ~= 0
            or key < 1 or key > length then return false end
        count = count + 1
    end
    return count == length
end

function FeatureRegistry.requirements()
    local result = {}
    for index, row in ipairs(definitions) do
        result[index] = { id = row[1], reader = row[2],
            planner = row[3], evidence = row[4] }
    end
    return result
end

function FeatureRegistry.build(exports, catalog)
    if type(exports) ~= "table" or type(catalog) ~= "table"
        or type(catalog.features) ~= "table" then
        return nil, "Missing feature exports or UI catalog"
    end
    local controls = {}
    for _, feature in ipairs(catalog.features) do
        if type(feature) ~= "table" or not name(feature.id)
            or controls[feature.id] then
            return nil, "Invalid or duplicate UI feature ID"
        end
        controls[feature.id] = true
    end
    local specs, seen = {}, {}
    for _, definition in ipairs(definitions) do
        local id, readerName, plannerName, evidenceName =
            definition[1], definition[2], definition[3], definition[4]
        if not name(id) or seen[id] or not controls[id] then
            return nil, "Missing or duplicate UI feature: " .. tostring(id)
        end
        seen[id] = true
        local reader = exports[readerName]
        if type(reader) ~= "table" or type(reader.read) ~= "function" then
            return nil, "Invalid feature reader: " .. readerName
        end
        local planner = exports[plannerName]
        if type(planner) ~= "table" or type(planner.propose) ~= "function" then
            return nil, "Invalid feature planner: " .. plannerName
        end
        local evidence = exports[evidenceName]
        if type(evidence) ~= "table"
            or type(evidence.capture) ~= "function"
            or type(evidence.evaluate) ~= "function" then
            return nil, "Invalid feature evidence: " .. evidenceName
        end
        specs[#specs + 1] = { id = id, reader = reader,
            planner = planner, evidence = evidence }
    end
    return specs, nil
end

-- Incremental modular entry point; a tab may supply one or more features.
function FeatureRegistry.fromTabs(tabs, catalog)
    if not dense(tabs, 25)
        or type(catalog) ~= "table"
        or type(catalog.pages) ~= "table"
        or type(catalog.features) ~= "table" then
        return nil, "Missing tab registry inputs"
    end
    local pages, controls = {}, {}
    for _, page in ipairs(catalog.pages) do
        if type(page) ~= "table" or not name(page.id)
            or pages[page.id] then
            return nil, "Invalid UI page"
        end
        pages[page.id] = true
    end
    for _, feature in ipairs(catalog.features) do
        if type(feature) ~= "table" or not name(feature.id)
            or not pages[feature.page] or controls[feature.id] then
            return nil, "Invalid UI feature"
        end
        controls[feature.id] = feature.page
    end
    local specs, seenTabs, seenFeatures = {}, {}, {}
    for _, tab in ipairs(tabs) do
        if type(tab) ~= "table" or not name(tab.id)
            or not pages[tab.id] or seenTabs[tab.id]
            or type(tab.Descriptors) ~= "function" then
            return nil, "Missing or duplicate tab module"
        end
        seenTabs[tab.id] = true
        local ok, descriptors = pcall(tab.Descriptors, tab)
        if not ok or not dense(descriptors, 55) then
            return nil, "Invalid tab descriptors"
        end
        for _, spec in ipairs(descriptors) do
            if type(spec) ~= "table" or not name(spec.id)
                or controls[spec.id] ~= tab.id or seenFeatures[spec.id]
                or type(spec.reader) ~= "table"
                or type(spec.reader.read) ~= "function"
                or type(spec.planner) ~= "table"
                or type(spec.planner.propose) ~= "function"
                or type(spec.evidence) ~= "table"
                or type(spec.evidence.capture) ~= "function"
                or type(spec.evidence.evaluate) ~= "function" then
                return nil, "Invalid tab feature descriptor"
            end
            seenFeatures[spec.id] = true
            specs[#specs + 1] = { id = spec.id, page = tab.id,
                reader = spec.reader, planner = spec.planner,
                evidence = spec.evidence }
        end
    end
    return specs, nil
end

return FeatureRegistry
