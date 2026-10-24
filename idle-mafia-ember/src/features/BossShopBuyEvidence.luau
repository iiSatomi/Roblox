-- Positive reply plus exact token debit and selected custody increase.
local BossShopBuyEvidence = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function matching(a, b)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or a[field] ~= b[field] then return false end
    end
    return true
end

local function count(map, id)
    if type(map) ~= "table" then return nil end
    local value = map[id]
    if value == nil then return 0 end
    if integer(value, 0) then return value end
    return nil
end

local function state(raw, item)
    local native = type(raw) == "table" and raw.native
    local proof = type(raw) == "table" and raw.bossShopProof
    if type(native) ~= "table" or native.fullSync ~= true
        or type(proof) ~= "table" or proof.account ~= raw.account
        or proof.capturedAt ~= raw.capturedAt
        or type(proof.catalogKey) ~= "string"
        or type(proof.items) ~= "table" then return nil end
    local tokens = count(native.inventory, "boss_token")
    local bound = count(native.inventoryBound, "boss_token")
    local owned = count(native.inventory, item)
    local ownedBound = count(native.inventoryBound, item)
    if not tokens or not bound or not owned or not ownedBound then
        return nil
    end
    local selected, seen = nil, {}
    for _, row in ipairs(proof.items) do
        if type(row) ~= "table" or type(row.item) ~= "string"
            or seen[row.item] or not integer(row.price, 1)
            or type(row.unlocked) ~= "boolean"
            or (row.kind ~= "crate" and row.kind ~= "gear") then
            return nil
        end
        seen[row.item] = true
        if row.item == item then selected = row end
    end
    return { tokens = tokens + bound, owned = owned + ownedBound,
        catalogKey = proof.catalogKey, selected = selected }
end

function BossShopBuyEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "bossShop"
        or type(intent) ~= "table" or intent.kind ~= "bossShopBuy"
        or type(intent.item) ~= "string" or #intent.item == 0
        or not integer(intent.quantity, 1)
        or not integer(intent.unitPrice, 1)
        or not integer(intent.totalCost, 1)
        or intent.totalCost ~= intent.unitPrice * intent.quantity
        or not integer(intent.tokenReserve, 0)
        or not integer(intent.attemptsBefore, 0)
        or not integer(intent.maxSends, 1)
        or intent.attemptsBefore >= intent.maxSends
        or (intent.itemKind ~= "crate" and intent.itemKind ~= "gear")
        or (intent.itemKind == "gear" and intent.quantity ~= 1)
        or (intent.itemKind == "crate" and intent.quantity ~= 1
            and intent.quantity ~= 10)
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Boss Shop baseline mismatch"
    end
    local current = state(before, intent.item)
    local usage = before.bossShopUsageProof
    if not current or not current.selected
        or current.selected.kind ~= intent.itemKind
        or current.selected.unlocked ~= true
        or current.selected.price ~= intent.unitPrice
        or current.catalogKey ~= intent.catalogKey
        or current.tokens < intent.totalCost + intent.tokenReserve
        or type(usage) ~= "table"
        or usage.account ~= before.account
        or usage.session ~= before.session
        or usage.capturedAt ~= before.capturedAt
        or usage.attempts ~= intent.attemptsBefore then
        return nil, "Boss Shop quote, reserve or attempt changed"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, tokens = current.tokens,
        owned = current.owned, item = intent.item,
        quantity = intent.quantity, totalCost = intent.totalCost,
        catalogKey = intent.catalogKey }, nil
end

function BossShopBuyEvidence.evaluate(proposal, beforeHeader, after,
    reply, baseline)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table"
        or type(after) ~= "table" or type(reply) ~= "table"
        or type(baseline) ~= "table"
        or not matching(proposal, beforeHeader)
        or not matching(proposal, after)
        or not matching(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision then
        return "pending"
    end
    local current = state(after, baseline.item)
    if not current then return "pending" end
    local advanced = integer(after.revision, baseline.revision + 1)
        and current.catalogKey == baseline.catalogKey
        and type(current.selected) == "table"
        and current.tokens <= baseline.tokens - baseline.totalCost
        and current.owned >= baseline.owned + baseline.quantity
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

return BossShopBuyEvidence
