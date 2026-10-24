-- Saved CrewAction("heal", slot) with current cost and exact injury proof.
local CrewHeal = {}

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

local function member(raw, slot)
    local native = type(raw) == "table" and raw.native
    local crew = type(native) == "table" and native.crew
    local row = type(crew) == "table" and crew[slot]
    if type(native) ~= "table" or native.fullSync ~= true
        or type(row) ~= "table" or type(row.name) ~= "string"
        or #row.name == 0 or #row.name > 64
        or not integer(row.rarity, 0)
        or type(row.healId) ~= "string" or #row.healId == 0
        or #row.healId > 128
        or not integer(row.injuredUntil or 0, 0) then return nil end
    return row
end

function CrewHeal.read(raw, context)
    if not same(raw, context) or raw.revision ~= context.revision
        or raw.capturedAt ~= context.capturedAt then
        return nil, "Crew heal snapshot changed"
    end
    local native, rules = raw.native, context.healRules
    local crew = type(native) == "table" and native.crew
    local stamina = type(native) == "table"
        and type(native.pools) == "table" and native.pools.stamina
    if type(native) ~= "table" or native.fullSync ~= true
        or type(crew) ~= "table" or not integer(native.serverNow, 0)
        or context.serverNow ~= native.serverNow
        or type(stamina) ~= "number" or stamina ~= stamina
        or stamina < 0 or stamina == math.huge
        or type(rules) ~= "table" or rules.release ~= context.release
        or not integer(rules.healStaminaCost, 1)
        or not integer(rules.healSeconds, 1) then
        return nil, "Current Crew heal resources and rules required"
    end
    local injured, identities = {}, {}
    for slot, row in pairs(crew) do
        if not integer(slot, 1) or slot > 32
            or type(row) ~= "table" then
            return nil, "Invalid Crew roster"
        end
        if slot > 1 then
            if type(row.name) ~= "string" or #row.name == 0
                or #row.name > 64 or not integer(row.rarity, 0) then
                return nil, "Invalid Crew identity"
            end
            local key = #row.name .. ":" .. row.name .. ":" .. row.rarity
            if identities[key] then
                return nil, "Duplicate Crew identity"
            end
            identities[key] = true
        end
        if slot > 1 and row.injuredUntil ~= nil then
            local memberRow = member(raw, slot)
            if not memberRow then return nil, "Invalid injured Crew member" end
            local remaining = memberRow.injuredUntil - native.serverNow
            if remaining > 0 and memberRow.duty == nil
                and memberRow.rolling ~= true
                and memberRow.training == nil
                and (memberRow.recalledUntil or 0)
                    < memberRow.injuredUntil then
                local cost = math.max(1, math.min(rules.healStaminaCost,
                    math.ceil(remaining * rules.healStaminaCost
                        / rules.healSeconds)))
                injured[#injured + 1] = { slot = slot,
                    name = memberRow.name, rarity = memberRow.rarity,
                    memberId = memberRow.healId,
                    injuredUntil = memberRow.injuredUntil,
                    remaining = remaining, cost = cost }
            end
        end
    end
    table.sort(injured, function(a, b)
        return a.remaining > b.remaining
            or (a.remaining == b.remaining and a.slot < b.slot)
    end)
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        serverNow = native.serverNow, stamina = stamina,
        injured = injured }, nil
end

function CrewHeal.propose(view, settings)
    if type(view) ~= "table" or type(settings) ~= "table" then
        return nil, "Missing Crew heal input"
    end
    if settings.enabled ~= true then return nil, "Crew heal disabled" end
    local reserve = type(settings.custom) == "table"
        and settings.custom.staminaReserve or settings.staminaReserve
    if not integer(reserve, 0) then
        return nil, "Crew heal stamina reserve required"
    end
    if not same(view, view) or not integer(view.revision, 0)
        or type(view.injured) ~= "table"
        or type(view.stamina) ~= "number" then
        return nil, "Invalid Crew heal view"
    end
    for _, row in ipairs(view.injured) do
        if view.stamina - row.cost >= reserve then
            return { session = view.session, account = view.account,
                place = view.place, release = view.release,
                revision = view.revision, feature = "crewHeal",
                actionKey = "crewHeal:" .. row.slot .. ":"
                    .. row.memberId .. ":" .. row.injuredUntil,
                resources = { stamina = row.cost },
                intent = { kind = "crewHeal", remote = "CrewAction",
                    args = { "heal", row.slot,
                        { memberId = row.memberId,
                            injuredUntil = row.injuredUntil } },
                    slot = row.slot, memberId = row.memberId,
                    name = row.name, rarity = row.rarity,
                    injuredUntil = row.injuredUntil,
                    expectedCost = row.cost, staminaReserve = reserve } }, nil
        end
    end
    return nil, "No eligible Crew injury within stamina reserve"
end

function CrewHeal.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "crewHeal"
        or type(intent) ~= "table" or intent.kind ~= "crewHeal"
        or not integer(intent.slot, 2) or intent.slot > 32
        or not integer(intent.expectedCost, 1)
        or not integer(intent.staminaReserve, 0)
        or not same(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Crew heal baseline changed"
    end
    local row = member(before, intent.slot)
    if not row or row.name ~= intent.name
        or row.rarity ~= intent.rarity
        or row.healId ~= intent.memberId
        or row.injuredUntil ~= intent.injuredUntil
        or not integer(before.native.pools
            and before.native.pools.stamina,
            intent.expectedCost + intent.staminaReserve) then
        return nil, "Exact injured Crew member unavailable"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, slot = intent.slot,
        name = intent.name, rarity = intent.rarity,
        memberId = intent.memberId,
        injuredUntil = intent.injuredUntil }, nil
end

function CrewHeal.evaluate(proposal, before, after, reply, baseline)
    if type(proposal) ~= "table" or type(reply) ~= "table"
        or not same(proposal, before) or not same(proposal, after)
        or not same(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or before.revision ~= baseline.revision
        or not integer(after.revision, baseline.revision + 1) then
        return "pending"
    end
    local row = member(after, baseline.slot)
    if not row or row.name ~= baseline.name
        or row.rarity ~= baseline.rarity
        or row.healId ~= baseline.memberId then return "pending" end
    if reply.ok == false then return "rejected" end
    if reply.ok == true and (row.injuredUntil or 0)
        < baseline.injuredUntil then return "confirmed" end
    return "pending"
end

return CrewHeal
