-- Playtime, verified-member Group and config-gated monthly claims.
local RewardsTab = {}
local Methods = {}
Methods.__index = Methods
local known = { playtime = true, groupBonus = true,
    monthlyRewards = true }

function RewardsTab.BuildUI(section, feature, bind)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "rewards" and known[feature.id]
        and type(bind) == "function", "Invalid Rewards UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", feature.id .. ".enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity for the prototype.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    if feature.id == "monthlyRewards" then
        group:Description({ Text = "The saved 0.26.530 monthly calendar is disabled; current config must enable it." })
    elseif feature.id == "groupBonus" then
        group:Description({ Text = "Only an existing, recently verified Group member is eligible." })
    end
    return { feature = feature, tabOwned = true,
        status = group:Status({ Text = "Activity",
            Default = "Off — UI only" }) }
end

function RewardsTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.NativeRewardsCatalog) == "table"
        and type(deps.NativeRewardsCatalog.new) == "function"
        and type(deps.PlaytimeState) == "table"
        and type(deps.PlaytimeState.read) == "function"
        and type(deps.Playtime) == "table"
        and type(deps.Playtime.propose) == "function"
        and type(deps.PlaytimeEvidence) == "table"
        and type(deps.PlaytimeEvidence.capture) == "function"
        and type(deps.PlaytimeEvidence.evaluate) == "function"
        and type(deps.GroupBonusState) == "table"
        and type(deps.GroupBonusState.read) == "function"
        and type(deps.GroupBonus) == "table"
        and type(deps.GroupBonus.propose) == "function"
        and type(deps.GroupBonusEvidence) == "table"
        and type(deps.GroupBonusEvidence.capture) == "function"
        and type(deps.GroupBonusEvidence.evaluate) == "function"
        and type(deps.MonthlyRewardsState) == "table"
        and type(deps.MonthlyRewardsState.read) == "function"
        and type(deps.MonthlyRewards) == "table"
        and type(deps.MonthlyRewards.propose) == "function"
        and type(deps.MonthlyRewardsEvidence) == "table"
        and type(deps.MonthlyRewardsEvidence.capture) == "function"
        and type(deps.MonthlyRewardsEvidence.evaluate) == "function",
        "Missing Rewards tab modules")
    local catalog = deps.NativeRewardsCatalog.new(deps.config,
        deps.fingerprint, deps.release)
    return setmetatable({ id = "rewards", deps = deps,
        catalog = catalog }, Methods)
end

function Methods:Enrich(snapshot)
    return self.catalog:Enrich(snapshot)
end

function Methods:Descriptors()
    local d = self.deps
    return {
        { id = "playtime", reader = d.PlaytimeState,
            planner = d.Playtime, evidence = d.PlaytimeEvidence },
        { id = "groupBonus", reader = d.GroupBonusState,
            planner = d.GroupBonus, evidence = d.GroupBonusEvidence },
        { id = "monthlyRewards", reader = d.MonthlyRewardsState,
            planner = d.MonthlyRewards,
            evidence = d.MonthlyRewardsEvidence },
    }
end

return RewardsTab
