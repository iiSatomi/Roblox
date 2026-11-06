-- Copy current Config.MARKET terms and bind them to a reviewed release.
local NativeMarketCatalog = {}
local Methods = {}
Methods.__index = Methods

local function integer(value, low, high)
    return type(value) == "number" and value == value
        and value >= low and value <= high and value % 1 == 0
end

local function finite(value, low, high)
    return type(value) == "number" and value == value
        and value > -math.huge and value < math.huge
        and value >= low and value <= high
end

function NativeMarketCatalog.new(config, fingerprint, release)
    local source = type(config) == "table" and config.MARKET
    assert(type(source) == "table"
        and type(fingerprint) == "string" and #fingerprint == 64
        and fingerprint:match("^[%x]+$")
        and type(release) == "string" and #release > 0
        and #release <= 200
        and integer(source.minLevel, 1, 1000000)
        and integer(source.maxPages, 1, 5)
        and integer(source.slots, 1, 20)
        and integer(source.maxSlots, source.slots, 20)
        and integer(source.rentPerPeriod, 1, 1000)
        and integer(source.rentPeriodHours, 1, 720)
        and integer(source.rentMaxDays, 1, 30)
        and finite(source.feePct, 0, 0.5)
        and finite(source.permanentFeePct, 0, source.feePct)
        and integer(source.minFee, 1, 1000)
        and integer(source.minPrice, 2, 9999999)
        and integer(source.maxPrice, source.minPrice, 9999999)
        and integer(source.maxQuantity, 1, 999)
        and type(source.minPriceByRarity) == "table",
        "Missing reviewed Market terms")
    local floors, count = {}, 0
    for rarity, value in pairs(source.minPriceByRarity) do
        count = count + 1
        assert(count <= 20 and integer(rarity, 1, 20)
            and integer(value, source.minPrice, source.maxPrice),
            "Invalid Market rarity price floor")
        floors[rarity] = value
    end
    return setmetatable({ release = release,
        key = fingerprint:lower(), minLevel = source.minLevel, maxPages = source.maxPages,
        slots = source.slots, maxSlots = source.maxSlots,
        rentPerPeriod = source.rentPerPeriod,
        rentPeriodHours = source.rentPeriodHours,
        rentMaxDays = source.rentMaxDays,
        feePct = source.feePct,
        permanentFeePct = source.permanentFeePct,
        minFee = source.minFee, minPrice = source.minPrice,
        maxPrice = source.maxPrice,
        maxQuantity = source.maxQuantity,
        floors = floors }, Methods)
end

local function matches(self, snapshot)
    return type(snapshot) == "table"
        and snapshot.release == self.release
        and type(snapshot.native) == "table"
        and snapshot.native.fullSync == true
end

function Methods:RentTerms(snapshot)
    if not matches(self, snapshot) then
        return nil, "Current Market Sync does not match Config"
    end
    return { release = self.release, sourceKey = self.key,
        minLevel = self.minLevel,
        rentPerPeriod = self.rentPerPeriod,
        rentPeriodHours = self.rentPeriodHours,
        rentMaxDays = self.rentMaxDays }, nil
end

function Methods:SaleTerms(snapshot, rarity)
    if not matches(self, snapshot)
        or not integer(rarity, 1, 20) then
        return nil, "Current Market item and Sync required"
    end
    local native = snapshot.native
    local market, derived = native.market, native.derived
    if type(market) ~= "table" or type(derived) ~= "table"
        or not integer(market.extraSlots, 0, 100)
        or type(derived.marketShop) ~= "boolean" then
        return nil, "Current Market slots and shop state required"
    end
    local permanent = derived.marketShop
    return { release = self.release, sourceKey = self.key,
        minPrice = self.floors[rarity] or self.minPrice,
        maxPrice = self.maxPrice, minFee = self.minFee,
        maxQuantity = self.maxQuantity,
        feeRate = permanent and self.permanentFeePct
            or self.feePct,
        rentAllowance = permanent and 0 or self.rentPerPeriod,
        permanent = permanent,
        maxSlots = math.min(self.slots + market.extraSlots,
            self.maxSlots) }, nil
end

return NativeMarketCatalog
