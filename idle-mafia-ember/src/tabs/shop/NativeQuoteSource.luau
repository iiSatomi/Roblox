-- Read-only saved Shop calculation path. The caller identifies current modules.
local NativeQuoteSource = {}
local Methods = {}
Methods.__index = Methods

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function near(clock, timestamp)
    local ok, now = pcall(clock.now)
    return ok and type(now) == "number" and now == now
        and now >= timestamp and now - timestamp <= 2
        and math.floor(now / 300) == math.floor(timestamp / 300), now
end

function NativeQuoteSource.new(current, release, catalogKey)
    if type(current) ~= "table"
        or type(release) ~= "string" or #release == 0
        or type(catalogKey) ~= "string" or #catalogKey ~= 64
        or not catalogKey:match("^[%x]+$")
        or type(current.gameData) ~= "table"
        or type(current.gameData.SHOP) ~= "table"
        or type(current.gameData.ITEMS_BY_ID) ~= "table"
        or type(current.util) ~= "table"
        or type(current.util.shopStock) ~= "function"
        or type(current.util.shopPrice) ~= "function"
        or type(current.territory) ~= "table"
        or type(current.territory.fromData) ~= "function"
        or type(current.territory.shopPrice) ~= "function"
        or type(current.globalBuff) ~= "table"
        or type(current.globalBuff.sale) ~= "function"
        or type(current.decree) ~= "table"
        or type(current.decree.pctFor) ~= "function"
        or type(current.clock) ~= "table"
        or type(current.clock.now) ~= "function"
        or current.mw == nil then
        return nil, "Missing current Shop source modules"
    end
    local offers, count = {}, 0
    for index, offer in ipairs(current.gameData.SHOP) do
        if index > 512 or type(offer) ~= "table"
            or type(offer.item) ~= "string"
            or type(current.gameData.ITEMS_BY_ID[offer.item]) ~= "table" then
            return nil, "Invalid current Shop catalog"
        end
        local item = current.gameData.ITEMS_BY_ID[offer.item]
        if offer.goldPrice == nil
            and not (item.kind == "crate" and item.paid == true) then
            if offers[offer.item] ~= nil then
                return nil, "Duplicate current cash Shop offer"
            end
            offers[offer.item] = offer
            count = count + 1
        end
    end
    if count == 0 then return nil, "No current cash Shop offers" end
    return setmetatable({ current = current, offers = offers,
        release = release, catalogKey = catalogKey:lower() }, Methods), nil
end

function Methods:Stock(serverNow)
    if not integer(serverNow, 0)
        or not near(self.current.clock, serverNow) then
        return nil
    end
    local ok, stocked, nextAt, slot = pcall(
        self.current.util.shopStock, self.current.gameData, serverNow)
    if not ok or type(stocked) ~= "table"
        or slot ~= math.floor(serverNow / 300)
        or nextAt ~= (slot + 1) * 300 then
        return nil
    end
    local result = {}
    for id in pairs(self.offers) do
        result[id] = stocked[id] == true
    end
    return result, nextAt, slot
end

function Methods:CashQuote(itemId, slot, raw)
    local offer = self.offers[itemId]
    local native = type(raw) == "table" and raw.native
    if not offer or type(native) ~= "table"
        or not integer(slot, 0)
        or not integer(native.serverNow, 0)
        or math.floor(native.serverNow / 300) ~= slot then
        return nil
    end
    local current, now = near(self.current.clock,
        native.serverNow)
    if not current then return nil end
    local family = type(native.family) == "table"
        and native.family.id or nil
    local ok, price = pcall(function()
        local base = self.current.util.shopPrice(offer, slot)
        local territory = self.current.territory.fromData(
            native, "shopDiscount")
        local sale = self.current.globalBuff.sale(
            self.current.mw, now)
        local decree = self.current.decree.pctFor(
            self.current.mw, "shop", family)
        return self.current.territory.shopPrice(
            base, territory, sale, decree)
    end)
    if not ok or not integer(price, 1) then return nil end
    return price
end

return NativeQuoteSource
