-- Inject native attributes/GlobalBossRules; project only the fields used by combat.
local NativeGlobalBossSource = {}
local MAX = 9007199254740991
local fields = {"session", "account", "place", "release", "revision", "capturedAt"}
local eventFields = {"id", "startAt", "endAt", "status", "hp", "dmg", "resultAt", "testUserId"}
local function number(value, low)
    return type(value) == "number" and value == value and value >= low and value <= MAX
end
local function header(raw, release)
    if type(raw) ~= "table" or raw.release ~= release or type(raw.native) ~= "table"
        or raw.native.fullSync ~= true or not number(raw.native.serverNow, 0)
        or not number(raw.revision, 0) or raw.revision % 1 ~= 0
        or not number(raw.capturedAt, 0) then return nil end
    local result = {}
    for _, field in ipairs(fields) do result[field] = raw[field] end
    for _, field in ipairs({"session", "account", "place", "release"}) do
        if type(result[field]) ~= "string" or #result[field] == 0 or #result[field] > 200 then return nil end
    end
    return result
end
local function same(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs(fields) do if a[field] ~= b[field] then return false end end
    return true
end
function NativeGlobalBossSource.new(rule, readAttributes, stateReader, userId, fingerprint, release)
    if type(rule) ~= "table" or rule.ATTR ~= "GlobalBossState"
        or rule.PRIVATE_ATTR ~= "GlobalBossPrivateState" or type(rule.decode) ~= "function"
        or type(rule.canAccess) ~= "function" or type(readAttributes) ~= "function"
        or type(stateReader) ~= "table" or type(stateReader.read) ~= "function"
        or not number(userId, 1) or userId % 1 ~= 0
        or type(fingerprint) ~= "string" or #fingerprint ~= 64 or not fingerprint:match("^[%x]+$")
        or type(release) ~= "string" or #release == 0 then
        return nil, "Current native Global Boss rule/attributes/identity required"
    end
    -- Event/claim evidence is independent of attack admission. Once a native
    -- cooldown has been observed, missing/bad values cannot revive legacy fallback.
    local observedCooldown = rule.ATTACK_COOLDOWN ~= nil
    local closed, generation = false, 0
    local sourceKey = fingerprint:lower()
    local result = {}
    function result:Enrich(snapshot)
        local bound = header(snapshot, release)
        if closed or not bound then return nil, "Matching full Global Boss Sync required" end
        local cooldown = rule.ATTACK_COOLDOWN
        if cooldown ~= nil then observedCooldown = true end
        generation = generation + 1
        local observedGeneration, serverNow = generation, snapshot.native.serverNow
        local ok, attributes = pcall(readAttributes)
        if not ok or type(attributes) ~= "table" then return nil, "Global Boss attributes unavailable" end
        -- Lua's native `private or public` preserves a present empty string.
        local encoded = attributes.GlobalBossPrivateState or attributes.GlobalBossState
        if encoded ~= nil and (type(encoded) ~= "string" or #encoded > 131072) then
            return nil, "Invalid Global Boss attribute"
        end
        local event
        if encoded ~= nil and encoded ~= "" then
            local decoded, value = pcall(rule.decode, encoded)
            if not decoded or type(value) ~= "table" then return nil, "Global Boss decode unavailable" end
            event = {}
            for _, field in ipairs(eventFields) do
                local item = value[field]
                if item ~= nil and type(item) ~= "number" and type(item) ~= "string" then
                    return nil, "Invalid Global Boss event field"
                end
                event[field] = item
            end
            if type(event.id) ~= "string" or #event.id > 120 then return nil, "Invalid Global Boss event id" end
            local checked, allowed = pcall(rule.canAccess, event, userId)
            if not checked or type(allowed) ~= "boolean" then return nil, "Global Boss access unavailable" end
            if not allowed then event = nil end
        end
        if closed or generation ~= observedGeneration or not same(header(snapshot, release), bound)
            or snapshot.native.serverNow ~= serverNow then return nil, "Global Boss source changed during capture" end
        local currentCooldown = rule.ATTACK_COOLDOWN
        if currentCooldown ~= nil then observedCooldown = true end
        local cooldownStatus = "unavailable"
        if cooldown == currentCooldown then
            if number(cooldown, 0) and cooldown > 0 and cooldown <= 120 then cooldownStatus = "known"
            elseif cooldown == nil and not observedCooldown then cooldownStatus = "legacy-absent" end
        end
        -- A changed or malformed cooldown fences new attacks, not exact terminal
        -- hit/award observations or independently eligible claims.
        local enriched = {}
        for key, value in pairs(snapshot) do enriched[key] = value end
        enriched.globalBossProof = {account = bound.account, capturedAt = bound.capturedAt,
            header = bound, sourceKey = sourceKey, event = event,
            attackCooldown = cooldownStatus == "known" and cooldown or nil,
            attackCooldownStatus = cooldownStatus, attackCooldownUnavailable = cooldownStatus == "unavailable"}
        enriched.localUserIdProof = {account = bound.account, capturedAt = bound.capturedAt,
            userId = userId, sourceKey = sourceKey}
        local context = {}
        for key, value in pairs(bound) do context[key] = value end
        context.serverNow = serverNow
        local checked, view, reason = pcall(stateReader.read, enriched, context)
        if not checked or not view then return nil, checked and reason or "Invalid Global Boss state" end
        return enriched, nil
    end
    function result:Close() closed, generation = true, generation + 1 end
    return result, nil
end
return NativeGlobalBossSource
