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
-- Saved Interface extensions were absent from Core.defaults but used by the
-- old planner as c[purpose .. "UseBank"] == true. Import the complete group
-- when present, so omitted old flags cannot inherit broader current defaults.
local savedFundingTargets = {
    heistsUseBank = "withdraw.custom.allowHeists",
    operationsUseBank = "withdraw.custom.allowOperations",
    propertiesUseBank = "withdraw.custom.allowProperties",
    safehouseUseBank = "withdraw.custom.allowSafehouse",
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
    shopBuyAll = "shop.custom.selection",
    shopSelected = "shop.custom.selectedIds",
    shopKind = "shop.custom.kind",
    shopRule = "shop.custom.priceRule",
    shopCashMax = "shop.custom.cashMax",
    shopOwnedCap = "shop.custom.ownedCap",
    shopMinRarity = "shop.custom.minRarity",
    shopCosmetics = "shop.custom.allowCosmetics",
    shopCrates = "shop.custom.allowCrates",
    shopRarityOverride = "shop.custom.rarityOverride",
    shopOverrideRarities = "shop.custom.overrideRarities",
    shopUseBank = "withdraw.custom.allowShop",
    bossHitDelay = "bosses.custom.confirmationDelay",
    bossMode = "bosses.custom.selection",
    globalBossHealthFloor = "globalBossAttack.custom.healthFloor",
    globalBossHitBufferPct = "globalBossAttack.custom.hitBufferPct",
    globalBossAttackDelay = "globalBossAttack.custom.minimumDelay",
    globalBossAttackMaxPerLoad = "globalBossAttack.custom.maxPerLoad",
    globalBossClaimMaxPerLoad = "globalBossClaim.custom.maxPerLoad",
    bossMinLevel = "bosses.custom.minLevel",
    bossMaxLevel = "bosses.custom.maxLevel",
    bossShopItem = "bossShop.custom.itemId",
    bossShopQuantity = "bossShop.custom.crateQuantity",
    bossShopTokenReserve = "bossShop.custom.tokenReserve",
    bossShopMaxPerLoad = "bossShop.custom.maxSends",
    crewGearObjective = "crewGear.policy",
    healthFloor = "combat.custom.healthFloor",
    staminaReserve = "combat.custom.staminaReserve",
    crewHealStaminaReserve = "crewHeal.custom.staminaReserve",
    crewTrainTargetLevel = "crewTrain.custom.targetLevel",
    crewTrainMaxCost = "crewTrain.custom.maxCost",
    crewTrainConcurrent = "crewTrain.custom.maxConcurrent",
    chestLimit = "chests.custom.totalLimit",
    chestLimitEnabled = "chests.custom.totalLimitEnabled",
    consumableHealthBelow = "restoratives.custom.healthBelow",
    consumableEnergyBelow = "restoratives.custom.energyBelow",
    consumableStaminaBelow = "restoratives.custom.staminaBelow",
    marketFlipMaxBuy = "marketFlip.custom.maxBuy",
    marketFlipGoldReserve = "marketFlip.custom.goldReserve",
    marketFlipSessionBudget = "marketFlip.custom.sessionBudget",
    -- Legacy Market.flipCandidate compares absolute net Gold, not a percentage.
    marketFlipMinMargin = "marketFlip.custom.minMargin",
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
    marketUndercutGold = "marketSell.custom.undercutGold",
    marketPriceFloorPct = "marketSell.custom.floorPct",
    marketRentGoldReserve = "marketRent.custom.goldReserve",
    marketCollectMinimum = "marketManage.custom.minEarnings",
    marketAgingHours = "marketWatch.custom.minAgeHours",
    familyCashAmount = "familyCash.custom.amount",
    familyGoldAmount = "familyGold.custom.amount",
    familyGoldReserve = "familyGold.custom.reserve",
    familyStaminaAmount = "familyStamina.custom.amount",
    familyStaminaReserve = "familyStamina.custom.reserve",
    familyPerk = "familyStamina.custom.selectedPerk",
    familyPerks = "familyStamina.custom.selectedPerk",
    stationMinHome = "station.custom.minHome",
    stationMaxStationed = "station.custom.maxStationed",
    heistMode = "heists.policy",
    heistSelection = "heists.custom.selection",
    selectedHeists = "heists.custom.selectedIds",
    heistLimits = "heists.custom.limitsEnabled",
    heistMinLevel = "heists.custom.minLevel", heistMaxLevel = "heists.custom.maxLevel",
    heistMinEnergy = "heists.custom.minEnergy", heistMaxEnergy = "heists.custom.maxEnergy",
    heistMinCrateRarity = "heists.custom.minCrateRarity",
    heistMaxHours = "heists.custom.maxHours", heistMaxHelps = "heists.custom.maxHelps",
    favorMode = "favors.policy",
    favorMinCash = "favors.custom.minRewardCash", favorMinXp = "favors.custom.minRewardXp",
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
    residencyMaxRent = "residency.custom.maxRentPct",
    trophyGoalId = "trophyFocus.custom.goalId",
    prestigeMaxRank = "prestige.custom.targetRank",
    combatHighEnabled = "combat.memory.preferHighValue",
    combatHighPromoteCash = "combat.memory.promoteCash",
    combatHighDemoteBelow = "combat.memory.demoteBelow",
    combatHighDemoteHits = "combat.memory.demoteHits",
    combatPriority = "combat.custom.targetPriority",
    combatDailyOnly = "combat.custom.dailyOnly",
    combatMinimum = "combat.custom.minimumPayout",
    combatMinWinRate = "combat.custom.minWinRate",
    combatMinWinChance = "combat.custom.minWinChance",
}

