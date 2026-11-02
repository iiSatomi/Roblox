-- Inert schema-17 preview. Non-default unsupported intent blocks staging.
local LegacySettings = {}
local defaults = {
    version = 17,
    jobMode = 'XP / energy',
    jobId = '',
    jobCity = '',
    masteryTarget = 'Gold',
    energyReserve = 0,
    jobLimits = false,
    propertyLimits = false,
    operationLimits = false,
    heistLimits = false,
    combatLimits = false,
    jobMinLevel = 1,
    jobMaxLevel = 10000,
    jobMinEnergy = 0,
    jobMaxEnergy = 1000000000000,
    depositThreshold = 10000,
    bankCashToKeep = 0,
    withdrawalLimit = 1000000,
    perAction = 100000,
    sessionBudget = 1000000,
    propertyCap = 10,
    propertyMode = 'ROI',
    propertyReplace = false,
    propertyReplaceMultiplier = 2,
    propertyReplacePaybackHours = 0,
    propertyMinLevel = 1,
    propertyMaxLevel = 10000,
    propertySelection = 'Automatic',
    selectedProperties = {},
    operationMode = 'Profit / hour',
    operationSelection = 'Automatic',
    selectedOperations = {},
    minOperationHours = 0,
    maxOperationHours = 24,
    operationMinLevel = 1,
    operationMaxLevel = 10000,
    operationMinCrateRarity = 0,
    healthFloor = 50,
    staminaReserve = 1,
    combatNativeRefresh = false,
    bossMode = 'Smart',
    bossMinLevel = 1,
    bossMaxLevel = 10000,
    bossMaxHits = 100,
    bossMaxStamina = 100,
    bossHitDelay = 5,
    bossShopItem = 'crate_loot',
    bossShopQuantity = 1,
    bossShopTokenReserve = 0,
    bossShopMaxPerLoad = 1,
    globalBossHealthFloor = 50,
    globalBossHitBufferPct = 25,
    globalBossAttackDelay = 5,
    globalBossAttackMaxPerLoad = 25,
    globalBossClaimMaxPerLoad = 1,
    prestigeMaxRank = 6,
    prestigeMaxPerLoad = 6,
    skill = 'energy',
    skillCap = 25,
    skillBatchMax = 100,
    interval = 1,
    timeout = 15,
    readTimeout = 8,
    combatConfirmGrace = 1,
    antiAfk = false,
    botCheckCapture = true,
    acrylic = false,
    transparent = false,
    theme = 'DuoTone Dark Earth',
    collectionObjective = 'Balanced',
    crewGearObjective = 'Balanced',
    crewGearStrategy = 'Safe swaps',
    briefcaseUseKeys = false,
    briefcaseKeyLimit = 10,
    crateLuckOnly = false,
    consumableHealthBelow = 25,
    consumableStaminaBelow = 25,
    consumableEnergyBelow = 25,
    consumableHealthMode = 'Balanced',
    consumableEnergyMode = 'Balanced',
    consumableStaminaMode = 'Balanced',
    consumableUseTradable = false,
    crewTrainMinRarity = 'Legendary',
    crewTrainTargetLevel = 3,
    crewTrainMaxCost = 100000000,
    crewTrainConcurrent = 1,
    chestLimit = 1,
    chestLimitEnabled = false,
    shopKind = 'All allowed',
    shopRule = 'Buy all allowed',
    shopCashMax = 100000,
    shopOwnedCap = 0,
    shopMinRarity = 1,
    shopCosmetics = false,
    shopCrates = false,
    shopRarityOverride = false,
    shopOverrideRarities = {Secret=true,Forbidden=true},
    shopUseBank = false,
    shopGold = false,
    shopGoldMax = 0,
    shopGoldReserve = 0,
    marketFlipMaxBuy = 100,
    marketFlipGoldReserve = 0,
    marketFlipSessionBudget = 500,
    marketFlipMinMargin = 10,
    marketFlipMinSales = 10,
    marketResearchMode = 'Balanced',
    marketSellKeepLoose = 1,
    marketSellMaxQuantity = 10,
    marketSellMinNet = 5,
    marketSellMinSales = 3,
    marketSellMaxListingsPerLoad = 5,
    marketSellFromCollection = true,
    marketSellLikelyOnly = false,
    marketSellBlockedKinds = {},
    marketSellBlockedRarities = {},
    marketSellBlockedItems = {},
    marketRentGoldReserve = 5,
    marketRentMaxPerLoad = 1,
    marketAutoCheck = true,
    marketCollectMinimum = 1,
    marketAgingHours = 24,
    eventScheduling = false,
    xpTargetLevel = 200,
    marketUndercutGold = 1,
    marketPriceFloorPct = 95,
    heistMode = 'Best chest',
    heistSelection = 'Automatic',
    selectedHeists = {},
    heistMaxHelps = 6,
    heistMaxHours = 2,
    heistPoll = 15,
    heistId = '',
    heistMinLevel = 1,
    heistMaxLevel = 10000,
    heistMinEnergy = 0,
    heistMaxEnergy = 1000000000000,
    heistMinCrateRarity = 1,
    favorMode = 'Balanced',
    favorRelationship = 'Friends & family',
    favorDailyCap = 5,
    favorReserve = 5,
    favorEnergyReserve = 10,
    favorMinCash = 0,
    favorMinXp = 0,
    favorUsageDay = -1,
    favorUsageCount = 0,
    sabotageEnabled = false,
    sabotageDailyCap = 5,
    sabotageFavorReserve = 5,
    sabotageEnergyReserve = 10,
    sabotageUsageDay = -1,
    sabotageUsageCount = 0,
    sabotageAttemptDay = -1,
    sabotageAttemptCount = 0,
    safehouseCap = 16,
    playtimeEnergy = false,
    playtimeEnergyBelow = 50,
    contractFocus = false,
    autoContracts = false,
    contractExcluded = {},
    trophyFocus = false,
    trophyGoalId = '',
    combatMinimum = 100000000,
    combatMinWinRate = 70,
    combatMinSamples = 1,
    combatPriority = 'Risk-adjusted value',
    combatDailyOnly = true,
    combatSource = 'Saved history',
    combatWarPriority = true,
    combatTakedownPriority = false,
    combatHighEnabled = false,
    combatHighPromoteCash = 1000000000,
    combatHighDemoteBelow = 100000000,
    combatHighDemoteHits = 3,
    combatScout = false,
    combatExploreUnknown = false,
    combatMinWinChance = 60,
    combatProfileRefresh = 600,
    combatScoutRefresh = 1800,
    combatMinPowerRatio = 1,
    combatMinTargetLevel = 1,
    combatMaxTargetLevel = 10000,
    combatMinStaminaCost = 1,
    combatMaxStaminaCost = 5,
    combatTargetRefresh = 30,
    crewRollTier = 'Street',
    crewRollRarity = 'Legendary',
    crewRollCashReserve = 1000000,
    crewRollUseBank = false,
    replaceCrew = false,
    crewRollWorstFirst = true,
    replaceWeakCrew = false,
    crewRollMinQuality = 25,
    crewRollMinAttackQuality = 0,
    crewRollMinDefenseQuality = 0,
    crewRollQualityScope = 'Selected rarity only',
    crewRollLuckOnly = false,
    crewHealStaminaReserve = 10,
    contractHireTier = 'Street',
    contractHireMaxCost = 10000,
    skipConfirmation = false,
    familyCashAmount = 1000000,
    familyCashMaxPerLoad = 1000000,
    familyGoldAmount = 1,
    familyGoldReserve = 0,
    familyGoldMaxPerLoad = 0,
    familyStaminaAmount = 1,
    familyStaminaReserve = 0,
    familyStaminaMaxPerLoad = 25,
    familyPerk = 'runners',
    familyPerks = {runners=true},
    familyHospitalOnly = false,
    familyStaminaOnlyStationed = false,
    familyBossHealthFloor = 50,
    familyBossStaminaReserve = 1,
    familyBossStrategy = 'Steady',
    residencyKind = 'landlord',
    residencyMaxRent = 0,
    residencyMinImprovement = 0,
    residencyDistricts = {},
    stationMinHome = 2,
    stationMaxStationed = 8,
    stationSignificantHpPercent = 50,
    stationMove = false,
    stationTrainRotation = false,
    stationMoveMinDeficit = 3,
    stationCombatRecovery = false,
    stationRecoveryHealth = 50,
    stationMinSourceDefenders = 2,
    stationMoveCooldownMinutes = 30,
}
local targets = {
    operationLimits = "operations.custom.limitsEnabled",
    operationMinLevel = "operations.custom.minLevel",
    operationMaxLevel = "operations.custom.maxLevel",
    minOperationHours = "operations.custom.minHours",
    maxOperationHours = "operations.custom.maxHours",
    operationMinCrateRarity = "operations.custom.minCrateRarity",
    operationSelection = "operations.custom.selection",
    selectedOperations = "operations.custom.selectedIds",
    energyReserve = "shared.energyReserve",
    masteryTarget = "jobs.custom.masteryTarget",
    jobCity = "jobs.custom.city",
    jobLimits = "jobs.custom.limitsEnabled",
    jobMinLevel = "jobs.custom.minLevel",
    jobMaxLevel = "jobs.custom.maxLevel",
    jobMinEnergy = "jobs.custom.minCost",
    jobMaxEnergy = "jobs.custom.maxCost",
    jobId = "jobs.custom.selectedJobId",
    crewRollCashReserve = "crewRoll.custom.cashReserve",
    depositThreshold = "bank.custom.depositThreshold",
    bankCashToKeep = "bank.custom.cashToKeep",
    withdrawalLimit = "withdraw.custom.maxWithdrawal",
    bossShopItem = "bossShop.custom.itemId",
    bossShopQuantity = "bossShop.custom.crateQuantity",
    bossShopTokenReserve = "bossShop.custom.tokenReserve",
    bossShopMaxPerLoad = "bossShop.custom.maxSends",
    crewGearObjective = "crewGear.policy",
    crewHealStaminaReserve = "crewHeal.custom.staminaReserve",
    crewTrainTargetLevel = "crewTrain.custom.targetLevel",
    crewTrainMaxCost = "crewTrain.custom.maxCost",
    crewTrainConcurrent = "crewTrain.custom.maxConcurrent",
    consumableHealthBelow = "restoratives.custom.healthBelow",
    consumableEnergyBelow = "restoratives.custom.energyBelow",
    consumableStaminaBelow = "restoratives.custom.staminaBelow",
    marketFlipMaxBuy = "marketFlip.custom.maxBuy",
    marketFlipGoldReserve = "marketFlip.custom.goldReserve",
    marketFlipSessionBudget = "marketFlip.custom.sessionBudget",
    marketFlipMinSales = "marketFlip.custom.minSales",
    marketSellFromCollection = "marketSell.custom.fromCollection",
    marketSellBlockedItems = "marketSell.custom.excludedItems",
    marketSellBlockedKinds = "marketSell.custom.excludedKinds",
    marketSellBlockedRarities = "marketSell.custom.excludedRarities",
    marketSellKeepLoose = "marketSell.custom.keepLoose",
    marketSellMaxQuantity = "marketSell.custom.maxQuantity",
    marketSellMinNet = "marketSell.custom.minNet",
    marketSellMinSales = "marketSell.custom.minSales",
    marketSellLikelyOnly = "marketSell.custom.likelyOnly",
    marketCollectMinimum = "marketManage.custom.minEarnings",
    marketAgingHours = "marketWatch.custom.minAgeHours",
    familyCashAmount = "familyCash.custom.amount",
    familyGoldAmount = "familyGold.custom.amount",
    familyGoldReserve = "familyGold.custom.reserve",
    familyStaminaAmount = "familyStamina.custom.amount",
    familyStaminaReserve = "familyStamina.custom.reserve",
    familyPerk = "familyStamina.custom.selectedPerk",
    stationMinHome = "station.custom.minHome",
    stationMaxStationed = "station.custom.maxStationed",
    favorDailyCap = "favors.custom.maxDailyAttempts",
    favorReserve = "favors.custom.minFavorReserve",
    favorEnergyReserve = "favors.custom.minEnergyReserve",
    skill = "skills.custom.stat",
    skillBatchMax = "skills.custom.batchSize",
    skillCap = "skills.custom.maxAllocations",
    safehouseCap = "safehouse.custom.maxTier",
    propertyCap = "properties.custom.ownedLimit",
    propertyLimits = "properties.custom.limitsEnabled",
    propertyMinLevel = "properties.custom.minLevel",
    propertyMaxLevel = "properties.custom.maxLevel",
    propertySelection = "properties.custom.selection",
    selectedProperties = "properties.custom.selectedIds",
    contractHireMaxCost = "crewHire.custom.maxCost",
    residencyKind = "residency.custom.selectedKind",
    prestigeMaxRank = "prestige.custom.targetRank",
    combatPriority = "combat.custom.targetPriority",
    combatDailyOnly = "combat.custom.dailyOnly",
    combatMinimum = "combat.custom.minimumPayout",
    combatMinWinRate = "combat.custom.minWinRate",
    combatMinWinChance = "combat.custom.minWinChance",
}

