-- CollectionAction("deposit", id, count) only for protected surplus.
local CollectionDonate = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
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

local function worn(native)
    local crew = type(native) == "table" and native.crew
    if type(crew) ~= "table" or #crew < 1
        or #crew > 46 then return nil end
    local used, countRows = {}, 0
    for slot, row in pairs(crew) do
        if not integer(slot, 1) or slot > #crew
            or type(row) ~= "table" then return nil end
        countRows = countRows + 1
        for _, kind in ipairs({ "weapon", "armor", "vehicle" }) do
            local id = row[kind]
            if id ~= nil then
                if type(id) ~= "string" then return nil end
                used[id] = (used[id] or 0) + 1
            end
        end
        local border = slot == 1 and native.equippedBorder
            or row.border
        if border ~= nil then
            if type(border) ~= "string" then return nil end
            used[border] = (used[border] or 0) + 1
        end
    end
    if countRows ~= #crew then return nil end
    if native.equippedBackground ~= nil then
        if type(native.equippedBackground) ~= "string" then return nil end
        used[native.equippedBackground] =
            (used[native.equippedBackground] or 0) + 1
    end
    return used
end

local function collected(native, id)
    local total = 0
    for _, field in ipairs({ "collection", "collectionBound" }) do
        local map = native[field]
        if type(map) ~= "table" then return nil end
        for key, amount in pairs(map) do
            if type(key) ~= "string" or not integer(amount, 0) then
                return nil
            end
            if key == id or key:sub(1, #id + 1) == id .. "@" then
                total = total + amount
            end
        end
    end
    return total
end

local function bonus(catalog, rarity, copies)
    local value = catalog.rarity[rarity]
    if not integer(value, 1) or not integer(copies, 0) then
        return nil
    end
    local multiplier = 0
    for _, tier in ipairs(catalog.tiers) do
        if copies >= tier.count then multiplier = tier.mult end
    end
    return value * multiplier
end

local function protection(raw, proof)
    if type(proof) ~= "table" or type(raw) ~= "table"
        or proof.account ~= raw.account
        or proof.session ~= raw.session
        or proof.place ~= raw.place
        or proof.release ~= raw.release
        or proof.revision ~= raw.revision
        or proof.capturedAt ~= raw.capturedAt
        or type(proof.key) ~= "string" or #proof.key == 0
        or type(proof.covers) ~= "table"
        or proof.covers.gear ~= true
        or proof.covers.cosmetics ~= true
        or type(proof.protected) ~= "table" then return nil end
    local copied, size = {}, 0
    for id, amount in pairs(proof.protected) do
        if type(id) ~= "string" or not integer(amount, 0) then
            return nil
        end
        copied[id] = amount
        size = size + 1
        if size > 5000 then return nil end
    end
    return copied
end

function CollectionDonate.read(raw, context)
    if not same(raw, context) or raw.revision ~= context.revision
        or raw.capturedAt ~= context.capturedAt
        or not integer(raw.revision, 0) then
        return nil, "Collection snapshot changed"
    end
    local native, catalog = raw.native, raw.collectionCatalog
    local protected = protection(raw, context.collectionProtection)
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.inventory) ~= "table"
        or type(native.inventoryBound) ~= "table"
        or type(native.collection) ~= "table"
        or type(native.collectionBound) ~= "table"
        or type(catalog) ~= "table"
        or catalog.release ~= context.release
        or catalog.catalogKey ~= context.collectionCatalogKey
        or type(catalog.items) ~= "table"
        or type(catalog.rarity) ~= "table"
        or type(catalog.tiers) ~= "table" then
        return nil, "Current Collection custody and source required"
    end
    local attached = protection(raw, raw.collectionProtection)
    if not protected or not attached
        or raw.collectionProtection.key
            ~= context.collectionProtection.key then
        return nil, "Current gear and cosmetic protection proof required"
    end
    for id, amount in pairs(protected) do
        if attached[id] ~= amount then
            return nil, "Collection protection proof changed"
        end
    end
    for id in pairs(attached) do
        if protected[id] == nil then
            return nil, "Collection protection proof changed"
        end
    end
    local used = worn(native)
    if not used then return nil, "Current worn items required" end
    local entries = {}
    for id, item in pairs(catalog.items) do
        if type(id) ~= "string" or id:find("@", 1, true)
            or type(item) ~= "table"
            or not integer(item.rarity, 1)
            or count(native.inventory, id) == nil
            or count(native.inventoryBound, id) == nil then
            return nil, "Invalid Collection catalog or inventory"
        end
        local copies = collected(native, id)
        if copies == nil then return nil, "Invalid Collection counts" end
        local loose = count(native.inventory, id)
        if loose > 0 then
            entries[#entries + 1] = { id = id,
                rarity = item.rarity, loose = loose,
                bound = count(native.inventoryBound, id),
                worn = used[id] or 0,
                collected = copies }
        end
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        catalogKey = catalog.catalogKey,
        protectionKey = context.collectionProtection.key,
        protected = protected,
        catalog = catalog, entries = entries }, nil
