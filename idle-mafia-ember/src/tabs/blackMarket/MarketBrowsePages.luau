-- Merge sequential item browse pages before using visible supply in quotes.
local MarketBrowsePages = {}
local Methods = {}
Methods.__index = Methods

local function integer(value, low, high)
    return type(value) == "number" and value == value
        and value >= low and value <= high and value % 1 == 0
end

local function timestamp(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

local function listing(row)
    return type(row) == "table"
        and ((type(row.id) == "string" and #row.id > 0)
            or integer(row.id, 1, 9007199254740991))
        and type(row.item) == "string" and #row.item > 0
        and integer(row.qty, 1, 1000000000)
        and integer(row.price, 1, 9999999)
        and type(row.mine) == "boolean"
end

local function copy(row)
    return { id = row.id, item = row.item,
        qty = row.qty, price = row.price, mine = row.mine,
        t = row.t, sellerId = row.sellerId,
        sellerName = row.sellerName }
end

local function unchanged(a, b)
    for _, key in ipairs({ "id", "item", "qty", "price", "mine",
        "t", "sellerId", "sellerName" }) do
        if a[key] ~= b[key] then return false end
    end
    return true
end

function MarketBrowsePages.new(maxPages, maxRows)
    assert(integer(maxPages, 1, 5)
        and integer(maxRows, 1, 500),
        "Invalid Market browse pagination bounds")
    return setmetatable({ maxPages = maxPages, maxRows = maxRows,
        current = nil, closed = false }, Methods)
end

function Methods:Begin(kind, arg)
    if self.closed then return nil, "Market pages closed" end
    if kind == "all" then
        if arg ~= nil then
            return nil, "Unsupported Market browse scope"
        end
    elseif kind == "item" then
        if type(arg) ~= "string" or #arg < 1 or #arg > 120 then
            return nil, "Unsupported Market browse scope"
        end
    else
        return nil, "Unsupported Market browse scope"
    end
    self.current = { kind = kind, arg = arg,
        nextPage = 1, rows = {}, byId = {}, firstAt = nil,
        lastAt = nil }
    return { kind = kind, arg = arg, page = 1 }, nil
end

function Methods:Accept(result)
    local current = self.current
    if self.closed or not current then
        return nil, nil, "Market page sequence unavailable"
    end
    if type(result) ~= "table"
        or result.kind ~= current.kind or result.arg ~= current.arg
        or result.page ~= current.nextPage
        or type(result.more) ~= "boolean"
        or not timestamp(result.capturedAt)
        or (current.lastAt and result.capturedAt < current.lastAt)
        or (current.firstAt and result.capturedAt - current.firstAt > 10)
        or type(result.rows) ~= "table"
        or #result.rows > self.maxRows then
        self.current = nil
        return nil, nil, "Market page sequence changed or stale"
    end
    local firstAt = current.firstAt or result.capturedAt
    local count = 0
    for index, row in ipairs(result.rows) do
        if not listing(row) then
            self.current = nil
            return nil, nil, "Invalid Market page listing"
        end
        count = index
        local key = tostring(row.id)
        local old = current.byId[key]
        if old then
            if not unchanged(old, row) then
                self.current = nil
                return nil, nil, "Market listing changed across pages"
            end
        else
            if #current.rows >= self.maxRows then
                self.current = nil
                return nil, nil, "Market row cap reached"
            end
            local saved = copy(row)
            current.rows[#current.rows + 1] = saved
            current.byId[key] = saved
        end
    end
    if count ~= #result.rows then
        self.current = nil
        return nil, nil, "Sparse Market page"
    end
    for key in pairs(result.rows) do
        if not integer(key, 1, count) then
            self.current = nil
            return nil, nil, "Sparse Market page"
        end
    end
    current.firstAt = firstAt
    current.lastAt = result.capturedAt
    if result.more then
        if current.nextPage >= self.maxPages then
            self.current = nil
            return nil, nil, "Market page cap reached"
        end
        current.nextPage = current.nextPage + 1
        return { kind = current.kind, arg = current.arg,
            page = current.nextPage }, nil, nil
    end
    self.current = nil
    local rows = {}
    for index, row in ipairs(current.rows) do rows[index] = copy(row) end
    return nil, { kind = current.kind, arg = current.arg,
        page = current.nextPage, pages = current.nextPage,
        capturedAt = current.lastAt, more = false, rows = rows }, nil
end

function Methods:Close()
    self.closed = true
    self.current = nil
end

return MarketBrowsePages