local translations = {
    -- Core.crewHire uses the same native tier ID; no hire allowance is imported.
    contractHireTier = { target = "crewHire.policy", options = { Street = "street", Professional = "professional", Elite = "elite" } },
    crewRollRarity = { target = "crewRoll.custom.targetRarity", options = { Common = 1, Uncommon = 2, Rare = 3, Epic = 4, Legendary = 5, Mythic = 6, Secret = 7, Forbidden = 8 } },
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
local shopFields = { "shopKind", "shopRule", "shopCashMax", "shopOwnedCap", "shopMinRarity",
    "shopCosmetics", "shopCrates", "shopRarityOverride", "shopOverrideRarities", "shopUseBank" }
-- The old shared switch gates level/cost ranges for both fight modes and samples for ordinary mugs.
local combatRanges = { combatMinTargetLevel = "minTargetLevel", combatMaxTargetLevel = "maxTargetLevel",
    combatMinStaminaCost = "minStaminaCost", combatMaxStaminaCost = "maxStaminaCost", combatMinSamples = "minSamples" }
local restorativeModes = { "consumableHealthMode", "consumableEnergyMode", "consumableStaminaMode" }
local restorativeModeKeys = { consumableHealthMode = true, consumableEnergyMode = true, consumableStaminaMode = true }
local restorativeThresholds = { consumableHealthBelow = true, consumableEnergyBelow = true, consumableStaminaBelow = true }
-- Every deliberately excluded schema-17 control is explained in the visible review.
-- Exclusion retains original intent; it never applies a permission or resets a ledger.
local blockedReasons = {
    perAction = "The old global per-action limit was replaced by feature-specific spending rules; select current limits explicitly.",
    sessionBudget = "The old global session budget was replaced by feature-specific allowances; import cannot establish unused funds.",
    propertyReplace = "Legacy property replacement permits selling an owned property; current import cannot authorize replacement or sale.",
    propertyReplaceMultiplier = "The replacement income multiplier has no current Property replacement control; it cannot become a purchase ROI preference.",
    propertyReplacePaybackHours = "The replacement payback-hours ceiling has no current equivalent; an ordinary purchase budget does not preserve it.",
    combatNativeRefresh = "Forced native hit-list refresh is a separate action; no current profile preference imports that opt-in.",
    prestigeMaxPerLoad = "Legacy resets per load are not the durable reset allowance; consumed or unknown resets cannot be cleared by import.",
    interval = "Legacy outbound spacing has no profile equivalent; the current one-second minimum and request owner remain authoritative.",
    timeout = "Legacy response timeout cannot replace the current 45-second unconfirmed-action deadline or establish cancellation.",
    readTimeout = "Legacy read timeout has no current profile field; source-owned read deadlines and stale-response checks remain.",
    combatConfirmGrace = "Legacy Combat confirmation grace has no current equivalent; elapsed time cannot prove the current owned fight outcome.",
    antiAfk = "Legacy anti-AFK activation has no current profile equivalent; native idle handling is not permission to start a fallback.",
    botCheckCapture = "Legacy bot-check evidence capture has no current profile switch; challenge handling remains native and manual.",
    acrylic = "Fluent acrylic is not an Ember preference; the visual choice is retained for manual theme review.",
    transparent = "Fluent transparency has no reviewed Ember profile equivalent; the original visual choice is retained.",
    theme = "Legacy Fluent theme names are not current Ember theme IDs; no nearest theme is guessed.",
    collectionObjective = "Legacy Attack/Defense/Balanced Collection scoring has no current surplus-donation objective control.",
    crewGearStrategy = "Legacy safe-swap or complete-set strategy is not the current native equip objective; no strategy is substituted.",
    briefcaseUseKeys = "Spending owned Briefcase keys requires separate current permission; legacy activation is never imported.",
    briefcaseKeyLimit = "The legacy Briefcase key-use limit has no current profile equivalent; import cannot reset consumed key allowance.",
    crateLuckOnly = "The old crate luck-only condition has no current Chest preference; dropping it would allow opening outside the chosen luck window.",
    consumableUseTradable = "Choose current item-custody permission explicitly; a legacy size preference never authorizes tradable consumption.",
    shopGold = "Legacy Gold Shop purchasing is a separate currency permission; current selected-Cash Shop controls cannot represent it.",
    shopGoldMax = "The legacy per-offer Gold ceiling has no current Cash-Shop equivalent; it cannot become Cash budget or earned-Gold permission.",
    shopGoldReserve = "The legacy Shop Gold reserve has no current Shop Gold lane; importing it into another feature would change its scope.",
    marketResearchMode = "Legacy turnover research modes have no exact current item-scope and evidence-policy equivalent.",
    marketSellMaxListingsPerLoad = "Legacy listing count per load is not the current durable listing-attempt allowance; prior or unknown listings cannot be reset.",
    marketRentMaxPerLoad = "Legacy rentals per load are not the current durable rental-attempt allowance; consumed or uncertain rentals remain owned.",
    marketAutoCheck = "Native manual challenge resolution is retained; automatic answering is not imported.",
    eventScheduling = "Legacy event-based scheduling has no current profile ordering switch; independent feature priorities remain unchanged.",
    xpTargetLevel = "The legacy XP target belongs to an unported progression controller; it is not a Trophy ID or permission to borrow activities.",
    heistPoll = "Legacy Heist poll cadence has no current profile equivalent; the native board source and request owner control refreshes.",
    favorUsageDay = "The Favor usage-day ledger identifies historical consumption; importing it as a preference could reset daily custody.",
    favorUsageCount = "The Favor usage-count ledger must be reconciled separately; import cannot invent remaining daily allowance.",
    sabotageEnabled = "Sabotage activation is a separate sensitive-action permission; no legacy enabled flag starts a current sender.",
    sabotageDailyCap = "The old sabotage daily cap has no current profile field; it cannot become a fresh attempt allowance without its ledger.",
    sabotageFavorReserve = "The sabotage-only Favor reserve has no current profile equivalent; mapping it to ordinary Favor help would change scope.",
    sabotageEnergyReserve = "The sabotage-only Energy reserve has no current profile equivalent; a shared reserve would change other activities.",
    sabotageUsageDay = "The sabotage usage-day ledger belongs to historical outcomes and cannot be reset or imported as a preference.",
    sabotageUsageCount = "The sabotage usage-count ledger must retain historical outcomes; import cannot grant an unused daily allowance.",
    sabotageAttemptDay = "The sabotage attempt-day ledger includes attempted actions; import cannot clear their day ownership.",
    sabotageAttemptCount = "The sabotage attempt-count ledger includes unknown outcomes; it must be reconciled without resetting attempted allowance.",
    playtimeEnergy = "Allowing an immediate Playtime Energy refill is a separate current permission; legacy consent is not imported.",
    playtimeEnergyBelow = "The legacy Playtime Energy threshold has no current profile field; it cannot grant refill permission or select a reward.",
    contractFocus = "Legacy Contract reprioritization is not the current explicit borrowing policy; current activity permissions must stay independent.",
    autoContracts = "Legacy Auto Contracts activation cannot enable the current controller or any of its independent borrowing permissions.",
    contractExcluded = "Legacy objective exclusions have no current profile list; silently dropping them could allow an explicitly excluded goal.",
    trophyFocus = "Legacy Trophy Focus activation cannot enable the current controller or its separate activity-borrowing permissions.",
    combatWarPriority = "Legacy War queue priority is not permission for the separate current War sender; there is no equivalent ordering field.",
    combatTakedownPriority = "Legacy Takedown queue priority has no current scheduler preference and cannot enable Family Boss attacks.",
    combatScout = "Paid scouting requires separate current Scout consent and attempted-Stamina allowance; neither is imported.",
    combatExploreUnknown = "Legacy exploration of unknown opponents cannot bypass current evidence requirements or grant player-attack permission.",
    combatProfileRefresh = "Legacy public-profile refresh cadence is not the current maximum evidence age; source-owned freshness remains.",
    combatScoutRefresh = "Legacy Scout refresh cadence is not current stats freshness or permission to spend Stamina on scouting.",
    combatMinPowerRatio = "Legacy scout power ratio constrained ordinary and War fights; the current ratio gates War only, so mapping it would lose ordinary-fight intent.",
    combatTargetRefresh = "Legacy target-cache refresh cadence has no current profile field; it is not native forced-refresh permission.",
    crewRollUseBank = "Using Bank funds for Crew hiring needs current funding permission; legacy settings cannot authorize withdrawal.",
    replaceCrew = "Replacing Crew can permanently dismiss a member; legacy opt-in cannot grant current dismissal permission or choose a slot.",
    crewRollWorstFirst = "Legacy worst-first Crew selection is not the current explicitly selected member slot; no member is chosen implicitly.",
    replaceWeakCrew = "Legacy weak-quality rerolls can dismiss owned Crew; current import cannot authorize dismissal or recreate that quality strategy.",
    crewRollMinQuality = "The legacy combined Crew-quality threshold has no current rarity-only replacement equivalent.",
    crewRollMinAttackQuality = "The legacy attack-quality percentile floor has no current Crew replacement field; rarity cannot represent it.",
    crewRollMinDefenseQuality = "The legacy defense-quality percentile floor has no current Crew replacement field; rarity cannot represent it.",
    crewRollQualityScope = "Legacy quality reroll scope across selected or higher rarities is not a current dismissal-rarity cap or selected-slot policy.",
    crewRollLuckOnly = "The legacy Crew luck-only condition has no current hire preference; dropping it would permit hiring outside the chosen luck window.",
    skipConfirmation = "Confirmation bypass is not supported; native confirmation remains required.",
    familyCashMaxPerLoad = "Legacy Family Cash per-load spending is not a fresh durable contribution allowance; prior or unknown consumption must remain held.",
    familyGoldMaxPerLoad = "Legacy Family Gold per-load spending cannot initialize unused durable allowance or reconcile unknown contribution custody.",
    familyStaminaMaxPerLoad = "Legacy Family Stamina per-load spending cannot reset durable consumption or grant remaining contribution allowance.",
    familyHospitalOnly = "The legacy hospital-only Family healing condition has no current profile field; dropping it would widen eligible patients.",
    familyStaminaOnlyStationed = "The legacy stationed-only contribution condition has no current Family Stamina field; omitting it changes contribution eligibility.",
    familyBossHealthFloor = "The legacy Family Boss health floor has no current profile field; ordinary or Global Boss floors do not cover this separate action.",
    familyBossStaminaReserve = "The legacy Family Boss Stamina reserve has no current profile field; mapping it to another combat lane would change scope.",
    familyBossStrategy = "Legacy Steady/Rank focus Family Boss strategies have no current profile equivalent; rank-based attack ordering is not inferred.",
    residencyMinImprovement = "Legacy minimum improvement compares a candidate against the existing residence; current minimum share is an absolute floor.",
    residencyDistricts = "Legacy district allowlist cannot map to the current single selected district without losing candidate selection intent.",
    stationSignificantHpPercent = "The legacy significant-health threshold for station choices has no current explicit-member stationing field.",
    stationMove = "Legacy automatic Crew movement combines recall and transfer; import cannot choose destinations or enable either action.",
    stationTrainRotation = "Legacy training rotation can recall and redeploy Crew; it is not current explicit station or recall permission.",
    stationMoveMinDeficit = "Legacy minimum destination defender deficit is not the current minimum retained garrison; their comparison and scope differ.",
    stationCombatRecovery = "Legacy automatic combat-recovery recall cannot enable the current explicit Crew recall action.",
    stationRecoveryHealth = "The legacy health-triggered recovery threshold has no current explicit-recall field; no threshold is silently discarded.",
    stationMinSourceDefenders = "Legacy retained defenders constrained automatic moves; mapping it to every current explicit recall would change its scope.",
    stationMoveCooldownMinutes = "Legacy automatic-move cooldown has no current explicit-station/recall profile equivalent; elapsed time cannot release unknown custody.",
    combatSource = "Only Saved history and History then discover have reviewed equivalents. Scout new hit-list targets inferred paid Scout permission; choose current source and separate Scout consent explicitly.",
    heistId = "The cached single Heist ID maps only with Selected heist mode and an unambiguous selection; importing it alone would change active targeting.",
}

local function copy(raw)
    local seen, nodes = {}, 0
    local function visit(value, depth)
        nodes = nodes + 1
        if nodes > 8192 or depth > 8 then error("Legacy import exceeds limits") end
        local kind = type(value)
        if type(value) == "number" and (value ~= value or math.abs(value) == math.huge)
            or type(value) == "string" and #value > 65536
            or kind ~= "table" and kind ~= "number" and kind ~= "string" and kind ~= "boolean" then
            error("Invalid legacy value")
        end
        if type(value) ~= "table" then return value end
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
        mapped = {}, currentDefaults = {}, defaultExclusions = {}, unresolved = {}, unresolvedReasons = {} }
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
    local hasSavedFunding = false
    for key in pairs(savedFundingTargets) do
        if settings[key] ~= nil then hasSavedFunding = true end
    end
    if hasSavedFunding then
        local mapped, valid = {}, true
        for key, target in pairs(savedFundingTargets) do
            local choice = settings[key]
            if choice == nil then choice = false end
            if type(choice) ~= "boolean" then
                block(key, "Saved purpose-specific Bank funding must be an explicit boolean.")
                valid = false
            else mapped[target] = choice end
        end
        if valid then
            if model:Validate({schema = 1, values = mapped}, true) then
                for target, choice in pairs(mapped) do report.mapped[target] = choice end
            else
                for key in pairs(savedFundingTargets) do
                    if settings[key] ~= nil then
                        block(key, "Current purpose-specific Bank funding controls are unavailable; no shared withdrawal permission is substituted.")
                    end
                end
            end
        end
    end
    local shopHandled, hasShop = {}, settings.shopBuyAll ~= nil
    for _, key in ipairs(shopFields) do if settings[key] ~= nil then hasShop = true end end
    if settings.shopSelected ~= nil and (type(settings.shopSelected) ~= "table" or next(settings.shopSelected) ~= nil) then hasShop = true end
    if hasShop then
        local mapped, valid = {}, true
        local function refuse(key, reason) block(key, reason); valid = false end
        local function selectionMap(value, rarity)
            if type(value) ~= "table" then return nil end
            local ids, count = {}, 0
            for id, on in pairs(value) do
                count = count + 1
                if count > 64 or type(id) ~= "string" or #id > 120 or not id:match("^[%w_%-]+$")
                    or type(on) ~= "boolean" or rarity and not saleRarities[id] then return nil end
                if on then ids[#ids + 1] = rarity and saleRarities[id] or id end
            end
            table.sort(ids)
            return table.concat(ids, ",")
        end
        for _, key in ipairs(shopFields) do
            shopHandled[key] = true
            local value = settings[key]
            if value == nil then value = defaults[key] end
            if key == "shopOverrideRarities" then value = selectionMap(value, true)
            elseif key == "shopKind" then value = ({["All gear"]="Combat gear",weapon="Weapons",armor="Armor",vehicle="Vehicles"})[value] or value end
            local target = targets[key]
            if value == nil or not model:Validate({schema=1,values={[target]=value}}, true) then
                refuse(key, "Invalid or unavailable cash Shop preference; the complete Shop group must be reviewed.")
            else mapped[target] = value end
        end
        shopHandled.shopBuyAll, shopHandled.shopSelected = true, true
        local mode = settings.shopBuyAll
        if mode ~= nil and type(mode) ~= "boolean" then refuse("shopBuyAll", "Saved Shop mode must be a boolean; no mode is inferred.") end
        local selected = settings.shopSelected
        if selected == nil then selected = {} end
        local ids = selectionMap(selected, false)
        if not ids then refuse("shopSelected", "Shop selections must be bounded item-ID-to-boolean maps.")
        elseif mode == nil and ids ~= "" then refuse("shopSelected", "A nonempty saved Shop selection needs its explicit shopBuyAll mode.") end
        mapped[targets.shopBuyAll] = mode == nil and "Category rules" or mode == true and "All cash items" or "Selected cash items"
        mapped[targets.shopSelected] = ids or ""
        if valid and not model:Validate({schema=1,values=mapped}, true) then
            refuse("shopBuyAll", "Current cash Shop selection controls are unavailable; no fallback item is imported.")
        end
        if valid then for target, value in pairs(mapped) do report.mapped[target] = value end end
    end
    local heistModes = {["Best chest"]=true,Balanced=true,["Highest tier"]=true,["Lowest stake"]=true,["XP / hour"]=true,["Profit / hour"]=true,["Selected heist"]=true}
    local favorModes = {Balanced=true,["Cash reward"]=true,["XP reward"]=true,["Ending soon"]=true,["Highest tier"]=true}
    if settings.heistMode ~= nil and not heistModes[settings.heistMode] then block("heistMode", "Unknown legacy Heist policy; no current-only policy is substituted.") end
    if settings.favorMode ~= nil and not favorModes[settings.favorMode] then block("favorMode", "Unknown legacy Favor policy; no current-only policy is substituted.") end
    local singleHeist = settings.heistMode == "Selected heist"
    if singleHeist then
        local id = settings.heistId
        local valid = type(id) == "string" and #id > 0 and #id <= 120 and id:match("^[%w_%-]+$")
        if settings.heistSelection ~= nil and settings.heistSelection ~= "Only selected" then valid = false end
        if settings.selectedHeists ~= nil then
            if type(settings.selectedHeists) ~= "table" then valid = false
            else
                for selected, on in pairs(settings.selectedHeists) do
                    if type(on) ~= "boolean" or type(selected) ~= "string" or on and selected ~= id then valid = false end
                end
            end
        end
        if valid then
            report.mapped["heists.policy"], report.mapped["heists.custom.selection"] = "Best chest", "Only selected"
            report.mapped["heists.custom.selectedIds"] = id
        else
            block("heistMode", "Selected heist needs one explicit unambiguous ID; conflicting selections require review.")
            block("heistId", "Selected heist needs one explicit unambiguous ID; conflicting selections require review.")
        end
    end
    if settings.heistLimits == true then
        for _, group in ipairs({{"heistMinLevel", "heistMaxLevel"}, {"heistMinEnergy", "heistMaxEnergy"}}) do
            local low, high = settings[group[1]], settings[group[2]]
            if low == nil then low = defaults[group[1]] end
            if high == nil then high = defaults[group[2]] end
            if type(low) ~= "number" or low ~= low or type(high) ~= "number" or high ~= high or low > high then
                block(group[1], "Legacy Heist bounds must be an inclusive non-inverted range.")
                block(group[2], "Legacy Heist bounds must be an inclusive non-inverted range.")
            end
        end
    end
    if type(settings.heistMinCrateRarity) == "number" and settings.heistMinCrateRarity > 8 then
        block("heistMinCrateRarity", "Legacy chest rarity must be within its original 1 to 8 range.")
    end
    if type(settings.favorMinXp) == "number" and settings.favorMinXp > 1e12 then
        block("favorMinXp", "Legacy XP threshold exceeds its original supported range.")
    end
    -- Legacy Boss bounds were always active. An explicitly present bound,
    -- including a default-valued one, imports the complete original range.
    local bossBounds = settings.bossMinLevel ~= nil or settings.bossMaxLevel ~= nil
    if bossBounds then
        local low, high = settings.bossMinLevel, settings.bossMaxLevel
        if low == nil then low = defaults.bossMinLevel end
        if high == nil then high = defaults.bossMaxLevel end
        local valid = type(low) == "number" and low == low and low % 1 == 0
            and low >= 1 and low <= 10000
            and type(high) == "number" and high == high and high % 1 == 0
            and high >= 1 and high <= 10000 and low <= high
        if not valid then
            block("bossMinLevel", "Legacy Boss bounds must form an inclusive integer range within 1 to 10000.")
            block("bossMaxLevel", "Legacy Boss bounds must form an inclusive integer range within 1 to 10000.")
        else
            report.mapped["bosses.custom.limitsEnabled"] = true
            report.mapped["bosses.custom.minLevel"] = low
            report.mapped["bosses.custom.maxLevel"] = high
        end
    end
    if settings.bossMaxHits ~= nil or settings.bossMaxStamina ~= nil then
        local hits, stamina = settings.bossMaxHits, settings.bossMaxStamina
        if hits == nil then hits = defaults.bossMaxHits end
        if stamina == nil then stamina = defaults.bossMaxStamina end
        if type(hits) ~= "number" or hits ~= hits or hits < 1 or hits > 100000
            or type(stamina) ~= "number" or stamina ~= stamina or stamina < 1 or stamina > 100000 then
            block("bossMaxHits", "Confirmed encounter limits must be within 1 to 100000.")
            block("bossMaxStamina", "Confirmed encounter limits must be within 1 to 100000.")
        else
            report.mapped["bosses.custom.confirmedLimitsEnabled"] = true
            report.mapped["bosses.custom.maxConfirmedHits"] = hits
            report.mapped["bosses.custom.maxConfirmedStamina"] = stamina
        end
    end
    -- Retain the shared choice when equal; mixed pools include omitted legacy defaults.
    local sharedMode, modesAgree, modesValid = nil, true, true
    for _, key in ipairs(restorativeModes) do
        local value = settings[key]
        if value == nil then value = defaults[key] end
        if value ~= "Balanced" and value ~= "Small first" and value ~= "Large first" then
            block(key, "Unknown legacy restorative size policy; no choice is substituted.")
            modesValid = false
        end
        if sharedMode ~= nil and value ~= sharedMode then modesAgree = false end
        sharedMode = value
    end
    if modesValid and not modesAgree then
        for index, key in ipairs(restorativeModes) do
            local value = settings[key]
            if value == nil then value = defaults[key] end
            if value == "Balanced" then value = "Balanced recovery" end
            local pool = ({ "health", "energy", "stamina" })[index]
            local target = "restoratives.custom." .. pool .. "Policy"
            if model:Validate({schema = 1, values = {[target] = value}}, true) then
                report.mapped[target] = value
            else block(key, "Current restorative pool policy unavailable.") end
        end
    elseif modesValid and sharedMode ~= "Balanced" then
        local mapped = { ["restoratives.policy"] = sharedMode }
        if model:Validate({schema = 1, values = mapped}, true) then
            report.mapped["restoratives.policy"] = sharedMode
        else
            for _, key in ipairs(restorativeModes) do block(key, "Current restorative policy unavailable.") end
        end
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
        if (key == "selectedOperations" or key == "selectedProperties" or key == "selectedHeists" or saleMaps[key]) and type(value) == "table" then
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
        if key == "familyPerks" and type(value) == "table" then
            local ids = {}
            for id, on in pairs(value) do
                if type(id) ~= "string" or type(on) ~= "boolean"
                    or not model:Validate({schema = 1, values = {[target] = id}}, true) then
                    block(key, "Family perks must be a current perk-ID-to-boolean map.")
                elseif on then ids[#ids + 1] = id end
            end
            table.sort(ids)
            if #ids == 0 then block(key, "Empty Family perk selections need explicit review.") end
            if #ids > 1 then target = "familyStamina.custom.selectedPerks" end
            mappedValue = #ids == 1 and ids[1] or table.concat(ids, ",")
        end
        if shopHandled[key] then
            -- Cash rules form one validated group; activity and remaining budgets are never imported.
        elseif savedFundingTargets[key] then
            -- The complete extension group was validated above; withdrawal stays off.
        elseif key == "shopSelected" and type(value) == "table" and next(value) == nil then
            report.currentDefaults[#report.currentDefaults + 1] = key
            report.defaultExclusions[key] = "The empty saved Shop selection contains no selected IDs. No offer is imported; current Shop defaults remain off, and an explicit saved selection mode still requires review."
        elseif baseline == nil or type(value) ~= type(baseline)
            or type(value) == "number" and math.abs(value) > 9007199254740991 then block(key)
        elseif singleHeist and (key == "heistMode" or key == "heistId" or key == "heistSelection" or key == "selectedHeists") then
            -- This original single-ID group was validated and mapped above.
        elseif key == "bossMinLevel" or key == "bossMaxLevel" or key == "bossMaxHits" or key == "bossMaxStamina" then
            -- The complete explicitly bounded legacy group was validated above.
            if same(value, baseline) then report.currentDefaults[#report.currentDefaults + 1] = key end
        elseif restorativeThresholds[key] and value == 0 then
            local policyTarget = target:gsub("Below$", "Policy")
            local mapped = {[target] = 0, [policyTarget] = "Off"}
            if model:Validate({schema = 1, values = mapped}, true) then
                for destination, choice in pairs(mapped) do report.mapped[destination] = choice end
            else block(key, "Current restorative pool disable unavailable.") end
        elseif restorativeModeKeys[key] then
            -- The complete pool-policy group, including omitted defaults, was checked above.
            if same(value, baseline) then report.currentDefaults[#report.currentDefaults + 1] = key end
        elseif settings.combatLimits == true and (key == "combatLimits" or combatRanges[key]) then
            -- The complete enabled group was validated above, including omitted legacy defaults.
            if same(value, baseline) then report.currentDefaults[#report.currentDefaults + 1] = key end
        elseif same(value, baseline) and key ~= "combatSource" and key ~= "familyPerks" and key ~= "bossMode" and key ~= "favorMode" and key ~= "bossHitDelay" and key ~= "globalBossAttackMaxPerLoad" and key ~= "globalBossClaimMaxPerLoad" and key ~= "marketFlipMinMargin" and not restorativeThresholds[key] then
            if key ~= "version" then report.currentDefaults[#report.currentDefaults + 1] = key end
        elseif key == "familyPerk" and settings.familyPerks ~= nil then block(key)
        elseif target then
            if mappedValue == nil then block(key)
            else
                local mapped = { [target] = mappedValue }
                if key == "bossHitDelay" then mapped["bosses.custom.confirmationDelayEnabled"] = true end
                if key == "globalBossAttackMaxPerLoad" then mapped["globalBossAttack.custom.useLoadCap"]=true end
                if key == "globalBossClaimMaxPerLoad" then mapped["globalBossClaim.custom.useLoadCap"]=true end
                -- Legacy sale exclusions and gentleAsk pricing guard both trade lanes.
                if saleMaps[key] or key == "marketUndercutGold" or key == "marketPriceFloorPct" then
                    mapped["marketFlip.custom." .. target:match("([^%.]+)$")] = mappedValue
                elseif key == "crewRollRarity" then
                    -- Presets override targetRarity in CrewTab.ReplacementSettings.
                    -- Custom preserves the requested threshold without enabling dismissal.
                    mapped["crewRoll.policy"] = "Custom"
                elseif key == "healthFloor" or key == "staminaReserve" then
                    mapped["warCombat.custom." .. key] = mappedValue
                    mapped["bosses.custom." .. key] = mappedValue
                    if key == "staminaReserve" then mapped["globalBossAttack.custom.staminaReserve"] = mappedValue end
                elseif key == "combatPriority" then
                    mapped["warCombat.custom.targetPriority"] = mappedValue
                end
                local prepared = model:Validate({ schema = 1, values = mapped }, true)
                if not prepared then block(key, "The legacy value is outside the current control's supported values.")
                else
                    for destination, choice in pairs(mapped) do report.mapped[destination] = choice end
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
