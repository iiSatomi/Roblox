-- Claim confirmation needs a newer exact row removal and attempt proof.
local FamilyBossClaimsEvidence = {}
local function familyId(value)
    return type(value) == "string" and #value > 0 and #value <= 120
        and not value:find("[%c]")
        or type(value) == "number" and value == value and value >= 1
            and value <= 9007199254740991 and value % 1 == 0
end

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

-- Wallet Cash can include native income fractions; reward counts stay integral.
local function cash(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

local function timestamp(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge
end

local function matching(a, b)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or a[field] ~= b[field] then return false end
    end
    return true
end

local function contains(list, target)
    if type(list) ~= "table" then return false end
    for _, value in ipairs(list) do
        if value == target then return true end
    end
    return false
end

local function current(raw)
    local native = type(raw) == "table" and raw.native
    local proof = type(raw) == "table" and raw.familyTakedownProof
    local usages = type(raw) == "table" and raw.familyClaimUsageProofs
    if type(usages) ~= "table" then
        usages = {}
        local legacy = type(raw) == "table"
            and raw.familyClaimUsageProof
        if type(legacy) == "table" then
            usages[tostring(legacy.week)] = legacy
        end
    end
    local state = type(proof) == "table" and proof.state
    if type(native) ~= "table" or native.fullSync ~= true
        or not timestamp(native.serverNow, 0)
        or type(proof) ~= "table"
        or proof.account ~= raw.account
        or proof.capturedAt ~= raw.capturedAt
        or type(state) ~= "table"
        or not integer(state.week, 1)
        or (not familyId(state.famId) and not (state.famId == nil
            and state.inFamily == false and native.family == nil))
        or type(state.inFamily) ~= "boolean"
        or type(state.claims) ~= "table"
        or type(usages) ~= "table" then
        return nil
    end
    return native, state, usages
end

local function claimPresent(state, week, stage, expiry)
    local found = false
    for _, row in ipairs(state.claims) do
        if type(row) ~= "table" then return nil end
        if row.week == week and row.stage == stage then
            if found then return nil end
            if expiry ~= nil and row.expiresAt ~= expiry then
                return nil
            end
            found = true
        end
    end
    return found
end

local function capture(proposal, before, dispatch)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table"
        or proposal.feature ~= "familyBossClaims"
        or type(intent) ~= "table"
        or intent.kind ~= "familyBossClaim"
        or not integer(intent.week, 1)
        or not integer(intent.currentWeek, intent.week)
        or (intent.famId ~= nil and not familyId(intent.famId))
        or not integer(intent.stage, 0) or intent.stage > 100
        or not timestamp(intent.expiresAt, 0)
        or not integer(intent.attemptsBefore, 0)
        or type(before) ~= "table"
        or not matching(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Family claim baseline mismatch"
    end
    local native, state, usages = current(before)
    local usage = usages and usages[tostring(intent.week)]
    if not native or intent.currentWeek ~= state.week
        or state.week < intent.week or state.famId ~= intent.famId
        or (intent.week == state.week
            and (state.inFamily ~= true
                or intent.stage < 1 or intent.stage > 5))
        or native.serverNow >= intent.expiresAt
        or (not dispatch and (type(usage) ~= "table"
            or usage.account ~= before.account or usage.capturedAt ~= before.capturedAt
            or usage.week ~= intent.week or type(usage.stages) ~= "table"))
        or claimPresent(state, intent.week, intent.stage,
            intent.expiresAt) ~= true
        or (intent.week == state.week
            and contains(state.claimedStages, intent.stage))
        or (not dispatch and (#usage.stages ~= intent.attemptsBefore or contains(usage.stages, intent.stage))) then
        return nil, "Family stage claim or attempt changed"
    end
    local selected
    for _, row in ipairs(state.claims) do
        if row.week == intent.week and row.stage == intent.stage then selected = row; break end
    end
    if not selected then return nil, "Exact Family reward row unavailable" end
    for _, pair in ipairs({{"cash","rewardCash"},{"gold","rewardGold"},{"crates","rewardCrates"}}) do
        if not integer(intent[pair[2]], 0) or (selected[pair[1]] or 0) ~= intent[pair[2]] then
            return nil, "Family reward quote changed"
        end
    end
    for _, pair in ipairs({{"crateId","rewardCrateId"},{"medal","rewardMedal"},{"border","rewardBorder"}}) do
        if selected[pair[1]] ~= intent[pair[2]] then return nil, "Family reward identity changed" end
    end
    local awards = {cash = intent.rewardCash, items = {}, serverNow = native.serverNow,
        sourceKey = before.familyTakedownProof.sourceKey}
    local function add(id, amount, boundOnly)
        if amount == 0 then return true end
        if type(id) ~= "string" or #id == 0 or #id > 120 or awards.items[id] then return false end
        local loose = type(native.inventory) == "table" and (native.inventory[id] or 0)
        local bound = type(native.inventoryBound) == "table" and (native.inventoryBound[id] or 0)
        if not integer(loose, 0) or not integer(bound, 0) then return false end
        awards.items[id] = {amount = amount, loose = loose, bound = bound, boundOnly = boundOnly == true}
        return true
    end
    if not cash(native.cash) or not add("gold_bar", intent.rewardGold, true)
        or not add(intent.rewardCrateId, intent.rewardCrates)
        or not add(intent.rewardMedal, intent.rewardMedal and 1 or 0)
        or not add(intent.rewardBorder, intent.rewardBorder and 1 or 0)
        or (awards.cash == 0 and next(awards.items) == nil) then
        return nil, "Known Family reward amounts and current custody required"
    end
    awards.cashBefore = native.cash
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, week = intent.week,
        currentWeek = state.week,
        famId = intent.famId, stage = intent.stage,
        expiresAt = intent.expiresAt, awards = awards }, nil
end

function FamilyBossClaimsEvidence.capture(proposal, before)
    return capture(proposal, before, false)
end

function FamilyBossClaimsEvidence.canDispatch(proposal, raw)
    return capture(proposal, raw, true) ~= nil
end

local function awarded(native, awards, unchanged)
    if not cash(native.cash) or native.cash ~= awards.cashBefore + (unchanged and 0 or awards.cash) then return false end
    for id, row in pairs(awards.items) do
        local loose = type(native.inventory) == "table" and (native.inventory[id] or 0)
        local bound = type(native.inventoryBound) == "table" and (native.inventoryBound[id] or 0)
        if not integer(loose, 0) or not integer(bound, 0) then return false end
        local dl, db = loose - row.loose, bound - row.bound
        if unchanged then
            if dl ~= 0 or db ~= 0 then return false end
        elseif not (dl == 0 and db == row.amount or not row.boundOnly and dl == row.amount and db == 0) then
            return false
        end
    end
    return true
end

local function reconcile(proposal, beforeHeader, after, reply, baseline, restart)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table" or type(after) ~= "table"
        or type(reply) ~= "table" or type(baseline) ~= "table" or type(baseline.awards) ~= "table"
        or not matching(proposal, beforeHeader) or not matching(proposal, baseline)
        or proposal.account ~= after.account or proposal.place ~= after.place or proposal.release ~= after.release
        or (not restart and not matching(proposal, after))
        or proposal.revision ~= baseline.revision or beforeHeader.revision ~= baseline.revision
        or not integer(after.revision, 0)
        or not (after.session == baseline.session and after.revision > baseline.revision
            or restart and after.session ~= baseline.session and type(after.native) == "table"
                and timestamp(after.native.serverNow, baseline.awards.serverNow)
                and after.native.serverNow > baseline.awards.serverNow)
        or reply.pending == true or reply.code == "rate_limited" or reply.code == "presence" then return "pending" end
    local native, state, usages = current(after)
    if not native or native.serverNow < baseline.awards.serverNow or native.serverNow >= baseline.expiresAt
        or state.week ~= baseline.currentWeek or state.famId ~= baseline.famId
        or after.familyTakedownProof.sourceKey ~= baseline.awards.sourceKey then return "pending" end
    local usage = usages[tostring(baseline.week)]
    if type(usage) ~= "table" or usage.account ~= after.account or usage.capturedAt ~= after.capturedAt
        or usage.week ~= baseline.week or type(usage.stages) ~= "table"
        or not contains(usage.stages, baseline.stage) then return "pending" end
    local present = claimPresent(state, baseline.week, baseline.stage, baseline.expiresAt)
    local claimed = baseline.week == baseline.currentWeek and contains(state.claimedStages, baseline.stage)
    if reply.ok == false then
        return present == true and not claimed and awarded(native, baseline.awards, true) and "rejected" or "pending"
    end
    return reply.ok == true and present == false and (baseline.week ~= baseline.currentWeek or claimed)
        and awarded(native, baseline.awards, false) and "confirmed" or "pending"
end

function FamilyBossClaimsEvidence.evaluate(proposal, before, after, reply, baseline)
    return reconcile(proposal, before, after, reply, baseline, false)
end
local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for k, v in pairs(a) do if not equal(v, b[k]) then return false end end
    for k in pairs(b) do if a[k] == nil then return false end end
    return true
end
function FamilyBossClaimsEvidence.recoverSaved(data, after)
    if type(data) ~= "table" or type(data.reply) ~= "table" then return nil end
    local baseline = capture(data.proposal, data.before, false)
    if not baseline or not equal(baseline, data.baseline) then return nil end
    local result = reconcile(data.proposal, data.before, after, data.reply, baseline, true)
    return (result == "confirmed" or result == "rejected") and result or nil
end
return FamilyBossClaimsEvidence
