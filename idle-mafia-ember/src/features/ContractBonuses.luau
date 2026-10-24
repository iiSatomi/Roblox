-- One separately enabled earned Contract completion bonus.
local ContractBonuses = {}

function ContractBonuses.propose(view, settings)
    if type(view) ~= "table" or type(settings) ~= "table" then
        return nil, "Missing Contract bonus input"
    end
    if settings.enabled ~= true then return nil, "Contract bonuses disabled" end
    local bonus = type(view.ready) == "table" and view.ready[1]
    if type(bonus) ~= "table" or (bonus.period ~= "daily"
        and bonus.period ~= "weekly")
        or type(bonus.reset) ~= "number"
        or type(bonus.rowKey) ~= "string" or #bonus.rowKey == 0
        or type(view.catalogKey) ~= "string" or #view.catalogKey == 0 then
        return nil, "No replicated ready Contract bonus"
    end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "bonuses",
        actionKey = "contract-bonus:" .. bonus.period .. ":" .. bonus.reset,
        resources = {},
        intent = { kind = "contractBonusClaim", period = bonus.period,
            command = bonus.period == "daily" and "claimbonus"
                or "claimweeklybonus", reset = bonus.reset,
            catalogKey = view.catalogKey, rowKey = bonus.rowKey,
            rewardKind = bonus.rewardKind,
            rewardSeals = bonus.rewardSeals,
            rewardItem = bonus.rewardItem },
    }, nil
end

return ContractBonuses
