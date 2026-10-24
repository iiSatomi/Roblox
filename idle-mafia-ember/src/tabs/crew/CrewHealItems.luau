-- Older saved CrewAction("healitem") payload; kept offline until current proof.
local CrewHealItems = {}

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

local function roster(native)
    local crew = type(native) == "table" and native.crew
    if type(crew) ~= "table" or #crew < 2
        or #crew > 46 then return nil end
    local injured, identities, count = {}, {}, 0
    for slot, row in pairs(crew) do
        if not integer(slot, 1) or slot > #crew
            or type(row) ~= "table" then return nil end
        count = count + 1
        if slot > 1 then
            if row.name ~= nil or row.rarity ~= nil then
                if type(row.name) ~= "string" or #row.name == 0
                    or #row.name > 64 or not integer(row.rarity, 1)
                    or not integer(row.injuredUntil or 0, 0)
                    or not integer(row.recalledUntil or 0, 0) then
                    return nil
                end
                local key = #row.name .. ":" .. row.name
                    .. ":" .. row.rarity
                if identities[key] then return nil end
                identities[key] = true
                if (row.injuredUntil or 0) > native.serverNow
                    and (row.recalledUntil or 0) < row.injuredUntil
                    and row.duty == nil and row.rolling ~= true
                    and row.training == nil then
                    if type(row.healId) ~= "string"
                        or #row.healId == 0
                        or #row.healId > 128 then return nil end
                    injured[#injured + 1] = { slot = slot,
                        name = row.name, rarity = row.rarity,
                        healId = row.healId,
                        injuredUntil = row.injuredUntil,
                        remaining = row.injuredUntil - native.serverNow }
                end
            elseif row.rolling == true then
                return nil
            end
        end
    end
    if count ~= #crew or type(crew[1]) ~= "table" then return nil end
    table.sort(injured, function(a, b)
        return a.remaining > b.remaining
            or (a.remaining == b.remaining and a.slot < b.slot)
    end)
    return injured
end

local function count(map, id)
    if type(map) ~= "table" then return nil end
    local value = map[id] or 0
    if not integer(value, 0) then return nil end
    return value
end

function CrewHealItems.read(raw, context)
    if not same(raw, context) or raw.revision ~= context.revision
        or raw.capturedAt ~= context.capturedAt
        or not integer(raw.revision, 0) then
        return nil, "Crew item healing snapshot changed"
    end
    local native, catalog = raw.native, raw.healItemCatalog
    if type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.serverNow, 0)
        or context.serverNow ~= native.serverNow
        or not integer(native.henchmanConsumableUseSequence, 0)
        or not integer(native.henchmanConsumableReadyAt, 0)
        or type(catalog) ~= "table"
        or catalog.release ~= context.release
        or catalog.catalogKey ~= context.healItemCatalogKey
        or type(catalog.items) ~= "table"
        or not integer(catalog.injurySeconds, 1)
        or not integer(catalog.cooldownSeconds, 1) then
        return nil, "Current Crew item cooldown and catalog required"
    end
    local injured = roster(native)
    if not injured then return nil, "Unique Crew injury identities required" end
    local bound, ordinary = {}, {}
    for id, percent in pairs(catalog.items) do
        if type(id) ~= "string"
            or (percent ~= 25 and percent ~= 50 and percent ~= 100)
            or count(native.inventoryBound, id) == nil
            or count(native.inventory, id) == nil then
            return nil, "Invalid Crew healing item custody"
        end
        bound[id] = count(native.inventoryBound, id)
        ordinary[id] = count(native.inventory, id)
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        serverNow = native.serverNow,
        sequence = native.henchmanConsumableUseSequence,
        readyAt = native.henchmanConsumableReadyAt,
        catalog = catalog, injured = injured,
        bound = bound, ordinary = ordinary }, nil
end

