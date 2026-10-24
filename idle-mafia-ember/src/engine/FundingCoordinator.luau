-- Pure funding request from currently enabled, source-backed purchases.
local FundingCoordinator = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function request(context, purpose, proposal, requiredCash)
    return { account = context.account, capturedAt = context.capturedAt,
        purpose = purpose, purchaseKey = proposal.actionKey,
        requiredCash = requiredCash }
end

local function operationNeed(raw, context, settings, reserves, modules, banked)
    local view = modules.OperationsState.read(raw, context)
    if not view then return nil end
    local current = modules.OperationsStart.propose(view,
        settings.operations, reserves)
    if current then return nil end
    local potential = view.cash + banked
    if not integer(potential, 0) then return nil end
    local hypothetical = {}
    for key, value in pairs(view) do hypothetical[key] = value end
    hypothetical.cash = potential
    local proposal = modules.OperationsStart.propose(hypothetical,
        settings.operations, reserves)
    if not proposal then return nil end
    local required = proposal.intent.expectedCost
        + (reserves.cash or 0) + (reserves.uncertainCash or 0)
    if not integer(required, 1) or required <= view.cash
        or required - view.cash > banked then return nil end
    return request(context, "operations", proposal, required)
end

local function safehouseNeed(raw, context, settings, reserves, modules, banked)
    local view = modules.SafehouseState.read(raw, context)
    if not view then return nil end
    local _, reason = modules.SafehouseUpgrades.propose(view,
        settings.safehouse, reserves)
    if reason ~= "Safehouse cash reserve blocks upgrade" then return nil end
    local required = view.nextCost + settings.safehouse.cashReserve
        + (reserves.cash or 0) + (reserves.uncertainCash or 0)
    if not integer(required, 1) or required <= view.cash
        or required - view.cash > banked then return nil end
    local hypothetical = {}
    for key, value in pairs(view) do hypothetical[key] = value end
    hypothetical.cash = required
    local proposal = modules.SafehouseUpgrades.propose(hypothetical,
        settings.safehouse, reserves)
    if not proposal then return nil end
    return request(context, "safehouse", proposal, required)
end

function FundingCoordinator.derive(raw, context, settings, reserves, modules)
    if type(raw) ~= "table" or type(context) ~= "table"
        or type(settings) ~= "table" or type(reserves) ~= "table"
        or type(modules) ~= "table" or type(settings.withdraw) ~= "table"
        or settings.withdraw.enabled ~= true then
        return nil, "Bank funding disabled or context missing"
    end
    local native = raw.native
    if type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.cash, 0) or not integer(native.banked, 0)
        or not integer(reserves.cash or 0, 0)
        or not integer(reserves.uncertainCash or 0, 0) then
        return nil, "Complete Bank balances required for funding"
    end
    if native.banked == 0 then return nil, "No banked cash" end
    if type(settings.operations) == "table"
        and settings.operations.enabled == true
        and type(modules.OperationsState) == "table"
        and type(modules.OperationsStart) == "table" then
        local candidate = operationNeed(raw, context, settings,
            reserves, modules, native.banked)
        if candidate then return candidate, nil end
    end
    if type(settings.safehouse) == "table"
        and settings.safehouse.enabled == true
        and type(modules.SafehouseState) == "table"
        and type(modules.SafehouseUpgrades) == "table" then
        local candidate = safehouseNeed(raw, context, settings,
            reserves, modules, native.banked)
        if candidate then return candidate, nil end
    end
    return nil, "No enabled purchase has a fundable shortfall"
end

return FundingCoordinator
