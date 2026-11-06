-- Compose all gameplay tabs from one pinned module set before creating a sender.
local RuntimeAssembly = {}

local pages = {
    "heists", "jobs", "operations", "favors", "combat", "crew",
    "inventory", "collection", "money", "property", "safehouse",
    "prestige", "shop", "blackMarket", "family", "territory",
    "contracts", "trophies", "skills", "rewards", "events",
}

local function closeTabs(tabs)
    for index = #tabs, 1, -1 do
        local tab = tabs[index]
        if type(tab.Close) == "function" then pcall(tab.Close, tab) end
    end
end

local function errorDetail(value)
    local firstLine = tostring(value):match("^[^\r\n]+") or "Unknown constructor error"
    return (firstLine:match("^.-:%d+:%s*(.+)$") or firstLine):sub(1, 120)
end

function RuntimeAssembly.compose(deps)
    if type(deps) ~= "table" or type(deps.Catalog) ~= "table"
        or type(deps.FeatureRegistry) ~= "table"
        or type(deps.TabComposition) ~= "table"
        or type(deps.TabSnapshotAssembler) ~= "table" then
        return nil, "Missing runtime composition modules"
    end
    local tabs = {}
    for _, page in ipairs(pages) do
        local name = string.upper(string.sub(page, 1, 1))
            .. string.sub(page, 2) .. "Tab"
        local module = deps[name]
        if type(module) ~= "table" or type(module.new) ~= "function" then
            closeTabs(tabs)
            return nil, "Missing required tab module: " .. page
        end
        local ok, tab = pcall(module.new, deps)
        if not ok or type(tab) ~= "table" or tab.id ~= page then
            if ok and type(tab) == "table" then tabs[#tabs + 1] = tab end
            closeTabs(tabs)
            return nil, "Invalid tab module: " .. page .. (not ok and (": " .. errorDetail(tab)) or "")
        end
        tabs[#tabs + 1] = tab
    end
    local ok, composed, reason = pcall(deps.TabComposition.build, tabs, deps.Catalog,
        deps.FeatureRegistry, deps.TabSnapshotAssembler, pages)
    if not ok or type(composed) ~= "table" then
        closeTabs(tabs)
        return nil, ok and reason or ("Tab composition failed: " .. errorDetail(composed))
    end
    return composed, reason
end

function RuntimeAssembly.start(deps)
    local composed, reason = RuntimeAssembly.compose(deps)
    if not composed then return nil, reason end
    local function fail(message)
        closeTabs(composed.tabs or {})
        return nil, message
    end
    if type(deps.AutomationRuntime) ~= "table"
        or type(deps.AutomationRuntime.new) ~= "function"
        or type(deps.identity) ~= "table"
        or type(deps.clock) ~= "table"
        or type(deps.transport) ~= "table"
        or type(deps.storage) ~= "table" then
        return fail("Missing runtime environment")
    end
    local sources, readSpecs, reservationSources = {}, {}, {}
    for _, tab in ipairs(composed.tabs or {}) do
        if type(tab.ReservationSources) == "function" then
            local made, rows = pcall(tab.ReservationSources, tab)
            if not made or type(rows) ~= "table" then return fail("Tab reservation sources unavailable") end
            for _, source in ipairs(rows) do reservationSources[#reservationSources + 1] = source end
        end
    end
    if type(deps.nativeReader) == "table" and type(deps.nativeExecutor) == "table"
        and type(deps.requestLane) == "table" and type(deps.ReadCoordinator) == "table"
        and type(deps.ReadBudget) == "table" then
        for _, tab in ipairs(composed.tabs or {}) do
            if type(tab.ReadSources) == "function" then
                local made, rows = pcall(tab.ReadSources, tab, deps.nativeReader)
                if not made or type(rows) ~= "table" then return fail("Tab read sources unavailable") end
                for _, source in ipairs(rows) do
                    sources[#sources + 1] = source
                    readSpecs[#readSpecs + 1] = {id = source.id, interval = source.interval}
                end
            end
        end
    end
    local reads
    if #sources > 0 then
        local built, value = pcall(function()
            return deps.ReadCoordinator.new({clock = deps.clock, lane = deps.requestLane,
                budget = deps.ReadBudget.new(deps.clock, readSpecs, 5, 60), executor = deps.nativeExecutor,
                sources = sources, currentSnapshot = function() return deps.nativeReader:Capture() end,
                borrowLease = function(feature) return deps.transport:ReadLease(feature) end})
        end)
        if not built then return fail("Shared read coordinator construction failed") end
        reads = value
    end
    local ok, runtime = pcall(deps.AutomationRuntime.new, {
        modules = deps, identity = deps.identity, clock = deps.clock,
        transport = deps.transport, storage = deps.storage,
        features = composed.features,
        featurePages = composed.featurePages,
        snapshotAssembler = composed.snapshotAssembler,
        tabInstances = composed.tabs, readCoordinator = reads, readSources = sources,
        reservationSources = reservationSources,
    })
    if not ok or type(runtime) ~= "table" then
        if reads and type(reads.Close) == "function" then pcall(reads.Close, reads) end
        if not ok then
            return fail("Runtime: " .. errorDetail(runtime))
        end
        return fail("Runtime startup failed")
    end
    return runtime, nil
end

return RuntimeAssembly
