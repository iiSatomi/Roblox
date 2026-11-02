-- Exact owned Scout result plus replicated resource evidence; no replay or spending inference.
local Evidence = {}
local MAX = 9007199254740991
local scope = {"session", "account", "place", "release"}
local function number(v, low) return type(v) == "number" and v == v and v >= low and v <= MAX end
local function integer(v, low, high) return number(v, low) and v % 1 == 0 and v <= (high or MAX) end
local function text(v, high) return type(v) == "string" and #v > 0 and #v <= high and not v:find("[%c]") end
local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for k, v in pairs(a) do if not equal(v, b[k]) then return false end end
    for k in pairs(b) do if a[k] == nil then return false end end
    return true
end
local function same(a, b, fresh)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, k in ipairs(scope) do if (not fresh or k ~= "session") and a[k] ~= b[k] then return false end end
    return true
end
local function header(raw, p, fresh)
    return same(raw, p, fresh) and integer(raw.revision, 0) and number(raw.capturedAt, 0)
        and type(raw.native) == "table" and raw.native.fullSync == true and number(raw.native.serverNow, 0)
end
function Evidence.capture(p, before)
    local i = type(p) == "table" and p.intent
    if type(i) ~= "table" or (p.feature ~= "combat" and p.feature ~= "warCombat") or i.kind ~= "playerScout"
        or i.allowScout ~= true or not header(before, p) or p.revision ~= before.revision
        or i.serverNow ~= before.native.serverNow or not integer(i.target, 1) or not text(i.targetName, 64)
        or not integer(i.targetLevel, 1) or not integer(i.expectedStaminaCost, 1, 5)
        or not integer(i.maxStaminaExposure, i.expectedStaminaCost, 5) or type(p.resources) ~= "table"
        or p.resources.stamina ~= i.maxStaminaExposure or not text(i.sourceKey, 64)
        or #i.sourceKey ~= 64 or not i.sourceKey:match("^[%x]+$") then return nil, "Exact opted-in Scout baseline required" end
    if i.highValueOnly ~= nil and type(i.highValueOnly) ~= "boolean" then return nil, "Invalid high-only option" end
    if i.highValueOnly == true then
        local ledger = before.playerFightHistoryProof
        local high = type(ledger) == "table" and ledger.highValue
        local target = type(high) == "table" and type(high.targets) == "table" and high.targets[tostring(i.target)]
        if p.feature ~= "combat" or not same(ledger, p) or ledger.revision ~= before.revision or ledger.capturedAt ~= before.capturedAt
            or high.known ~= true or type(target) ~= "table" or target.userId ~= i.target then
            return nil, "Owned high-value membership required"
        end
    end
    for k in pairs(p.resources) do if k ~= "stamina" then return nil, "Unsupported Scout charge" end end
    local proof, usage, pools = before.hitListProof, before.playerFightUsageProof, before.native.pools
    if type(proof) ~= "table" or proof.account ~= p.account or proof.capturedAt ~= before.capturedAt
        or proof.sourceKey ~= i.sourceKey or type(proof.rows) ~= "table" or #proof.rows > 128
        or type(proof.profiles) ~= "table" or type(usage) ~= "table" or usage.account ~= p.account
        or usage.capturedAt ~= before.capturedAt or type(usage.usage) ~= "table" or type(usage.usage.lanes) ~= "table"
        or type(pools) ~= "table" or not number(pools.stamina, i.maxStaminaExposure) or not number(pools.health, 0) then
        return nil, "Owned Scout quote, allowance and pools required"
    end
    local lane = usage.usage.lanes[p.feature]
    local spent = type(lane) == "table" and lane.scout
    if type(spent) ~= "table" or spent.attempted ~= i.attemptedBefore or spent.spent ~= i.spentBefore then
        return nil, "Independent Scout allowance changed"
    end
    local selected
    for _, row in ipairs(proof.rows) do
        if row.userId == i.target then if selected then return nil, "Duplicate Scout target" end; selected = row end
    end
    local profile = proof.profiles[tostring(i.target)]
    if not selected or selected.name ~= i.targetName or selected.level ~= i.targetLevel or selected.shielded ~= false
        or selected.familyId ~= i.familyId or type(profile) ~= "table" or profile.userId ~= i.target
        or profile.name ~= i.targetName or profile.level ~= i.targetLevel or profile.familyId ~= i.familyId
        or profile.scoutCost ~= i.expectedStaminaCost or profile.friend ~= false or profile.friendshipStatus ~= "reported"
        or not number(profile.observedServerNow, 0) or profile.observedServerNow > i.serverNow
        or i.serverNow - profile.observedServerNow > 30 or not number(profile.observedAt, 0)
        or profile.observedAt > before.capturedAt or before.capturedAt - profile.observedAt > 30 then
        return nil, "Scout target or current profile quote changed"
    end
    local b = {revision = p.revision, capturedAt = before.capturedAt, target = i.target, targetName = i.targetName,
        targetLevel = i.targetLevel, familyId = i.familyId, staminaCost = i.expectedStaminaCost,
        staminaExposure = i.maxStaminaExposure, staminaBefore = pools.stamina, healthBefore = pools.health,
        sourceKey = i.sourceKey, serverNow = i.serverNow}
    for _, k in ipairs(scope) do b[k] = p[k] end
    return b, nil
