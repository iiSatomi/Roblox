-- Owned player UseConsumable with sequence, cooldown and newer-Sync proof.
local Restoratives = {}

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

function Restoratives.read(raw, context)
    if not same(raw, context) or raw.revision ~= context.revision
        or raw.capturedAt ~= context.capturedAt
        or not integer(raw.revision, 0) then
        return nil, "Restorative snapshot changed"
    end
    local native, catalog = raw.native, raw.restorativeCatalog
    if type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.serverNow, 0)
        or context.serverNow ~= native.serverNow
        or not integer(native.consumableUseSequence, 0)
        or not integer(native.consumableReadyAt, 0)
        or type(native.pools) ~= "table"
        or type(native.stats) ~= "table"
        or type(native.derived) ~= "table"
        or type(catalog) ~= "table"
        or catalog.release ~= context.release
        or catalog.catalogKey ~= context.restorativeCatalogKey
        or not integer(catalog.cooldown, 1)
        or type(catalog.items) ~= "table"
        or #catalog.items ~= 9 then
        return nil, "Current restorative catalog, pool and cooldown required"
    end
    local max = { health = native.stats.maxHealth,
        energy = native.derived.effMaxEnergy,
        stamina = native.stats.maxStamina }
    local pools, bound, ordinary, items = {}, {}, {}, {}
    for pool, maximum in pairs(max) do
        local current = native.pools[pool]
        if not finite(maximum) or maximum <= 0
            or not finite(current) or current < 0
            or current > maximum then
            return nil, "Invalid current restorative pool"
        end
        pools[pool] = { current = current, maximum = maximum }
    end
    local seen = {}
    for index, row in pairs(catalog.items) do
        if not integer(index, 1) or index > 9
            or type(row) ~= "table" or type(row.id) ~= "string"
            or seen[row.id] or not pools[row.pool]
            or (row.percent ~= 25 and row.percent ~= 50
                and row.percent ~= 100)
            or count(native.inventoryBound, row.id) == nil
            or count(native.inventory, row.id) == nil then
            return nil, "Invalid restorative catalog or custody"
        end
        seen[row.id] = true
        items[index] = { id = row.id, pool = row.pool,
            percent = row.percent }
        bound[row.id] = count(native.inventoryBound, row.id)
        ordinary[row.id] = count(native.inventory, row.id)
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        serverNow = native.serverNow,
        sequence = native.consumableUseSequence,
        readyAt = native.consumableReadyAt,
        catalogKey = catalog.catalogKey,
        cooldown = catalog.cooldown, pools = pools,
        items = items, bound = bound, ordinary = ordinary }, nil
end

