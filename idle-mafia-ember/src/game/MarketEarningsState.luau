-- Earned Black Market payout from complete replicated account state.
local MarketEarningsState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

function MarketEarningsState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Market earnings state or context"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Market earnings snapshot header changed"
        end
    end
    local native = raw.native
    local inventory = type(native) == "table" and native.inventory
    local gold = type(inventory) == "table"
        and inventory.gold_bar
    if gold == nil then gold = 0 end
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.market) ~= "table"
        or type(native.inventory) ~= "table"
        or not integer(native.market.earnings, 0)
        or not integer(gold, 0) then
        return nil, "Complete Market earnings and Gold Sync required"
    end
    if native.market.earnings == 0 then
        return nil, "No sold earnings to collect"
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        earnings = native.market.earnings,
        gold = gold }, nil
end

return MarketEarningsState
