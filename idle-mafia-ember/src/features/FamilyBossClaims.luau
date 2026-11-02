-- Exact current or unexpired historical Family reward claims.
local FamilyBossClaims = {}
local function familyId(value)
    return type(value) == "string" and #value > 0 and #value <= 120
        and not value:find("[%c]")
        or type(value) == "number" and value == value and value >= 1
            and value <= 9007199254740991 and value % 1 == 0
end
local function rewardKnown(row)
    for _, field in ipairs({"cash", "gold", "crates"}) do
        local value = row[field] or 0
        if type(value) ~= "number" or value ~= value or value < 0
            or value > 9007199254740991 or value % 1 ~= 0 then return false end
    end
    for _, field in ipairs({"crateId", "medal", "border"}) do
        local value = row[field]
        if value ~= nil and (type(value) ~= "string" or #value == 0 or #value > 120) then return false end
    end
    return ((row.crates or 0) == 0 or row.crateId ~= nil)
        and ((row.cash or 0) > 0 or (row.gold or 0) > 0 or (row.crates or 0) > 0
            or row.medal ~= nil or row.border ~= nil)
end

function FamilyBossClaims.propose(view, settings)
    if type(view) ~= "table" or type(settings) ~= "table" then
        return nil, "Missing Family claim planning input"
    end
    if settings.enabled ~= true then
        return nil, "Family reward claims disabled"
    end
    if view.status ~= "known" or type(view.week) ~= "number"
        or not familyId(view.famId)
        or type(view.serverNow) ~= "number"
        or type(view.claims) ~= "table"
        or type(view.claimedStages) ~= "table"
        or type(view.attemptedByWeek) ~= "table"
        or type(view.attemptCountByWeek) ~= "table" then
        return nil, "Current Family claim state required"
    end
    local claimed = {}
    for _, stage in ipairs(view.claimedStages) do
        claimed[stage] = true
    end
    local chosen
    for _, claim in ipairs(view.claims) do
        if type(claim) == "table" then
            local week, stage = claim.week, claim.stage
            local current = week == view.week
            local valid = type(week) == "number" and week >= 1
                and week <= view.week and week % 1 == 0
                and type(stage) == "number" and stage >= 0
                and stage <= 100 and stage % 1 == 0
            if current then
                valid = valid and view.inFamily == true
                    and stage >= 1 and stage <= 5
            end
            local attempted = view.attemptedByWeek[week]
            local attempts = view.attemptCountByWeek[week] or 0
            if valid and rewardKnown(claim) and type(claim.expiresAt) == "number"
                and claim.expiresAt > view.serverNow
                and attempts < 32
                and not (attempted and attempted[stage])
                and not (current and claimed[stage])
                and (not chosen or claim.expiresAt < chosen.expiresAt
                    or (claim.expiresAt == chosen.expiresAt
                        and week > chosen.week)
                    or (claim.expiresAt == chosen.expiresAt
                        and week == chosen.week and stage < chosen.stage)) then
                chosen = claim
            end
        end
    end
    if not chosen then
        return nil, "No unattempted unexpired Family reward claim"
    end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "familyBossClaims",
        actionKey = "familyBossClaims:" .. tostring(chosen.week)
            .. ":" .. tostring(chosen.stage),
        resources = {}, intent = { kind = "familyBossClaim",
            week = chosen.week, currentWeek = view.week,
            famId = view.famId, stage = chosen.stage,
            expiresAt = chosen.expiresAt,
            rewardCash = chosen.cash or 0, rewardGold = chosen.gold or 0,
            rewardCrates = chosen.crates or 0, rewardCrateId = chosen.crateId,
            rewardMedal = chosen.medal, rewardBorder = chosen.border,
            attemptsBefore = view.attemptCountByWeek[chosen.week] or 0 } }, nil
end

return FamilyBossClaims
