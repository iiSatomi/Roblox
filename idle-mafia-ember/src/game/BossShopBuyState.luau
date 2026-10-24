-- Only checkpoint-injected usage and a complete current shop view are spendable.
local BossShopBuyState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

function BossShopBuyState.read(raw, context)
    local shop = type(context) == "table" and context.bossShop
    local usage = type(raw) == "table" and raw.bossShopUsageProof
    if type(shop) ~= "table" or shop.status ~= "known"
        or type(usage) ~= "table"
        or usage.account ~= context.account
        or usage.session ~= context.session
        or usage.capturedAt ~= context.capturedAt
        or not integer(usage.attempts, 0)
        or usage.attempts > 20 then
        return nil, "Current Boss Shop and attempt proof required"
    end
    return { status = "known", session = context.session,
        account = context.account, place = context.place,
        release = context.release, revision = context.revision,
        catalogKey = shop.catalogKey, tokens = shop.tokens,
        items = shop.items, attempts = usage.attempts }, nil
end

return BossShopBuyState
