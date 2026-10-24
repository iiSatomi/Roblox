-- Read-only saved Black Market browse shape and bounded response staging.
local MarketBrowse = {}
local Methods = {}
Methods.__index = Methods
local groups = { weapon = true, armor = true, vehicle = true,
    crate = true, cosmetic = true, trophy = true, misc = true }

local function integer(value, low, high)
    return type(value) == "number" and value == value
        and value >= low and value <= high and value % 1 == 0
end

local function rows(raw)
    if type(raw) ~= "table" or #raw > 500 then return nil end
    local length = #raw
    local count = 0
    for key in pairs(raw) do
        if not integer(key, 1, length) then return nil end
        count = count + 1
    end
    if count ~= length then return nil end
    local result = {}
    for index = 1, length do
        local row = raw[index]
        if type(row) ~= "table"
            or (type(row.id) == "string" and #row.id == 0)
            or (type(row.id) ~= "string" and not integer(row.id, 1, 9007199254740991))
            or type(row.item) ~= "string" or #row.item == 0
            or not integer(row.qty, 1, 999999)
            or not integer(row.price, 1, 999999999)
            or (row.t ~= nil and not integer(row.t, 0, 9007199254740991))
            or (row.sellerId ~= nil and not integer(row.sellerId, 1, 9007199254740991))
            or (row.sellerName ~= nil and type(row.sellerName) ~= "string")
            or (row.mine ~= nil and type(row.mine) ~= "boolean") then
            return nil
        end
        result[index] = {
            id = row.id, item = row.item, qty = row.qty,
            price = row.price, t = row.t, sellerId = row.sellerId,
            sellerName = row.sellerName, mine = row.mine == true,
        }
    end
    return result
end

function MarketBrowse.new(maxPages)
    assert(integer(maxPages, 1, 5), "Invalid saved Market page cap")
    return setmetatable({ maxPages = maxPages, current = nil,
        nextToken = 0, closed = false }, Methods)
end

function Methods:Prepare(scope)
    if self.closed then return nil, "Market browse closed" end
    if type(scope) ~= "table"
        or not integer(scope.page, 1, self.maxPages) then
        return nil, "Unsupported Market browse scope"
    end
    if scope.kind == "all" then
        if scope.arg ~= nil then
            return nil, "Unsupported Market browse scope"
        end
    elseif scope.kind == "group" then
        if not groups[scope.arg] then
            return nil, "Unsupported Market browse group"
        end
    elseif scope.kind == "item" then
        if type(scope.arg) ~= "string" or #scope.arg == 0
            or #scope.arg > 120 then
            return nil, "Invalid Market browse item"
        end
    else
        return nil, "Unsupported Market browse scope"
    end
    self.nextToken = self.nextToken + 1
    local request = { remote = "MarketAction", method = "InvokeServer",
        arity = 4, args = { "browse", scope.kind, scope.arg, scope.page },
        token = self.nextToken, page = scope.page }
    self.current = request
    return request, nil
end

function Methods:Accept(request, reply)
    if self.closed or request ~= self.current then
        return nil, "Stale Market browse reply"
    end
    if type(reply) ~= "table" or reply.ok ~= true then
        return nil, "Market browse rejected"
    end
    local accepted = rows(reply.rows)
    if not accepted then return nil, "Invalid Market browse rows" end
    local pages = reply.pages or 1
    if not integer(pages, 1, self.maxPages) then
        return nil, "Invalid Market browse pages"
    end
    for _, field in ipairs({ "more", "stale", "small" }) do
        if reply[field] ~= nil and type(reply[field]) ~= "boolean" then
            return nil, "Invalid Market browse metadata"
        end
    end
    self.current = nil
    return { page = request.page, pages = pages,
        more = reply.more == true, stale = reply.stale == true,
        small = reply.small == true, rows = accepted }, nil
end

function Methods:Close()
    self.closed = true
    self.current = nil
end

return MarketBrowse
