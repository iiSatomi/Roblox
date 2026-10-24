-- Saved OpenCrate(id, false, count, luck) for owned unbound crates.
local Chests = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function finite(value)
    return type(value) == "number" and value == value
        and value > -math.huge and value < math.huge
end

local function same(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or a[field] ~= b[field] then return false end
    end
    return true
end

local function count(map, id)
    if type(map) ~= "table" then return nil end
    local value = map[id] or 0
    if not integer(value, 0) then return nil end
    return value
end

local function luck(raw, proof)
    if type(raw) ~= "table" or type(proof) ~= "table"
        or proof.account ~= raw.account
        or proof.capturedAt ~= raw.capturedAt
        or proof.revision ~= raw.revision
        or not finite(proof.luck)
        or proof.luck < 0 or proof.luck > 10 then return nil end
    return proof.luck
end

function Chests.read(raw, context)
    if not same(raw, context) or raw.revision ~= context.revision
        or raw.capturedAt ~= context.capturedAt
        or not integer(raw.revision, 0) then
        return nil, "Chest snapshot changed"
    end
    local native, catalog = raw.native, raw.ownedCrateCatalog
    local currentLuck = luck(raw, context.crateLuckProof)
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.inventory) ~= "table"
        or type(native.inventoryBound) ~= "table"
        or type(catalog) ~= "table"
        or catalog.release ~= context.release
        or catalog.catalogKey ~= context.crateCatalogKey
        or not integer(catalog.batchMax, 1)
        or type(catalog.crates) ~= "table"
        or currentLuck == nil
        or luck(raw, raw.crateLuckProof) ~= currentLuck then
        return nil, "Current crate catalog, inventory and luck required"
    end
    local owned, total = {}, 0
    for id in pairs(catalog.crates) do
        if type(id) ~= "string"
            or count(native.inventory, id) == nil
            or count(native.inventoryBound, id) == nil then
            return nil, "Invalid crate custody"
        end
        local amount = count(native.inventory, id)
        if amount > 0 then
            owned[#owned + 1] = { id = id, count = amount }
        end
        total = total + 1
        if total > 500 then return nil, "Crate catalog too large" end
    end
    table.sort(owned, function(a, b) return a.id < b.id end)
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        catalogKey = catalog.catalogKey,
        batchMax = catalog.batchMax,
        luck = currentLuck, owned = owned }, nil
end

function Chests.propose(view, settings)
    if type(view) ~= "table" or type(settings) ~= "table"
        or not same(view, view) then return nil, "Missing chest input" end
    if settings.enabled ~= true then return nil, "Chests disabled" end
    local policy = settings.policy
    if policy ~= "Smallest stack" and policy ~= "Largest stack" then
        return nil, "Select a supported chest order"
    end
    local custom = type(settings.custom) == "table"
        and settings.custom or settings
    if not integer(custom.maxBatch, 1)
        or custom.maxBatch > 10
        or not integer(view.batchMax, 1) then
        return nil, "Chest batch limit required"
    end
    local chosen
    for _, row in ipairs(view.owned or {}) do
        if not chosen or (policy == "Smallest stack"
            and row.count < chosen.count)
            or (policy == "Largest stack"
                and row.count > chosen.count) then
            chosen = row
        end
    end
    if not chosen then return nil, "No owned unbound crate" end
    local amount = math.min(chosen.count, custom.maxBatch,
        view.batchMax)
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "chests",
        actionKey = "chests:" .. view.catalogKey .. ":"
            .. chosen.id .. ":" .. chosen.count .. ":"
            .. amount,
        resources = { [chosen.id] = amount },
        intent = { kind = "chests", remote = "OpenCrate",
            args = { chosen.id, false, amount, view.luck },
            itemId = chosen.id, amount = amount,
            beforeCount = chosen.count, luck = view.luck,
            catalogKey = view.catalogKey } }, nil
end

function Chests.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    local native = type(before) == "table" and before.native
    if type(proposal) ~= "table" or proposal.feature ~= "chests"
        or type(intent) ~= "table" or intent.kind ~= "chests"
        or not same(proposal, before)
        or proposal.revision ~= before.revision
        or type(native) ~= "table" or native.fullSync ~= true
        or type(before.ownedCrateCatalog) ~= "table"
        or before.ownedCrateCatalog.catalogKey ~= intent.catalogKey
        or before.ownedCrateCatalog.crates[intent.itemId] ~= true
        or not integer(intent.amount, 1)
        or intent.amount > before.ownedCrateCatalog.batchMax
        or count(native.inventory, intent.itemId)
            ~= intent.beforeCount
        or intent.beforeCount < intent.amount
        or luck(before, before.crateLuckProof) ~= intent.luck
        or type(intent.args) ~= "table"
        or intent.args[1] ~= intent.itemId
        or intent.args[2] ~= false
        or intent.args[3] ~= intent.amount
        or intent.args[4] ~= intent.luck then
        return nil, "Exact owned crate and luck quote unavailable"
    end
    local inventory = {}
    for _, field in ipairs({ "inventory", "inventoryBound" }) do
        if type(native[field]) ~= "table" then
            return nil, "Full crate inventory required"
        end
        for id, amount in pairs(native[field]) do
            if type(id) ~= "string" or not integer(amount, 0) then
                return nil, "Invalid crate inventory"
            end
            inventory[id] = (inventory[id] or 0) + amount
        end
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, itemId = intent.itemId,
        amount = intent.amount, count = intent.beforeCount,
        inventory = inventory }, nil
end

function Chests.evaluate(proposal, before, after, reply, baseline)
    if type(proposal) ~= "table" or type(reply) ~= "table"
        or not same(proposal, before) or not same(proposal, after)
        or not same(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or before.revision ~= baseline.revision
        or not integer(after.revision, baseline.revision + 1) then
        return "pending"
    end
    if reply.ok == false then return "rejected" end
    local native = after.native
    local rewards = reply.itemIds
    if reply.ok ~= true or type(native) ~= "table"
        or native.fullSync ~= true
        or type(rewards) ~= "table"
        or #rewards ~= baseline.amount
        or reply.opened ~= baseline.amount
        or type(native.inventory) ~= "table"
        or type(native.inventoryBound) ~= "table" then
        return "pending"
    end
    local rewardCounts = {}
    for index, id in pairs(rewards) do
        if not integer(index, 1) or index > baseline.amount
            or type(id) ~= "string" or #id == 0 then
            return "pending"
        end
        rewardCounts[id] = (rewardCounts[id] or 0) + 1
    end
    if count(native.inventory, baseline.itemId)
        ~= baseline.count - baseline.amount then
        return "pending"
    end
    for id, amount in pairs(rewardCounts) do
        local ordinary = count(native.inventory, id)
        local bound = count(native.inventoryBound, id)
        if ordinary == nil or bound == nil
            or ordinary + bound - (baseline.inventory[id] or 0)
                < amount - (id == baseline.itemId
                    and baseline.amount or 0) then
            return "pending"
        end
    end
    return "confirmed"
end

return Chests
