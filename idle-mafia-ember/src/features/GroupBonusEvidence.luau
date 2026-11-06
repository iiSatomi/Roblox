-- A successful reply must be followed by the exact claimed flag in full Sync.
local GroupBonusEvidence = {}

local function matching(a, b)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or a[field] ~= b[field] then return false end
    end
    return true
end

local function claimState(raw, groupId)
    if type(raw) ~= "table" or type(raw.native) ~= "table"
        or raw.native.fullSync ~= true
        or type(raw.native.groupBonus) ~= "boolean"
        or type(raw.groupConfig) ~= "table"
        or raw.groupConfig.id ~= groupId then return nil end
    return raw.native.groupBonus
end

function GroupBonusEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "groupBonus"
        or type(intent) ~= "table" or intent.kind ~= "groupBonusClaim"
        or type(intent.groupId) ~= "number"
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision
        or claimState(before, intent.groupId) ~= false then
        return nil, "Group bonus baseline mismatch"
    end
    local proof = before.groupMembership
    if type(proof) ~= "table" or proof.groupId ~= intent.groupId
        or proof.session ~= proposal.session
        or proof.account ~= proposal.account
        or proof.place ~= proposal.place
        or proof.release ~= proposal.release
        or proof.isMember ~= true
        or type(proof.checkedAt) ~= "number"
        or proof.checkedAt ~= proof.checkedAt
        or proof.checkedAt < 0
        or proof.checkedAt >= math.huge
        or proof.checkedAt > before.capturedAt
        or before.capturedAt - proof.checkedAt > 30 then
        return nil, "Group membership changed before claim"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, groupId = intent.groupId }, nil
end

function GroupBonusEvidence.evaluate(proposal, beforeHeader, after, reply, baseline)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table"
        or type(after) ~= "table" or type(reply) ~= "table"
        or type(baseline) ~= "table"
        or not matching(proposal, beforeHeader)
        or not matching(proposal, after)
        or not matching(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision
        or type(proposal.intent) ~= "table"
        or proposal.intent.groupId ~= baseline.groupId
        or type(after.revision) ~= "number" or after.revision ~= after.revision
        or after.revision >= math.huge or after.revision % 1 ~= 0
        or after.revision <= baseline.revision
        or reply.pending == true or reply.code == "pending" or reply.code == "no_pending"
        or reply.code == "rate_limited" or reply.code == "busy" or reply.code == "presence" then return "pending" end
    local claimed = claimState(after, baseline.groupId)
    if claimed == nil then return "pending" end
    local advanced = claimed == true and type(after.revision) == "number"
        and after.revision > baseline.revision
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

function GroupBonusEvidence.new(source)
    assert(type(source) == "table" and type(source.GroupEffect) == "function",
        "Current Group effect source required")
    local readEffect = source.GroupEffect
    local function effectAt(raw)
        if source.GroupEffect ~= readEffect then return nil, "Group effect source changed" end
        return readEffect(source, raw)
    end
    local function equal(a, b, depth)
        if type(a) ~= type(b) or (depth or 0) > 16 then return false end
        if type(a) ~= "table" then return a == b end
        if getmetatable(a) ~= nil or getmetatable(b) ~= nil then return false end
        local count = 0
        for key, value in pairs(a) do
            count = count + 1
            if count > 512 or not equal(value, b[key], (depth or 0) + 1) then return false end
        end
        for key in pairs(b) do if a[key] == nil then return false end end
        return true
    end
    local function clock(value) return type(value) == "number" and value == value and value >= 0 and value < math.huge end
    local result
    result = {
        capture = function(proposal, before)
            local baseline, reason = GroupBonusEvidence.capture(proposal, before)
            if not baseline then return nil, reason end
            local effect, effectReason = effectAt(before)
            if not effect or effect.groupId ~= baseline.groupId or effect.active ~= false then
                return nil, effectReason or "Group income baseline changed"
            end
            baseline.effect = effect
            return baseline, nil
        end,
        evaluate = function(proposal, before, after, reply, baseline)
            local outcome = GroupBonusEvidence.evaluate(proposal, before, after, reply, baseline)
            if outcome == "pending" then return outcome end
            local effect = effectAt(after)
            local prior = type(baseline) == "table" and baseline.effect
            if not effect or type(prior) ~= "table" or prior.kind ~= "propertyIncome"
                or prior.active ~= false or prior.multiplier ~= 1
                or effect.sourceKey ~= prior.sourceKey or effect.release ~= prior.release
                or effect.incomeBonus ~= prior.incomeBonus or effect.groupId ~= prior.groupId then return "pending" end
            if outcome == "confirmed" and (effect.active ~= true
                or effect.multiplier ~= 1 + prior.incomeBonus) then return "pending" end
            return outcome
        end,
    }
    function result.recoverSaved(data, after)
        local reply = type(data) == "table" and data.reply
        if type(reply) ~= "table" or type(reply.ok) ~= "boolean" or reply.pending == true
            or reply.code == "pending" or reply.code == "no_pending" or reply.code == "rate_limited"
            or reply.code == "busy" or reply.code == "presence" or type(after) ~= "table" then return nil end
        local p, before = data.proposal, data.before
        local baseline = result.capture(p, before)
        if not baseline or not equal(baseline, data.baseline) or not matching(p, before)
            or type(after.session) ~= "string" or #after.session == 0
            or type(after.native) ~= "table" or not clock(before.native.serverNow)
            or not clock(after.native.serverNow) or after.native.serverNow <= before.native.serverNow
            or not clock(after.revision) or after.revision % 1 ~= 0
            or after.session == baseline.session and (after.revision <= baseline.revision
                or not clock(after.capturedAt) or after.capturedAt < before.capturedAt)
            or type(p.resources) ~= "table" or p.actionKey ~= "groupBonus:" .. baseline.groupId then return nil end
        for _, field in ipairs({"account", "place", "release"}) do if after[field] ~= p[field] then return nil end end
        for _, amount in pairs(p.resources) do if amount ~= 0 then return nil end end
        if claimState(after, baseline.groupId) ~= reply.ok then return nil end
        local prior, effect = baseline.effect, effectAt(after)
        if type(prior) ~= "table" or prior.kind ~= "propertyIncome" or prior.active ~= false
            or prior.multiplier ~= 1 or type(prior.incomeBonus) ~= "number" then return nil end
        local expected = {}; for key, value in pairs(prior) do expected[key] = value end
        if reply.ok then expected.active, expected.multiplier = true, 1 + prior.incomeBonus end
        if not equal(expected, effect) then return nil end
        return reply.ok and "confirmed" or "rejected"
    end
    return result
end

return GroupBonusEvidence
