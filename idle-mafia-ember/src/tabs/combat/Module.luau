-- Combat tab owns six separately configurable offline feature contracts.
local CombatTab = {}
local Methods = {}
Methods.__index = Methods

local rows = {
    { "bosses", "BossesState", "Bosses", "BossesEvidence" },
    { "globalBossAttack", "GlobalBossAttackState", "GlobalBossAttack", "GlobalBossAttackEvidence" },
    { "globalBossClaim", "GlobalBossClaimState", "GlobalBossClaim", "GlobalBossClaimEvidence" },
    { "familyBossAttacks", "FamilyBossAttackState", "FamilyBossAttacks", "FamilyBossAttacksEvidence" },
    { "familyBossClaims", "FamilyBossClaimState", "FamilyBossClaims", "FamilyBossClaimsEvidence" },
    { "bossShop", "BossShopBuyState", "BossShopBuy", "BossShopBuyEvidence" },
}

local known = { combat = true, warCombat = true }
for _, row in ipairs(rows) do known[row[1]] = true end

function CombatTab.BuildUI(section, feature, bind, numeric)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "combat" and known[feature.id]
        and type(bind) == "function" and type(numeric) == "table"
        and type(feature.custom) == "table"
        and type(feature.policies) == "table",
        "Invalid Combat UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", feature.id .. ".enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity for the prototype.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    if #feature.policies > 0 then
        bind(group, "Dropdown", feature.id .. ".policy", {
            Text = "Goal", Options = feature.policies,
            Default = feature.policies[1],
        })
    end
    local reason = (feature.id == "combat" or feature.id == "warCombat")
        and "Unavailable: player-target contract not implemented" or nil
    local row = { feature = feature, tabOwned = true, blockedReason = reason,
        status = group:Status({ Text = "Activity",
            Default = reason and ("Blocked — " .. reason) or "Off — UI only" }) }
    if feature.limits then group:Description({ Text = feature.limits }) end
    if #feature.custom > 0 then
        row.custom = group:Group({ Text = "Custom limits", Open = false })
        for _, field in ipairs(feature.custom) do
            local key = feature.id .. ".custom." .. field.id
            if field.type == "number" then
                numeric[key] = true
                bind(row.custom, "Input", key, {
                    Text = field.label, Default = tostring(field.value),
                    FireOnBlur = true,
                })
            else
                bind(row.custom, "Dropdown", key, {
                    Text = field.label, Default = field.value,
                    Options = field.options,
                })
            end
        end
    end
    return row
end

function CombatTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.HitListQuery) == "table"
        and type(deps.HitListQuery.new) == "function"
        and type(deps.PlayerTargetState) == "table"
        and type(deps.PlayerTargetState.read) == "function"
        and type(deps.BlockedFight) == "table"
        and type(deps.BlockedFight.new) == "function"
        and type(deps.combatRules) == "table",
        "Missing Combat tab modules")
    local descriptors = {}
    for index, row in ipairs(rows) do
        local reader, planner, evidence = deps[row[2]], deps[row[3]], deps[row[4]]
        assert(type(reader) == "table" and type(reader.read) == "function"
            and type(planner) == "table"
            and type(planner.propose) == "function"
            and type(evidence) == "table"
            and type(evidence.capture) == "function"
            and type(evidence.evaluate) == "function",
            "Missing Combat feature modules: " .. row[1])
        descriptors[index] = { id = row[1], reader = reader,
            planner = planner, evidence = evidence }
    end
    local player = deps.BlockedFight.new("combat")
    local war = deps.BlockedFight.new("warCombat")
    return setmetatable({ id = "combat", descriptors = descriptors,
        blocked = { { id = "combat", reader = player,
            planner = player, evidence = player },
            { id = "warCombat", reader = war,
            planner = war, evidence = war } },
        hitListQuery = deps.HitListQuery.new(deps.identity),
        targetReader = deps.PlayerTargetState,
        combatRules = deps.combatRules }, Methods)
end

function Methods:HitListCall(refresh)
    return self.hitListQuery:Describe(refresh)
end

function Methods:StageHitList(snapshot, reply)
    return self.hitListQuery:Stage(snapshot, reply)
end

function Methods:SearchCall(term)
    return self.hitListQuery:DescribeSearch(term)
end

function Methods:StageSearch(snapshot, reply, term)
    return self.hitListQuery:StageSearch(snapshot, reply, term)
end

function Methods:ReadTargets(raw, context)
    return self.targetReader.read(raw, context, self.combatRules)
end

function Methods:Descriptors()
    local result = {}
    for index, descriptor in ipairs(self.blocked) do
        result[index] = { id = descriptor.id,
            reader = descriptor.reader, planner = descriptor.planner,
            evidence = descriptor.evidence }
    end
    for index, descriptor in ipairs(self.descriptors) do
        result[index + #self.blocked] = { id = descriptor.id, reader = descriptor.reader,
            planner = descriptor.planner, evidence = descriptor.evidence }
    end
    return result
end

return CombatTab
