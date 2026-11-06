-- Bounded read-only Market RAP batches from the native research action.
local MarketRap = {}
local Methods = {}
Methods.__index = Methods

local function integer(value, low, high)
    return type(value) == "number" and value == value
        and value >= low and value <= high and value % 1 == 0
end

local function average(value)
    return type(value) == "number" and value == value
        and value >= 0 and value <= 1000000000
end

local function itemId(value)
    return type(value) == "string" and #value > 0 and #value <= 120
end

local function copy(row)
    return { itemId = row.itemId,
        quantity = row.quantity, sales = row.sales,
        average = row.average, available = row.available,
        capturedAt = row.capturedAt }
end

function MarketRap.new(clock)
    assert(type(clock) == "table" and type(clock.Now) == "function",
        "Missing Market RAP clock")
    return setmetatable({ clock = clock, cache = {}, current = nil,
        closed = false }, Methods)
end

function Methods:Get(id)
    if self.closed or not itemId(id) then return nil end
    local saved = self.cache[id]
    if not saved or self.clock:Now() - saved.capturedAt >= 120 then
        return nil
    end
    return copy(saved)
end

function Methods:Prepare(ids)
    if self.closed then return nil, "Market RAP reader closed" end
    if type(ids) ~= "table" or #ids < 1 or #ids > 20 then
        return nil, "Invalid Market RAP batch"
    end
    local count, selected, seen, allCached = 0, {}, {}, true
    for index, id in ipairs(ids) do
        if not itemId(id) or seen[id] then
            return nil, "Invalid Market RAP item"
        end
        count = index
        selected[index] = id
        seen[id] = true
        if not self:Get(id) then allCached = false end
    end
    for key in pairs(ids) do
        if not integer(key, 1, count) then
            return nil, "Invalid Market RAP batch"
        end
    end
    if count ~= #ids then return nil, "Invalid Market RAP batch" end
    if allCached then return nil, "Market RAP cached" end
    local request = { remote = "MarketAction", method = "InvokeServer",
        arity = 4, args = { "rap", selected, nil, nil },
        ids = selected, expected = seen }
    self.current = request
    return request, nil
end

function Methods:Accept(request, reply)
    if self.closed or request ~= self.current then
        return nil, "Stale Market RAP reply"
    end
    local values = type(reply) == "table" and reply.values
    if type(reply) ~= "table" or reply.ok ~= true
        or type(values) ~= "table" then
        return nil, "Market RAP query rejected"
    end
    local result = { capturedAt = self.clock:Now(), values = {} }
    local count = 0
    for id, row in pairs(values) do
        if not request.expected[id] or type(row) ~= "table"
            or not integer(row.quantity, 0, 1000000000)
            or not integer(row.sales, 0, 1000000000)
            or not (average(row.average) or row.average == nil and row.quantity == 0 and row.sales == 0)
            or type(row.available) ~= "boolean" then
            return nil, "Invalid Market RAP values"
        end
        count = count + 1
        result.values[id] = { itemId = id,
            quantity = row.quantity,
            sales = row.sales, average = row.average,
            available = row.available, capturedAt = result.capturedAt }
    end
    if count ~= #request.ids then
        return nil, "Incomplete Market RAP values"
    end
    for id, row in pairs(result.values) do self.cache[id] = copy(row) end
    self.current = nil
    local public = { capturedAt = result.capturedAt, values = {} }
    for id, row in pairs(result.values) do
        public.values[id] = copy(row)
    end
    return public, nil
end

function Methods:Close()
    self.closed = true
    self.current = nil
    self.cache = {}
end

return MarketRap
