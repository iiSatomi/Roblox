-- Scalar preferences -> existing Market helper shapes. Never reads or sends.
local MarketSettings = {}

local function integer(value, low, high)
    return type(value) == "number" and value == value
        and value % 1 == 0 and value >= low and value <= high
end

local function itemId(value)
    return type(value) == "string" and #value > 0 and #value <= 120
        and value:match("^[%w_%-]+$") ~= nil
end

-- Saved Config.MARKET.groupOfKind plus GameData misc kinds. RARITY_NAMES
-- has nine entries in the reviewed October 11 snapshot; unknown values hold.
local kinds = { weapon = true, armor = true, vehicle = true,
    crate = true, border = true, background = true, trophy = true,
    consumable = true, token = true }

local function csv(value, mode)
    if type(value) ~= "string" or #value > 1024 then return nil end
    local result, count = {}, 0
    if value:match("^%s*$") then return result end
    for rawToken in (value .. ","):gmatch("(.-),") do
        count = count + 1
        local token = rawToken:match("^%s*(.-)%s*$")
        if count > 64 or not itemId(token) then return nil end
        if mode == "kind" and not kinds[token] then return nil end
        if mode == "rarity" then
            if not token:match("^[1-9]$") then return nil end
            token = tonumber(token)
        end
        result[token] = true
    end
    return result
end

local watchNumbers = { minSales = { 3, 1000000 }, minUnits = { 3, 1000000000 },
    minMargin = { 1, 1000000 }, minMarginPct = { 0, 100 },
    undercutGold = { 0, 3 }, floorPct = { 90, 100 } }
local sellNumbers = { keepLoose = { 0, 999 }, maxQuantity = { 1, 999 },
    maxWithdraw = { 1, 999 }, maxWithdrawAttempts = { 0, 20 },
    minNet = { 1, 1000000000 }, minSales = { 3, 1000000 },
    minUnits = { 3, 1000000000 }, undercutGold = { 0, 3 },
    floorPct = { 90, 100 }, maxListings = { 0, 20 }, maxListAttempts = { 0, 20 } }
local rentNumbers = { goldReserve = { 0, 1000000000 },
    maxAttempts = { 0, 20 }, maxGoldSpend = { 0, 1000 } }
local flipNumbers = { maxBuy = { 0, 9999999 }, sessionBudget = { 0, 1000000000 },
    goldReserve = { 0, 1000000000 }, maxAttempts = { 0, 20 }, maxListAttempts = { 0, 20 } }
local agingNumbers = { minAgeHours = { 1, 720 },
    demandMultiplier = { 1, 5 }, maxReviews = { 1, 20 } }

local function validateNumbers(options, ranges, allowed)
    for field, range in pairs(ranges) do
        allowed[field] = true
        if not integer(options[field], range[1], range[2]) then return false end
    end
    return true
end

local function subset(options, fields)
    local result = {}
    for _, field in ipairs(fields) do result[field] = options[field] end
    return result
end

local function selection(options, allowed)
    for _, field in ipairs({ "scope", "selectedItemId", "excludedItems",
        "excludedKinds", "excludedRarities" }) do allowed[field] = true end
    if options.scope ~= "Selected item" and options.scope ~= "All eligible items" then
        return nil, "Explicit Market item scope required"
    end
    if type(options.selectedItemId) ~= "string"
        or (options.selectedItemId ~= "" and not itemId(options.selectedItemId))
        or (options.scope == "Selected item" and options.selectedItemId == "") then
        return nil, "Select a Market item ID or explicitly select all eligible items"
    end
    local items, blockedKinds, rarities = csv(options.excludedItems),
        csv(options.excludedKinds, "kind"), csv(options.excludedRarities, "rarity")
    if not items or not blockedKinds or not rarities then
        return nil, "Invalid Market item, kind or rarity exclusions"
    end
    return { scope = options.scope, selectedItemId = options.selectedItemId,
        blockedItems = items, blockedKinds = blockedKinds, blockedRarities = rarities }, nil
end

function MarketSettings.projectSelection(options)
    local chosen, reason = selection(options, {})
    if not chosen then return nil, reason end
    return {selection = chosen}, nil
end

-- Read-only preview: no invented run counters and no dispatch permission.
function MarketSettings.projectSalePreview(options)
    if type(options) ~= "table" then return nil, "Current sale preferences required" end
    local chosen, reason = selection(options, {})
    if not chosen then return nil, reason end
    if not validateNumbers(options, sellNumbers, {})
        or type(options.likelyOnly) ~= "boolean"
        or type(options.fromCollection) ~= "boolean" then
        return nil, "Invalid Market sale preferences"
    end
    return {selection = chosen, custody = {keepLoose = options.keepLoose,
        maxQuantity = options.maxQuantity, fromCollection = options.fromCollection,
        blockedItems = chosen.blockedItems, blockedKinds = chosen.blockedKinds,
        blockedRarities = chosen.blockedRarities},
        quote = subset(options, {"minSales", "minUnits", "minNet", "likelyOnly", "undercutGold", "floorPct"})}, nil
end

local function watch(options)
    return subset(options, { "minSales", "minUnits", "minMargin", "minMarginPct",
        "undercutGold", "floorPct", "requireCoverage" })
end

