-- Claim confirmation needs a newer exact row removal and attempt proof.
local FamilyBossClaimsEvidence = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
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
        or not integer(native.serverNow, 0)
        or type(proof) ~= "table"
        or proof.account ~= raw.account
        or proof.capturedAt ~= raw.capturedAt
        or type(state) ~= "table"
        or not integer(state.week, 1)
        or not integer(state.famId, 1)
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

function FamilyBossClaimsEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table"
        or proposal.feature ~= "familyBossClaims"
        or type(intent) ~= "table"
        or intent.kind ~= "familyBossClaim"
        or not integer(intent.week, 1)
        or not integer(intent.currentWeek, intent.week)
        or not integer(intent.famId, 1)
        or not integer(intent.stage, 0) or intent.stage > 100
        or not integer(intent.expiresAt, 0)
        or not integer(intent.attemptsBefore, 0)
        or type(before) ~= "table"
        or not matching(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Family claim baseline mismatch"
    end
    local native, state, usages = current(before)
    local usage = usages and usages[tostring(intent.week)]
    if not native or intent.currentWeek ~= state.week
        or state.week < intent.week
        or (intent.week == state.week
            and (state.famId ~= intent.famId
                or state.inFamily ~= true
                or intent.stage < 1 or intent.stage > 5))
        or native.serverNow >= intent.expiresAt
        or type(usage) ~= "table"
        or usage.account ~= before.account
        or usage.capturedAt ~= before.capturedAt
        or usage.week ~= intent.week
        or type(usage.stages) ~= "table"
        or claimPresent(state, intent.week, intent.stage,
            intent.expiresAt) ~= true
        or (intent.week == state.week
            and contains(state.claimedStages, intent.stage))
        or #usage.stages ~= intent.attemptsBefore
        or contains(usage.stages, intent.stage) then
        return nil, "Family stage claim or attempt changed"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, week = intent.week,
        currentWeek = state.week,
        famId = intent.famId, stage = intent.stage,
        expiresAt = intent.expiresAt }, nil
end

function FamilyBossClaimsEvidence.evaluate(proposal, beforeHeader,
    after, reply, baseline)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table"
        or type(after) ~= "table" or type(reply) ~= "table"
        or type(baseline) ~= "table"
        or not matching(proposal, beforeHeader)
        or not matching(proposal, after)
        or not matching(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision then
        return "pending"
    end
    local native, state, usages = current(after)
    if not native then return "pending" end
    local usage = usages[tostring(baseline.week)]
    if type(usage) ~= "table"
        or usage.account ~= after.account
        or usage.capturedAt ~= after.capturedAt
        or usage.week ~= baseline.week
        or type(usage.stages) ~= "table" then
        return "pending"
    end
    local advanced = type(after.revision) == "number"
        and after.revision > baseline.revision
        and state.week == baseline.currentWeek
        and (baseline.week ~= baseline.currentWeek
            or state.famId == baseline.famId)
        and native.serverNow < baseline.expiresAt
        and claimPresent(state, baseline.week,
            baseline.stage) == false
        and (baseline.week ~= baseline.currentWeek
            or contains(state.claimedStages, baseline.stage))
        and contains(usage.stages, baseline.stage)
    if reply.ok == false then
        return advanced and "pending" or "rejected"
    end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

return FamilyBossClaimsEvidence
