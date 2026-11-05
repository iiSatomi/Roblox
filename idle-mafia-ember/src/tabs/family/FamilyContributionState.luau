-- Reviewed Family terms plus snapshot-bound, personally attributable info.
local FamilyContributionState = {}
local Methods = {}
Methods.__index = Methods
local headers = { "session", "account", "place", "release", "revision", "capturedAt" }
local ledgerFields = { cash = "donated", gold_bar = "donatedGold", stamina = "contributed" }

local function finite(value, low, high)
    return type(value) == "number" and value == value and value >= low and value <= high
end
local function integer(value, low, high)
    return finite(value, low, high) and value % 1 == 0
end
local function actorId(snapshot)
    local native = type(snapshot) == "table" and snapshot.native
    if type(native) ~= "table" then return nil end
    local actor = native.userId
    if actor == nil then actor = tonumber(snapshot.account) end
    return integer(actor, 1, 9007199254740991) and actor or nil
end
local function id(value)
    return type(value) == "string" and #value > 0 and #value <= 160
        or integer(value, 1, 9007199254740991)
end
local function map(source, maximum)
    if type(source) ~= "table" then return nil end
    local result, count = {}, 0
    for key, value in pairs(source) do
        count = count + 1
        if count > 64 or type(key) ~= "string" or #key == 0 or #key > 80
            or not integer(value, 0, maximum) then return nil end
        result[key] = value
    end
    return result
