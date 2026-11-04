-- Recheck rotation/quote, then require a newer exact item grant.
local ShopBuyEvidence = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function finiteAtLeast(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge
end

local function same(a, b, restart)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or (not restart or field ~= "session") and a[field] ~= b[field] then return false end
    end
    return true
end

local function validRotation(rotation, slot, id)
    if rotation == nil then return true end
    return type(rotation) == "table" and integer(rotation.slot, 0)
        and rotation.slot <= slot
        and (rotation.bought == nil or type(rotation.bought) == "table"
            and (rotation.bought[id] == nil or type(rotation.bought[id]) == "boolean"))
end

local function boughtThisRotation(rotation, slot, id)
    return rotation ~= nil and rotation.slot == slot
        and type(rotation.bought) == "table" and rotation.bought[id] == true
end

local function sameRotation(a, b, id)
    if a == nil or b == nil then return a == b end
    return type(a) == "table" and type(b) == "table" and a.slot == b.slot
        and type(a.bought) == type(b.bought)
        and (a.bought == nil or a.bought[id] == b.bought[id])
end

function ShopBuyEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if not same(proposal, before)
        or proposal.feature ~= "shop"
        or type(intent) ~= "table" or intent.kind ~= "shopCashBuy"
        or type(intent.itemId) ~= "string" or #intent.itemId == 0
        or not integer(intent.slot, 0)
        or not integer(intent.expectedCost, 1)
        or not integer(intent.beforeOwned, 0)
        or not integer(intent.beforeBought, 0)
        or not integer(intent.cashReserve, 0)
        or type(proposal.resources) ~= "table"
        or proposal.resources.cash ~= intent.expectedCost
        or proposal.revision ~= before.revision then
        return nil, "Shop baseline mismatch"
    end
    local native, proof, catalog = before.native,
        before.shopQuoteProof, before.shopCatalog
    local offer = type(catalog) == "table"
        and type(catalog.offers) == "table"
        and catalog.offers[intent.itemId]
    if type(native) ~= "table" or native.fullSync ~= true
        or not finiteAtLeast(native.serverNow, 0)
        or math.floor(native.serverNow / 300) ~= intent.slot
        or native.serverNow % 300 > 295
        or not validRotation(native.shopRotation, intent.slot, intent.itemId)
        or boughtThisRotation(native.shopRotation, intent.slot, intent.itemId)
        or (native.shopBought ~= nil
            and type(native.shopBought) ~= "table")
        or (type(native.shopBought) == "table"
            and (native.shopBought[intent.itemId] or 0) or 0)
            ~= intent.beforeBought
        or type(native.inventory) ~= "table"
        or (native.inventory[intent.itemId] or 0) ~= intent.beforeOwned
        or type(native.autoBuyRules) == "table"
            and native.autoBuyRules.on == true
        or not finiteAtLeast(native.cash,
            intent.expectedCost + intent.cashReserve)
        or type(proof) ~= "table"
        or type(catalog) ~= "table"
        or catalog.release ~= proposal.release
        or catalog.key ~= intent.catalogKey
        or proof.session ~= proposal.session
        or proof.account ~= proposal.account
        or proof.place ~= proposal.place
        or proof.release ~= proposal.release
        or proof.revision ~= proposal.revision
        or proof.capturedAt ~= before.capturedAt
        or proof.slot ~= intent.slot
        or proof.catalogKey ~= intent.catalogKey
        or type(proof.stock) ~= "table"
        or proof.stock[intent.itemId] ~= true
        or type(proof.quotes) ~= "table"
        or proof.quotes[intent.itemId] ~= intent.expectedCost
        or type(offer) ~= "table"
        or not integer(native.level, 1)
        or not integer(catalog.unlockLevel or 1, 0)
        or native.level < (catalog.unlockLevel or 1)
        or not integer(offer.level, 1)
        or offer.level > native.level
        or (offer.limit ~= nil
            and intent.beforeBought >= offer.limit) then
        return nil, "Shop stock, quote or custody changed"
    end
    for _, origin in ipairs({"inventoryBound", "collection", "collectionBound"}) do
        if native[origin] ~= nil and (type(native[origin]) ~= "table"
            or not integer(native[origin][intent.itemId] or 0, 0)) then return nil, "Invalid Shop item origin" end
    end
    if intent.attemptedBefore ~= nil or intent.spentBefore ~= nil or intent.maxSpend ~= nil then
        local usage = before.shopUsageProof
        if type(usage) ~= "table" or not same(before, usage) or usage.revision ~= before.revision
            or usage.capturedAt ~= before.capturedAt or usage.unknown ~= nil
            or not integer(usage.attempted, 0) or not integer(usage.spent, usage.attempted)
            or usage.spent > 9007199254740991 - intent.expectedCost
            or usage.attempted ~= intent.attemptedBefore or usage.spent ~= intent.spentBefore
            or type(intent.limitTotal) ~= "boolean" or not integer(intent.maxSpend, 0)
            or intent.maxSpend > 9007199254740991
            or intent.limitTotal and usage.spent + intent.expectedCost > intent.maxSpend then
            return nil, "Shop Cash allowance changed"
        end
    end
    local baseline = { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, itemId = intent.itemId,
        slot = intent.slot, beforeOwned = intent.beforeOwned,
        beforeBought = intent.beforeBought,
        cashBefore = native.cash, cost = intent.expectedCost,
        trackedBought = type(native.shopBought) == "table",
        inventoryBound = type(native.inventoryBound) == "table" and (native.inventoryBound[intent.itemId] or 0) or nil,
        collection = type(native.collection) == "table" and (native.collection[intent.itemId] or 0) or nil,
        collectionBound = type(native.collectionBound) == "table" and (native.collectionBound[intent.itemId] or 0) or nil }
    -- Existing current-rotation baselines retain their exact saved schema.
    -- Older/absent rotations need their own no-effect rejection evidence.
    if native.shopRotation == nil then
        baseline.priorRotation = false
    elseif native.shopRotation.slot < intent.slot then
        baseline.priorRotation = {slot = native.shopRotation.slot}
        if native.shopRotation.bought ~= nil then
            baseline.priorRotation.bought = {[intent.itemId] = native.shopRotation.bought[intent.itemId]}
        end
    end
    return baseline, nil
end

local function reconcile(proposal, beforeHeader, after, reply, baseline, restart)
    if not same(proposal, beforeHeader) or not same(proposal, after, restart)
        or not same(proposal, baseline)
        or type(reply) ~= "table"
        or reply.pending == true
        or type(proposal.intent) ~= "table"
        or proposal.intent.itemId ~= baseline.itemId
        or proposal.intent.expectedCost ~= baseline.cost
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision then
        return "pending"
    end
    local native = after.native
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.inventory) ~= "table"
        or not validRotation(native.shopRotation, baseline.slot, baseline.itemId)
        or (native.shopBought ~= nil
            and type(native.shopBought) ~= "table")
        or (type(native.shopBought) == "table")
            ~= baseline.trackedBought
        or not integer(native.inventory[baseline.itemId] or 0, 0)
        or (baseline.trackedBought
            and not integer(native.shopBought[baseline.itemId] or 0, 0))
        or not finiteAtLeast(native.cash, 0)
        or (not restart and not integer(after.revision, baseline.revision + 1)) then
        return "pending"
    end
    for _, origin in ipairs({"inventoryBound", "collection", "collectionBound"}) do
        local original = baseline[origin]
        if original ~= nil and (not integer(original, 0) or type(native[origin]) ~= "table"
            or (native[origin][baseline.itemId] or 0) ~= original) then return "pending" end
    end
    if restart and (type(beforeHeader.native) ~= "table"
        or not finiteAtLeast(beforeHeader.native.serverNow, 0)
        or not finiteAtLeast(native.serverNow, beforeHeader.native.serverNow)) then return "pending" end
    local granted = native.inventory[baseline.itemId]
        == baseline.beforeOwned + 1
        and boughtThisRotation(native.shopRotation, baseline.slot, baseline.itemId)
        and native.cash == baseline.cashBefore - baseline.cost
        and (not baseline.trackedBought
            or native.shopBought[baseline.itemId]
                == baseline.beforeBought + 1)
    local samePriorRotation = baseline.priorRotation == false and native.shopRotation == nil
        or type(baseline.priorRotation) == "table"
            and sameRotation(native.shopRotation, baseline.priorRotation, baseline.itemId)
    local currentEmpty = native.shopRotation ~= nil
        and native.shopRotation.slot == baseline.slot
        and not boughtThisRotation(native.shopRotation, baseline.slot, baseline.itemId)
    local unchanged = (native.inventory[baseline.itemId] or 0) == baseline.beforeOwned
        and (samePriorRotation or currentEmpty)
        and not boughtThisRotation(native.shopRotation, baseline.slot, baseline.itemId)
        and native.cash == baseline.cashBefore
        and (not baseline.trackedBought or (native.shopBought[baseline.itemId] or 0) == baseline.beforeBought)
    if reply.ok == false then return unchanged and "rejected" or "pending" end
    if reply.ok == true and granted then return "confirmed" end
    return "pending"
end

function ShopBuyEvidence.evaluate(proposal, beforeHeader, after, reply, baseline)
    return reconcile(proposal, beforeHeader, after, reply, baseline, false)
end

local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not equal(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end

function ShopBuyEvidence.recoverSaved(data, after)
    if type(data) ~= "table" or type(data.reply) ~= "table" then return nil end
    local baseline = ShopBuyEvidence.capture(data.proposal, data.before)
    if not baseline or not equal(baseline, data.baseline) then return nil end
    local result = reconcile(data.proposal, data.before, after, data.reply, baseline, true)
    return (result == "confirmed" or result == "rejected") and result or nil
end

return ShopBuyEvidence
