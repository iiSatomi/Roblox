-- Recheck rotation/quote, then require a newer exact item grant.
local ShopBuyEvidence = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function same(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or a[field] ~= b[field] then return false end
    end
    return true
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
        or proposal.revision ~= before.revision then
        return nil, "Shop baseline mismatch"
    end
    local native, proof, catalog = before.native,
        before.shopQuoteProof, before.shopCatalog
    local offer = type(catalog) == "table"
        and type(catalog.offers) == "table"
        and catalog.offers[intent.itemId]
    if type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.serverNow, 0)
        or math.floor(native.serverNow / 300) ~= intent.slot
        or native.serverNow % 300 > 295
        or type(native.shopRotation) ~= "table"
        or native.shopRotation.slot ~= intent.slot
        or type(native.shopRotation.bought) ~= "table"
        or native.shopRotation.bought[intent.itemId] == true
        or type(native.shopBought) ~= "table"
        or (native.shopBought[intent.itemId] or 0) ~= intent.beforeBought
        or type(native.inventory) ~= "table"
        or (native.inventory[intent.itemId] or 0) ~= intent.beforeOwned
        or type(native.autoBuyRules) == "table"
            and native.autoBuyRules.on == true
        or not integer(native.cash,
            intent.expectedCost + intent.cashReserve)
        or type(proof) ~= "table"
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
        or (offer.limit ~= nil
            and intent.beforeBought >= offer.limit) then
        return nil, "Shop stock, quote or custody changed"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, itemId = intent.itemId,
        slot = intent.slot, beforeOwned = intent.beforeOwned,
        beforeBought = intent.beforeBought }, nil
end

function ShopBuyEvidence.evaluate(proposal, beforeHeader, after,
    reply, baseline)
    if not same(proposal, beforeHeader) or not same(proposal, after)
        or not same(proposal, baseline)
        or type(reply) ~= "table"
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision then
        return "pending"
    end
    local native = after.native
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.inventory) ~= "table"
        or type(native.shopBought) ~= "table"
        or not integer(native.inventory[baseline.itemId] or 0, 0)
        or not integer(native.shopBought[baseline.itemId] or 0, 0)
        or not integer(after.revision, baseline.revision + 1) then
        return "pending"
    end
    local granted = native.inventory[baseline.itemId]
        == baseline.beforeOwned + 1
        and native.shopBought[baseline.itemId]
        == baseline.beforeBought + 1
    if reply.ok == false then return granted and "pending" or "rejected" end
    if reply.ok == true and granted then return "confirmed" end
    return "pending"
end

return ShopBuyEvidence
