-- Read-only ordinary-fight facts. No target selection or attack proposal.
local PlayerTargetState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function nonempty(value)
    return type(value) == "string" and #value > 0
end

local function finite(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

local function dense(rows)
    if type(rows) ~= "table" or #rows > 128 then return false end
    local count = 0
    for key in pairs(rows) do
        if not integer(key, 1) or key > #rows then return false end
        count = count + 1
    end
    return count == #rows
end

local function readTargets(raw, context, rules, ownedTargets)
    if type(raw) ~= "table" or type(context) ~= "table"
        or type(rules) ~= "table" then
        return nil, "Missing Combat target input"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Combat snapshot header changed"
        end
    end
    local native, proof = raw.native, ownedTargets or raw.hitListProof
    local pools = type(native) == "table" and native.pools
    local daily = type(native) == "table" and native.attackDaily
    if type(native) ~= "table" or native.fullSync ~= true
        or not finite(native.serverNow)
        or context.serverNow ~= native.serverNow
        or type(pools) ~= "table"
        or not finite(pools.health)
        or not finite(pools.stamina)
        or type(daily) ~= "table"
        or daily.day ~= math.floor(native.serverNow / 86400)
        or type(daily.counts) ~= "table"
        or type(proof) ~= "table"
        or proof.account ~= context.account
        or proof.capturedAt ~= context.capturedAt
        or not dense(proof.rows)
        or not integer(rules.hospitalHealth, 1)
        or not integer(rules.staminaCost, 1)
        or not integer(rules.dailyTargetCap, 1) then
        return nil, "Current Combat target and daily proof required"
    end
    local rows, seen = {}, {}
    for index, item in ipairs(proof.rows) do
        local key = type(item) == "table" and tostring(item.userId)
        local count = key and daily.counts[key]
        if type(item) ~= "table" or not integer(item.userId, 1)
            or seen[item.userId] or not nonempty(item.name)
            or not integer(item.level, 1)
            or (item.shielded ~= nil and type(item.shielded) ~= "boolean"
                and (type(item.shielded) ~= "number"
                    or item.shielded ~= item.shielded
                    or item.shielded == math.huge
                    or item.shielded == -math.huge))
            or (count ~= nil and not integer(count, 0)) then
            return nil, "Invalid Combat target or daily count"
        end
        seen[item.userId] = true
        local remaining = math.max(0, rules.dailyTargetCap - (count or 0))
        rows[index] = { userId = item.userId, name = item.name,
            level = item.level, shielded = item.shielded == true
                or type(item.shielded) == "number" and item.shielded > 0,
            remainingDaily = remaining, attacksToday = count or 0 }
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        serverNow = native.serverNow, health = pools.health,
        stamina = pools.stamina,
        resourceReady = pools.health >= rules.hospitalHealth
            and pools.stamina >= rules.staminaCost,
        rows = rows }, nil
end

function PlayerTargetState.read(raw, context, rules)
    return readTargets(raw, context, rules)
end

local scopeFields = {"session", "account", "place", "release", "revision", "capturedAt"}
local function matchingHeader(proof, raw)
    if type(proof) ~= "table" then return false end
    for _, key in ipairs(scopeFields) do if proof[key] ~= raw[key] then return false end end
    return proof.serverNow == nil or proof.serverNow == raw.native.serverNow
end
local function family(value)
    return integer(value, 0) and value <= 9007199254740991
        or type(value) == "string" and #value > 0 and #value <= 120 and not value:find("[%c]")
end
local function readHeader(proof, raw)
    local first = proof.readHeader
    if type(first) ~= "table" or not integer(first.revision, 0) or first.revision > raw.revision
        or first.capturedAt ~= proof.observedAt or first.serverNow ~= proof.observedServerNow then return false end
    for _, key in ipairs({"session", "account", "place", "release"}) do if first[key] ~= raw[key] then return false end end
    return first.revision ~= raw.revision or first.capturedAt == raw.capturedAt and first.serverNow == raw.native.serverNow
end
local function usageRow(row)
    return type(row) == "table" and integer(row.attempted, 0) and integer(row.spent, 0)
        and row.attempted <= 1000000 and row.spent <= 1000000
        and row.spent >= row.attempted and row.spent <= row.attempted * 5