function CrewHealItems.propose(view, settings)
    if type(view) ~= "table" or type(settings) ~= "table"
        or not same(view, view) then
        return nil, "Missing Crew item healing input"
    end
    if settings.enabled ~= true then
        return nil, "Crew item healing disabled"
    end
    local id = settings.policy
    local custom = type(settings.custom) == "table"
        and settings.custom or settings
    if type(id) ~= "string" or type(view.catalog) ~= "table"
        or not integer(view.catalog.items[id], 1)
        or not integer(custom.minRemaining, 1)
        or not integer(view.serverNow, 0)
        or not integer(view.readyAt, 0)
        or view.readyAt > view.serverNow then
        return nil, "Selected item or Crew cooldown unavailable"
    end
    local fromBound = (view.bound[id] or 0) > 0
    if not fromBound and (view.ordinary[id] or 0) < 1 then
        return nil, "Selected Crew healing item not owned"
    end
    local chosen
    for _, row in ipairs(view.injured) do
        if row.remaining >= custom.minRemaining then
            chosen = row
            break
        end
    end
    if not chosen then return nil, "No qualifying Crew injury" end
    local payload = { itemId = id, fromBound = fromBound,
        memberId = chosen.healId,
        injuredUntil = chosen.injuredUntil,
        sequence = view.sequence }
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "crewHealItems",
        actionKey = "crewHealItems:" .. view.catalog.catalogKey
            .. ":" .. view.sequence .. ":" .. chosen.slot .. ":"
            .. chosen.healId .. ":" .. id,
        resources = { [id] = 1 },
        intent = { kind = "crewHealItems", remote = "CrewAction",
            args = { "healitem", chosen.slot, payload },
            slot = chosen.slot, name = chosen.name,
            rarity = chosen.rarity, memberId = chosen.healId,
            itemId = id, fromBound = fromBound,
            injuredUntil = chosen.injuredUntil,
            sequence = view.sequence,
            minRemaining = custom.minRemaining,
            catalogKey = view.catalog.catalogKey } }, nil
end

function CrewHealItems.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table"
        or proposal.feature ~= "crewHealItems"
        or type(intent) ~= "table"
        or intent.kind ~= "crewHealItems"
        or not integer(intent.minRemaining, 1)
        or not same(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Crew item healing baseline changed"
    end
    local context = { session = proposal.session,
        account = proposal.account, place = proposal.place,
        release = proposal.release, revision = proposal.revision,
        capturedAt = before.capturedAt,
        serverNow = before.native and before.native.serverNow,
        healItemCatalogKey = intent.catalogKey }
    local view = CrewHealItems.read(before, context)
    if not view or view.readyAt > view.serverNow
        or view.sequence ~= intent.sequence then
        return nil, "Current Crew item sequence unavailable"
    end
    local fromBound = (view.bound[intent.itemId] or 0) > 0
    if fromBound ~= intent.fromBound
        or (not fromBound and (view.ordinary[intent.itemId] or 0) < 1) then
        return nil, "Selected Crew item stack changed"
    end
    local row
    for _, member in ipairs(view.injured) do
        if member.slot == intent.slot then row = member break end
    end
    if not row or row.name ~= intent.name
        or row.rarity ~= intent.rarity
        or row.healId ~= intent.memberId
        or row.injuredUntil ~= intent.injuredUntil
        or row.remaining < intent.minRemaining then
        return nil, "Exact Crew injury changed"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, slot = row.slot,
        name = row.name, rarity = row.rarity,
        memberId = row.healId,
        injuredUntil = row.injuredUntil,
        itemId = intent.itemId, fromBound = fromBound,
        sequence = view.sequence,
        count = fromBound and view.bound[intent.itemId]
            or view.ordinary[intent.itemId] }, nil
end

function CrewHealItems.evaluate(proposal, before, after, reply, baseline)
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
    local crew = type(native) == "table" and native.crew
    local member = type(crew) == "table" and crew[baseline.slot]
    local inventory = type(native) == "table"
        and (baseline.fromBound and native.inventoryBound
            or native.inventory)
    if reply.ok ~= true or type(native) ~= "table"
        or native.fullSync ~= true
        or not integer(native.serverNow, 0)
        or not integer(reply.sequence, baseline.sequence + 1)
        or reply.sequence ~= baseline.sequence + 1
        or not integer(reply.readyAt, 0)
        or native.henchmanConsumableUseSequence ~= reply.sequence
        or native.henchmanConsumableReadyAt ~= reply.readyAt
        or count(inventory, baseline.itemId) ~= baseline.count - 1
        or type(member) ~= "table"
        or member.name ~= baseline.name
        or member.rarity ~= baseline.rarity
        or not integer(member.injuredUntil or 0, 0)
        or (member.healId ~= baseline.memberId
            and (member.injuredUntil or 0) > native.serverNow)
        or member.injuredUntil >= baseline.injuredUntil then
        return "pending"
    end
    return "confirmed"
end

return CrewHealItems
