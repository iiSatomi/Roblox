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
        Description = "Select this activity; the status below shows whether this entry can run it.",
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
        and type(deps.RewardEffects) == "table"
        and type(deps.RewardEffects.new) == "function"
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
    local groupEvidence = type(deps.GroupBonusEvidence.new) == "function"
        and deps.GroupBonusEvidence.new(catalog) or deps.GroupBonusEvidence
    local playtimeEvidence, monthlyEvidence = deps.PlaytimeEvidence, deps.MonthlyRewardsEvidence
    local playtimeReader, monthlyReader = deps.PlaytimeState, deps.MonthlyRewardsState
    do
        playtimeEvidence = deps.RewardEffects.new(catalog, playtimeEvidence, "playtime", deps.rewardsSource)
        monthlyEvidence = deps.RewardEffects.new(catalog, monthlyEvidence, "monthlyRewards")
        playtimeReader = {read = function(raw, context)
            local view, reason = deps.PlaytimeState.read(raw, context)
            if not view then return nil, reason end
            local ready, skipped = {}, nil
            for _, row in ipairs(view.ready) do
                local supported, why = playtimeEvidence:Supports(raw, row.index)
                if supported then ready[#ready + 1] = row else skipped = skipped or why end
            end
            view.ready = ready
            if #ready == 0 and skipped then return nil, skipped end
            return view, nil
        end}
        monthlyReader = {read = function(raw, context)
            local view, reason = deps.MonthlyRewardsState.read(raw, context)
            if not view then return nil, reason end
            local supported, why = monthlyEvidence:Supports(raw, view.nextDay)
            if not supported then return nil, why end
            return view, nil
        end}
    end
    return setmetatable({ id = "rewards", deps = deps,
        catalog = catalog, groupEvidence = groupEvidence,
        playtimeEvidence = playtimeEvidence, monthlyEvidence = monthlyEvidence,
        playtimeReader = playtimeReader, monthlyReader = monthlyReader }, Methods)
end

function Methods:GroupEffect(snapshot)
    return self.catalog:GroupEffect(snapshot)
end

function Methods:Enrich(snapshot)
    return self.catalog:Enrich(snapshot)
end

function Methods:Descriptors()
    local d = self.deps
    return {
        { id = "playtime", reader = self.playtimeReader,
            planner = d.Playtime, evidence = self.playtimeEvidence, recoverSaved = self.playtimeEvidence.recoverSaved },
        { id = "groupBonus", reader = d.GroupBonusState,
            planner = d.GroupBonus, evidence = self.groupEvidence, recoverSaved = self.groupEvidence.recoverSaved },
        { id = "monthlyRewards", reader = self.monthlyReader,
            planner = d.MonthlyRewards,
            evidence = self.monthlyEvidence, recoverSaved = self.monthlyEvidence.recoverSaved },
    }
end

return RewardsTab
