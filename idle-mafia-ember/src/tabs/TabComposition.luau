-- Build descriptor/source boundaries from loaded per-tab entries.
local TabComposition = {}

function TabComposition.build(tabs, catalog, registry, assemblerModule,
    requiredPages)
    if type(tabs) ~= "table" or type(registry) ~= "table"
        or type(registry.fromTabs) ~= "function"
        or type(assemblerModule) ~= "table"
        or type(assemblerModule.new) ~= "function" then
        return nil, "Missing modular composition inputs"
    end
    if requiredPages ~= nil then
        if type(requiredPages) ~= "table" or #requiredPages == 0
            or #requiredPages > 25 then
            return nil, "Invalid required tab list"
        end
        local required, observed = {}, {}
        local count = 0
        for key, page in pairs(requiredPages) do
            if type(key) ~= "number" or key % 1 ~= 0
                or key < 1 or key > #requiredPages
                or type(page) ~= "string" or #page == 0
                or required[page] then
                return nil, "Invalid required tab list"
            end
            required[page] = true
            count = count + 1
        end
        if count ~= #requiredPages then
            return nil, "Invalid required tab list"
        end
        for _, tab in ipairs(tabs) do
            if type(tab) ~= "table" or not required[tab.id]
                or observed[tab.id] then
                return nil, "Unexpected or duplicate tab module"
            end
            observed[tab.id] = true
        end
        for page in pairs(required) do
            if not observed[page] then
                return nil, "Missing required tab module: " .. page
            end
        end
    end
    local features, reason = registry.fromTabs(tabs, catalog)
    if not features then return nil, reason end
    local featurePages = {}
    for _, spec in ipairs(features) do
        featurePages[spec.id] = spec.page
    end
    local enrichers = {}
    for _, tab in ipairs(tabs) do
        if tab.Enrich ~= nil then
            if type(tab.Enrich) ~= "function" then
                return nil, "Invalid tab source adapter: " .. tab.id
            end
            enrichers[#enrichers + 1] = tab
        end
    end
    local assembler = nil
    if #enrichers > 0 then
        local ok, value = pcall(assemblerModule.new, enrichers)
        if not ok then return nil, "Invalid tab snapshot adapters" end
        assembler = value
    end
    return { features = features, featurePages = featurePages,
        snapshotAssembler = assembler }, nil
end

return TabComposition
