-- One native cumulative browse observation; never merge independent replies.
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
    self.current = { kind = kind, arg = arg, page = self.maxPages }
    return { kind = kind, arg = arg, page = self.maxPages }, nil
end

function Methods:Accept(result)
    local current = self.current
    if self.closed or not current then
        return nil, nil, "Market browse observation unavailable"
    end
    self.current = nil
    if type(result) ~= "table"
        or result.kind ~= current.kind or result.arg ~= current.arg
        or result.page ~= current.page or not integer(result.pages, 1, current.page)
        or type(result.more) ~= "boolean"
        or type(result.stale) ~= "boolean" or type(result.small) ~= "boolean"
        or not timestamp(result.capturedAt)
        or type(result.rows) ~= "table"
        or #result.rows > self.maxRows then
        return nil, nil, "Market browse observation changed or invalid"
    end
    local count, rows, seen = 0, {}, {}
    for index, row in ipairs(result.rows) do
        if not listing(row) or (current.kind == "item" and row.item ~= current.arg)
            or seen[tostring(row.id)] then
            return nil, nil, "Invalid or duplicate Market browse listing"
        end
        count = index
        rows[index], seen[tostring(row.id)] = copy(row), true
    end
    if count ~= #result.rows then
        return nil, nil, "Sparse Market browse"
    end
    for key in pairs(result.rows) do
        if not integer(key, 1, count) then
            return nil, nil, "Sparse Market browse"
        end
    end
    return nil, { kind = current.kind, arg = current.arg,
        page = current.page, pages = result.pages,
        capturedAt = result.capturedAt, more = result.more,
        stale = result.stale, small = result.small, rows = rows }, nil
end

function Methods:Close()
    self.closed = true
    self.current = nil
end

return MarketBrowsePages