function MarketSettings.project(feature, options, state)
    if type(options) ~= "table" or type(options.enabled) ~= "boolean" then
        return nil, "Typed Market preferences required"
    end
    if feature ~= "marketWatch" and feature ~= "marketSell" and feature ~= "marketFlip"
        and feature ~= "marketRent" and feature ~= "marketManage" then
        return nil, "Unknown Market activity"
    end
    if not options.enabled then return nil, "Market activity disabled" end
    local result, allowed = {}, { enabled = true }
    if feature == "marketManage" then
        allowed.minEarnings = true
        if not integer(options.minEarnings, 1, 1000000000) then
            return nil, "Invalid Market earned-payout minimum"
        end
        result.earnings = { enabled = true, minEarnings = options.minEarnings }
    elseif feature == "marketRent" then
        if not validateNumbers(options, rentNumbers, allowed) then
            return nil, "Invalid Market rental limits"
        end
        if type(state) ~= "table" or not integer(state.spent, 0, 1000)
            or not integer(state.attempted, 0, 20) then
            return nil, "Current independent rental run counters required"
        end
        if options.maxAttempts == 0 or options.maxGoldSpend <= state.spent then
            return nil, "Market rental spend or attempt limit disabled"
        end
        result.rent = { goldReserve = options.goldReserve, maxAttempts = options.maxAttempts,
            maxGoldSpend = options.maxGoldSpend - state.spent }
        result.attempted = state.attempted
    else
        local chosen, reason = selection(options, allowed)
        if not chosen then return nil, reason end
        result.selection = chosen
        if feature == "marketSell" then
            if not validateNumbers(options, sellNumbers, allowed)
                or type(options.fromCollection) ~= "boolean"
                or type(options.likelyOnly) ~= "boolean" then
                return nil, "Invalid Market sale limits"
            end
            allowed.fromCollection, allowed.likelyOnly = true, true
            if type(state) ~= "table" or type(state.transactionOpen) ~= "boolean"
                or not integer(state.listingAttempts, 0, 20)
                or not integer(state.withdrawAttempts, 0, 20) then
                return nil, "Current independent sale run counters required"
            end
            if options.maxListings == 0 or options.maxListAttempts == 0 then
                return nil, "Market listing attempt limits disabled"
            end
            if options.fromCollection and options.maxWithdrawAttempts == 0 then
                return nil, "Collection withdrawal attempt limit disabled"
            end
            result.custody = { keepLoose = options.keepLoose, maxQuantity = options.maxQuantity,
                fromCollection = options.fromCollection, blockedItems = chosen.blockedItems,
                blockedKinds = chosen.blockedKinds, blockedRarities = chosen.blockedRarities }
            result.quote = subset(options, { "minSales", "minUnits", "minNet", "likelyOnly",
                "undercutGold", "floorPct" })
            result.directList = { minNet = options.minNet, maxListings = options.maxListings,
                transactionOpen = state.transactionOpen }
            result.followupList = { minNet = options.minNet, maxListAttempts = options.maxListAttempts }
            if options.fromCollection then
                result.withdraw = { maxWithdraw = options.maxWithdraw,
                    maxAttempts = options.maxWithdrawAttempts }
            end
            result.listingAttempts, result.withdrawAttempts = state.listingAttempts, state.withdrawAttempts
        else
            if not validateNumbers(options, watchNumbers, allowed)
                or type(options.requireCoverage) ~= "boolean" then
                return nil, "Invalid Market research thresholds"
            end
            allowed.requireCoverage = true
            result.watch = watch(options)
            if feature == "marketWatch" then
                if not validateNumbers(options, agingNumbers, allowed) then
                    return nil, "Invalid Market listing-review limits"
                end
                result.aging = { minAgeHours = options.minAgeHours,
                    minSales = options.minSales, minSoldUnits = options.minUnits,
                    demandMultiplier = options.demandMultiplier, maxReviews = options.maxReviews }
            else
                if not validateNumbers(options, flipNumbers, allowed) then
                    return nil, "Invalid Market flip limits"
                end
                if type(state) ~= "table" or type(state.transactionOpen) ~= "boolean"
                    or not integer(state.spent, 0, 1000000000)
                    or not integer(state.attempted, 0, 20) then
                    return nil, "Current independent flip run counters required"
                end
                if options.maxBuy == 0 or options.sessionBudget == 0
                    or options.maxAttempts == 0 or options.maxListAttempts == 0 then
                    return nil, "Market flip spend or attempt limits disabled"
                end
                result.buyBudget = { maxBuy = options.maxBuy, sessionBudget = options.sessionBudget,
                    goldReserve = options.goldReserve, maxAttempts = options.maxAttempts,
                    transactionOpen = state.transactionOpen, blockedItems = chosen.blockedItems,
                    blockedKinds = chosen.blockedKinds, blockedRarities = chosen.blockedRarities }
                result.followupList = { minMargin = options.minMargin, maxListAttempts = options.maxListAttempts }
                result.spent, result.attempted = state.spent, state.attempted
            end
        end
    end
    local count = 0
    for key in pairs(options) do
        count = count + 1
        if count > 32 or not allowed[key] then return nil, "Unknown Market preference" end
    end
    return result, nil
end

-- Selection/exclusions only. A true result supplies no tradability/custody proof.
function MarketSettings.allows(projected, item)
    local chosen = type(projected) == "table" and projected.selection
    if type(chosen) ~= "table" or type(item) ~= "table" or not itemId(item.id)
        or not kinds[item.kind] or not integer(item.rarity, 1, 9)
        or type(chosen.blockedItems) ~= "table" or type(chosen.blockedKinds) ~= "table"
        or type(chosen.blockedRarities) ~= "table"
        or (chosen.scope ~= "Selected item" and chosen.scope ~= "All eligible items") then
        return false, "Current Market item selection required"
    end
    if chosen.scope == "Selected item" and item.id ~= chosen.selectedItemId
        or chosen.blockedItems[item.id] or chosen.blockedKinds[item.kind]
        or chosen.blockedRarities[item.rarity] then
        return false, "Item excluded by Market scope or filters"
    end
    return true, nil
end

return MarketSettings
