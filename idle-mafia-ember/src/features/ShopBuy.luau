-- Source-ordered cash selection; native Auto Buy and paid offers stay separate.
local ShopBuy = {}
local MAX = 9007199254740991

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function nonnegative(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

-- Authorized Cash, not measured spend: sent outcomes retain exposure. The
-- checkpoint refunds only requests it proves never reached the native call.
function ShopBuy.copy(raw)
    if raw == nil then return {version = 1, attempted = 0, spent = 0} end
    if type(raw) ~= "table" or raw.version ~= 1 or raw.unknown ~= nil and raw.unknown ~= true
        or not integer(raw.attempted, 0) or not integer(raw.spent, 0)
        or raw.spent > MAX or raw.attempted > raw.spent
        or raw.attempted == 0 and raw.spent ~= 0 then return nil end
    for key in pairs(raw) do
        if key ~= "version" and key ~= "attempted" and key ~= "spent" and key ~= "unknown" then return nil end
    end
    return {version = 1, attempted = raw.attempted, spent = raw.spent, unknown = raw.unknown}
end

function ShopBuy.copyCharge(raw, feature, resources)
    if feature ~= "shop" or type(raw) ~= "table" or type(raw.itemId) ~= "string" or #raw.itemId == 0
        or not integer(raw.price, 1) or raw.price > MAX
        or not ShopBuy.copy({version = 1, attempted = raw.attemptedBefore, spent = raw.spentBefore})
        or raw.spentBefore > MAX - raw.price or type(resources) ~= "table"
        or resources.cash ~= raw.price then return nil end
    for key in pairs(resources) do if key ~= "cash" then return nil end end
    for key in pairs(raw) do
        if key ~= "itemId" and key ~= "price" and key ~= "attemptedBefore" and key ~= "spentBefore" then return nil end
    end
    return {itemId = raw.itemId, price = raw.price, attemptedBefore = raw.attemptedBefore, spentBefore = raw.spentBefore}
end

function ShopBuy.charge(raw, proposal)
    local usage = ShopBuy.copy(raw)
    local i = type(proposal) == "table" and proposal.intent
    if not usage or usage.unknown or type(i) ~= "table" or i.kind ~= "shopCashBuy"
        or type(i.limitTotal) ~= "boolean" or not integer(i.maxSpend, 0) or i.maxSpend > MAX then
        return nil, nil, "Shop Cash allowance intent invalid"
    end
    local charge = ShopBuy.copyCharge({itemId = i.itemId, price = i.expectedCost,
        attemptedBefore = i.attemptedBefore, spentBefore = i.spentBefore}, proposal.feature, proposal.resources)
    if not charge or usage.attempted ~= charge.attemptedBefore or usage.spent ~= charge.spentBefore
        or i.limitTotal and usage.spent + charge.price > i.maxSpend then
        return nil, nil, "Shop authorized Cash changed or limit reached"
    end
    return {version = 1, attempted = usage.attempted + 1, spent = usage.spent + charge.price}, charge, nil
end

function ShopBuy.holds(raw, charge)
    local usage = ShopBuy.copy(raw)
    return usage ~= nil and usage.attempted >= charge.attemptedBefore + 1
        and usage.spent >= charge.spentBefore + charge.price
end

function ShopBuy.rollback(raw, charge)
    local usage = ShopBuy.copy(raw)
    if not usage or usage.attempted ~= charge.attemptedBefore + 1
        or usage.spent ~= charge.spentBefore + charge.price then return nil end
    return {version = 1, attempted = charge.attemptedBefore, spent = charge.spentBefore, unknown = usage.unknown}
end

function ShopBuy.propose(view, settings, reservations)
    if type(view) ~= "table" or type(settings) ~= "table"
        or type(reservations) ~= "table" then
        return nil, "Missing Shop planning input"
    end
    if settings.enabled ~= true then return nil, "Shop buying disabled" end
    local usage = view.usage and ShopBuy.copy(view.usage)
    local maxSpend = settings.maxSpend or 5000000
    if settings.limitTotal ~= nil and type(settings.limitTotal) ~= "boolean"
        or not integer(maxSpend, 0) or maxSpend > MAX
        or view.usage ~= nil and (not usage or usage.unknown)
        or settings.limitTotal == true and not usage then return nil, "Shop Cash allowance unavailable" end
    if view.autoBuy then return nil, "Native Auto Buy owns the Shop" end
    if not integer(view.unlockLevel or 1, 0) or not integer(view.level, 1)
        or view.level < (view.unlockLevel or 1) then return nil, "Shop level locked" end
    if type(view.offers) ~= "table"
        or not integer(view.slot, 0) or not integer(view.level, 1)
        or not nonnegative(view.cash)
        or not integer(settings.cashReserve, 0)
        or not integer(settings.purchaseCap, 1)
        or not integer(reservations.cash or 0, 0)
        or not integer(reservations.uncertainCash or 0, 0)
        or type(view.catalogKey) ~= "string" then
        return nil, "Current cash Shop quote or budget unavailable"
    end
    local mode = settings.selection or "Single item"
    if mode ~= "Single item" and mode ~= "All cash items"
        and mode ~= "Selected cash items" and mode ~= "Category rules" then
        return nil, "Invalid Shop selection mode"
    end
    local category = settings.kind or "All allowed"
    local categories = { ["All allowed"]=true, ["Combat gear"]=true, Weapons=true,
        Armor=true, Vehicles=true, Cosmetics=true, Crates=true }
    local minRarity, ownedCap = settings.minRarity or 1, settings.ownedCap or 0
    local priceRule, cashMax = settings.priceRule or "Buy all allowed", settings.cashMax or 100000
    if not categories[category] or not nonnegative(minRarity) or minRarity < 1 or minRarity > 9
        or not integer(ownedCap, 0) or not nonnegative(cashMax)
        or priceRule ~= "Buy all allowed" and priceRule ~= "Buy cash items under price" then
        return nil, "Invalid Shop category or price rules"
    end
    for _, field in ipairs({"allowCosmetics", "allowCrates", "rarityOverride"}) do
        if settings[field] ~= nil and type(settings[field]) ~= "boolean" then return nil, "Invalid Shop permission" end
    end
    local function selections(text, rarities)
        if type(text) ~= "string" or #text > 4096 then return nil end
        if text:match("^%s*$") then return {} end
        local result, count = {}, 0
        for token in (text .. ","):gmatch("(.-),") do
            local id = token:match("^%s*(.-)%s*$")
            count = count + 1
            if count > 64 or result[id] or #id > 120 or not id:match("^[%w_%-]+$")
                or rarities and not id:match("^[1-9]$")
                or not rarities and (type(view.knownIds) ~= "table" or not view.knownIds[id]) then return nil end
            result[id] = true
        end
        return result
    end
    local selected = {}
    if mode == "Single item" then
        if type(settings.itemId) ~= "string" or #settings.itemId == 0 then return nil, "Select one cash Shop item" end
        selected[settings.itemId] = true
    elseif mode == "Selected cash items" then
        selected = selections(settings.selectedIds, false)
        if not selected then return nil, "Invalid or unknown selected Shop IDs" end
    end
    local overrides = {}
    if settings.rarityOverride == true then
        overrides = selections(settings.overrideRarities, true)
        if not overrides then return nil, "Invalid Shop rarity overrides" end
    end
    local order = view.order
    if mode == "Single item" and settings.rarityOverride ~= true then order = {settings.itemId} end
    if type(order) ~= "table" or #order > 512 then return nil, "Current native Shop order required" end
    local chosen, chosenId, chosenOverride
    local available = view.cash - settings.cashReserve
        - (reservations.cash or 0) - (reservations.uncertainCash or 0)
    for pass = 1, 2 do
        for _, id in ipairs(order) do
            local row = view.offers[id]
            if row then
                if not integer(row.cost, 1) or not integer(row.level, 1)
                    or not integer(row.bought, 0) or not integer(row.owned, 0)
                    or not integer(row.rarity, 1) or row.rarity > 9
                    or type(row.rotationBought) ~= "boolean"
                    or row.limit ~= nil and not integer(row.limit, 1) then return nil, "Invalid current Shop offer" end
                local gear = row.kind == "weapon" or row.kind == "armor" or row.kind == "vehicle"
                local cosmetic = row.kind == "border" or row.kind == "background" or row.kind == "trophy"
                local crate = row.kind == "crate"
                local override = overrides[tostring(row.rarity)] == true
                local allowed = gear or cosmetic or crate
                local matches = mode == "All cash items" or selected[id] == true
                if mode == "Category rules" then
                    allowed = gear or cosmetic and settings.allowCosmetics == true or crate and settings.allowCrates == true
                    matches = category == "All allowed" or category == "Combat gear" and gear
                        or category == "Weapons" and row.kind == "weapon"
                        or category == "Armor" and row.kind == "armor"
                        or category == "Vehicles" and row.kind == "vehicle"
                        or category == "Cosmetics" and cosmetic or category == "Crates" and crate
                    if override then allowed, matches = gear or cosmetic or crate, true end
                elseif override then matches = true end
                local owned = mode ~= "Category rules" or ownedCap == 0
                    or integer(row.totalOwned, 0) and row.totalOwned < ownedCap
                local rarity = mode ~= "Category rules" or override or row.rarity >= minRarity
                if allowed and matches and owned and rarity and row.level <= view.level
                    and not row.rotationBought and (row.limit == nil or row.bought < row.limit)
                    and row.cost <= settings.purchaseCap and row.cost <= available
                    and (not usage or row.cost <= MAX - usage.spent)
                    and (settings.limitTotal ~= true or usage.spent + row.cost <= maxSpend)
                    and (pass == 1 and override or pass == 2
                        and (priceRule == "Buy all allowed" or row.cost <= cashMax)) then
                    chosen, chosenId, chosenOverride = row, id, pass == 1
                    break
                end
            end
        end
        if chosen then break end
    end
    if not chosen then return nil, "No eligible cash Shop offer within selection and budget" end
    local id, row = chosenId, chosen
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "shop",
        actionKey = "shop:" .. view.catalogKey .. ":" .. view.slot
            .. ":" .. id,
        resources = { cash = row.cost },
        intent = { kind = "shopCashBuy", itemId = id,
            slot = view.slot, expectedCost = row.cost,
            beforeOwned = row.owned, beforeBought = row.bought,
            cashReserve = settings.cashReserve,
            attemptedBefore = usage and usage.attempted, spentBefore = usage and usage.spent,
            limitTotal = usage ~= nil and settings.limitTotal == true, maxSpend = usage and maxSpend,
            rarityOverride = chosenOverride,
            quoteServerNow = view.serverNow, quoteCapturedAt = view.capturedAt,
            quoteExpires = (view.slot + 1) * 300,
            catalogKey = view.catalogKey } }, nil
end

return ShopBuy
