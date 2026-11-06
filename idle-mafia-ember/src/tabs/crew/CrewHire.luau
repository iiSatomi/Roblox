-- Empty-slot-only CrewAction("hire", tier, quotedCost, nil).
local CrewHire = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function balance(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum
end

local function same(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or a[field] ~= b[field] then return false end
    end
    return true
end

local function equal(a,b)
    if type(a)~=type(b) then return false end
    if type(a)~="table" then return a==b end
    for k,v in pairs(a) do if not equal(v,b[k]) then return false end end
    for k in pairs(b) do if a[k]==nil then return false end end
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
        or not balance(raw.native and raw.native.cash, 0) then
        return nil, "Current Crew hire snapshot and catalog required"
    end
    local proof=raw.crewHireUsageProof
    if not same(raw,proof) or proof.revision~=raw.revision or proof.capturedAt~=raw.capturedAt
        or not integer(proof.attempted,0) or proof.attempted>1000 or not integer(proof.spent,0) then
        return nil,"Owned current hire allowance required"
    end
    local slot, count = roster(raw)
    if not count then return nil, "Valid stable Crew roster required" end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        usage={attempted=proof.attempted,spent=proof.spent},cash = raw.native.cash, emptySlot = slot,
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
        or not integer(custom.maxAttempts,1) or custom.maxAttempts>1000 or not integer(custom.maxSpend,1)
        or type(view.usage)~="table" or view.usage.attempted>=custom.maxAttempts
        or not integer(view.emptySlot, 2) then
        return nil, "Selected tier, limits and empty slot required"
    end
    local cost, revision, pct = quote({ account = view.account,
        release = view.release, capturedAt = view.capturedAt,
        native = { cityId = view.cityId },
        economyProof = view.proof }, view.catalog, tier)
    if not cost or cost > custom.maxCost or view.usage.spent+cost>custom.maxSpend
        or view.cash - cost < custom.cashReserve then
        return nil, "Current Crew hire quote exceeds cash limits"
    end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "crewHire",
        actionKey = "crewHire:" .. view.catalog.catalogKey .. ":"
            .. tier .. ":" .. view.emptySlot .. ":" .. revision
            .. ":" .. pct .. ":" .. view.usage.attempted,
        resources = { cash = cost },
        intent = { kind = "crewHire",
            tier = tier, slot = view.emptySlot,
            cost = cost, maxCost = custom.maxCost, reserve = custom.cashReserve,
            attemptedBefore=view.usage.attempted,spentBefore=view.usage.spent,maxAttempts=custom.maxAttempts,maxSpend=custom.maxSpend,
            catalogKey = view.catalog.catalogKey,
            decreeRevision = revision, hirePct = pct } }, nil
end

function CrewHire.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "crewHire"
        or type(intent) ~= "table" or intent.kind ~= "crewHire"
        or not integer(intent.slot, 2)
        or not integer(intent.cost, 1)
        or not integer(intent.reserve, 0)
        or not same(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Crew hire baseline changed"
    end
    local view = CrewHire.read(before, { session = before.session, account = before.account,
        place = before.place, release = before.release, revision = before.revision,
        capturedAt = before.capturedAt, hireCatalogKey = intent.catalogKey })
    local planned = view and CrewHire.propose(view, { enabled = true, policy = intent.tier,
        maxCost = intent.maxCost, cashReserve = intent.reserve,maxAttempts=intent.maxAttempts,maxSpend=intent.maxSpend })
    if not planned or not equal(planned.intent, intent) or not equal(planned.resources, proposal.resources)
        or planned.actionKey ~= proposal.actionKey then return nil, "Crew hire limits or exposure changed" end
    local slot = roster(before)
    local cost, revision, pct = quote(before,
        before.hireCatalog, intent.tier)
    if slot ~= intent.slot or cost ~= intent.cost
        or revision ~= intent.decreeRevision
        or pct ~= intent.hirePct
        or before.hireCatalog.catalogKey ~= intent.catalogKey
        or not balance(before.native.cash,
            intent.cost + intent.reserve) then
        return nil, "Exact empty slot and hire quote unavailable"
    end
    local identities={}
    for index,row in pairs(before.native.crew) do
        if index~=slot then identities[index]={name=row.name,rarity=row.rarity,memberId=row.healId} end
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        serverNow=before.native.serverNow,identities=identities,
        revision = proposal.revision, slot = slot,
        cost = cost, cash = before.native.cash, count = #before.native.crew,
        intent = planned.intent, actionKey = planned.actionKey }, nil
end

local function reconcile(proposal,before,after,reply,baseline,restart)
    if type(proposal) ~= "table" or type(reply) ~= "table"
        or not same(proposal,before) or type(after)~="table"
        or (not restart and not same(proposal,after))
        or proposal.account~=after.account or proposal.place~=after.place or proposal.release~=after.release
        or not same(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or before.revision ~= baseline.revision
        or proposal.actionKey ~= baseline.actionKey or not equal(proposal.intent, baseline.intent)
        or not equal(proposal.resources, {cash = baseline.cost})
        or not integer(after.revision,0)
        or not (after.session==baseline.session and after.revision>baseline.revision
            or restart and after.session~=baseline.session and type(after.native)=="table"
                and balance(baseline.serverNow,0) and balance(after.native.serverNow,0) and after.native.serverNow>baseline.serverNow)
        or reply.pending==true or reply.code=="pending" or reply.code=="busy"
        or reply.code=="rate_limited" or reply.code=="presence" then
        return "pending"
    end
    local native = after.native
    local crew = type(native) == "table" and native.crew
    local member = type(crew) == "table" and crew[baseline.slot]
    local returned = reply.member
    if type(crew)~="table" or #crew~=baseline.count then return "pending" end
    for index,original in pairs(baseline.identities or {}) do
        local row=crew[index]
        if type(row)~="table" or row.name~=original.name or row.rarity~=original.rarity or row.healId~=original.memberId then return "pending" end
    end
    if reply.ok == false then
        return type(native) == "table" and native.fullSync == true and native.cash == baseline.cash
            and type(member) == "table" and member.rarity == nil and member.rolling ~= true
            and "rejected" or "pending"
    end
    if reply.ok ~= true or reply.pending == true or reply.code == "rate_limited"
        or (reply.index ~= nil and reply.index ~= baseline.slot)
        or type(native) ~= "table" or native.fullSync ~= true
        or not balance(native.cash, 0)
        or type(crew) ~= "table" or #crew ~= baseline.count
        or type(returned) ~= "table" or type(member) ~= "table"
        or type(returned.name) ~= "string"
        or not integer(returned.rarity, 1)
        or not integer(returned.atk, 0)
        or not integer(returned.def, 0)
        or returned.healId~=nil and member.healId~=returned.healId
        or member.name ~= returned.name
        or member.rarity ~= returned.rarity
        or member.atk ~= returned.atk
        or member.def ~= returned.def then return "pending" end
    if native.cash == baseline.cash - baseline.cost then return "confirmed" end
    -- Passive income can change Cash before Sync. Independently prove the exact
    -- newly owned member; never infer a debit from an estimated income rate.
    if not balance(baseline.serverNow,0) or not balance(native.serverNow,0)
        or native.serverNow<=baseline.serverNow
        or type(returned.healId)~="string" or #returned.healId==0 or #returned.healId>128 then return "pending" end
    for _,original in pairs(baseline.identities or {}) do
        if original.memberId==returned.healId then return "pending" end
    end
    return "confirmed"
end

function CrewHire.evaluate(proposal,before,after,reply,baseline)
    return reconcile(proposal,before,after,reply,baseline,false)
end
function CrewHire.recoverSaved(data,after)
    if type(data)~="table" or type(data.reply)~="table" then return nil end
    local baseline=CrewHire.capture(data.proposal,data.before)
    if not baseline or not equal(baseline,data.baseline) then return nil end
    local outcome=reconcile(data.proposal,data.before,after,data.reply,baseline,true)
    return (outcome=="confirmed" or outcome=="rejected") and outcome or nil
end
return CrewHire
