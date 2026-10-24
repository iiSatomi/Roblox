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
        or proposal.intent.groupId ~= baseline.groupId then return "pending" end
    local claimed = claimState(after, baseline.groupId)
    if claimed == nil then return "pending" end
    local advanced = claimed == true and type(after.revision) == "number"
        and after.revision > baseline.revision
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

return GroupBonusEvidence
