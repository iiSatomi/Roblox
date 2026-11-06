-- Saved OpenCrate(id, false, count, luck) for owned unbound crates.
local Chests = {}
local MAX = 9007199254740991

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

-- Durable exposure uses the existing checkpoint transaction and explicit reset.
function Chests.copy(raw)
    if raw == nil then return {version = 1, attempted = 0, spent = 0} end
    if type(raw) ~= "table" or raw.version ~= 1 or raw.unknown ~= nil and raw.unknown ~= true
        or not integer(raw.attempted, 0)
        or not integer(raw.spent, 0) or raw.spent > MAX or raw.attempted > raw.spent
        or raw.spent > raw.attempted * 10 or (raw.attempted == 0 and raw.spent ~= 0) then return nil end
    for key in pairs(raw) do if key ~= "version" and key ~= "attempted" and key ~= "spent" and key ~= "unknown" then return nil end end
    return {version = 1, attempted = raw.attempted, spent = raw.spent, unknown = raw.unknown}
end

function Chests.copyCharge(raw, feature, resources)
    if feature ~= "chests" or type(raw) ~= "table" or type(raw.itemId) ~= "string"
        or #raw.itemId == 0 or not integer(raw.amount, 1) or raw.amount > 10
        or not Chests.copy({version = 1, attempted = raw.attemptedBefore, spent = raw.spentBefore})
        or raw.spentBefore > MAX - raw.amount or type(resources) ~= "table"
        or resources[raw.itemId] ~= raw.amount then return nil end
    for key in pairs(resources) do if key ~= raw.itemId then return nil end end
    for key in pairs(raw) do
        if key ~= "itemId" and key ~= "amount" and key ~= "attemptedBefore" and key ~= "spentBefore" then return nil end
    end
    return {itemId = raw.itemId, amount = raw.amount, attemptedBefore = raw.attemptedBefore, spentBefore = raw.spentBefore}
end

function Chests.charge(raw, proposal)
    local usage = Chests.copy(raw)
    local intent = type(proposal) == "table" and proposal.intent
    if not usage or usage.unknown == true or type(intent) ~= "table" or intent.kind ~= "chests"
        or type(intent.totalLimitEnabled) ~= "boolean"
        or not integer(intent.totalLimit, 1) or intent.totalLimit > 1000 then return nil, nil, "Chest allowance intent invalid" end
    local charge = Chests.copyCharge({itemId = intent.itemId, amount = intent.amount,
        attemptedBefore = intent.attemptedBefore, spentBefore = intent.spentBefore}, proposal.feature, proposal.resources)
    if not charge or usage.attempted ~= charge.attemptedBefore or usage.spent ~= charge.spentBefore
        or intent.totalLimitEnabled and usage.spent + charge.amount > intent.totalLimit then
        return nil, nil, "Chest allowance changed or exhausted"
    end
    return {version = 1, attempted = usage.attempted + 1, spent = usage.spent + charge.amount}, charge, nil
end

function Chests.holds(usage, charge)
    return type(usage) == "table" and usage.attempted >= charge.attemptedBefore + 1
        and usage.spent >= charge.spentBefore + charge.amount
end

function Chests.rollback(raw, charge)
    local usage = Chests.copy(raw)
    if not usage or not Chests.holds(usage, charge) or usage.attempted ~= charge.attemptedBefore + 1
        or usage.spent ~= charge.spentBefore + charge.amount then return nil end
    return {version = 1, attempted = charge.attemptedBefore, spent = charge.spentBefore, unknown = usage.unknown}
end

local function usageProof(raw)
    local proof = raw.chestUsageProof
    if not same(raw, proof) or proof.revision ~= raw.revision or proof.capturedAt ~= raw.capturedAt then return nil end
    return Chests.copy({version = 1, attempted = proof.attempted, spent = proof.spent})
end

