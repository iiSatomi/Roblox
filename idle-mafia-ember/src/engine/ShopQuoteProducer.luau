-- Stage current native Shop stock and discounted cash quotes for one Sync.
local ShopQuoteProducer = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

function ShopQuoteProducer.derive(raw, context, source)
    local native = type(raw) == "table" and raw.native
    local catalog = type(raw) == "table" and raw.shopCatalog
    if type(context) ~= "table" or type(source) ~= "table"
        or type(source.Stock) ~= "function"
        or type(source.CashQuote) ~= "function"
        or type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.serverNow, 0)
        or type(native.shopRotation) ~= "table"
        or type(catalog) ~= "table"
        or catalog.release ~= context.release
        or type(catalog.key) ~= "string" or #catalog.key ~= 64
        or source.release ~= context.release
        or source.catalogKey ~= catalog.key
        or type(catalog.offers) ~= "table"
        or raw.session ~= context.session
        or raw.account ~= context.account
        or raw.place ~= context.place
        or raw.release ~= context.release
        or raw.revision ~= context.revision
        or raw.capturedAt ~= context.capturedAt then
        return nil, "Current native Shop quote source required"
    end
    local slot = math.floor(native.serverNow / 300)
    if native.serverNow % 300 > 295
        or native.shopRotation.slot ~= slot then
        return nil, "Shop rotation is changing"
    end
    local ok, stock, nextAt, stockSlot = pcall(
        source.Stock, source, native.serverNow)
    if not ok or type(stock) ~= "table"
        or nextAt ~= (slot + 1) * 300
        or stockSlot ~= slot then
        return nil, "Native Shop stock unavailable"
    end
    local copiedStock, quotes, count = {}, {}, 0
    for id, row in pairs(catalog.offers) do
        count = count + 1
        if count > 512 or type(id) ~= "string"
            or type(row) ~= "table"
            or type(stock[id]) ~= "boolean" then
            return nil, "Invalid native Shop offer stock"
        end
        copiedStock[id] = stock[id]
        if stock[id] then
            local priceOk, price = pcall(source.CashQuote,
                source, id, slot, raw)
            if not priceOk or not integer(price, 1)
                or not integer(row.ceiling, 1)
                or price > row.ceiling then
                return nil, "Invalid native Shop cash quote"
            end
            quotes[id] = price
        end
    end
    if count == 0 then return nil, "Empty cash Shop catalog" end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision,
        capturedAt = context.capturedAt,
        catalogKey = catalog.key, slot = slot,
        stock = copiedStock, quotes = quotes }, nil
end

return ShopQuoteProducer
