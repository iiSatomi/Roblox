-- Territory owns holdings reads and bounded selected Station/admission routes.
local TerritoryTab = {}
local Methods = {}
Methods.__index = Methods

local known = { territoryWatch = true, station = true,
    residency = true }
local limitations = {
    station = "Station or recall one selected own member using current deployment identity, defense reserves and a bounded deployment attempt limit. Uncertain recalls remain held for status checks.",
    residency = "Compare the selected resident contribution and rent using current native bonuses and caps. Replacement must improve the same bonus without higher rent, or lower rent without losing that bonus. Different bonus kinds and unverified tradeoffs are unavailable.",
}

function TerritoryTab.BuildUI(section, feature, bind, numeric)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "territory" and known[feature.id]
        and type(bind) == "function", "Invalid Territory UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", feature.id .. ".enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity; the status below shows whether this entry can run it.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    local reason = limitations[feature.id]
    if reason then group:Description({ Text = reason }) end
    if feature.id == "residency" then
        bind(group, "Dropdown", "residency.policy", {
            Text = "Goal", Options = feature.policies,
            Default = feature.policies[1],
        })
    end
    numeric = numeric or {}
    local custom
    if #feature.custom > 0 then
        custom = group:Group({ Text = "Selection and limits", Open = false })
        for _, field in ipairs(feature.custom) do
            local key = feature.id .. ".custom." .. field.id
            if field.type == "number" or field.type == "text" then
                numeric[key] = field.type == "number" or nil
                bind(custom, "Input", key, { Text = field.label, Default = tostring(field.value), FireOnBlur = true })
            elseif field.type == "boolean" then
                bind(custom, "Toggle", key, { Text = field.label, Default = field.value })
            else
                assert(field.type == "select", "Invalid Territory preference")
                bind(custom, "Dropdown", key, { Text = field.label, Default = field.value, Options = field.options })
            end
        end
    end
    return { feature = feature, tabOwned = true,
        custom = custom,
        status = group:Status({ Text = "Activity",
            Default = "Off — current client information required" }) }
end

function TerritoryTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.TerritoryMapQuery) == "table"
        and type(deps.TerritoryMapQuery.new) == "function"
        and type(deps.ResidencyQuery) == "table"
        and type(deps.ResidencyQuery.new) == "function"
        and type(deps.TerritoryState) == "table"
        and type(deps.TerritoryState.read) == "function"
        and type(deps.ReadAttachment) == "table"
        and type(deps.ReadAttachment.attach) == "function"
        and type(deps.TerritoryBlocked) == "table"
        and type(deps.TerritoryBlocked.propose) == "function"
        and type(deps.TerritoryBlocked.capture) == "function"
        and type(deps.TerritoryBlocked.evaluate) == "function",
        "Missing Territory tab modules")
    local station
    if type(deps.Stationing) == "table" and type(deps.config) == "table"
        and type(deps.config.TERRITORY) == "table" and type(deps.gameData) == "table"
        and type(deps.gameData.DISTRICTS_BY_ID) == "table" then
        station = deps.Stationing.new(deps.config, deps.gameData, deps.fingerprint, deps.release, deps.cityMaps)
    end
    local season = deps.territorySeasonSource
    if season ~= nil then
        assert(type(season) == "table" and type(season.Enrich) == "function"
            and type(season.Read) == "function" and season.release == deps.release
            and type(deps.fingerprint) == "string" and season.sourceKey == deps.fingerprint:lower(),
            "Invalid current Territory season source")
    end
    local readOwner
    if type(deps.TerritoryReadSources) == "table" then readOwner = deps.TerritoryReadSources.new(deps) end
    local recall, recallReason
    if station and type(deps.RecallRuntime) == "table" and type(deps.storage) == "table"
        and deps.storage.strictRecovery == true and type(deps.identity) == "table" then
        recall, recallReason = deps.RecallRuntime.new(deps)
        assert(recall, recallReason or "Recall custody unavailable")
    end
    return setmetatable({ id = "territory", ownedProofs = {"stationCatalogProof"}, deps = deps, station = station,
        season = season, readOwner = readOwner, recall = recall }, Methods)
end

