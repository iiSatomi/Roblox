-- Heist start and sabotage are separate controls; sends remain protocol-gated.
local HeistsTab = {}
local Methods = {}
Methods.__index = Methods

local blocked = {
    heists = "Mutation sequence ownership unverified",
    heistCollect = "Result identity and sequence ownership unverified",
    sabotage = "Mutation sequence ownership unverified",
}

function HeistsTab.BuildUI(section, feature, bind, nativeAvailable)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "heists" and blocked[feature.id]
        and type(bind) == "function"
        and type(feature.custom) == "table" and #feature.custom == 0,
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
    local unavailable = nativeAvailable ~= true and blocked[feature.id] or nil
    local row = { feature = feature, tabOwned = true,
        blockedReason = unavailable,
        status = group:Status({ Text = "Activity",
            Default = unavailable and ("Blocked — " .. unavailable) or "Off" }) }
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
    local runtime = deps.heistRuntime
    if runtime == nil and type(deps.HeistRuntime) == "table" and deps.nativeHeistController ~= nil then
        local reason
        runtime, reason = deps.HeistRuntime.new(deps)
        assert(runtime, reason or "Heist lifecycle unavailable")
        deps.heistRuntime = runtime -- Shared with the separately owned Favors tab.
    end
    return setmetatable({ id = "heists", deps = deps,
        catalog = catalog, recovery = deps.SequenceRecovery,
        boardQuery = boardQuery, closed = false, runtime = runtime,
        ownedProofs = {"heistControllerProof"} }, Methods)
end

function Methods:Enrich(snapshot)
    local enriched, reason = self.catalog:Enrich(snapshot)
    if not enriched then return nil, reason end
    return self.runtime and self.runtime:Enrich(enriched) or enriched, nil
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
    local sources = {{id = "heistBoard", interval = 5,
        confirmFeatures = {heists = true, heistCollect = true, favors = true, sabotage = true},
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
    if self.runtime then
        for _, source in ipairs(self.runtime:ReadSources()) do sources[#sources + 1] = source end
    end
    return sources
end

function Methods:Close()
    self.closed = true
    if self.runtime then self.runtime:Close() end
end

function Methods:NewBoardRead(budget, executor, currentSnapshot,
    onResult)
    return self.deps.BoardReadRuntime.new(budget, self.boardQuery,
        executor, currentSnapshot, onResult)
end

function Methods:Descriptors()
    local deps = self.deps
    local features = {
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
    if self.runtime then
        for index, feature in ipairs(features) do features[index] = self.runtime:Feature(feature) end
    end
    return features
end

return HeistsTab