local translations = {
    combatSource = { target = "combat.custom.targetSource", options = { ["Saved history"] = "Saved only", ["History then discover"] = "Saved and new" } },
    jobMode = { target = "jobs.policy", options = { ["XP / energy"] = "XP", ["Cash / energy"] = "Cash", ["Selected job"] = "Selected job", ["Job count"] = "Job count", ["Highest tier"] = "Highest tier", Mastery = "Mastery" } },
    propertyMode = { target = "properties.policy", options = { ROI = "Best value", Income = "Most income", ["Highest tier"] = "Highest tier" } },
    operationMode = { target = "operations.policy", options = { ["Best chest"] = "Best chest", ["Highest tier"] = "Highest tier", ["Profit / hour"] = "Profit / hour", ["XP / hour"] = "XP / hour", ["Shortest duration"] = "Shortest duration", Balanced = "Balanced" } },
    crewTrainMinRarity = { target = "crewTrain.custom.minRarity", options = { Epic = 4, Legendary = 5, Mythic = 6, Secret = 7, Forbidden = 8 } },
    crewRollTier = { target = "crewRoll.custom.tier", options = { Street = "street", Professional = "professional", Elite = "elite" } },
    favorRelationship = { target = "favors.custom.relations", options = { ["Friends only"] = "Friends only", ["Family only"] = "Family only" } },
}
-- Legacy Core.rarityNames / Market.saleExcluded; current MarketSettings CSV contract.
local saleRarities = { Common = "1", Uncommon = "2", Rare = "3", Epic = "4", Legendary = "5",
    Mythic = "6", Secret = "7", Forbidden = "8", Contraband = "9" }