function Restoratives.propose(view, settings)
    if type(view) ~= "table" or type(settings) ~= "table"
        or not same(view, view) then
        return nil, "Missing restorative input"
    end
    if settings.enabled ~= true then return nil, "Restoratives disabled" end
    local policy = settings.policy
    if policy ~= "Balanced recovery" and policy ~= "Small first"
        and policy ~= "Large first" then
        return nil, "Select a supported restorative strategy"
    end
    local custom = type(settings.custom) == "table"
        and settings.custom or settings
    for _, key in ipairs({ "healthBelow", "energyBelow",
        "staminaBelow" }) do
        if not integer(custom[key], 0) or custom[key] > 100 then
            return nil, "Restorative thresholds required"
        end
    end
    if custom.custody ~= "Bound only"
        and custom.custody ~= "Bound or tradable" then
        return nil, "Restorative custody choice required"
    end
    if not integer(view.readyAt, 0)
        or not integer(view.serverNow, 0)
        or view.readyAt > view.serverNow then
        return nil, "Player consumables cooling down"
    end
    local rank = { health = 1, energy = 2, stamina = 3 }
    local best, bestRank, bestSource, bestScore
    for _, row in ipairs(view.items or {}) do
        local pool = view.pools[row.pool]
        local threshold = custom[row.pool .. "Below"]
        local fromBound = (view.bound[row.id] or 0) > 0
        local owned = fromBound or (custom.custody
            == "Bound or tradable" and (view.ordinary[row.id] or 0) > 0)
        if pool and owned and pool.current < pool.maximum
            and pool.current / pool.maximum * 100 <= threshold then
            local gain = math.max(1,
                math.ceil(pool.maximum * row.percent / 100))
            local waste = math.max(0,
                gain - (pool.maximum - pool.current))
            local source = fromBound and 1 or 2
            local score = policy == "Small first" and -row.percent
                or policy == "Large first" and row.percent
                or -waste * 1000 + row.percent
            if not best or rank[row.pool] < bestRank
                or (rank[row.pool] == bestRank
                    and (source < bestSource
                        or (source == bestSource
                            and score > bestScore))) then
                best, bestRank, bestSource, bestScore = row,
                    rank[row.pool], source, score
                best.fromBound = fromBound
                best.expectedGain = gain
                best.beforePool = pool.current
            end
        end
    end
    if not best then return nil, "No eligible owned restorative" end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "restoratives",
        actionKey = "restoratives:" .. view.catalogKey .. ":"
            .. view.sequence .. ":" .. best.id .. ":"
            .. tostring(best.fromBound),
        resources = { [best.id] = 1 },
        intent = { kind = "restoratives",
            remote = "UseConsumable",
            args = { best.id, best.fromBound, view.sequence },
            itemId = best.id, fromBound = best.fromBound,
            sequence = view.sequence, resource = best.pool,
            beforePool = best.beforePool,
            expectedGain = best.expectedGain,
            catalogKey = view.catalogKey } }, nil
end

function Restoratives.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "restoratives"
        or type(intent) ~= "table" or intent.kind ~= "restoratives"
        or not same(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Restorative baseline changed"
    end
    local native = before.native
    local inventory = type(native) == "table"
        and (intent.fromBound and native.inventoryBound
            or native.inventory)
    local amount = count(inventory, intent.itemId)
    if type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.serverNow, 0)
        or native.consumableUseSequence ~= intent.sequence
        or not integer(native.consumableReadyAt, 0)
        or native.consumableReadyAt > native.serverNow
        or type(before.restorativeCatalog) ~= "table"
        or before.restorativeCatalog.catalogKey
            ~= intent.catalogKey
        or not amount or amount < 1
        or (intent.fromBound ~= true
            and count(native.inventoryBound, intent.itemId) ~= 0)
        or type(native.pools) ~= "table"
        or native.pools[intent.resource] ~= intent.beforePool
        or type(intent.args) ~= "table"
        or intent.args[1] ~= intent.itemId
        or intent.args[2] ~= intent.fromBound
        or intent.args[3] ~= intent.sequence then
        return nil, "Restorative item, pool or sequence changed"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision,
        itemId = intent.itemId, fromBound = intent.fromBound,
        sequence = intent.sequence, resource = intent.resource,
        beforePool = intent.beforePool, count = amount }, nil
end

function Restoratives.evaluate(proposal, before, after, reply,
    baseline)
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
    local inventory = type(native) == "table"
        and (baseline.fromBound and native.inventoryBound
            or native.inventory)
    local pools = type(native) == "table" and native.pools
    if reply.ok ~= true or type(native) ~= "table"
        or native.fullSync ~= true
        or not integer(reply.sequence, baseline.sequence + 1)
        or reply.sequence ~= baseline.sequence + 1
        or not integer(reply.readyAt, 0)
        or native.consumableUseSequence ~= reply.sequence
        or native.consumableReadyAt ~= reply.readyAt
        or reply.resource ~= baseline.resource
        or not finite(reply.gain) or reply.gain <= 0
        or count(inventory, baseline.itemId) ~= baseline.count - 1
        or type(pools) ~= "table"
        or not finite(pools[baseline.resource])
        or pools[baseline.resource] <= baseline.beforePool then
        return "pending"
    end
    return "confirmed"
end

return Restoratives
