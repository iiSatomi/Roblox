-- Bounded selection only. Transport, durable usage and fresh source ownership
-- belong to the existing Combat runtime; estimates never prove a fight outcome.
local TargetSelection = {}
local MAX = 9007199254740991
local function number(value, low)
    return type(value) == "number" and value == value and value >= low and value <= MAX
end
local function integer(value, low) return number(value, low) and value % 1 == 0 end
local function familyId(value, minimum)
    return type(value) == "string" and #value > 0 and #value <= 120
        and not value:find("[%c]") or integer(value, minimum)
end
local function dense(rows, limit)
    if type(rows) ~= "table" or #rows > limit then return false end
    local count = 0
    for key in pairs(rows) do
        if not integer(key, 1) or key > #rows then return false end
        count = count + 1
    end
    return count == #rows
end

-- The legacy bounded-variance model, retained as an estimate rather than a
-- promise about server rolls. Current Config supplies variance and its cap.
function TargetSelection.winChance(attack, defense, variance, cap)
    if not number(attack, 1) or not number(defense, 1)
        or not number(variance, 0) or not number(cap, 0) then return nil end
    local av, dv = math.min(attack * variance, cap), math.min(defense * variance, cap)
    local a0, a1, d0, d1 = attack - av, attack + av, defense - dv, defense + dv
    if a0 >= d1 then return 1 end
    if a1 <= d0 then return 0 end
    if d0 == d1 then return math.max(0, math.min(1, (a1 - d0) / (a1 - a0))) end
    if a0 == a1 then return math.max(0, math.min(1, (a0 - d0) / (d1 - d0))) end
    local below = math.max(0, math.min(d1, a0) - d0)
    local lo, hi = math.max(d0, a0), math.min(d1, a1)
    local middle = hi > lo and (a1 * (hi - lo) - (hi * hi - lo * lo) / 2) / (a1 - a0) or 0
    return math.max(0, math.min(1, (below + middle) / (d1 - d0)))
end

