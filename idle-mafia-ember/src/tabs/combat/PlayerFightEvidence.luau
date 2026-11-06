-- Native staged receipts establish outcomes; balances alone never establish a fight.
local Evidence = {}
local MAX = 9007199254740991
local scope = {"session", "account", "place", "release"}
local function number(v, low, high)
    return type(v) == "number" and v == v and v >= low and v <= (high or MAX)
end
local function integer(v, low, high) return number(v, low, high) and v % 1 == 0 end
local function text(v, high)
    return type(v) == "string" and #v > 0 and #v <= high and not v:find("[%c]")
end
local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for k, v in pairs(a) do if not equal(v, b[k]) then return false end end
    for k in pairs(b) do if a[k] == nil then return false end end
    return true
end
local function same(a, b, restart)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, k in ipairs(scope) do
        if (k ~= "session" or not restart) and (not text(a[k], 200) or a[k] ~= b[k]) then return false end
    end
    return true
end
local function header(raw, proposal, restart)
    return same(proposal, raw, restart) and integer(raw.revision, 0)
        and type(raw.capturedAt) == "number" and raw.capturedAt == raw.capturedAt
        and raw.capturedAt >= 0 and raw.capturedAt <= MAX
        and type(raw.native) == "table" and raw.native.fullSync == true
        and number(raw.native.serverNow, 0)
end
local function daily(native, target)
    local data = native.attackDaily
    if type(data) ~= "table" or data.day ~= math.floor(native.serverNow / 86400)
        or type(data.counts) ~= "table" then return nil end
    local count = data.counts[tostring(target)]
    if count == nil then count = 0 end
    return integer(count, 0) and count or nil
