-- Compose tab-owned snapshot enrichers without allowing cross-tab overrides.
local TabSnapshotAssembler = {}
local Methods = {}
Methods.__index = Methods

local function copy(source)
    local result = {}
    for key, value in pairs(source) do result[key] = value end
    return result
end

function TabSnapshotAssembler.new(tabs)
    assert(type(tabs) == "table" and #tabs > 0 and #tabs <= 25,
        "Expected tab modules")
    local count = 0
    for key in pairs(tabs) do
        assert(type(key) == "number" and key % 1 == 0
            and key >= 1 and key <= #tabs, "Expected dense tab modules")
        count = count + 1
    end
    assert(count == #tabs, "Expected dense tab modules")
    local ordered, seen, proofOwners = {}, {}, {}
    for index, tab in ipairs(tabs) do
        assert(type(tab) == "table" and type(tab.id) == "string"
            and #tab.id > 0 and not seen[tab.id]
            and type(tab.Enrich) == "function",
            "Invalid or duplicate tab module")
        seen[tab.id] = true
        if tab.ownedProofs ~= nil then
            assert(type(tab.ownedProofs) == "table" and #tab.ownedProofs <= 10, "Invalid tab proof declaration")
            local size = 0
            for key, field in pairs(tab.ownedProofs) do
                size = size + 1
                assert(type(key) == "number" and key % 1 == 0 and key >= 1 and key <= #tab.ownedProofs
                    and type(field) == "string" and #field <= 80 and field:match("^%a[%w]*Proof$")
                    and not proofOwners[field], "Invalid or duplicate tab proof owner")
                proofOwners[field] = tab.id
            end
            assert(size == #tab.ownedProofs, "Sparse tab proof declaration")
        end
        ordered[index] = tab
    end
    assert(#ordered == #tabs, "Expected dense tab modules")
    return setmetatable({ tabs = ordered, proofOwners = proofOwners }, Methods)
end

function Methods:Enrich(snapshot, settings)
    if type(snapshot) ~= "table" then
        return nil, { snapshot = "Expected snapshot table" }
    end
    local current, reasons = copy(snapshot), {}
    for field in pairs(self.proofOwners) do current[field] = nil end
    for _, tab in ipairs(self.tabs) do
        local ok, candidate, reason = pcall(tab.Enrich, tab, current, settings)
        if not ok then
            reasons[tab.id] = "Tab enrichment failed"
        elseif type(candidate) ~= "table" then
            reasons[tab.id] = reason or "Tab enrichment unavailable"
        elseif current.catalogKey ~= nil
            and candidate.catalogKey ~= current.catalogKey then
            reasons[tab.id] = "Catalog fingerprint mismatch"
        else
            local changed = false
            for key, value in pairs(current) do
                if candidate[key] ~= value and key ~= "catalogKey" then
                    changed = true
                    break
                end
            end
            for key, value in pairs(candidate) do
                if self.proofOwners[key] and self.proofOwners[key] ~= tab.id and current[key] ~= value then changed = true end
            end
            if changed then
                reasons[tab.id] = "Tab enrichment replaced existing snapshot data"
            else
                current = candidate
            end
        end
    end
    return current, reasons
end

return TabSnapshotAssembler