end
local function selection(raw, context, mode)
    local warMode = mode == "warCombat"
    local proof = type(raw) == "table" and (warMode and raw.warRosterProof or raw.hitListProof)
    local frame = type(proof) == "table" and proof.nativeFrame
    if type(raw) ~= "table" or type(raw.native) ~= "table" or type(context) ~= "table"
        or not integer(raw.revision, 0) or not finite(raw.capturedAt) or not finite(raw.native.serverNow)
        or type(frame) ~= "table" or type(proof.sourceKey) ~= "string" or #proof.sourceKey ~= 64
        or not proof.sourceKey:match("^[%x]+$") or frame.sourceKey ~= proof.sourceKey
        or not matchingHeader(proof.header, raw) or not matchingHeader(frame.header, raw)
        or proof.header.serverNow ~= raw.native.serverNow or frame.header.serverNow ~= raw.native.serverNow
        or not finite(proof.observedAt) or not finite(proof.observedServerNow) or not readHeader(proof, raw)
        or raw.capturedAt < proof.observedAt or raw.capturedAt - proof.observedAt > 10
        or raw.native.serverNow < proof.observedServerNow or raw.native.serverNow - proof.observedServerNow > 10
        or type(proof.profiles) ~= "table" or type(frame.targets) ~= "table"
        or not integer(frame.ownUserId, 1) or not family(frame.ownFamilyId)
        or raw.native.userId ~= nil and raw.native.userId ~= frame.ownUserId
        or not finite(frame.attack) or frame.attack < 1 or not finite(frame.maxHealth) or frame.maxHealth < 1
        or not finite(frame.scoutCost) or frame.scoutCost < 1 or frame.scoutCost > 5 or frame.scoutCost % 1 ~= 0
        or not integer(frame.maxStaminaCost, 1) or frame.maxStaminaCost > 5
        or not finite(frame.targetCooldown) or not finite(frame.fightVariance) or not finite(frame.fightVarianceCap)
        or type(frame.busy) ~= "boolean" or type(frame.shielded) ~= "boolean" or not finite(frame.globalCooldown) then
        return nil, "Current owned player resources and target source required"
    end
    local war = proof.war
    if type(war) ~= "table" or type(war.active) ~= "boolean" or not finite(war.statusServerNow)
        or raw.native.serverNow - war.statusServerNow > 10 or war.statusServerNow - raw.native.serverNow > 10
        or war.active and (frame.ownFamilyId == 0 or not family(war.enemyFamilyId) or war.enemyFamilyId == 0
            or war.enemyFamilyId == frame.ownFamilyId or type(war.enemyFamilyId) ~= type(frame.ownFamilyId))
        or not war.active and war.enemyFamilyId ~= nil then return nil, "Verified current war state and enemy identity required" end
    local base, why = readTargets(raw, context, frame, proof)
    local pools, stats = raw.native.pools, raw.native.stats
    local ownFamily = type(raw.native.family) == "table" and raw.native.family.id or raw.native.family == nil and 0
    if not base or type(stats) ~= "table" or frame.maxHealth ~= stats.maxHealth
        or frame.health ~= pools.health or frame.stamina ~= pools.stamina or frame.ownFamilyId ~= ownFamily then
        return nil, why or "Player source snapshot changed"
    end
    if frame.busy or frame.shielded or frame.globalCooldown > 0 then return nil, "Native Combat, shield or cooldown needs manual attention" end
    local usage = raw.playerFightUsageProof
    local lane = type(usage) == "table" and type(usage.usage) == "table" and type(usage.usage.lanes) == "table" and usage.usage.lanes[mode]
    if type(usage) ~= "table" or usage.account ~= raw.account or usage.capturedAt ~= raw.capturedAt
        or type(lane) ~= "table" or not usageRow(lane.attack) or not usageRow(lane.scout) then
        return nil, "Owned independent player Stamina allowances required"
    end
    local ledger = raw.playerFightHistoryProof
    if not matchingHeader(ledger, raw) or not dense(ledger.recent) or #ledger.recent > 32 then
        return nil, "Owned fight history required"
    end
    local histories, cooldowns, unknownTimes, todayCounts, lastId = {}, {}, {}, {}, 0
    for _, row in ipairs(ledger.recent) do
        if type(row) ~= "table" or not integer(row.requestId, lastId + 1) or not integer(row.target, 1)
            or (row.feature ~= "combat" and row.feature ~= "warCombat") or not finite(row.serverNow)
            or type(row.receipt) ~= "table" or type(row.receipt.won) ~= "boolean"
            or not integer(row.receipt.cashConfirmed, 0) then return nil, "Saved fight history is unavailable" end
        lastId = row.requestId
        local key = tostring(row.target)
        local daily = type(row.initial) == "table" and row.initial.targetDaily
        local at = type(daily) == "table" and daily.serverNow
        if not finite(at) or at + 1 < row.serverNow or at > raw.native.serverNow then unknownTimes[key] = true
        else
            if math.floor(at / 86400) == math.floor(base.serverNow / 86400) then
                todayCounts[key] = (todayCounts[key] or 0) + 1
            end
            local upperTime = at % 1 == 0 and at + 1 or at
            cooldowns[key] = math.max(cooldowns[key] or 0, math.max(row.serverNow, upperTime) + frame.targetCooldown)
            if row.feature == mode then
                histories[key] = histories[key] or {}
                histories[key][#histories[key] + 1] = {at = at, cash = row.receipt.cashConfirmed, won = row.receipt.won}
            end
        end
    end
    -- Optional high-only history comes from this tab's ledger, never native estimates.
    -- Malformed/unknown metadata keeps ordinary selection available but cannot opt in.
    local high, highTargets = ledger.highValue, {}
    local highKnown = not warMode and type(high) == "table" and high.known == true and high.lastRequestId == lastId
        and integer(high.count, 0) and high.count <= 128 and type(high.targets) == "table"
    if highKnown then
        local count, seen, present, retained = 0, {}, {}, {}
        for _, target in ipairs(proof.rows) do present[tostring(target.userId)] = true end
        for _, row in ipairs(ledger.recent) do retained[row.requestId] = row end
        for key, target in pairs(high.targets) do
            count = count + 1
            if count > high.count or not present[key] or type(target) ~= "table" or not integer(target.userId, 1)
                or key ~= tostring(target.userId) or not dense(target.history) or #target.history < 1 or #target.history > 32 then
                highKnown = false; break
            end
            local rows, previous = {}, 0
            for _, item in ipairs(target.history) do
                if type(item) ~= "table" or not integer(item.requestId, previous + 1) or item.requestId > lastId
                    or seen[item.requestId] or not finite(item.at) or item.at < 0 or item.at > base.serverNow
                    or not integer(item.cash, 0) or type(item.won) ~= "boolean" then highKnown = false; break end
                local owned = retained[item.requestId]
                if owned and (owned.feature ~= "combat" or owned.target ~= target.userId or owned.initial.targetDaily.serverNow ~= item.at
                    or owned.receipt.cashConfirmed ~= item.cash or owned.receipt.won ~= item.won) then highKnown = false; break end
                rows[#rows + 1] = {at=item.at,cash=item.cash,won=item.won}
                previous, seen[item.requestId] = item.requestId, true
            end
            if not highKnown then break end
            highTargets[key] = rows
        end
    end
    if highKnown then
        for key, rows in pairs(highTargets) do
            histories[key] = rows -- Replace overlapping receipts; never add them twice.
            local today = 0
            for _, item in ipairs(rows) do
                if math.floor(item.at / 86400) == math.floor(base.serverNow / 86400) then today = today + 1 end
                local upper = item.at % 1 == 0 and item.at + 1 or item.at
                cooldowns[key] = math.max(cooldowns[key] or 0, upper + frame.targetCooldown)
            end
            todayCounts[key] = math.max(todayCounts[key] or 0, today)
        end
    end
    local view = {status = "known", serverNow = base.serverNow, ownUserId = frame.ownUserId,
        ownFamilyId = frame.ownFamilyId, health = base.health, maxHealth = frame.maxHealth,
        stamina = base.stamina, attack = frame.attack, hospitalHealth = frame.hospitalHealth,
        scoutCost = frame.scoutCost, maxNativeStaminaCost = frame.maxStaminaCost,
        fightVariance = frame.fightVariance, fightVarianceCap = frame.fightVarianceCap,
        attackAttempted = lane.attack.attempted, attackSpent = lane.attack.spent,
        scoutAttempted = lane.scout.attempted, scoutSpent = lane.scout.spent,
        sourceKey = proof.sourceKey, highValueKnown = highKnown == true,
        war = {active = war.active, enemyFamilyId = war.enemyFamilyId}, targets = {}}
    if warMode then
        for _, key in ipairs({"statusServerNow", "ownRemaining", "ownCap", "canScore", "canFeed", "eligibleAt"}) do
            view.war[key] = war[key]
        end
    end
    for _, key in ipairs(scopeFields) do view[key] = raw[key] end
    for index, target in ipairs(proof.rows) do
        local key, facts = tostring(target.userId), frame.targets[tostring(target.userId)]
        local profile = proof.profiles[key]
        local quote = target.stamina
        if warMode and type(facts) == "table" and facts.staminaCost ~= nil then
            if quote == nil then quote = facts.staminaCost
            elseif quote ~= facts.staminaCost then quote = nil end
        end
        local valid = type(profile) == "table" and profile.userId == target.userId and profile.name == target.name
            and profile.level == target.level and profile.familyId == target.familyId and family(target.familyId)
            and finite(profile.observedServerNow) and profile.observedServerNow <= base.serverNow
            and base.serverNow - profile.observedServerNow <= 30 and finite(profile.observedAt)
            and profile.observedAt <= raw.capturedAt and raw.capturedAt - profile.observedAt <= 30
            and type(profile.statsHidden) == "boolean" and (profile.statsHidden or finite(profile.defense) and profile.defense >= 1)
            and (not warMode or profile.statsHidden or finite(profile.attack) and profile.attack >= 1 and finite(profile.crew))
            and integer(profile.scoutCost, frame.scoutCost) and profile.scoutCost <= 5
            and type(facts) == "table" and integer(facts.remainingDaily, 0) and facts.remainingDaily <= frame.dailyTargetCap and finite(facts.cooldownLeft)
            and facts.sameFamily == false and facts.manualWarning == false
            and (profile.shieldUntil == nil or finite(profile.shieldUntil) and profile.shieldUntil <= base.serverNow)
            and (not warMode and target.shielded == false or warMode and target.shielded ~= true
                and (target.shielded == nil or target.shielded == false or target.shielded == 0)
                and (profile.shieldStatus == "clear" or profile.shieldStatus == "shielded"
                    and finite(profile.shieldUntil) and profile.shieldUntil <= base.serverNow))
            and integer(quote, frame.staminaCost) and quote <= frame.maxStaminaCost
            and not unknownTimes[key]
        if valid then
            local row = {userId = target.userId, name = target.name, level = target.level,
                familyId = target.familyId, highValue = highKnown and highTargets[key] ~= nil or nil,
                staminaCost = quote, scoutCost = profile.scoutCost,
                remainingDaily = math.min(base.rows[index].remainingDaily, facts.remainingDaily), shieldUntil = 0,
                attacksToday = math.max(base.rows[index].attacksToday, frame.dailyTargetCap - facts.remainingDaily, todayCounts[key] or 0),
                cooldownUntil = math.max(base.serverNow + facts.cooldownLeft, cooldowns[key] or 0), history = histories[key] or {}}
            if warMode then
                row.warFamilyId = war.enemyFamilyId
                if type(target.warStatus) == "table" then
                    row.warStatus = {}
                    for _, field in ipairs({"day", "remaining", "cap", "attacksRemaining", "attacksCap", "pairRemaining", "canScore"}) do
                        row.warStatus[field] = target.warStatus[field]
                    end
                end
            end
            if profile.friendshipStatus == "reported" and type(profile.friend) == "boolean"
                and profile.friendshipObservedAt == profile.observedServerNow then row.friend = profile.friend end
            if profile.statsHidden == false and finite(profile.defense) and profile.defense >= 1 then
                row.stats = {at = profile.observedServerNow, defense = profile.defense, kind = "public", level = profile.level}
            end
            local scout = profile.scout
            if type(scout) == "table" and scout.kind == "scout" and scout.level == profile.level
                and finite(scout.defense) and scout.defense >= 1 and finite(scout.at)
                and scout.at <= base.serverNow and base.serverNow - scout.at <= 1800
                and (warMode or not row.stats or scout.at > row.stats.at) then
                row.stats = {at = scout.at, defense = scout.defense, kind = "scout", level = scout.level}
            end
            view.targets[#view.targets + 1] = row
        end
    end
    return view, nil
end

function PlayerTargetState.readSelection(raw, context)
    return selection(raw, context, "combat")
end

-- War observations are independent of ordinary hit-list/profile facts. This
-- view is read-only; it does not establish scoring eligibility or an attack.
function PlayerTargetState.readWar(raw, context)
    local proof = type(raw) == "table" and raw.warRosterProof
    if type(raw) ~= "table" or type(context) ~= "table" or type(raw.native) ~= "table"
        or raw.native.fullSync ~= true or not finite(raw.native.serverNow)
        or context.serverNow ~= raw.native.serverNow or not finite(raw.capturedAt)
        or not integer(raw.revision, 0) or type(proof) ~= "table"
        or type(proof.sourceKey) ~= "string" or #proof.sourceKey ~= 64 or not proof.sourceKey:match("^[%x]+$")
        or not matchingHeader(proof.header, raw) or proof.header.serverNow ~= raw.native.serverNow
        or not finite(proof.observedAt) or not finite(proof.observedServerNow) or not readHeader(proof, raw)
        or raw.capturedAt < proof.observedAt or raw.capturedAt - proof.observedAt > 10
        or raw.native.serverNow < proof.observedServerNow or raw.native.serverNow - proof.observedServerNow > 10
        or not dense(proof.rows) then return nil, "Current owned war roster required" end
    for _, key in ipairs(scopeFields) do
        if raw[key] ~= context[key] then return nil, "War snapshot header changed" end
    end
    local war = proof.war
    local own = type(raw.native.family) == "table" and raw.native.family.id or raw.native.family == nil and 0
    local nativeWar = type(raw.native.derived) == "table" and raw.native.derived.war
    if type(war) ~= "table" or type(war.active) ~= "boolean" or not finite(war.statusServerNow)
        or math.abs(raw.native.serverNow - war.statusServerNow) > 10
        or not family(own) or war.active and (own == 0 or not family(war.enemyFamilyId) or war.enemyFamilyId == 0
            or war.enemyFamilyId == own or type(war.enemyFamilyId) ~= type(own)
            or type(nativeWar) ~= "table" or nativeWar.state ~= "active"
            or nativeWar.enemyId ~= nil and nativeWar.enemyId ~= war.enemyFamilyId)
        or not war.active and (war.enemyFamilyId ~= nil or #proof.rows ~= 0
            or type(nativeWar) == "table" and nativeWar.state == "active") then
        return nil, "Current war status and exact enemy identity required"
    end
    local view = {status = "observed", sourceKey = proof.sourceKey, serverNow = raw.native.serverNow,
        ownFamilyId = own, war = {}, targets = {}}
    for _, key in ipairs(scopeFields) do view[key] = raw[key] end
    for _, key in ipairs({"active", "statusServerNow", "enemyFamilyId", "ownRemaining", "ownCap", "canScore", "canFeed", "eligibleAt"}) do
        view.war[key] = war[key]
    end
    local seen = {}
    for index, row in ipairs(proof.rows) do
        if type(row) ~= "table" or not integer(row.userId, 1) or row.userId > 9007199254740991 or seen[row.userId]
            or not nonempty(row.name) or #row.name > 64 or not integer(row.level, 1)
            or row.familyId ~= war.enemyFamilyId then return nil, "Unambiguous native war roster required" end
        seen[row.userId] = true
        local target = {userId = row.userId, name = row.name, level = row.level, familyId = row.familyId}
        if type(row.warStatus) == "table" then
            target.warStatus = {}
            for _, key in ipairs({"day", "remaining", "cap", "attacksRemaining", "attacksCap", "pairRemaining", "canScore"}) do
                target.warStatus[key] = row.warStatus[key]
            end
        end
        local profile = type(proof.profiles) == "table" and proof.profiles[tostring(row.userId)]
        if type(profile) == "table" and profile.userId == row.userId and profile.name == row.name
            and profile.level == row.level and profile.familyId == row.familyId and type(profile.statsHidden) == "boolean"
            and integer(profile.scoutCost, 1) and profile.scoutCost <= 5
            and finite(profile.observedAt) and profile.observedAt <= raw.capturedAt and raw.capturedAt - profile.observedAt <= 30
            and finite(profile.observedServerNow) and profile.observedServerNow <= raw.native.serverNow
            and raw.native.serverNow - profile.observedServerNow <= 30 then
            local projected = {statsHidden = profile.statsHidden, scoutCost = profile.scoutCost,
                observedAt = profile.observedAt, observedServerNow = profile.observedServerNow,
                friendshipStatus = "unknown", shieldStatus = "unknown"}
            if profile.friendshipStatus == "reported" and type(profile.friend) == "boolean"
                and profile.friendshipObservedAt == profile.observedServerNow then
                projected.friendshipStatus, projected.friend = "reported", profile.friend
            end
            if profile.shieldStatus == "clear" then projected.shieldStatus = "clear"
            elseif profile.shieldStatus == "shielded" and finite(profile.shieldUntil) then
                projected.shieldStatus, projected.shieldUntil = "shielded", profile.shieldUntil
            end
            if profile.statsHidden == false and finite(profile.attack) and profile.attack >= 1
                and finite(profile.defense) and profile.defense >= 1 and finite(profile.crew) then
                projected.attack, projected.defense, projected.crew = profile.attack, profile.defense, profile.crew
            end
            target.profile = projected
        end
        view.targets[index] = target
    end
    return view, nil
end

-- Selection consumes the independent roster and its native frame. The ordinary
-- list is never consulted for War identity, quotes, profiles or scoring caps.
function PlayerTargetState.readWarSelection(raw, context)
    local observed, why = PlayerTargetState.readWar(raw, context)
    if not observed or observed.war.active ~= true then return observed, why end
    return selection(raw, context, "warCombat")
end

-- Capture-time/final-dispatch proof for one exact War target. Durable allowance
-- custody remains in Checkpoint; this rechecks native identity and eligibility.
function PlayerTargetState.readWarAttempt(p, raw)
    local i = type(p) == "table" and p.intent
    if type(i) ~= "table" or p.feature ~= "warCombat" or type(raw) ~= "table"
        or type(raw.native) ~= "table" or p.revision ~= raw.revision then return nil end
    for _, key in ipairs({"session", "account", "place", "release"}) do if p[key] ~= raw[key] then return nil end end
    local context = {serverNow = raw.native.serverNow}
    for _, key in ipairs(scopeFields) do context[key] = raw[key] end
    local view = PlayerTargetState.readWarSelection(raw, context)
    local war = view and view.war
    if not view or view.status ~= "known" or i.serverNow ~= view.serverNow
        or i.attack ~= view.attack or i.ownFamilyId ~= view.ownFamilyId or i.warFamilyId ~= war.enemyFamilyId or i.familyId ~= war.enemyFamilyId
        or i.warDay ~= math.floor(view.serverNow / 86400) or i.warStatusServerNow ~= war.statusServerNow
        or war.canScore ~= true or not finite(war.statusServerNow)
        or math.floor(war.statusServerNow / 86400) ~= i.warDay
        or war.eligibleAt ~= nil and (not finite(war.eligibleAt) or war.eligibleAt > view.serverNow)
        or not integer(war.ownRemaining, 0) or not integer(war.ownCap, war.ownRemaining)
        or not integer(i.scoutMaxAge, 1) or i.scoutMaxAge > 1800
        or i.maxStaminaExposure ~= view.maxNativeStaminaCost or i.attackExposure ~= view.maxNativeStaminaCost
        or type(p.resources) ~= "table" or p.resources.stamina ~= i.maxStaminaExposure then return nil end
    for _, row in ipairs(view.targets) do
        if row.userId == i.target then
            local cap, stats = row.warStatus, row.stats
            if row.name ~= i.targetName or row.level ~= i.targetLevel or row.familyId ~= i.familyId
                or row.warFamilyId ~= i.warFamilyId or row.userId == view.ownUserId or row.friend ~= false
                or row.staminaCost ~= i.attackQuote or row.remainingDaily < 1 or row.cooldownUntil > view.serverNow
                or type(cap) ~= "table" or cap.day ~= i.warDay or cap.canScore ~= true
                or not integer(cap.remaining, 1) or not integer(cap.cap, cap.remaining)
                or not integer(cap.attacksRemaining, 1) or not integer(cap.attacksCap, cap.attacksRemaining)
                or not integer(cap.pairRemaining, 1) then return nil end
            local fresh = type(stats) == "table" and stats.kind == "scout" and stats.level == row.level
                and finite(stats.at) and stats.at <= view.serverNow and view.serverNow - stats.at <= i.scoutMaxAge
                and finite(stats.defense) and stats.defense >= 1
            if i.kind == "playerAttack" then
                if not fresh or i.statsAt ~= stats.at or i.defense ~= stats.defense
                    or not finite(i.minPowerRatio) or i.minPowerRatio < 0.01
                    or view.attack / stats.defense < i.minPowerRatio
                    or i.expectedStaminaCost ~= row.staminaCost then return nil end
            elseif i.kind == "playerScout" then
                if i.allowScout ~= true or fresh or i.expectedStaminaCost ~= row.scoutCost then return nil end
            else return nil end
            return {view = view, target = row}
        end
    end
    return nil
end

return PlayerTargetState
