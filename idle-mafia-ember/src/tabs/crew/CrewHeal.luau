-- Saved guarded CrewAction("heal", slot, payload), exact quote and injury proof.
local CrewHeal = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function timestamp(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
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
        or not timestamp(row.injuredUntil or 0)
        or not timestamp(row.recalledUntil or 0) then return nil end
    return row
end

local function uniqueMember(raw, id)
    local crew = raw.native.crew
    if type(crew) ~= "table" or #crew < 2 or #crew > 46 then return false end
    local rows, matches = 0, 0
    for slot, row in pairs(crew) do
        if not integer(slot, 1) or slot > #crew or type(row) ~= "table" then return false end
        rows = rows + 1
        if row.healId == id then matches = matches + 1 end
    end
    return rows == #crew and matches == 1
end

function CrewHeal.read(raw, context)
    if not same(raw, context) or raw.revision ~= context.revision
        or raw.capturedAt ~= context.capturedAt then
        return nil, "Crew heal snapshot changed"
    end
    local native, rules = raw.native, raw.healRules
    local crew = type(native) == "table" and native.crew
    local stamina = type(native) == "table"
        and type(native.pools) == "table" and native.pools.stamina
    if type(native) ~= "table" or native.fullSync ~= true
        or type(crew) ~= "table" or not timestamp(native.serverNow)
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
        if not integer(slot, 1) or slot > 46
            or type(row) ~= "table" then
            return nil, "Invalid Crew roster"
        end
        if slot > 1 then
            if type(row.name) ~= "string" or #row.name == 0
                or #row.name > 64 or not integer(row.rarity, 0) then
                return nil, "Invalid Crew identity"
            end
            if row.healId ~= nil then
                if type(row.healId) ~= "string" or #row.healId == 0 or #row.healId > 128
                    or identities[row.healId] then return nil, "Duplicate or invalid Crew heal identity" end
                identities[row.healId] = true
            end
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
        injured = injured, healSeconds = rules.healSeconds }, nil
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
                intent = { kind = "crewHeal",
                    slot = row.slot, memberId = row.memberId,
                    name = row.name, rarity = row.rarity,
                    injuredUntil = row.injuredUntil,
                    expectedCost = row.cost, healSeconds = view.healSeconds,
                    staminaReserve = reserve } }, nil
        end
    end
    return nil, "No eligible Crew injury within stamina reserve"
end

function CrewHeal.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "crewHeal"
        or type(intent) ~= "table" or intent.kind ~= "crewHeal"
        or not integer(intent.slot, 2) or intent.slot > 46
        or not integer(intent.expectedCost, 1)
        or not integer(intent.staminaReserve, 0)
        or not same(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Crew heal baseline changed"
    end
    local view = CrewHeal.read(before, { session = before.session, account = before.account,
        place = before.place, release = before.release, revision = before.revision,
        capturedAt = before.capturedAt, serverNow = before.native and before.native.serverNow })
    local current = view and CrewHeal.propose(view, { enabled = true,
        staminaReserve = intent.staminaReserve })
    if not current or current.actionKey ~= proposal.actionKey
        or not equal(current.intent, intent) or not equal(current.resources, proposal.resources) then
        return nil, "Crew heal quote, custody or intent changed"
    end
    local row = member(before, intent.slot)
    if not row or row.name ~= intent.name
        or row.rarity ~= intent.rarity
        or row.healId ~= intent.memberId
        or row.injuredUntil ~= intent.injuredUntil
        or not timestamp(before.native.pools and before.native.pools.stamina)
        or before.native.pools.stamina < intent.expectedCost + intent.staminaReserve then
        return nil, "Exact injured Crew member unavailable"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, slot = intent.slot,
        name = intent.name, rarity = intent.rarity,
        memberId = intent.memberId,
        injuredUntil = intent.injuredUntil, stamina = before.native.pools.stamina,
        expectedCost = intent.expectedCost, serverNow = view.serverNow,
        reduction = math.min(row.injuredUntil - view.serverNow, view.healSeconds),
        intent = current.intent, actionKey = current.actionKey }, nil
end

local function reconcile(proposal,before,after,reply,baseline,restart)
    if type(proposal) ~= "table" or type(reply) ~= "table"
        or not same(proposal,before) or type(after)~="table"
        or (not restart and not same(proposal,after))
        or proposal.account~=after.account or proposal.place~=after.place or proposal.release~=after.release
        or not same(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or before.revision ~= baseline.revision
        or proposal.actionKey ~= baseline.actionKey
        or not equal(proposal.intent, baseline.intent)
        or not equal(proposal.resources, {stamina = baseline.expectedCost})
        or not integer(after.revision,0)
        or not (after.session==baseline.session and after.revision>baseline.revision
            or restart and after.session~=baseline.session and type(after.native)=="table"
                and timestamp(after.native.serverNow) and after.native.serverNow>baseline.serverNow)
        or reply.pending==true or reply.code=="pending" or reply.code=="busy"
        or reply.code=="rate_limited" or reply.code=="presence" then
        return "pending"
    end
    local row = member(after, baseline.slot)
    if not row or row.name ~= baseline.name
        or row.rarity ~= baseline.rarity
        or row.healId ~= baseline.memberId then return "pending" end
    local stamina = after.native.pools and after.native.pools.stamina
    if not timestamp(stamina) or not timestamp(after.native.serverNow)
        or after.native.serverNow < baseline.serverNow then return "pending" end
    if reply.ok == false then
        return row.injuredUntil == baseline.injuredUntil and stamina == baseline.stamina
            and "rejected" or "pending"
    end
    local expected = baseline.injuredUntil - baseline.reduction
    local full = baseline.reduction >= baseline.injuredUntil - baseline.serverNow
    local healed = full and (row.injuredUntil or 0)<baseline.injuredUntil
        and (row.injuredUntil or 0) <= after.native.serverNow
        or (not full and row.injuredUntil == expected)
    if reply.ok == true and healed then
        if stamina == baseline.stamina - baseline.expectedCost then return "confirmed" end
        -- Exact owned injury reduction proves the heal independently of passive
        -- Stamina. Preserve the quote; no regeneration amount is inferred.
        if after.native.serverNow > baseline.serverNow
            and after.native.serverNow < baseline.injuredUntil
            and stamina >= baseline.stamina - baseline.expectedCost
            and row.duty == nil and row.training == nil
            and (row.rolling == nil or row.rolling == false)
            and uniqueMember(after, baseline.memberId) then return "confirmed" end
    end
    return "pending"
end

function CrewHeal.evaluate(proposal,before,after,reply,baseline)
    return reconcile(proposal,before,after,reply,baseline,false)
end
function CrewHeal.recoverSaved(data,after)
    if type(data)~="table" or type(data.reply)~="table" then return nil end
    local baseline=CrewHeal.capture(data.proposal,data.before)
    if not baseline or not equal(baseline,data.baseline) then return nil end
    local outcome=reconcile(data.proposal,data.before,after,data.reply,baseline,true)
    return (outcome=="confirmed" or outcome=="rejected") and outcome or nil
end
return CrewHeal