end
local function same(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs(headers) do if a[field] ~= b[field] then return false end end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0 or #a[field] > 200 then return false end
    end
    return integer(a.revision, 0, 9007199254740991)
        and finite(a.capturedAt, 0, 9007199254740991)
end
local function copied(source)
    local result = {}
    for key, value in pairs(source) do result[key] = value end
    return result
end

function FamilyContributionState.parseFamily(family, actorId)
    if type(family) ~= "table" or not id(family.id)
        or not integer(actorId, 1, 9007199254740991)
        or type(family.members) ~= "table" or #family.members < 1 or #family.members > 50 then
        return nil
    end
    local perks = map(family.perks, 25)
    local progress = map(family.perkProgress == nil and {} or family.perkProgress, 1000000000)
    if not perks or not progress then return nil end
    local seen, own, count = {}, nil, 0
    for slot, row in pairs(family.members) do
        count = count + 1
        if not integer(slot, 1, #family.members) or type(row) ~= "table"
            or not integer(row.userId, 1, 9007199254740991) or seen[row.userId] then return nil end
        seen[row.userId] = true
        if row.userId == actorId then own = row end
    end
    if count ~= #family.members or not own then return nil end
    local ledger = {}
    for resource, field in pairs(ledgerFields) do
        local value = own[field]
        if value == nil then value = 0 end
        if not integer(value, 0, 9007199254740991) then return nil end
        ledger[resource] = value
    end
    return { familyId = family.id, actorId = actorId, ledger = ledger,
        perks = perks, progress = progress }
end

function FamilyContributionState.new(config, fingerprint, release)
    local source = type(config) == "table" and config.FAMILY
    assert(type(source) == "table" and integer(source.donateMin, 1, 1000000000)
        and integer(source.contributeMax, 1, 25)
        and type(source.staminaPerkCosts) == "table" and #source.staminaPerkCosts >= 1
        and #source.staminaPerkCosts <= 25 and type(source.perkTracks) == "table"
        and type(fingerprint) == "string" and #fingerprint == 64
        and fingerprint:match("^[%x]+$") and type(release) == "string" and #release > 0,
        "Missing reviewed Family contribution terms")
    local costs, tracks, orders, rows = {}, {}, {}, 0
    for index, cost in pairs(source.staminaPerkCosts) do
        assert(integer(index, 1, #source.staminaPerkCosts) and integer(cost, 1, 1000000000),
            "Invalid Family Stamina cost")
        rows = rows + 1
        costs[index] = cost
    end
    assert(rows == #source.staminaPerkCosts, "Sparse Family Stamina costs")
    rows = 0
    for key, track in pairs(source.perkTracks) do
        rows = rows + 1
        assert(rows <= 64 and type(key) == "string" and #key > 0 and #key <= 80
            and type(track) == "table", "Invalid Family perk track")
        if track.kind == "stamina" then
            tracks[key] = true
            orders[key] = finite(track.order, -1000000000, 1000000000) and track.order or 1000
        end
    end
    return setmetatable({ release = release, key = fingerprint:lower(),
        donateMin = source.donateMin, contributeMax = source.contributeMax,
        costs = costs, tracks = tracks, orders = orders }, Methods)
end

function Methods:Enrich(snapshot)
    if not same(snapshot, snapshot) or snapshot.release ~= self.release
        or type(snapshot.native) ~= "table" or snapshot.native.fullSync ~= true then
        return nil, "Current full Family Sync required"
    end
    local result = copied(snapshot)
    result.familyContributionCatalog = { key = self.key, release = self.release,
        donateMin = self.donateMin, contributeMax = self.contributeMax,
        staminaCosts = copied(self.costs), staminaTracks = copied(self.tracks),
        staminaTrackOrder = copied(self.orders) }
    return result, nil
end

function Methods:Stage(snapshot, reply)
    local native = type(snapshot) == "table" and snapshot.native
    local actor = actorId(snapshot)
    local family = type(reply) == "table" and reply.family
    local parsed = FamilyContributionState.parseFamily(family, actor)
    if not same(snapshot, snapshot) or snapshot.release ~= self.release
        or type(native) ~= "table" or native.fullSync ~= true
        or type(native.family) ~= "table" or not parsed
        or parsed.familyId ~= native.family.id or reply.ok ~= true
        or reply.pending == true or reply.code == "rate_limited" then return nil, "Current personal Family info required" end
    local result, proof = copied(snapshot), {}
    for _, field in ipairs(headers) do proof[field] = snapshot[field] end
    proof.family = parsed
    proof.sourceKey = self.key
    result.familyContributionProof = proof
    return result, nil
end

function FamilyContributionState.read(raw, context)
    if not same(raw, context) then return nil, "Family contribution snapshot changed" end
    local proof, native, catalog = raw.familyContributionProof, raw.native, raw.familyContributionCatalog
    local family = type(proof) == "table" and proof.family
    if not same(proof, context) or type(family) ~= "table"
        or not integer(family.actorId, 1, 9007199254740991)
        or family.actorId ~= actorId(raw)
        or type(family.ledger) ~= "table"
        or type(native) ~= "table" or native.fullSync ~= true
        or type(native.family) ~= "table" or family.familyId ~= native.family.id
        or not id(family.familyId) or not finite(native.cash, 0, 9007199254740991)
        or type(native.pools) ~= "table" or not finite(native.pools.stamina, 0, 1000000000)
        or type(native.inventory) ~= "table" or type(native.inventoryBound) ~= "table"
        or type(catalog) ~= "table" or catalog.release ~= context.release
        or proof.sourceKey ~= catalog.key
        or type(catalog.key) ~= "string" or #catalog.key ~= 64
        or not catalog.key:match("^[%x]+$")
        or not integer(catalog.donateMin, 1, 1000000000)
        or not integer(catalog.contributeMax, 1, 25)
        or type(catalog.staminaCosts) ~= "table" or #catalog.staminaCosts < 1
        or #catalog.staminaCosts > 25 or type(catalog.staminaTracks) ~= "table" then
        return nil, "Fresh source-bound Family contribution info required"
    end
    local gold, bound = native.inventory.gold_bar, native.inventoryBound.gold_bar
    if gold == nil then gold = 0 end
    if bound == nil then bound = 0 end
    if not integer(gold, 0, 1000000000) or not integer(bound, 0, 1000000000) then
        return nil, "Invalid Family Gold custody"
    end
    local perks, progress = map(family.perks, 25), map(family.progress, 1000000000)
    if not perks or not progress then return nil, "Invalid Family perk state" end
    local trackCount, orders = 0, {}
    for track, enabled in pairs(catalog.staminaTracks) do
        trackCount = trackCount + 1
        if trackCount > 64 or type(track) ~= "string" or #track == 0 or #track > 80
            or enabled ~= true then return nil, "Invalid Family Stamina catalog" end
        local order = type(catalog.staminaTrackOrder) == "table" and catalog.staminaTrackOrder[track]
        if order ~= nil and not finite(order, -1000000000, 1000000000) then
            return nil, "Invalid Family Stamina track order"
        end
        orders[track] = order or 1000
        if perks[track] == nil then perks[track] = 0 end
        if progress[track] == nil then progress[track] = 0 end
    end
    local ledger = {}
    for resource in pairs(ledgerFields) do
        if not integer(family.ledger[resource], 0, 9007199254740991) then
            return nil, "Invalid personal Family ledger"
        end
        ledger[resource] = family.ledger[resource]
    end
    local view = { familyId = family.familyId, actorId = family.actorId,
        ledger = ledger, perks = perks, progress = progress, cash = native.cash,
        stamina = native.pools.stamina, gold = gold, boundGold = bound,
        donateMin = catalog.donateMin, contributeMax = catalog.contributeMax,
        staminaCosts = copied(catalog.staminaCosts), staminaTracks = copied(catalog.staminaTracks),
        staminaTrackOrder = orders }
    for _, field in ipairs(headers) do view[field] = raw[field] end
    if same(raw.familyUsageProof, context) and type(raw.familyUsageProof.usage) == "table" then
        local usage = {}
        for _, feature in ipairs({ "familyCash", "familyGold", "familyStamina" }) do
            local row = raw.familyUsageProof.usage[feature]
            if type(row) ~= "table" or not integer(row.attempted, 0, 1000)
                or not integer(row.spent, 0, 1000000000000000) then
                return nil, "Invalid Family run usage"
            end
            usage[feature] = { attempted = row.attempted, spent = row.spent }
        end
        view.usage = usage
    end
    return view, nil
end

Methods.read = FamilyContributionState.read
return FamilyContributionState
