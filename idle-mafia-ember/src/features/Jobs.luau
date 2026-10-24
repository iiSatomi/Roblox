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
    if settings.city ~= nil then
        return nil, "City-specific Job eligibility is unverified"
    end
    local policy = settings.policy
    if policy ~= "Balanced" and policy ~= "XP" and policy ~= "Cash"
        and policy ~= "Mastery" and policy ~= "Selected job" then
        return nil, "Jobs policy has no verified parameters"
    end
    if policy == "Selected job" and (type(settings.selectedJobId) ~= "string"
        or #settings.selectedJobId == 0) then
        return nil, "Selected Job ID missing"
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
    local available = view.energy - reserved - uncertain
    if available < 1 then return nil, "Energy reserved or unavailable" end
    local eligible, maxXp, maxCash = {}, 0, 0
    for _, job in ipairs(view.jobs) do
        if type(job) == "table" and type(job.id) == "string"
            and nonnegative(job.cost) and job.cost >= 1
            and nonnegative(job.level) and nonnegative(job.xp)
            and nonnegative(job.cash) and job.level <= view.level
            and job.cost <= available then
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
        elseif policy == "Balanced" then
            local xp = maxXp > 0 and job.xp / maxXp or 0
            local cash = maxCash > 0 and job.cash / maxCash or 0
            score = (xp + cash) / job.cost
        elseif policy == "Mastery" and nonnegative(job.masteryTier)
            and job.masteryTier % 1 == 0
            and nonnegative(job.masteryProgress) then
            local nextRule = view.masteryRules[job.masteryTier + 1]
            if nextRule then
                local remaining = math.max(0,
                    nextRule.completions - job.masteryProgress)
                score = -remaining
            end
        end
        if score and chooseBetter(job, score, best, bestScore) then
            best, bestScore = job, score
        end
    end
    if not best then return nil, "No Job matches selected policy" end
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
