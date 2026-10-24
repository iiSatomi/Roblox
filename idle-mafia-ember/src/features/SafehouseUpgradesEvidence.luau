-- Exact newer tier increase proves the selected upgrade, not reply alone.
local SafehouseUpgradesEvidence = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function matching(a, b)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or a[field] ~= b[field] then return false end
    end
    return true
end

local function tier(raw, catalogKey)
    local native = type(raw) == "table" and raw.native
    if type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.safehouse, 1) or native.safehouse > 18
        or raw.catalogKey ~= catalogKey then return nil end
    return native.safehouse
end

function SafehouseUpgradesEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "safehouse"
        or type(intent) ~= "table" or intent.kind ~= "safehouseUpgrade"
        or not integer(intent.fromTier, 1)
        or intent.nextTier ~= intent.fromTier + 1
        or not integer(intent.expectedCost, 1)
        or not integer(intent.cashReserve, 0)
        or type(intent.catalogKey) ~= "string" or #intent.catalogKey == 0
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Safehouse upgrade baseline mismatch"
    end
    local current = tier(before, intent.catalogKey)
    local quote = type(before.safehouseCatalog) == "table"
        and before.safehouseCatalog[intent.nextTier]
    if current ~= intent.fromTier or type(quote) ~= "table"
        or quote.cost ~= intent.expectedCost
        or not integer(before.native.cash,
            intent.expectedCost + intent.cashReserve)
        or not integer(before.native.level, quote.level)
            and not integer(before.native.maxLevel, quote.level) then
        return nil, "Selected Safehouse tier is no longer affordable"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, fromTier = current,
        nextTier = intent.nextTier, catalogKey = intent.catalogKey }, nil
end

function SafehouseUpgradesEvidence.evaluate(proposal, beforeHeader, after,
    reply, baseline)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table"
        or type(after) ~= "table" or type(reply) ~= "table"
        or type(baseline) ~= "table"
        or not matching(proposal, beforeHeader)
        or not matching(proposal, after)
        or not matching(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision
        or type(proposal.intent) ~= "table"
        or proposal.intent.fromTier ~= baseline.fromTier
        or proposal.intent.nextTier ~= baseline.nextTier then
        return "pending"
    end
    local current = tier(after, baseline.catalogKey)
    if not current then return "pending" end
    local advanced = type(after.revision) == "number"
        and after.revision > baseline.revision
        and current == baseline.nextTier
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

return SafehouseUpgradesEvidence
