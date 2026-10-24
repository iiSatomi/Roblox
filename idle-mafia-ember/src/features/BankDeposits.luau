-- Deposit only exact excess after threshold, savings and uncertainty.
local BankDeposits = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

function BankDeposits.propose(view, settings, reservations)
    if type(view) ~= "table" or type(settings) ~= "table"
        or type(reservations) ~= "table" then
        return nil, "Missing Bank deposit input"
    end
    if settings.enabled ~= true then return nil, "Bank deposits disabled" end
    if not integer(view.cash, 0) or not integer(view.banked, 0)
        or not integer(view.savings, 0)
        or not integer(settings.depositThreshold, 1)
        or not integer(settings.cashToKeep, 0)
        or not integer(reservations.cash or 0, 0)
        or not integer(reservations.uncertainCash or 0, 0)
        or type(view.feeRate) ~= "number"
        or view.feeRate < 0 or view.feeRate > 1 then
        return nil, "Invalid Bank deposit limits or reserves"
    end
    local keep = math.max(settings.cashToKeep, view.savings,
        reservations.cash or 0)
    local amount = view.cash - keep - (reservations.uncertainCash or 0)
    if amount < settings.depositThreshold then
        return nil, "Cash below deposit threshold after savings"
    end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "bank",
        actionKey = "bank-deposit:" .. view.revision .. ":" .. amount,
        resources = { cash = amount },
        intent = { kind = "bankDeposit", amount = amount,
            keepCash = keep, expectedFeeRate = view.feeRate,
            noFee = view.noFee },
    }, nil
end

return BankDeposits