local function luck(raw, proof)
    if type(raw) ~= "table" or type(proof) ~= "table"
        or proof.session ~= raw.session
        or proof.account ~= raw.account
        or proof.place ~= raw.place
        or proof.release ~= raw.release
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
    local currentLuck = luck(raw, raw.crateLuckProof)
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.inventory) ~= "table"
        or type(native.inventoryBound) ~= "table"
        or type(catalog) ~= "table"
        or catalog.release ~= context.release
        or catalog.catalogKey ~= context.crateCatalogKey
        or not integer(catalog.batchMax, 1)
        or type(catalog.crates) ~= "table"
        or currentLuck == nil then
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
        luck = currentLuck, owned = owned, usage = usageProof(raw) }, nil
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
    local limited = custom.totalLimitEnabled == true
    local totalLimit = custom.totalLimit or 1
    if custom.totalLimitEnabled ~= nil and type(custom.totalLimitEnabled) ~= "boolean"
        or not integer(totalLimit, 1) or totalLimit > 1000 then return nil, "Invalid chest total allowance" end
    if limited and not view.usage then return nil, "Chest usage owner unavailable" end
    local remaining = limited and totalLimit - view.usage.spent or MAX
    if remaining <= 0 then return nil, "Chest total allowance reached" end
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
        view.batchMax, remaining)
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "chests",
        actionKey = "chests:" .. view.catalogKey .. ":"
            .. chosen.id .. ":" .. chosen.count .. ":"
            .. amount,
        resources = { [chosen.id] = amount },
        intent = { kind = "chests",
            itemId = chosen.id, amount = amount,
            beforeCount = chosen.count, luck = view.luck,
            catalogKey = view.catalogKey, totalLimitEnabled = limited, totalLimit = totalLimit,
            attemptedBefore = view.usage and view.usage.attempted,
            spentBefore = view.usage and view.usage.spent } }, nil
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
        or before.ownedCrateCatalog.release ~= proposal.release
        or before.ownedCrateCatalog.catalogKey ~= intent.catalogKey
        or type(before.ownedCrateCatalog.crates) ~= "table"
        or before.ownedCrateCatalog.crates[intent.itemId] ~= true
        or not integer(intent.amount, 1)
        or not integer(before.ownedCrateCatalog.batchMax, 1)
        or intent.amount > before.ownedCrateCatalog.batchMax
        or type(proposal.resources) ~= "table"
        or proposal.resources[intent.itemId] ~= intent.amount
        or count(native.inventory, intent.itemId)
            ~= intent.beforeCount
        or intent.beforeCount < intent.amount
        or luck(before, before.crateLuckProof) ~= intent.luck then
        return nil, "Exact owned crate and luck quote unavailable"
    end
    if intent.attemptedBefore ~= nil or intent.totalLimitEnabled == true then
        local usage = usageProof(before)
        if not usage or not Chests.charge(usage, proposal) then return nil, "Chest allowance quote changed" end
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
    if reply.pending ~= nil and reply.pending ~= false or reply.code ~= nil and reply.code ~= "" then return "pending" end
    local native = after.native
    if reply.ok == false then
        if type(native) ~= "table" or native.fullSync ~= true
            or type(native.inventory) ~= "table" or type(native.inventoryBound) ~= "table"
            or type(baseline.inventory) ~= "table"
            or count(native.inventory, baseline.itemId) ~= baseline.count then return "pending" end
        local current = {}
        for _, field in ipairs({"inventory", "inventoryBound"}) do
            for id, amount in pairs(native[field]) do
                if type(id) ~= "string" or not integer(amount, 0) then return "pending" end
                current[id] = (current[id] or 0) + amount
            end
        end
        for id, amount in pairs(baseline.inventory) do
            if (current[id] or 0) ~= amount then return "pending" end
        end
        for id, amount in pairs(current) do
            if (baseline.inventory[id] or 0) ~= amount then return "pending" end
        end
        return "rejected"
    end
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

local function exact(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not exact(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end

-- Saved evidence only observes the original request; it never renews allowance.
function Chests.recoverSaved(data, after)
    if type(data) ~= "table" or type(data.reply) ~= "table" or type(after) ~= "table"
        or type(data.before) ~= "table" or type(data.proposal) ~= "table" then return nil end
    local proposal, before, reply = data.proposal, data.before, data.reply
    local baseline = Chests.capture(proposal, before)
    if not baseline or not exact(baseline, data.baseline) or type(after.native) ~= "table"
        or after.native.fullSync ~= true or type(after.ownedCrateCatalog) ~= "table"
        or after.ownedCrateCatalog.catalogKey ~= proposal.intent.catalogKey
        or after.ownedCrateCatalog.release ~= proposal.release then return nil end
    for _, key in ipairs({"account", "place", "release"}) do if after[key] ~= proposal[key] then return nil end end
    if type(after.session) ~= "string" or #after.session == 0 then return nil end
    local current = after
    if after.session ~= proposal.session then
        if not finite(before.native.serverNow) or not finite(after.native.serverNow)
            or after.native.serverNow <= before.native.serverNow then return nil end
        current = {}
        for key, value in pairs(after) do current[key] = value end
        current.session, current.revision = proposal.session, proposal.revision + 1
    end
    local outcome = Chests.evaluate(proposal, before, current, reply, baseline)
    if outcome ~= "confirmed" and outcome ~= "rejected" then return nil end
    local rewards, ids = {}, {}
    if outcome == "confirmed" then
        for _, id in ipairs(reply.itemIds) do rewards[id] = (rewards[id] or 0) + 1 end
    end
    for _, native in ipairs({before.native, after.native}) do
        for _, field in ipairs({"inventory", "inventoryBound"}) do
            if type(native[field]) ~= "table" then return nil end
            for id, amount in pairs(native[field]) do
                if type(id) ~= "string" or not integer(amount, 0) then return nil end
                ids[id] = true
            end
        end
    end
    for id in pairs(ids) do
        local looseDelta = count(after.native.inventory, id) - count(before.native.inventory, id)
        local boundDelta = count(after.native.inventoryBound, id) - count(before.native.inventoryBound, id)
        local consumed = outcome == "confirmed" and id == baseline.itemId and baseline.amount or 0
        if looseDelta + consumed < 0 or boundDelta < 0
            or looseDelta + boundDelta ~= (rewards[id] or 0) - consumed then return nil end
    end
    return outcome
end

return Chests
