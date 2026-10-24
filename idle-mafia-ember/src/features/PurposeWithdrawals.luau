-- Exact shortfall only for a concurrently enabled ordinary purchase.
local PurposeWithdrawals = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

function PurposeWithdrawals.propose(view, settings)
    if type(view) ~= "table" or type(settings) ~= "table" then
        return nil, "Missing withdrawal planning input"
    end
    if settings.enabled ~= true then return nil, "Bank funding disabled" end
    if not integer(view.cash, 0) or not integer(view.banked, 0)
        or not integer(view.requiredCash, 1)
        or not integer(settings.maxWithdrawal, 1)
        or type(view.purchaseKey) ~= "string" or #view.purchaseKey == 0
        or (view.purpose ~= "operations"
            and view.purpose ~= "safehouse") then
        return nil, "Invalid funding request or withdrawal limit"
    end
    local allowed = view.purpose == "operations"
        and settings.allowOperations == true
        or view.purpose == "safehouse"
            and settings.allowSafehouse == true
    if not allowed then return nil, "Funding purpose is not enabled" end
    local amount = view.requiredCash - view.cash
    if amount <= 0 then return nil, "Purchase has no cash shortfall" end
    if amount > settings.maxWithdrawal or amount > view.banked then
        return nil, "Bank balance or withdrawal limit blocks purchase"
    end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "withdraw",
        actionKey = "withdraw:" .. view.purpose .. ":"
            .. #view.purchaseKey .. ":" .. view.purchaseKey
            .. ":" .. amount,
        resources = {},
        intent = { kind = "purposeWithdrawal", amount = amount,
            purpose = view.purpose, purchaseKey = view.purchaseKey,
            requiredCash = view.requiredCash },
    }, nil
end

return PurposeWithdrawals