local saleKinds = { weapon = true, armor = true, vehicle = true, crate = true, border = true,
    background = true, trophy = true, consumable = true, token = true }
local saleMaps = { marketSellBlockedItems = true, marketSellBlockedKinds = true, marketSellBlockedRarities = true }
-- The old shared switch gates level/cost ranges for both fight modes and samples for ordinary mugs.
local combatRanges = { combatMinTargetLevel = "minTargetLevel", combatMaxTargetLevel = "maxTargetLevel",
    combatMinStaminaCost = "minStaminaCost", combatMaxStaminaCost = "maxStaminaCost", combatMinSamples = "minSamples" }
local blockedReasons = {
    combatHighEnabled = "The legacy parallel high-value lane has no direct equivalent. High-only sources require a separate explicit current choice; no lane is auto-enabled.",
    combatHighPromoteCash = "Current owned tracking uses fixed default rules: promote at 1B confirmed Cash, demote after 3 consecutive payouts below 100M. Custom rules and historical replay require separate review.",
    combatHighDemoteBelow = "Current owned tracking uses fixed default rules: promote at 1B confirmed Cash, demote after 3 consecutive payouts below 100M. Custom rules and historical replay require separate review.",
    combatHighDemoteHits = "Current owned tracking uses fixed default rules: promote at 1B confirmed Cash, demote after 3 consecutive payouts below 100M. Custom rules and historical replay require separate review.",
    combatSource = "Only Saved history and History then discover have reviewed equivalents. Scout new hit-list targets inferred paid Scout permission; choose current source and separate Scout consent explicitly.",
    perAction = "The legacy engine replaced this global limit with feature-specific spending rules. Select current per-feature limits explicitly.",
    sessionBudget = "The legacy engine replaced this global budget with feature-specific spending rules. Select current per-feature allowances explicitly.",
    skipConfirmation = "Confirmation bypass is not supported; native confirmation remains required.",
    marketAutoCheck = "Native manual challenge resolution is retained; automatic answering is not imported.",
    favorUsageDay = "Runtime ledger data must be reconciled separately, never imported as a preference.",
    favorUsageCount = "Runtime ledger data must be reconciled separately, never imported as a preference.",
    sabotageUsageDay = "Runtime ledger data must be reconciled separately, never imported as a preference.",
    sabotageUsageCount = "Runtime ledger data must be reconciled separately, never imported as a preference.",
    sabotageAttemptDay = "Runtime ledger data must be reconciled separately, never imported as a preference.",
    sabotageAttemptCount = "Runtime ledger data must be reconciled separately, never imported as a preference.",
}

