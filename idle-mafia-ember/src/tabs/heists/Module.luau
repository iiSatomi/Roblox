-- Heist start and sabotage are separate controls; sends remain protocol-gated.
local HeistsTab = {}
local Methods = {}
Methods.__index = Methods

local blocked = {
    heists = "Mutation sequence ownership unverified",
    heistCollect = "Result identity and sequence ownership unverified",
    sabotage = "Mutation sequence ownership unverified",
}

function HeistsTab.BuildUI(section, feature, bind, numeric)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "heists" and blocked[feature.id]
        and type(bind) == "function"
        and type(feature.custom) == "table" and type(numeric) == "table",
        "Invalid Heists UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", feature.id .. ".enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity; the status below shows whether this entry can run it.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    if #feature.policies > 0 then
        bind(group, "Dropdown", feature.id .. ".policy", {
            Text = "Goal", Options = feature.policies,
            Default = feature.policies[1],
        })
    end
    local custom
    if #feature.custom > 0 then
        custom = group:Group({Text = "Start limits", Open = false})
        for _, field in ipairs(feature.custom) do
            local key = feature.id .. ".custom." .. field.id
            if field.type == "number" then
                numeric[key] = true
                bind(custom, "Input", key, {Text = field.label, Default = tostring(field.value), FireOnBlur = true})
            elseif field.type == "boolean" then
                bind(custom, "Toggle", key, {Text = field.label, Default = field.value})
            elseif field.type == "select" then
                bind(custom, "Dropdown", key, {Text = field.label, Default = field.value, Options = field.options})
            else
                assert(field.type == "text", "Invalid Heist custom control")
                bind(custom, "Input", key, {Text = field.label, Default = field.value, FireOnBlur = true})
            end
        end
    end
    local row = { feature = feature, tabOwned = true, custom = custom,
        blockedReason = blocked[feature.id],
        status = group:Status({ Text = "Activity",
            Default = "Blocked — " .. blocked[feature.id] }) }
    if feature.limits then group:Description({ Text = feature.limits }) end
    return row
end

function HeistsTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.NativeHeistCatalog) == "table"
        and type(deps.NativeHeistCatalog.new) == "function"
        and type(deps.SequenceRecovery) == "table"
        and type(deps.SequenceRecovery.statusCall) == "function"
        and type(deps.SequenceRecovery.classify) == "function"
        and type(deps.BoardQuery) == "table"
        and type(deps.BoardQuery.new) == "function"
        and type(deps.BoardReadRuntime) == "table"
        and type(deps.BoardReadRuntime.new) == "function"
        and type(deps.HeistBoardState) == "table"
        and type(deps.HeistBoardState.read) == "function"
        and type(deps.HeistStart) == "table"
        and type(deps.HeistStart.propose) == "function"
        and type(deps.HeistStartEvidence) == "table"
        and type(deps.HeistStartEvidence.capture) == "function"
        and type(deps.HeistStartEvidence.evaluate) == "function"
        and type(deps.HeistCollect) == "table"
        and type(deps.HeistCollect.propose) == "function"
        and type(deps.HeistCollectEvidence) == "table"
        and type(deps.HeistCollectEvidence.capture) == "function"
        and type(deps.HeistCollectEvidence.evaluate) == "function"
        and type(deps.SabotageState) == "table"
        and type(deps.SabotageState.read) == "function"
        and type(deps.Sabotage) == "table"
        and type(deps.Sabotage.propose) == "function"
        and type(deps.SabotageEvidence) == "table"
        and type(deps.SabotageEvidence.capture) == "function"
        and type(deps.SabotageEvidence.evaluate) == "function",
        "Missing Heists tab modules")
    local catalog = deps.NativeHeistCatalog.new(deps.gameData,
        deps.fingerprint, deps.release)
    local boardQuery = deps.BoardQuery.new(deps.identity)
    return setmetatable({ id = "heists", deps = deps,
        catalog = catalog, recovery = deps.SequenceRecovery,
        boardQuery = boardQuery, closed = false }, Methods)
end

function Methods:Enrich(snapshot)
    if self.closed then return nil, "Heists tab closed" end
    return self.catalog:Enrich(snapshot)
end

function Methods:StatusCall(record, identity)
    return self.recovery.statusCall(record, identity)
end

function Methods:BoardCall()
    return self.boardQuery:Describe()
end

function Methods:StageBoard(snapshot, reply)
    if self.closed then return nil, "Heists tab closed" end
    local staged, reason = self.boardQuery:Stage(snapshot, reply)
    if not staged then return nil, reason end
    local proof = staged.heistBoardProof
    proof.sourceKey, proof.header = self.catalog.catalogKey, {}
    for _, field in ipairs({"session", "account", "place", "release", "revision", "capturedAt"}) do
        proof.header[field] = snapshot[field]
    end
    return staged, nil
end

function Methods:ReadSources(reader)
    if self.closed or type(reader) ~= "table" or type(reader.AttachHeistBoard) ~= "function" then return {} end
    return {{id = "heistBoard", interval = 5,
        enabled = function(settings)
            for _, id in ipairs({"heists", "heistCollect", "sabotage", "favors"}) do
                if type(settings[id]) == "table" and settings[id].enabled == true then return true end
            end
            return false
        end,
        prepare = function()
            if self.closed then return nil, "Heists tab closed" end
            return self:BoardCall()
        end,
        accept = function(snapshot, _, reply) return self:StageBoard(snapshot, reply) end,
        commit = function(staged) return not self.closed and reader:AttachHeistBoard(staged) end,
    }}
end

function Methods:Close() self.closed = true end

function Methods:NewBoardRead(budget, executor, currentSnapshot,
    onResult)
    return self.deps.BoardReadRuntime.new(budget, self.boardQuery,
        executor, currentSnapshot, onResult)
end

function Methods:Descriptors()
    local deps = self.deps
    return {
        { id = "heists", reader = deps.HeistBoardState,
            planner = deps.HeistStart,
            evidence = deps.HeistStartEvidence },
        { id = "heistCollect", reader = deps.HeistBoardState,
            planner = deps.HeistCollect,
            evidence = deps.HeistCollectEvidence },
        { id = "sabotage", reader = deps.SabotageState,
            planner = deps.Sabotage,
            evidence = deps.SabotageEvidence },
    }
end

return HeistsTab