end
local function baseline(p, before, b)
    local i = type(p) == "table" and p.intent
    if type(i) ~= "table" or type(b) ~= "table" or not same(p, b) or not same(p, before)
        or (p.feature ~= "combat" and p.feature ~= "warCombat") or i.kind ~= "playerScout" or i.allowScout ~= true
        or p.revision ~= b.revision or p.revision ~= before.revision or b.capturedAt ~= before.capturedAt
        or i.target ~= b.target or i.targetName ~= b.targetName or i.targetLevel ~= b.targetLevel or i.familyId ~= b.familyId
        or i.expectedStaminaCost ~= b.staminaCost or i.maxStaminaExposure ~= b.staminaExposure
        or i.sourceKey ~= b.sourceKey or i.serverNow ~= b.serverNow or type(p.resources) ~= "table"
        or p.resources.stamina ~= b.staminaExposure or not integer(b.staminaCost, 1, 5)
        or not integer(b.staminaExposure, b.staminaCost, 5) or not number(b.serverNow, 0)
        or not number(b.staminaBefore, b.staminaExposure) or not number(b.healthBefore, 0) then return nil end
    return b
end
local function stats(reply, b)
    if type(reply) ~= "table" or reply.ok ~= true or reply.pending == true or reply.code == "presence"
        or reply.code == "rate_limited" or reply.code == "busy" or reply.fightId ~= nil
        or not number(reply.atk, 1) or not number(reply.def, 1) or not number(reply.crew, 0)
        or reply.target ~= nil and reply.target ~= b.target or reply.userId ~= nil and reply.userId ~= b.target
        or reply.staminaCost ~= nil and reply.staminaCost ~= b.staminaCost then return nil end
    return {target = b.target, name = b.targetName, level = b.targetLevel, familyId = b.familyId,
        attack = reply.atk, defense = reply.def, crew = reply.crew, at = b.serverNow, kind = "scout", sourceKey = b.sourceKey}
end
function Evidence.evaluate(p, before, after, reply, b)
    if not baseline(p, before, b) or not header(after, p, true) or after.native.serverNow < b.serverNow
        or after.session == p.session and after.revision <= p.revision or type(reply) ~= "table" then return "pending" end
    local pools = after.native.pools
    if type(pools) ~= "table" or pools.health ~= b.healthBefore then return "pending" end
    if stats(reply, b) and pools.stamina == b.staminaBefore - b.staminaCost then return "confirmed" end
    if reply.ok == false and reply.pending ~= true and reply.code ~= "presence" and reply.code ~= "rate_limited"
        and reply.code ~= "busy" and reply.fightId == nil and pools.stamina == b.staminaBefore then return "rejected" end
    return "pending"
end
local function saved(data)
    if type(data) ~= "table" then return nil end
    local b = Evidence.capture(data.proposal, data.before)
    return b and equal(b, data.baseline) and b or nil
end
function Evidence.recoverSaved(data, after)
    local b = saved(data)
    if not b then return nil end
    local status = Evidence.evaluate(data.proposal, data.before, after, data.reply, b)
    return status ~= "pending" and status or nil
end
function Evidence.outcome(data, after)
    local b = saved(data)
    if not b or not integer(data.proposal.requestId, 1)
        or Evidence.evaluate(data.proposal, data.before, after, data.reply, b) ~= "confirmed" then return nil end
    local row = stats(data.reply, b)
    row.requestId = data.proposal.requestId
    return row
end
return Evidence
