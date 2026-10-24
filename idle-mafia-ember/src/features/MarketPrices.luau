-- Read-only saved Black Market price-history query and bounded local cache.
local MarketPrices = {}
local Methods = {}
Methods.__index = Methods

local function integer(value, low, high)
    return type(value) == "number" and value == value
        and value >= low and value <= high and value % 1 == 0
end

local function nonnegative(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

local function array(value, limit)
    if type(value) ~= "table" or #value > limit then return false end
    local length = #value
    local count = 0
    for key in pairs(value) do
        if not integer(key, 1, length) then return false end
        count = count + 1
    end
    return count == length
end

local function copyHistory(history)
    local result = { itemId = history.itemId, capturedAt = history.capturedAt,
        recent = {}, days = {} }
    for index, row in ipairs(history.recent) do
        result.recent[index] = { price = row.price }
    end
    for index, row in ipairs(history.days) do
        result.days[index] = { day = row.day, qty = row.qty, avg = row.avg }
    end
    return result
end

function MarketPrices.new(clock)
    assert(type(clock) == "table" and type(clock.Now) == "function",
        "Missing Market price clock")
    return setmetatable({ clock = clock, cache = {}, current = nil,
        token = 0, closed = false }, Methods)
end

function Methods:Get(itemId)
    if self.closed then return nil end
    local saved = self.cache[itemId]
    if not saved or self.clock:Now() - saved.capturedAt >= 120 then
        return nil
    end
    return copyHistory(saved)
end

function Methods:Prepare(itemId)
    if self.closed then return nil, "Market price reader closed" end
    if type(itemId) ~= "string" or #itemId == 0 or #itemId > 120 then
        return nil, "Invalid Market item ID"
    end
    if self:Get(itemId) then return nil, "Market prices cached" end
    self.token = self.token + 1
    local request = { remote = "MarketAction", method = "InvokeServer",
        arity = 4, args = { "prices", itemId },
        itemId = itemId, token = self.token }
    self.current = request
    return request, nil
end

function Methods:Accept(request, reply)
    if self.closed or request ~= self.current then
        return nil, "Stale Market price reply"
    end
    if type(reply) ~= "table" or reply.ok ~= true then
        return nil, "Market price query rejected"
    end
    local recent, days = reply.recent or {}, reply.days or {}
    if not array(recent, 50) or not array(days, 14) then
        return nil, "Invalid Market price history"
    end
    local result = { itemId = request.itemId,
        capturedAt = self.clock:Now(), recent = {}, days = {} }
    for index, row in ipairs(recent) do
        if type(row) ~= "table" or not integer(row.price, 1, 9999999) then
            return nil, "Invalid recent Market price"
        end
        result.recent[index] = { price = row.price }
    end
    for index, row in ipairs(days) do
        if type(row) ~= "table"
            or not integer(row.day, 19000101, 99991231)
            or not integer(row.qty, 0, 1000000000)
            or not nonnegative(row.avg) then
            return nil, "Invalid Market daily price"
        end
        result.days[index] = { day = row.day,
            qty = row.qty, avg = row.avg }
    end
    self.cache[request.itemId] = result
    self.current = nil
    return copyHistory(result), nil
end

function Methods:Close()
    self.closed = true
    self.current = nil
    self.cache = {}
end

return MarketPrices