local function history(rows, now)
    if not dense(rows, 64) then return nil end
    local recent, samples, wins = {}, 0, 0
    for _, row in ipairs(rows) do
        if type(row) ~= "table" or not number(row.at, 0) or row.at > now
            or not integer(row.cash, 0) or type(row.won) ~= "boolean" then return nil end
        if now - row.at <= 30 * 86400 then
            samples = samples + 1
            wins = wins + (row.won and 1 or 0)
            recent[#recent + 1] = row
        end
    end
    table.sort(recent, function(a, b) return a.at > b.at end)
    local payout, weight = 0, 0
    for index = 1, math.min(5, #recent) do
        local factor = 2 ^ (1 - index)
        payout, weight = payout + recent[index].cash * factor, weight + factor
    end
    return {samples = samples, winRate = samples > 0 and wins / samples * 100 or 0,
        payout = weight > 0 and payout / weight or 0}
end

function TargetSelection.history(rows, now)
    if not number(now, 0) then return nil end
    return history(rows, now)
end

local function scoringWar(war, now)
    return war.canScore == true and number(war.statusServerNow, 0)
        and math.abs(now - war.statusServerNow) <= 10
        and math.floor(now / 86400) == math.floor(war.statusServerNow / 86400)
        and (war.eligibleAt == nil or number(war.eligibleAt, 0) and war.eligibleAt <= now)
        and integer(war.ownRemaining, 0) and integer(war.ownCap, 0) and war.ownRemaining <= war.ownCap
end
local function scoringTarget(row, now)
    local allowance = row.warStatus
    return type(allowance) == "table" and allowance.day == math.floor(now / 86400) and allowance.canScore == true
        and integer(allowance.remaining, 1) and integer(allowance.cap, 1) and allowance.remaining <= allowance.cap
        and integer(allowance.attacksRemaining, 1) and integer(allowance.attacksCap, 1)
        and allowance.attacksRemaining <= allowance.attacksCap and integer(allowance.pairRemaining, 1)
end

-- Bounded scalar profile lists; names never grant permission. A configured
-- ally always wins conflict with enemy targeting. Reusable by future hostile lanes.
function TargetSelection.relations(settings)
    local function ids(value)
        if value == nil then value = "" end
        if type(value) ~= "string" or #value > 7743 then return nil end
        local out, count = {}, 0
        if value:match("^%s*$") then return out end
        for raw in (value .. ","):gmatch("(.-),") do
            local id = raw:match("^%s*(.-)%s*$")
            count = count + 1
            if count > 64 or #id > 120 or id == "0" or not id:match("^[%w_%-]+$") then return nil end
            out[id] = true
        end
        return out
    end
    local allies, enemies = ids(settings.relationAllies), ids(settings.relationEnemies)
    local mode = settings.enemyMode or "Off"
    if not allies or not enemies or (mode ~= "Off" and mode ~= "Prefer enemies" and mode ~= "Enemies only") then return nil end
    return {allies = allies, enemies = enemies, mode = mode}
end
function TargetSelection.familyAllowed(policy, id)
    if not policy or not familyId(id, 0) then return false end
    local key = tostring(id)
    return not policy.allies[key] and (policy.mode ~= "Enemies only" or policy.enemies[key] == true)
end

function TargetSelection.choose(view, settings, held, mode)
    if type(view) ~= "table" or type(settings) ~= "table" or type(held) ~= "table"
        or (mode ~= "combat" and mode ~= "warCombat") then return nil, "Missing target selection input" end
    if settings.enabled ~= true then return nil, "Player mode disabled" end
    local relations = TargetSelection.relations(settings)
    if not relations then return nil, "Invalid Alliance/Enemy preferences" end
    if view.status ~= "known" or not number(view.serverNow, 0)
        or not integer(view.ownUserId, 1) or not familyId(view.ownFamilyId, 0)
        or not number(view.health, 0) or not number(view.maxHealth, 1) or view.health > view.maxHealth
        or not number(view.stamina, 0) or not number(view.attack, 1)
        or not integer(view.hospitalHealth, 1) or not integer(view.scoutCost, 1)
        or not number(view.fightVariance, 0) or not number(view.fightVarianceCap, 0)
        or not dense(view.targets, 128) or view.manualChallenge == true
        or view.maxNativeStaminaCost ~= nil and (not integer(view.maxNativeStaminaCost, 1) or view.maxNativeStaminaCost > 5) then
        return nil, "Current player resources, identity and native rules required"
    end
    for _, field in ipairs({"minimumPayout", "maxScoutSpend", "maxAttackSpend", "minSamples"}) do
        if not integer(settings[field], 0) then return nil, "Explicit player limits required" end
    end
    if not number(settings.staminaReserve, 0) or settings.staminaReserve > 1e12 then return nil, "Invalid player stamina reserve" end
    if settings.preferHighValue ~= nil and type(settings.preferHighValue) ~= "boolean" then return nil, "Invalid high-value preference" end
    local highPreferred = mode == "combat" and settings.preferHighValue == true and view.highValueKnown == true
    local targetSource = settings.targetSource
    if targetSource == "Saved only + lookup" then targetSource = "Saved only"
    elseif targetSource == "Saved and new + lookup" then targetSource = "Saved and new" end
    local highOnly = targetSource == "High value only" or targetSource == "High value only + lookup"
    if highOnly then
        if mode ~= "combat" or view.highValueKnown ~= true then return nil, "Known owned high-value history required" end
        targetSource = "Saved and new"
    end
    local priority = settings.targetPriority
    if priority == nil then priority = "Risk-adjusted value" end
    if priority ~= "Risk-adjusted value" and priority ~= "Value / stamina" and priority ~= "Recent payout"
        and priority ~= "Safest history" and priority ~= "Highest eligible level" then
        return nil, "Invalid player target priority"
    end
    local minStaminaCost = settings.minStaminaCost
    if minStaminaCost == nil then minStaminaCost = 1 end -- Compatible callers retain the native floor.
    if not integer(minStaminaCost, 1) or minStaminaCost > 5
        or not number(settings.healthFloor, 1) or settings.healthFloor > 100
        or not number(settings.minWinRate, 0) or settings.minWinRate > 100
        or not number(settings.minWinChance, 0) or settings.minWinChance > 100
        or not number(settings.minPowerRatio, 0.01)
        or not number(settings.scoutMaxAge, 1) or settings.scoutMaxAge > 1800
        or not integer(settings.maxStaminaCost, 1) or settings.maxStaminaCost > 5 or settings.maxStaminaCost < minStaminaCost
        or not integer(settings.minTargetLevel, 1) or not integer(settings.maxTargetLevel, settings.minTargetLevel)
        or settings.dailyOnly ~= nil and type(settings.dailyOnly) ~= "boolean"
        or (targetSource ~= "Saved only" and targetSource ~= "Saved and new")
        or (settings.policy ~= "Cautious" and settings.policy ~= "Balanced" and settings.policy ~= "Custom") then
        return nil, "Invalid player target limits"
    end
    for _, field in ipairs({"stamina", "health", "attackSpent", "scoutSpent"}) do
        if not number(held[field], 0) then return nil, "Trusted player usage and custody required" end
    end
    local floor = math.max(view.hospitalHealth, view.maxHealth * settings.healthFloor / 100)
    if view.health < held.health + floor then return nil, "Player Health reserve" end
    local war = type(view.war) == "table" and view.war or {}
    if war.active == true and (not familyId(war.enemyFamilyId, 1)
        or view.ownFamilyId ~= 0 and type(war.enemyFamilyId) ~= type(view.ownFamilyId)) then
        return nil, "Consistent current enemy Family identity required"
    end
    if mode == "warCombat" and (war.active ~= true or not familyId(war.enemyFamilyId, 1)
        or war.enemyFamilyId == view.ownFamilyId) then return nil, "Verified active enemy Family required" end
    if mode == "warCombat" and not scoringWar(war, view.serverNow) then
        return nil, "Current native war scoring allowance required"
    end
    local seen = {}
    for _, row in ipairs(view.targets) do
        if type(row) ~= "table" or not integer(row.userId, 1) or seen[row.userId] then
            return nil, "Ambiguous player target identity"
        end
        seen[row.userId] = true
    end
    local minWinRate = math.max(settings.minWinRate, settings.policy == "Cautious" and 90 or 0)
    local minChance = math.max(settings.minWinChance, settings.policy == "Cautious" and 90 or 0)
    local best
    for _, row in ipairs(view.targets) do
        local saved = history(row.history, view.serverNow)
        local warTarget = mode == "warCombat"
        local attackExposure = view.maxNativeStaminaCost
        if attackExposure == nil then attackExposure = row.staminaCost end
        local excludedEnemy = not warTarget and war.active == true and row.familyId == war.enemyFamilyId
        local eligible = saved and (not highOnly or row.highValue == true) and row.userId ~= view.ownUserId and row.friend == false
            and TargetSelection.familyAllowed(relations, row.familyId)
            and (row.familyId == 0 or view.ownFamilyId == 0 or type(row.familyId) == type(view.ownFamilyId))
            and (view.ownFamilyId == 0 or row.familyId ~= view.ownFamilyId)
            and not excludedEnemy and type(row.name) == "string" and #row.name > 0 and #row.name <= 64
            and integer(row.level, settings.minTargetLevel) and row.level <= settings.maxTargetLevel
            and integer(row.staminaCost, minStaminaCost) and row.staminaCost <= settings.maxStaminaCost
            and integer(attackExposure, row.staminaCost) and attackExposure <= 5
            and (warTarget or settings.dailyOnly ~= true or integer(row.attacksToday, 0) and row.attacksToday == 0)
            and integer(row.remainingDaily, 1) and number(row.shieldUntil, 0) and row.shieldUntil <= view.serverNow
            and number(row.cooldownUntil, 0) and row.cooldownUntil <= view.serverNow
            and held.attackSpent + attackExposure <= settings.maxAttackSpend
            and view.stamina >= attackExposure + held.stamina + settings.staminaReserve
            and (targetSource ~= "Saved only" or saved.samples > 0)
            and saved.samples >= settings.minSamples
            and (saved.samples == 0 and settings.minimumPayout == 0 or saved.payout >= settings.minimumPayout)
            and (saved.samples == 0 or saved.winRate >= minWinRate)
            and (not warTarget or row.warFamilyId == war.enemyFamilyId and row.familyId == war.enemyFamilyId
                and scoringTarget(row, view.serverNow))
        if eligible then
            local stats = row.stats
            local fresh = type(stats) == "table" and number(stats.at, 0) and stats.at <= view.serverNow
                and view.serverNow - stats.at <= settings.scoutMaxAge and stats.level == row.level
                and number(stats.defense, 1) and (stats.kind == "scout" or not warTarget and stats.kind == "public")
            local chance = fresh and TargetSelection.winChance(view.attack, stats.defense,
                view.fightVariance, view.fightVarianceCap) or nil
            local kind, cost, exposure = "attack", row.staminaCost, attackExposure
            if not fresh then
                local scoutCost = row.scoutCost
                if scoutCost == nil then scoutCost = view.scoutCost end
                local scoutExposure = view.maxNativeStaminaCost
                if scoutExposure == nil then scoutExposure = scoutCost end
                -- Public stats can be refreshed without spending Scout Stamina.
                eligible = not (not warTarget and type(stats) == "table" and stats.kind == "public")
                    and settings.allowScout == true and integer(scoutCost, 1) and scoutCost <= 5
                    and integer(scoutExposure, scoutCost) and scoutExposure <= 5
                    and held.scoutSpent + scoutExposure <= settings.maxScoutSpend
                    and view.stamina >= scoutExposure + attackExposure + held.stamina + settings.staminaReserve
                kind, cost, exposure = "scout", scoutCost, scoutExposure
            else
                eligible = chance ~= nil and chance * 100 >= minChance
                    and (not warTarget or stats.kind == "scout" and view.attack / stats.defense >= settings.minPowerRatio)
            end
            if eligible then
                local selected = {userId = row.userId, name = row.name, level = row.level,
                    kind = kind, cost = cost, exposure = exposure, attackCost = row.staminaCost, attackExposure = attackExposure,
                    familyId = row.familyId, warFamilyId = row.warFamilyId,
                    highValue = view.highValueKnown == true and row.highValue == true,
                    samples = saved.samples, payout = saved.payout, winRate = saved.winRate,
                    chance = chance, statsAt = fresh and stats.at or nil,
                    defense = fresh and stats.defense or nil}
                local score, second, third = saved.payout * (chance or 1) ^ 2, 0, 0
                if priority == "Value / stamina" then score = saved.payout / row.staminaCost
                elseif priority == "Recent payout" then score = saved.payout
                elseif priority == "Safest history" then score, second = chance or 0, saved.payout
                elseif priority == "Highest eligible level" then score, second, third = row.level, saved.winRate, saved.payout end
                local tier = (relations.mode == "Prefer enemies" and relations.enemies[tostring(row.familyId)] and 2 or 0)
                    + (highPreferred and row.highValue == true and 1 or 0)
                if not best or tier > best.highValueTier or tier == best.highValueTier
                    and ((saved.samples > 0 and best.samples == 0)
                        or ((saved.samples > 0) == (best.samples > 0)
                            and (score > best.score or score == best.score and (second > best.second
                                or second == best.second and (third > best.third or third == best.third and row.userId < best.userId))))) then
                    selected.highValueTier = tier
                    selected.score, selected.second, selected.third = score, second, third
                    best = selected
                end
            end
        end
    end
    return best, best == nil and "No eligible player target with fresh required evidence" or nil
end
return TargetSelection
