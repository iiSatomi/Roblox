-- Pure ordinary-Job policy. A verified native adapter must translate intent to transport.
local Jobs = {}

local function nonnegative(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

local function chooseBetter(candidate, score, best, bestScore)
    return not best or score > bestScore
        or (score == bestScore and candidate.id < best.id)
end

function Jobs.propose(view, settings, reservations)
    if type(view) ~= "table" or type(settings) ~= "table"
        or type(reservations) ~= "table" then
        return nil, "Missing Jobs planning input"
    end
    if settings.enabled ~= true then return nil, "Jobs disabled" end
    local city = settings.city
    if city == "" or city == "All unlocked cities" then city = nil end
    if city ~= nil and (type(city) ~= "string" or type(view.cities) ~= "table" or view.cities[city] ~= true) then
        return nil, "City-specific Job membership is unverified or unavailable"
    end
    local policy = settings.policy
    if policy ~= "Balanced" and policy ~= "XP" and policy ~= "Cash"
        and policy ~= "Mastery" and policy ~= "Selected job"
        and policy ~= "Job count" and policy ~= "Highest tier" then
        return nil, "Jobs policy has no verified parameters"
    end
    if policy == "Selected job" and (type(settings.selectedJobId) ~= "string"
        or #settings.selectedJobId == 0) then
        return nil, "Selected Job ID missing"
    end
    if settings.limitsEnabled ~= nil and type(settings.limitsEnabled) ~= "boolean" then
        return nil, "Invalid Job bounds setting"
    end
    local limited = settings.limitsEnabled == true
    local minLevel, maxLevel = settings.minLevel or 1, settings.maxLevel or 10000
    local minCost, maxCost = settings.minCost or 0, settings.maxCost or 1000000000000
    if limited and (not nonnegative(minLevel) or not nonnegative(maxLevel)
        or minLevel < 1 or maxLevel < minLevel or minLevel % 1 ~= 0 or maxLevel % 1 ~= 0
        or not nonnegative(minCost) or not nonnegative(maxCost)
        or minCost % 1 ~= 0 or maxCost % 1 ~= 0 or maxCost < minCost) then
        return nil, "Invalid or inverted Job level/cost bounds"
    end
    local reserved = reservations.energy or 0
    local uncertain = reservations.uncertainEnergy or 0
    if not nonnegative(reserved) or not nonnegative(uncertain)
        or not nonnegative(view.energy) or type(view.jobs) ~= "table"
        or type(view.masteryRules) ~= "table"
        or not nonnegative(view.level) or not nonnegative(view.revision)
        or view.revision % 1 ~= 0
        or type(view.catalogKey) ~= "string" or #view.catalogKey == 0 then
        return nil, "Invalid Job resource view"
    end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(view[field]) ~= "string" or #view[field] == 0 then
            return nil, "Invalid Job identity"
        end
    end
    local masteryLimit, masteryCompletions
    if policy == "Mastery" and settings.masteryTarget ~= nil and settings.masteryTarget ~= "All native tiers" then
        if type(settings.masteryTarget) ~= "string" then return nil, "Invalid native Mastery target" end
        for index, rule in ipairs(view.masteryRules) do
            if type(rule) == "table" and rule.name == settings.masteryTarget then
                if masteryLimit or not nonnegative(rule.completions) or rule.completions < 1 then
                    return nil, "Native Mastery target is ambiguous"
                end
                masteryLimit, masteryCompletions = index, rule.completions
            end
        end
        if not masteryLimit then return nil, "Named native Mastery target is unverified or unavailable" end
    end
    local capacity = view.capacityEnergy
    if policy == "Highest tier" and (not nonnegative(capacity) or capacity <= 0) then
        return nil, "Native maximum energy capacity is unverified"
    end
    local floor = settings.energyReserve or 0
    if not nonnegative(floor) or floor % 1 ~= 0 or floor > 1000000000000 then return nil, "Invalid shared energy reserve" end
    local available = view.energy - reserved - uncertain - floor
    if available < 1 then return nil, "Energy reserved or unavailable" end
    local ceiling = policy == "Highest tier" and (capacity - floor) or available
    local eligible, maxXp, maxCash = {}, 0, 0
    for _, job in ipairs(view.jobs) do
        if type(job) == "table" and type(job.id) == "string"
            and nonnegative(job.cost) and job.cost >= 1
            and nonnegative(job.level) and nonnegative(job.xp)
            and nonnegative(job.cash) and job.level <= view.level
            and job.cost <= ceiling and (not city or job.cityId == city)
            and (not limited or job.level >= minLevel and job.level <= maxLevel
                and job.cost >= minCost and job.cost <= maxCost) then
            if policy == "Highest tier" and (not nonnegative(job.tier) or job.tier < 1 or job.tier % 1 ~= 0) then
                return nil, "Native Job tier is unverified"
            end
            eligible[#eligible + 1] = job
            maxXp = math.max(maxXp, job.xp)
            maxCash = math.max(maxCash, job.cash)
        end
    end
    if #eligible == 0 then return nil, "No unlocked Job within energy reserve" end
    local best, bestScore = nil, nil
    for _, job in ipairs(eligible) do
        local score = nil
        if policy == "Selected job" then
            if job.id == settings.selectedJobId then score = 1 end
        elseif policy == "XP" then
            score = job.xp / job.cost
        elseif policy == "Cash" then
            score = job.cash / job.cost
        elseif policy == "Job count" then
            score = -job.cost
        elseif policy == "Highest tier" then
            score = job.tier
        elseif policy == "Balanced" then
            local xp = maxXp > 0 and job.xp / maxXp or 0
            local cash = maxCash > 0 and job.cash / maxCash or 0
            score = (xp + cash) / job.cost
        elseif policy == "Mastery" and nonnegative(job.masteryTier)
            and job.masteryTier % 1 == 0
            and nonnegative(job.masteryProgress)
            and (not masteryLimit or job.masteryTier < masteryLimit and job.masteryProgress < masteryCompletions) then
            local nextRule = view.masteryRules[job.masteryTier + 1]
            if nextRule then
                local remaining = math.max(0,
                    nextRule.completions - job.masteryProgress)
                score = -remaining
            end
        end
        local better = score and chooseBetter(job, score, best, bestScore)
        if policy == "Highest tier" then
            better = not best or job.tier > best.tier or job.tier == best.tier and job.level > best.level
        end
        if better then best, bestScore = job, score end
    end
    if not best then return nil, "No Job matches selected policy" end
    if policy == "Highest tier" and best.cost > available then
        return nil, "Waiting for energy for the highest native Job tier"
    end
    local key = "jobs:" .. #view.catalogKey .. ":" .. view.catalogKey
        .. ":" .. #best.id .. ":" .. best.id .. ":" .. view.revision
    return {
        session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "jobs", actionKey = key,
        resources = { energy = best.cost },
        intent = { kind = "job", targetId = best.id,
            expectedCost = best.cost, catalogKey = view.catalogKey },
    }, nil
end

return Jobs