end

function CollectionDonate.propose(view, settings)
    if type(view) ~= "table" or type(settings) ~= "table"
        or not same(view, view) then
        return nil, "Missing Collection input"
    end
    if settings.enabled ~= true then return nil, "Collection disabled" end
    local custom = type(settings.custom) == "table"
        and settings.custom or settings
    if not integer(custom.maxBatch, 1)
        or custom.maxBatch > 10
        or not integer(custom.sparesToKeep, 1) then
        return nil, "Collection batch and spare limits required"
    end
    local chosen, bestGain
    for _, row in ipairs(view.entries or {}) do
        local reserve = math.max(row.worn + custom.sparesToKeep,
            view.protected[row.id] or 0)
        local amount = math.min(custom.maxBatch, row.loose - reserve)
        if amount >= 1 then
            local beforeBonus = bonus(view.catalog,
                row.rarity, row.collected)
            local afterBonus = bonus(view.catalog,
                row.rarity, row.collected + amount)
            if beforeBonus and afterBonus then
                local gain = afterBonus - beforeBonus
                if not chosen or gain > bestGain
                    or (gain == bestGain and row.id < chosen.id) then
                    chosen = { id = row.id, amount = amount,
                        loose = row.loose,
                        collected = row.collected,
                        worn = row.worn,
                        reserve = reserve,
                        expectedGain = gain }
                    bestGain = gain
                end
            end
        end
    end
    if not chosen then return nil, "No safe unbound Collection surplus" end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "collectionDonate",
        actionKey = "collectionDonate:" .. view.catalogKey .. ":"
            .. chosen.id .. ":" .. chosen.loose .. ":"
            .. chosen.collected .. ":" .. chosen.amount,
        resources = { [chosen.id] = chosen.amount },
        intent = { kind = "collectionDonate",
            remote = "CollectionAction",
            args = { "deposit", chosen.id, chosen.amount },
            itemId = chosen.id, amount = chosen.amount,
            loose = chosen.loose,
            collected = chosen.collected,
            worn = chosen.worn,
            reserve = chosen.reserve,
            catalogKey = view.catalogKey,
            protectionKey = view.protectionKey,
            expectedGain = chosen.expectedGain } }, nil
end

function CollectionDonate.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table"
        or proposal.feature ~= "collectionDonate"
        or type(intent) ~= "table"
        or intent.kind ~= "collectionDonate"
        or not same(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Collection baseline changed"
    end
    local native = before.native
    local used = worn(native)
    local protected = protection(before, before.collectionProtection)
    if type(native) ~= "table" or native.fullSync ~= true
        or type(before.collectionCatalog) ~= "table"
        or before.collectionCatalog.catalogKey
            ~= intent.catalogKey
        or not protected
        or before.collectionProtection.key ~= intent.protectionKey
        or (protected[intent.itemId] or 0) > intent.reserve
        or not used or (used[intent.itemId] or 0) ~= intent.worn
        or count(native.inventory, intent.itemId) ~= intent.loose
        or collected(native, intent.itemId) ~= intent.collected
        or not integer(intent.amount, 1)
        or intent.amount > 10
        or intent.loose - intent.amount < intent.reserve
        or type(intent.args) ~= "table"
        or intent.args[1] ~= "deposit"
        or intent.args[2] ~= intent.itemId
        or intent.args[3] ~= intent.amount then
        return nil, "Exact protected Collection surplus changed"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, itemId = intent.itemId,
        amount = intent.amount, loose = intent.loose,
        collected = intent.collected,
        worn = intent.worn }, nil
end

function CollectionDonate.evaluate(proposal, before, after,
    reply, baseline)
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
    local used = worn(native)
    if reply.ok ~= true or reply.moved ~= baseline.amount
        or type(native) ~= "table" or native.fullSync ~= true
        or not used or (used[baseline.itemId] or 0) ~= baseline.worn
        or count(native.inventory, baseline.itemId)
            ~= baseline.loose - baseline.amount
        or collected(native, baseline.itemId)
            ~= baseline.collected + baseline.amount then
        return "pending"
    end
    return "confirmed"
end

return CollectionDonate