function Methods:ReadSources(reader)
    local sources = self.readOwner and self.readOwner:Sources(reader) or {}
    if self.recall then
        for _, source in ipairs(self.recall:ReadSources()) do sources[#sources + 1] = source end
    end
    return sources
end

function Methods:ReservationSources()
    return self.recall and self.recall:ReservationSources() or {}
end

function Methods:Close()
    self.closed, self.latestSnapshot = true, nil
    if self.readOwner then self.readOwner:Close() end
    if self.season then self.season:Close() end
    if self.recall then self.recall:Close() end
end

function Methods:Enrich(snapshot)
    local result = snapshot
    if self.station then result = self.station:Enrich(result) or result end
    if self.season then result = self.season:Enrich(result) or result end
    if self.recall then result = self.recall:Enrich(result) or result end
    self.latestSnapshot = result
    return result, nil
end

function Methods:NewDistrictQuery()
    local source = self.deps.DistrictQuery
    if type(source) ~= "table" then return nil, "District reader unavailable" end
    return source.new(), nil
end

function Methods:NewFortificationQuery()
    local source = self.deps.FortificationQuery
    if type(source) ~= "table" then return nil, "Fortification reader unavailable" end
    return source.new(), nil
end

function Methods:AttachFortification(snapshot, accepted)
    local source = self.deps.FortificationQuery
    if type(source) ~= "table" or type(snapshot) ~= "table" then
        return nil, "Fortification reader unavailable"
    end
    local candidate = {}
    for key, value in pairs(snapshot) do candidate[key] = value end
    candidate.fortificationView = accepted
    local view, reason = source.read(candidate, candidate)
    if not view then return nil, reason end
    candidate.fortificationView = view
    return candidate, nil
end

function Methods:NewSeasonSource(readLive, status)
    local source = self.deps.TerritorySeasonSource
    if type(source) ~= "table" then return nil, "Native season source unavailable" end
    return source.new(readLive, status, self.deps.fingerprint, self.deps.release)
end

function Methods:NewRecallTransactions(storage, scope)
    local source = self.deps.RecallTransactions
    local config = self.deps.config
    if type(source) ~= "table" or type(source.new) ~= "function"
        or type(config) ~= "table" or type(config.TERRITORY) ~= "table" then
        return nil, "Reviewed recall transaction capabilities unavailable"
    end
    return source.new(storage, scope, { release = self.deps.release,
        recallCooldownSeconds = config.TERRITORY.recallCooldownSeconds })
end

function Methods:PreviewResidency(snapshot, context, settings)
    local source = self.deps.Residency
    if type(source) ~= "table" then return nil, "Residency preview unavailable" end
    return source.preview(snapshot, context, settings)
end

function Methods:ReadBonuses(snapshot, context)
    local source = self.deps.TerritoryBonuses
    if type(source) ~= "table" then return nil, "Holder bonus reader unavailable" end
    return source.read(snapshot, context)
end

function Methods:NewMapQuery()
    return self.deps.TerritoryMapQuery.new()
end

function Methods:NewResidencyQuery()
    return self.deps.ResidencyQuery.new()
end

function Methods:AttachReads(snapshot, map, residency)
    return self.deps.ReadAttachment.attach(snapshot, map, residency)
end

function Methods:NewReadRuntime(budget, executor,
    currentSnapshot, onResult)
    local module = self.deps.TerritoryReadRuntime
    if type(module) ~= "table"
        or type(module.new) ~= "function" then
        return nil, "Territory read scheduler unavailable"
    end
    local ok, runtime = pcall(module.new, budget,
        self:NewMapQuery(), self:NewResidencyQuery(),
        self.deps.ReadAttachment, executor,
        currentSnapshot, onResult)
    if not ok or type(runtime) ~= "table" then
        return nil, "Territory read scheduler unavailable"
    end
    return runtime, nil
end

function Methods:Descriptors()
    local d = self.deps
    local watchReader, watchPlanner = d.TerritoryState, d.TerritoryBlocked
    if type(d.TerritoryBonuses) == "table" then
        watchReader = { read = function(raw, context)
            local view, reason = d.TerritoryState.read(raw, context)
            if not view then return nil, reason end
            view.bonuses, view.bonusReason = self:ReadBonuses(raw, context)
            if self.season then view.season, view.seasonReason = self.season:Read(raw, context) end
            if type(d.FortificationQuery) == "table" then
                view.fortification, view.fortReason = d.FortificationQuery.read(raw, context)
            end
            return view, nil
        end }
        watchPlanner = { propose = function(view, settings)
            if type(settings) ~= "table" or settings.enabled ~= true then return nil, "Territory watch disabled" end
            settings = settings.custom or settings
            local report = tostring(view.cityId) .. ": " .. tostring(view.held) .. "/"
                .. tostring(view.totalDistricts) .. " held; "
                .. (view.bonuses and d.TerritoryBonuses.summary(view.bonuses)
                    or view.bonusReason or "Holder bonuses unavailable")
            report = report .. (view.familyCapacity and ("; Family " .. tostring(view.familyCapacity.held)
                .. "/" .. tostring(view.familyCapacity.maximum) .. " districts") or "; Family capacity unavailable")
            if view.season and settings.showSeason ~= false then
                report = report .. "; season " .. tostring(view.season.n) .. " " .. view.season.phase
            end
            local selected = settings.districtId
            if type(selected) == "string" and #selected > 0 then
                local detail = view.districtDetail
                if detail and detail.id == selected then
                    report = report .. "; " .. selected .. " garrison " .. tostring(detail.garrisonCount)
                        .. "/" .. (detail.garrisonCap and tostring(detail.garrisonCap) or "unknown")
                end
                for _, district in ipairs(view.districts) do
                    if district.id == selected and district.shieldRemaining ~= nil then
                        report = report .. "; shield observed " .. tostring(math.floor(district.shieldRemaining)) .. "s"
                        break
                    end
                end
            end
            if view.fortification and settings.showFortifications ~= false then
                local parts = {}
                for _, row in ipairs(view.fortification.fort.structures) do
                    parts[#parts + 1] = row.key .. " L" .. tostring(row.lv)
                end
                report = report .. "; " .. table.concat(parts, ", ")
            end
            return nil, report
        end }
    end
    local station = self.station and { id = "station", reader = self.station,
        planner = d.Stationing, evidence = d.Stationing, recoverSaved = d.Stationing.recoverSaved,
        canDispatch = function(proposal)
            return not self.closed and d.Stationing.canDispatch(proposal, self.latestSnapshot)
        end }
        or { id = "station", reader = d.TerritoryState,
            planner = d.TerritoryBlocked, evidence = d.TerritoryBlocked }
    local residency = type(d.Residency) == "table"
        and { id = "residency", reader = d.Residency, planner = d.Residency, evidence = d.Residency,
            recoverSaved = d.Residency.recoverSaved,
            canDispatch = function(proposal) return not self.closed and d.Residency.canDispatch(proposal, self.latestSnapshot) end }
        or { id = "residency", reader = d.TerritoryState,
            planner = d.TerritoryBlocked, evidence = d.TerritoryBlocked }
    if self.station and self.recall then station = self.recall:Feature(station) end
    return {
        { id = "territoryWatch", reader = watchReader,
            planner = watchPlanner, evidence = d.TerritoryBlocked },
        station,
        residency,
    }
end

return TerritoryTab