local function copy(raw)
    local seen, nodes = {}, 0
    local function visit(value, depth)
        nodes = nodes + 1
        if nodes > 8192 or depth > 8 then error("Legacy import exceeds limits") end
        local kind = type(value)
        if kind == "number" and (value ~= value or math.abs(value) == math.huge)
            or kind == "string" and #value > 65536
            or kind ~= "table" and kind ~= "number" and kind ~= "string" and kind ~= "boolean" then
            error("Invalid legacy value")
        end
        if kind ~= "table" then return value end
        if seen[value] or getmetatable(value) ~= nil then error("Invalid legacy table") end
        seen[value] = true
        local result = {}
        for key, child in pairs(value) do
            if type(key) ~= "string" and type(key) ~= "number" then error("Invalid legacy key") end
            result[key] = visit(child, depth + 1)
        end
        seen[value] = nil
        return result
    end
    local ok, value = pcall(visit, raw, 0)
    return ok and value or nil
end
local function same(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not same(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
function LegacySettings.defaults() return copy(defaults) end
function LegacySettings.preview(raw, model)
    local original = copy(raw)
    if not original then return nil, nil, "Invalid or oversized legacy settings" end
    local report = { baseline = 17, original = original,
        mapped = {}, currentDefaults = {}, unresolved = {}, unresolvedReasons = {} }
    local settings = original.settings or original
    if type(settings) ~= "table" or settings.version ~= 17 then
        return nil, report, "Unsupported legacy settings version; expected 17"
    end
    local unresolved = {}
    local function block(key, reason)
        key = tostring(key)
        unresolved[key] = true
        report.unresolvedReasons[key] = reason or blockedReasons[key]
            or "No reviewed equivalent for this legacy choice; original intent is retained. Choose current settings explicitly."
    end
    if settings.combatLimits == true then
        for key, field in pairs(combatRanges) do
            local value = settings[key]
            if value == nil then value = defaults[key] end
            local pages = key == "combatMinSamples" and {"combat"} or {"combat", "warCombat"}
            for _, page in ipairs(pages) do
                local target = page .. ".custom." .. field
                local prepared = model:Validate({schema = 1, values = {[target] = value}}, true)
                if not prepared or key == "combatMinSamples" and (type(value) ~= "number" or value < 1) then
                    block(key, "The enabled legacy Combat bound is outside the current supported range.")
                else report.mapped[target] = value end
            end
        end
        for _, pair in ipairs({{"combatMinTargetLevel", "combatMaxTargetLevel"}, {"combatMinStaminaCost", "combatMaxStaminaCost"}}) do
            local low, high = settings[pair[1]], settings[pair[2]]
            if low == nil then low = defaults[pair[1]] end
            if high == nil then high = defaults[pair[2]] end
            if type(low) == "number" and type(high) == "number" and low > high then
                block(pair[1], "The enabled legacy Combat range is inverted.")
                block(pair[2], "The enabled legacy Combat range is inverted.")
            end
        end
    end
    if settings.jobMode == "Selected job" and (type(settings.jobId) ~= "string" or settings.jobId == "") then
        block("jobId", "Selected job requires an explicit current Job ID; no default Job is substituted.")
    end
    if original.settings ~= nil then
        for key in pairs(original) do
            if key ~= "settings" and key ~= "enabled" and key ~= "combatPermission" then block(key) end
        end
        if original.enabled ~= nil then
            if type(original.enabled) ~= "table" then block("enabled")
            else
                for key, value in pairs(original.enabled) do
                    if value ~= false or not model.specs[tostring(key) .. ".enabled"] then
                        block("enabled." .. tostring(key))
                    end
                end
            end
        end
        if original.combatPermission ~= nil and original.combatPermission ~= false then block("combatPermission") end
    end
    for key, value in pairs(settings) do
        local baseline, target = defaults[key], targets[key]
        local translation, mappedValue = translations[key], value
        if translation then target, mappedValue = translation.target, translation.options[value] end
        if (key == "selectedOperations" or key == "selectedProperties" or saleMaps[key]) and type(value) == "table" then
            local ids = {}
            for id, on in pairs(value) do
                if type(id) ~= "string" or #id > 120 or not id:match("^[%w_%-]+$") or type(on) ~= "boolean" then
                    block(key, "Selections must be a reviewed ID-to-boolean map.")
                elseif key == "marketSellBlockedKinds" and not saleKinds[id]
                    or key == "marketSellBlockedRarities" and not saleRarities[id] then
                    block(key, "Unknown legacy sale kind or rarity; no exclusion is guessed.")
                elseif on then ids[#ids + 1] = key == "marketSellBlockedRarities" and saleRarities[id] or id end
            end
            table.sort(ids)
            mappedValue = table.concat(ids, ",")
        end
        if baseline == nil or type(value) ~= type(baseline)
            or type(value) == "number" and math.abs(value) > 9007199254740991 then block(key)
        elseif settings.combatLimits == true and (key == "combatLimits" or combatRanges[key]) then
            -- The complete enabled group was validated above, including omitted legacy defaults.
            if same(value, baseline) then report.currentDefaults[#report.currentDefaults + 1] = key end
        elseif same(value, baseline) and key ~= "combatSource" then
            if key ~= "version" then report.currentDefaults[#report.currentDefaults + 1] = key end
        elseif key == "familyPerk" and settings.familyPerks ~= nil then block(key)
        elseif target then
            if mappedValue == nil then block(key)
            else
                local prepared = model:Validate({ schema = 1, values = { [target] = mappedValue } }, true)
                if not prepared then block(key, "The legacy value is outside the current control's supported values.")
                else
                    report.mapped[target] = mappedValue
                    if key == "combatPriority" then report.mapped["warCombat.custom.targetPriority"] = mappedValue end
                end
            end
        elseif combatRanges[key] then
            block(key, "Cached Combat ranges need combatLimits=true; importing an inactive range would activate it.")
        else block(key) end
    end
    if settings.jobLimits == true then
        for _, pair in ipairs({ { "jobMinLevel", "jobMaxLevel" }, { "jobMinEnergy", "jobMaxEnergy" } }) do
            local low, high = settings[pair[1]], settings[pair[2]]
            if low == nil then low = defaults[pair[1]] end
            if high == nil then high = defaults[pair[2]] end
            if type(low) == "number" and type(high) == "number" and low > high then
                block(pair[1], "The enabled legacy range is inverted; choose valid inclusive bounds.")
                block(pair[2], "The enabled legacy range is inverted; choose valid inclusive bounds.")
            end
        end
    end
    if settings.operationLimits == true then
        for _, pair in ipairs({ { "operationMinLevel", "operationMaxLevel" }, { "minOperationHours", "maxOperationHours" } }) do
            local low, high = settings[pair[1]], settings[pair[2]]
            if low == nil then low = defaults[pair[1]] end
            if high == nil then high = defaults[pair[2]] end
            if type(low) == "number" and type(high) == "number" and low > high then
                block(pair[1], "The enabled Operation range is inverted; choose valid inclusive bounds.")
                block(pair[2], "The enabled Operation range is inverted; choose valid inclusive bounds.")
            end
        end
    end
    if settings.propertyLimits == true then
        local low = settings.propertyMinLevel or defaults.propertyMinLevel
        local high = settings.propertyMaxLevel or defaults.propertyMaxLevel
        if type(low) == "number" and type(high) == "number" and low > high then
            block("propertyMinLevel", "The enabled Property range is inverted; choose valid inclusive bounds.")
            block("propertyMaxLevel", "The enabled Property range is inverted; choose valid inclusive bounds.")
        end
    end
    for key in pairs(unresolved) do report.unresolved[#report.unresolved + 1] = key end
    table.sort(report.unresolved)
    table.sort(report.currentDefaults)
    if #report.unresolved > 0 then
        return nil, report, "Legacy choices need review: " .. table.concat(report.unresolved, ", ")
    end
    local prepared, reason = model:Validate({ schema = 1, values = report.mapped }, true)
    if not prepared then return nil, report, reason end
    -- Every sender and newly required permission starts at current reviewed defaults.
    return { schema = 1, values = prepared }, report, nil
end
return LegacySettings
