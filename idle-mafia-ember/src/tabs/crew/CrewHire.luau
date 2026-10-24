-- Empty-slot-only CrewAction("hire", tier, quotedCost, nil).
local CrewHire = {}

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

local function roster(raw)
    local native = type(raw) == "table" and raw.native
    local crew = type(native) == "table" and native.crew
    if type(native) ~= "table" or native.fullSync ~= true
        or type(crew) ~= "table" or #crew < 2
        or #crew > 46 then return nil end
    local empty, seen, count = nil, {}, 0
    for slot, member in pairs(crew) do
        if not integer(slot, 1) or slot > #crew
            or type(member) ~= "table" then return nil end
        count = count + 1
        if slot > 1 then
            if member.rolling == true then return nil end
            if member.rarity == nil then
                if member.duty ~= nil or member.stationed == true
                    or member.name ~= nil then return nil end
                empty = empty or slot
            else
                if not integer(member.rarity, 1)
                    or type(member.name) ~= "string"
                    or #member.name == 0 or #member.name > 64 then
                    return nil
                end
                local key = #member.name .. ":" .. member.name
                    .. ":" .. member.rarity
                if seen[key] then return nil end
                seen[key] = true
            end
        end
    end
    if count ~= #crew or type(crew[1]) ~= "table" then return nil end
    return empty, count
end

local function quote(raw, catalog, tier)
    local proof = raw.economyProof
    local native = raw.native
    if type(proof) ~= "table" or type(native) ~= "table"
        or proof.account ~= raw.account
        or proof.capturedAt ~= raw.capturedAt
        or proof.city ~= native.cityId
        or not integer(proof.revision, 0)
        or type(proof.familyId) ~= "string"
        or type(proof.rulerId) ~= "string"
        or not integer(proof.hirePct, -25)
        or proof.hirePct > 25
        or type(catalog) ~= "table"
        or catalog.release ~= raw.release
        or type(catalog.catalogKey) ~= "string"
        or type(catalog.tiers) ~= "table"
        or not integer(catalog.tiers[tier], 1) then return nil end
    local exempt = #proof.familyId > 0
        and proof.familyId == proof.rulerId
    local pct = exempt and math.min(proof.hirePct, 0)
        or proof.hirePct
    return math.max(1, math.floor(catalog.tiers[tier]
        * (100 + pct) / 100 + 0.5)), proof.revision, pct
end

function CrewHire.read(raw, context)
    if not same(raw, context) or raw.revision ~= context.revision
        or raw.capturedAt ~= context.capturedAt
        or not integer(raw.revision, 0)
        or type(raw.hireCatalog) ~= "table"
        or raw.hireCatalog.catalogKey ~= context.hireCatalogKey
        or not integer(raw.native and raw.native.cash, 0) then
        return nil, "Current Crew hire snapshot and catalog required"
    end
    local slot, count = roster(raw)
    if not count then return nil, "Valid stable Crew roster required" end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        cash = raw.native.cash, emptySlot = slot,
        count = count, catalog = raw.hireCatalog,
        proof = raw.economyProof, cityId = raw.native.cityId }, nil
end

function CrewHire.propose(view, settings)
    if type(view) ~= "table" or type(settings) ~= "table"
        or not same(view, view) then return nil, "Missing Crew hire input" end
    if settings.enabled ~= true then return nil, "Crew hire disabled" end
    local tier = settings.policy
    local custom = type(settings.custom) == "table"
        and settings.custom or settings
    if type(tier) ~= "string" or not integer(custom.maxCost, 1)
        or not integer(custom.cashReserve, 0)
        or not integer(view.emptySlot, 2) then
        return nil, "Selected tier, limits and empty slot required"
    end
    local cost, revision, pct = quote({ account = view.account,
        release = view.release, capturedAt = view.capturedAt,
        native = { cityId = view.cityId },
        economyProof = view.proof }, view.catalog, tier)
    if not cost or cost > custom.maxCost
        or view.cash - cost < custom.cashReserve then
        return nil, "Current Crew hire quote exceeds cash limits"
    end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "crewHire",
        actionKey = "crewHire:" .. view.catalog.catalogKey .. ":"
            .. tier .. ":" .. view.emptySlot .. ":" .. revision
            .. ":" .. pct,
        resources = { cash = cost },
        intent = { kind = "crewHire", remote = "CrewAction",
            args = { "hire", tier, cost }, argCount = 4,
            tier = tier, slot = view.emptySlot,
            cost = cost, reserve = custom.cashReserve,
            catalogKey = view.catalog.catalogKey,
            decreeRevision = revision, hirePct = pct } }, nil
end

function CrewHire.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "crewHire"
        or type(intent) ~= "table" or intent.kind ~= "crewHire"
        or intent.remote ~= "CrewAction" or intent.argCount ~= 4
        or not integer(intent.slot, 2)
        or not integer(intent.cost, 1)
        or not integer(intent.reserve, 0)
        or type(intent.args) ~= "table"
        or intent.args[1] ~= "hire"
        or intent.args[2] ~= intent.tier
        or intent.args[3] ~= intent.cost
        or intent.args[4] ~= nil
        or not same(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Crew hire baseline changed"
    end
    local slot = roster(before)
    local cost, revision, pct = quote(before,
        before.hireCatalog, intent.tier)
    if slot ~= intent.slot or cost ~= intent.cost
        or revision ~= intent.decreeRevision
        or pct ~= intent.hirePct
        or before.hireCatalog.catalogKey ~= intent.catalogKey
        or not integer(before.native.cash,
            intent.cost + intent.reserve) then
        return nil, "Exact empty slot and hire quote unavailable"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, slot = slot,
        cost = cost, count = #before.native.crew }, nil
end

function CrewHire.evaluate(proposal, before, after, reply, baseline)
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
    local returned = reply.member
    if reply.ok ~= true or reply.index ~= baseline.slot
        or type(native) ~= "table" or native.fullSync ~= true
        or type(crew) ~= "table" or #crew ~= baseline.count
        or type(returned) ~= "table" or type(member) ~= "table"
        or type(returned.name) ~= "string"
        or not integer(returned.rarity, 1)
        or not integer(returned.atk, 0)
        or not integer(returned.def, 0)
        or member.name ~= returned.name
        or member.rarity ~= returned.rarity
        or member.atk ~= returned.atk
        or member.def ~= returned.def then return "pending" end
    return "confirmed"
end

return CrewHire
