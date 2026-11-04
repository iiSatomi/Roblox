-- Pure funding request from currently enabled, source-backed purchases.
local FundingCoordinator = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function balance(value)
    return type(value) == "number" and value == value
        and value < math.huge and value >= 0
end

local function request(context, purpose, proposal, requiredCash)
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        purpose = purpose, purchaseKey = proposal.actionKey,
        requiredCash = requiredCash }
end

local purposes = {
    { "heists", "allowHeists", "HeistBoardState", "HeistStart" },
    { "operations", "allowOperations", "OperationsState", "OperationsStart" },
    { "safehouse", "allowSafehouse", "SafehouseState", "SafehouseUpgrades" },
    { "properties", "allowProperties", "PropertiesState", "Properties" },
    { "shop", "allowShop", "ShopState", "ShopBuy" },
}

local function copy(value)
    local result = {}
    for key, item in pairs(value) do result[key] = item end
    return result
end

local function purchaseNeed(raw, context, config, reserves, purpose, spec, banked)
    if type(spec) ~= "table" or type(spec.reader) ~= "table"
        or type(spec.reader.read) ~= "function" or type(spec.planner) ~= "table"
        or type(spec.planner.propose) ~= "function" then return nil end
    local view = spec.reader.read(raw, context)
    if not view or not balance(view.cash) then return nil end
    -- Reuse the actual planner, including the native Heist protocol quote.
    if spec.planner.propose(view, config, reserves) then return nil end
    local potential = view.cash + banked
    if not balance(potential) then return nil end
    local hypothetical = copy(view)
    hypothetical.cash = potential
    local proposal = spec.planner.propose(hypothetical, config, reserves)
    if type(proposal) ~= "table" or proposal.feature ~= purpose
        or type(proposal.resources) ~= "table"
        or not integer(proposal.resources.cash, 0) then return nil end
    local floor = (purpose == "safehouse" or purpose == "properties" or purpose == "shop")
        and config.cashReserve or 0
    if not integer(floor, 0) then return nil end
    local required = proposal.resources.cash + floor
        + (reserves.cash or 0) + (reserves.uncertainCash or 0)
    if not integer(required, 1) or required <= view.cash
        or math.ceil(required - view.cash) > banked then return nil end
    hypothetical.cash = required
    local exact = spec.planner.propose(hypothetical, config, reserves)
    if not exact or exact.actionKey ~= proposal.actionKey then return nil end
    return request(context, purpose, proposal, required)
end

function FundingCoordinator.derive(raw, context, settings, reserves, modules, owners)
    if type(raw) ~= "table" or type(context) ~= "table"
        or type(settings) ~= "table" or type(reserves) ~= "table"
        or type(modules) ~= "table" or type(settings.withdraw) ~= "table"
        or settings.withdraw.enabled ~= true then
        return nil, "Bank funding disabled or context missing"
    end
    local native = raw.native
    if type(native) ~= "table" or native.fullSync ~= true
        or not balance(native.cash) or not balance(native.banked)
        or not integer(reserves.cash or 0, 0)
        or not integer(reserves.uncertainCash or 0, 0) then
        return nil, "Complete Bank balances required for funding"
    end
    if native.banked == 0 then return nil, "No banked cash" end
    local banked = native.banked
    if owners ~= nil then
        if type(owners) ~= "table" or type(owners.features) ~= "table"
            or type(owners.tabReasons) ~= "table" then
            return nil, "Current funding feature ownership required"
        end
        if owners.reservations then
            local held = owners.reservations:Held(raw)
            if type(held) ~= "table" or type(held.funds) ~= "table" then
                return nil, "Current funding custody required"
            end
            if not balance(held.funds.banked or 0) then return nil, "Current Bank custody required" end
            banked = math.max(0, banked - (held.funds.banked or 0))
            reserves = copy(reserves)
            for _, fund in ipairs({ "cash", "energy" }) do
                local uncertain = fund == "cash" and "uncertainCash" or "uncertainEnergy"
                if not integer(held.funds[fund] or 0, 0)
                    or not integer(reserves[fund] or 0, 0)
                    or not integer(reserves[uncertain] or 0, 0) then
                    return nil, "Current funding custody required"
                end
                -- Held already includes pending exposure; add durable holds
                -- without charging pending Cash or Energy twice.
                reserves[fund] = math.max(reserves[fund] or 0,
                    (held.funds[fund] or 0) - (reserves[uncertain] or 0))
            end
        end
    end
    for _, row in ipairs(purposes) do
        local config = settings[row[1]]
        if settings.withdraw[row[2]] == true and type(config) == "table"
            and config.enabled == true then
            local spec = { reader = modules[row[3]], planner = modules[row[4]] }
            local blocked = false
            if owners then
                spec = owners.features[row[1]]
                local page = type(owners.featurePages) == "table" and owners.featurePages[row[1]]
                blocked = type(owners.blockedFeatures) == "table" and owners.blockedFeatures[row[1]] == true
                    or owners.tabReasons["*"] ~= nil
                    or owners.requirePages == true and not page
                    or page ~= nil and owners.tabReasons[page] ~= nil
                    or row[1] == "heists" and (type(spec) ~= "table" or type(spec.lifecycle) ~= "table")
            end
            if not blocked then
                local candidate = purchaseNeed(raw, context, config,
                    reserves, row[1], spec, banked)
                if candidate and (settings.withdraw.maxWithdrawal == nil
                    or integer(settings.withdraw.maxWithdrawal, 1)
                        and math.ceil(candidate.requiredCash - native.cash) <= settings.withdraw.maxWithdrawal) then
                    return candidate, nil
                end
            end
        end
    end
    return nil, "No enabled purchase has a fundable shortfall"
end

return FundingCoordinator