end
function Evidence.new(receipts)
    assert(type(receipts) == "table" and type(receipts.Project) == "function"
        and type(receipts.Settled) == "function", "Missing native fight receipt validators")
    local result = {}
    local function pair(initial, receipt, baseline)
        local first, last = receipts.Project(initial), receipts.Project(receipt)
        if not first or not last or first.ok ~= true or type(first.won) ~= "boolean" or first.cashStage ~= 1
            or not receipts.Settled(last) or first.fightId ~= last.fightId or first.won ~= last.won
            or first.targetName ~= baseline.targetName or first.targetShownLevel ~= baseline.targetLevel
            or first.staminaCost ~= baseline.staminaCost or last.staminaCost ~= first.staminaCost then return nil end
        for _, k in ipairs({"targetName", "targetLevel", "targetShownLevel"}) do
            if last[k] ~= first[k] then return nil end
        end
        local d = first.targetDaily
        if not d or d.day ~= baseline.day or d.count ~= baseline.dailyBefore + 1 then return nil end
        return first, last
    end
    function result.capture(p, before)
        local i = type(p) == "table" and p.intent
        local exposure = type(i) == "table" and i.maxStaminaExposure
        if type(i) == "table" and exposure == nil then exposure = i.expectedStaminaCost end
        if type(i) ~= "table" or (p.feature ~= "combat" and p.feature ~= "warCombat") or i.kind ~= "playerAttack"
            or not header(before, p) or p.revision ~= before.revision or i.serverNow ~= before.native.serverNow
            or not integer(i.target, 1) or not text(i.targetName, 64) or not integer(i.targetLevel, 1)
            or not integer(i.expectedStaminaCost, 1, 5) or type(p.resources) ~= "table"
            or not integer(exposure, i.expectedStaminaCost, 5) or p.resources.stamina ~= exposure or not text(i.sourceKey, 64) or #i.sourceKey ~= 64
            or not i.sourceKey:match("^[%x]+$") then return nil, "Exact player fight baseline required" end
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
        for k in pairs(p.resources) do if k ~= "stamina" then return nil, "Unsupported fight charge" end end
        local targets = before[p.feature == "warCombat" and "warRosterProof" or "hitListProof"]
        local proof, usage = before.playerFightProof, before.playerFightUsageProof
        if type(proof) ~= "table" or not same(proof, before) or proof.sourceKey ~= i.sourceKey
            or proof.revision ~= before.revision or proof.capturedAt ~= before.capturedAt
            or type(targets) ~= "table" or targets.account ~= before.account or targets.capturedAt ~= before.capturedAt
            or type(targets.rows) ~= "table" or #targets.rows > 128 or type(usage) ~= "table"
            or usage.account ~= before.account or usage.capturedAt ~= before.capturedAt
            or type(usage.usage) ~= "table" or type(usage.usage.lanes) ~= "table" then
            return nil, "Owned player source and allowance required"
        end
        local lane = usage.usage.lanes[p.feature]
        local spent = type(lane) == "table" and lane.attack
        if type(spent) ~= "table" or spent.attempted ~= i.attemptedBefore or spent.spent ~= i.spentBefore then
            return nil, "Player fight allowance changed"
        end
        local selected
        for _, row in ipairs(targets.rows) do
            if row.userId == i.target then if selected then return nil, "Duplicate player target" end; selected = row end
        end
        local pools, count = before.native.pools, daily(before.native, i.target)
        if not selected or selected.name ~= i.targetName or selected.level ~= i.targetLevel
            or selected.stamina ~= i.expectedStaminaCost or selected.shielded ~= false
            or type(pools) ~= "table" or not number(pools.stamina, exposure)
            or not number(pools.health, 0) or count == nil then return nil, "Selected player quote changed" end
        if p.feature == "warCombat" then
            local war, allowance = targets.war, selected.warStatus
            local nativeWar = type(before.native.derived) == "table" and before.native.derived.war
            if type(war) ~= "table" or war.active ~= true or war.canScore ~= true
                or war.enemyFamilyId ~= i.warEnemyFamilyId or selected.familyId ~= i.warEnemyFamilyId or i.familyId ~= i.warEnemyFamilyId
                or type(before.native.family) ~= "table" or before.native.family.id ~= i.warOwnFamilyId
                or i.warOwnFamilyId == i.warEnemyFamilyId or i.warDay ~= math.floor(i.serverNow / 86400)
                or i.warStatusServerNow ~= war.statusServerNow or type(nativeWar) ~= "table" or nativeWar.state ~= "active"
                or nativeWar.enemyId ~= nil and nativeWar.enemyId ~= i.warEnemyFamilyId
                or type(allowance) ~= "table" or allowance.day ~= i.warDay or allowance.canScore ~= true
                or not integer(allowance.remaining, 1) or not integer(allowance.attacksRemaining, 1)
                or not integer(allowance.pairRemaining, 1) then return nil, "Exact scoring enemy baseline required" end
        end
        if i.dailyOnly ~= nil and type(i.dailyOnly) ~= "boolean" or i.dailyOnly == true and count ~= 0 then
            return nil, "Daily-only target was already attacked or the option is invalid"
        end
        local baseline = {revision = p.revision, capturedAt = before.capturedAt, sourceKey = i.sourceKey,
            serverNow = i.serverNow, target = i.target, targetName = i.targetName, targetLevel = i.targetLevel,
            staminaCost = i.expectedStaminaCost, staminaBefore = pools.stamina, healthBefore = pools.health,
            day = math.floor(i.serverNow / 86400), dailyBefore = count}
        for _, k in ipairs(scope) do baseline[k] = p[k] end
        if i.maxStaminaExposure ~= nil then baseline.staminaExposure = exposure end
        return baseline, nil
    end
    local function original(data, live)
        if type(data) ~= "table" or type(data.proposal) ~= "table" or type(data.reply) ~= "table" then return nil end
        if live then
            -- Broker supplies its immutable header and the capture result here;
            -- full original snapshots exist only in the saved recovery record.
            local p, b, i = data.proposal, data.baseline, data.proposal.intent
            if type(b) ~= "table" or type(i) ~= "table" or not same(p, data.before) or not same(p, b)
                or p.revision ~= data.before.revision or p.revision ~= b.revision
                or b.capturedAt ~= data.before.capturedAt or i.kind ~= "playerAttack"
                or (p.feature ~= "combat" and p.feature ~= "warCombat") or i.target ~= b.target
                or i.targetName ~= b.targetName or i.targetLevel ~= b.targetLevel
                or i.expectedStaminaCost ~= b.staminaCost or i.maxStaminaExposure ~= b.staminaExposure
                or type(p.resources) ~= "table" or p.resources.stamina ~= (b.staminaExposure or b.staminaCost)
                or i.sourceKey ~= b.sourceKey
                or i.serverNow ~= b.serverNow or not number(b.serverNow, 0)
                or b.day ~= math.floor(b.serverNow / 86400) or not integer(b.dailyBefore, 0) then return nil end
            return b
        end
        local baseline = result.capture(data.proposal, data.before)
        return baseline and equal(baseline, data.baseline) and baseline or nil
    end
    function result.copyOutcome(raw)
        if type(raw) ~= "table" or not integer(raw.requestId, 1) or not text(raw.actionKey, 1000)
            or (raw.feature ~= "combat" and raw.feature ~= "warCombat") or not integer(raw.target, 1)
            or not text(raw.session, 200) or not integer(raw.revision, 0) or not number(raw.serverNow, 0)
            or not integer(raw.staminaCost, 1, 5) or not text(raw.sourceKey, 64) or #raw.sourceKey ~= 64
            or not raw.sourceKey:match("^[%x]+$") or not integer(raw.targetLevel, 1)
            or not text(raw.targetName, 64) or not integer(raw.day, 0) or raw.day ~= math.floor(raw.serverNow / 86400)
            or not integer(raw.dailyBefore, 0) then return nil end
        local first, last = pair(raw.initial, raw.receipt, raw)
        if not first then return nil end
        local out = {initial = first, receipt = last}
        for _, k in ipairs({"requestId", "actionKey", "feature", "target", "session", "revision", "serverNow",
            "staminaCost", "sourceKey", "targetLevel", "targetName", "day", "dailyBefore"}) do out[k] = raw[k] end
        for k in pairs(raw) do if out[k] == nil then return nil end end
        return out
    end
    local function row(p, baseline, initial, receipt)
        local out = {requestId = p.requestId, actionKey = p.actionKey, feature = p.feature,
            session = p.session, revision = p.revision, initial = initial, receipt = receipt}
        for _, k in ipairs({"serverNow", "target", "staminaCost", "sourceKey", "targetLevel", "targetName", "day", "dailyBefore"}) do
            out[k] = baseline[k]
        end
        return result.copyOutcome(out)
    end
    local function matched(data, after, live, persistOwned)
        local baseline = original(data, live)
        local p = data and data.proposal
        if not baseline or not header(after, p, true) or after.native.serverNow < baseline.serverNow then return nil end
        -- A previous durable write may have succeeded before generic cleanup failed.
        local ledger = after.playerFightHistoryProof
        if type(ledger) == "table" and same(ledger, after) and ledger.revision == after.revision
            and ledger.capturedAt == after.capturedAt and type(ledger.recent) == "table" and #ledger.recent <= 32 then
            for _, saved in ipairs(ledger.recent) do
                if saved.requestId == p.requestId then
                    local copied = result.copyOutcome(saved)
                    if copied and equal(copied, row(p, baseline, data.reply, copied.receipt)) then
                        return copied.initial, copied.receipt, baseline
                    end
                    return nil
                end
            end
        end
        if after.session ~= p.session or after.revision < p.revision
            or after.revision == p.revision and not persistOwned then return nil end
        local proof = after.playerFightProof
        if type(proof) ~= "table" or not same(proof, after) or proof.revision ~= after.revision
            or proof.capturedAt ~= after.capturedAt or proof.sourceKey ~= baseline.sourceKey
            or type(proof.attempts) ~= "table" or #proof.attempts ~= 1 then return nil end
        local attempt = proof.attempts[1]
        if type(attempt) ~= "table" or attempt.status ~= "settled" or attempt.target ~= p.intent.target
            or attempt.actionKey ~= p.actionKey or attempt.feature ~= p.feature
            or not equal(receipts.Project(data.reply), receipts.Project(attempt.initial)) then return nil end
        local first, last = pair(data.reply, attempt.receipt, baseline)
        if first then return first, last, baseline end
        return nil
    end
    function result.outcome(data, after)
        -- Durable storage may retain an already-owned terminal receipt before the
        -- next Sync. Broker confirmation/evaluate still requires a newer revision.
        local first, last, baseline = matched(data, after, nil, true)
        return first and row(data.proposal, baseline, first, last) or nil
    end
    function result.evaluate(p, before, after, reply, baseline)
        local data = {proposal = p, before = before, reply = reply, baseline = baseline}
        if matched(data, after, true) then return "confirmed" end
        if not original(data, true) or not header(after, p, true) or after.native.serverNow < baseline.serverNow
            or after.session == p.session and after.revision <= p.revision then return "pending" end
        if reply.ok == false and reply.pending ~= true and reply.fightId == nil
            and reply.code ~= "presence" and reply.code ~= "rate_limited" and reply.code ~= "busy" then
            local pools = after.native.pools
            if type(pools) == "table" and pools.stamina == baseline.staminaBefore
                and pools.health == baseline.healthBefore and daily(after.native, baseline.target) == baseline.dailyBefore
                and math.floor(after.native.serverNow / 86400) == baseline.day then return "rejected" end
        end
        return "pending"
    end
    function result.recoverSaved(data, after)
        if not original(data) then return nil end
        local status = result.evaluate(data.proposal, data.before, after, data.reply, data.baseline)
        return (status == "confirmed" or status == "rejected") and status or nil
    end
    return result
end
return Evidence
