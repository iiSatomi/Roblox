-- Saved guarded item healing with member/sequence/custody/effect evidence.
local CrewHealItems = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function timestamp(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

local function same(a, b, restart)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0 or type(b[field]) ~= "string" or #b[field] == 0
            or not (restart and field == "session") and a[field] ~= b[field] then return false end
    end
    return true
end

local function equal(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for key, value in pairs(a) do if b[key] ~= value then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
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
                    or not timestamp(row.injuredUntil or 0)
                    or not timestamp(row.recalledUntil or 0) then
                    return nil
                end
                if row.healId ~= nil then
                    if type(row.healId) ~= "string" or #row.healId == 0 or #row.healId > 128
                        or identities[row.healId] then return nil end
                    identities[row.healId] = true
                end
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
    local sequence = type(native) == "table" and native.henchmanConsumableUseSequence
    local readyAt = type(native) == "table" and native.henchmanConsumableReadyAt
    if sequence == nil then sequence = 0 end
    if readyAt == nil then readyAt = 0 end
    if type(native) ~= "table" or native.fullSync ~= true
        or not timestamp(native.serverNow)
        or context.serverNow ~= native.serverNow
        or not integer(sequence, 0) or sequence >= 9007199254740991
        or not timestamp(readyAt)
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
        sequence = sequence, readyAt = readyAt,
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
        or not timestamp(view.serverNow)
        or not timestamp(view.readyAt)
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
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "crewHealItems",
        actionKey = "crewHealItems:" .. view.catalog.catalogKey
            .. ":" .. view.sequence .. ":" .. chosen.slot .. ":"
            .. chosen.healId .. ":" .. id,
        resources = { [id] = 1 },
        intent = { kind = "crewHealItems",
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
    local planned = CrewHealItems.propose(view, { enabled = true, policy = intent.itemId,
        minRemaining = intent.minRemaining })
    if not planned or planned.actionKey ~= proposal.actionKey
        or not equal(planned.intent, intent) or not equal(planned.resources, proposal.resources) then
        return nil, "Crew healing intent or item exposure changed"
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
        count = fromBound and view.bound[intent.itemId] or view.ordinary[intent.itemId],
        otherCount = fromBound and view.ordinary[intent.itemId] or view.bound[intent.itemId],
        reduction = view.catalog.items[intent.itemId] == 100 and row.remaining
            or math.min(row.remaining, math.ceil(view.catalog.injurySeconds * view.catalog.items[intent.itemId] / 100)),
        serverNow = view.serverNow, actionKey = planned.actionKey, intent = planned.intent }, nil
end

local function reconcile(proposal, before, after, reply, baseline, restart)
    if type(proposal) ~= "table" or type(reply) ~= "table"
        or not same(proposal, before) or not same(proposal, after, restart)
        or not same(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or before.revision ~= baseline.revision
        or proposal.actionKey ~= baseline.actionKey or not equal(proposal.intent, baseline.intent)
        or not equal(proposal.resources, {[baseline.itemId] = 1})
        or not integer(after.revision, restart and after.session ~= before.session and 0 or baseline.revision + 1) then
        return "pending"
    end
    local native = after.native
    local crew = type(native) == "table" and native.crew
    local member = type(crew) == "table" and crew[baseline.slot]
    local inventory = type(native) == "table"
        and (baseline.fromBound and native.inventoryBound
            or native.inventory)
    local other = type(native) == "table"
        and (baseline.fromBound and native.inventory or native.inventoryBound)
    if reply.pending == true then return "pending" end
    if reply.ok == false then
        return type(native) == "table" and native.fullSync == true
            and type(member) == "table" and member.healId == baseline.memberId
            and member.name == baseline.name and member.rarity == baseline.rarity
            and member.injuredUntil == baseline.injuredUntil
            and count(inventory, baseline.itemId) == baseline.count
            and count(other, baseline.itemId) == baseline.otherCount and "rejected" or "pending"
    end
    if reply.ok ~= true or reply.pending == true or reply.code == "rate_limited"
        or type(native) ~= "table"
        or native.fullSync ~= true
        or not timestamp(native.serverNow)
        or native.serverNow < baseline.serverNow
        or not integer(reply.sequence, baseline.sequence + 1)
        or reply.sequence ~= baseline.sequence + 1
        or not timestamp(reply.readyAt)
        or native.henchmanConsumableUseSequence ~= reply.sequence
        or native.henchmanConsumableReadyAt ~= reply.readyAt
        or count(inventory, baseline.itemId) ~= baseline.count - 1
        or count(other, baseline.itemId) ~= baseline.otherCount
        or type(member) ~= "table"
        or member.name ~= baseline.name
        or member.rarity ~= baseline.rarity
        or not timestamp(member.injuredUntil or 0)
        or member.healId ~= baseline.memberId
        or (member.injuredUntil or 0) >= baseline.injuredUntil then
        return "pending"
    end
    local full = baseline.reduction >= baseline.injuredUntil - baseline.serverNow
    if full and (member.injuredUntil or 0) <= native.serverNow
        or (not full and member.injuredUntil == baseline.injuredUntil - baseline.reduction) then
        return "confirmed"
    end
    return "pending"
end

function CrewHealItems.evaluate(proposal, before, after, reply, baseline)
    return reconcile(proposal, before, after, reply, baseline, false)
end
function CrewHealItems.recoverSaved(data, after)
    if type(data) ~= "table" or type(data.baseline) ~= "table" then return nil end
    local expected = CrewHealItems.capture(data.proposal, data.before)
    if not expected then return nil end
    for key, value in pairs(expected) do
        if key == "intent" then
            if not equal(value, data.baseline.intent) then return nil end
        elseif data.baseline[key] ~= value then return nil end
    end
    for key in pairs(data.baseline) do if expected[key] == nil then return nil end end
    local result = reconcile(data.proposal, data.before, after, data.reply, data.baseline, true)
    return (result == "confirmed" or result == "rejected") and result or nil
end

return CrewHealItems
