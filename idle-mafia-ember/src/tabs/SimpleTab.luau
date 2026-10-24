-- Validated descriptor entry for tabs without a tab-specific source adapter.
local SimpleTab = {}
local Methods = {}
Methods.__index = Methods

function SimpleTab.new(page, deps, rows)
    assert(type(page) == "string" and #page > 0
        and type(deps) == "table" and type(rows) == "table"
        and #rows > 0, "Invalid tab definition")
    local count = 0
    for key in pairs(rows) do
        assert(type(key) == "number" and key % 1 == 0
            and key >= 1 and key <= #rows, "Expected dense tab definition")
        count = count + 1
    end
    assert(count == #rows, "Expected dense tab definition")
    local descriptors, seen = {}, {}
    for index, row in ipairs(rows) do
        assert(type(row) == "table" and type(row[1]) == "string"
            and #row[1] > 0 and not seen[row[1]],
            "Invalid tab feature ID")
        local reader, planner, evidence = deps[row[2]], deps[row[3]], deps[row[4]]
        assert(type(reader) == "table" and type(reader.read) == "function"
            and type(planner) == "table"
            and type(planner.propose) == "function"
            and type(evidence) == "table"
            and type(evidence.capture) == "function"
            and type(evidence.evaluate) == "function",
            "Missing tab feature modules: " .. row[1])
        seen[row[1]] = true
        descriptors[index] = { id = row[1], reader = reader,
            planner = planner, evidence = evidence }
    end
    return setmetatable({ id = page, descriptors = descriptors }, Methods)
end

function Methods:Descriptors()
    local result = {}
    for index, descriptor in ipairs(self.descriptors) do
        result[index] = { id = descriptor.id, reader = descriptor.reader,
            planner = descriptor.planner, evidence = descriptor.evidence }
    end
    return result
end

return SimpleTab
