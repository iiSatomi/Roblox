-- Pure ordinary Operation start policy. No paid finish or transport path.
local OperationsStart = {}

local function finite(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

local function identity(view)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(view[field]) ~= "string" or #view[field] == 0 then return false end
    end
    return true
end

function OperationsStart.propose(view, settings, reservations)
    if type(view) ~= "table" or type(settings) ~= "table"
        or type(reservations) ~= "table" then
        return nil, "Missing Operation planning input"
    end
    if settings.enabled ~= true then return nil, "Operations disabled" end
    local policy = settings.policy
    if policy ~= "Best chest" and policy ~= "Highest tier"
        and policy ~= "Profit / hour" and policy ~= "XP / hour"
        and policy ~= "Shortest duration" and policy ~= "Balanced" then
        return nil, "Operation policy has no verified parameters"
    end
    if not identity(view) or not finite(view.revision)
        or view.revision % 1 ~= 0 or not finite(view.level)
        or not finite(view.respect) or not finite(view.cash)
        or not finite(view.openSlots) or view.openSlots % 1 ~= 0
        or type(view.catalogKey) ~= "string" or #view.catalogKey == 0
        or type(view.operations) ~= "table"
        or not finite(reservations.cash or 0)
        or not finite(reservations.uncertainCash or 0) then
        return nil, "Invalid Operation resource view"
    end
    if view.openSlots < 1 then return nil, "No open Operation slot" end
    local custom = settings
    if type(custom) ~= "table" then return nil, "Invalid Operation constraints" end
    local selected = nil
    local selection = custom.selection or "Automatic"
    if selection ~= "Automatic" and selection ~= "Only selected" then return nil, "Invalid Operation selection" end
    if selection == "Only selected" then
        if type(custom.selectedIds) ~= "string" or #custom.selectedIds > 4096 then return nil, "Select Operation IDs" end
        selected = {}
        local count, known = 0, {}
        for _, row in ipairs(view.operations) do known[row.id] = true end
        for token in (custom.selectedIds .. ","):gmatch("(.-),") do
            local id = token:match("^%s*(.-)%s*$")
            count = count + 1
            if count > 64 or #id > 120 or not id:match("^[%w_%-]+$") or not known[id] then
                return nil, "Selected Operation ID is empty, invalid or unavailable"
            end
            selected[id] = true
        end
        if count == 0 then return nil, "Select Operation IDs" end
    end
    local bounds = custom.limitsEnabled == true
    local minLevel, maxLevel = custom.minLevel or 1, custom.maxLevel or 10000
    local minHours, maxHours = custom.minHours or 0, custom.maxHours or 24
    local minRarity = custom.minCrateRarity or 0
    if bounds and (not finite(minLevel) or minLevel < 1 or minLevel % 1 ~= 0
        or not finite(maxLevel) or maxLevel % 1 ~= 0 or minLevel > maxLevel
        or not finite(minHours) or not finite(maxHours) or minHours > maxHours
        or not finite(minRarity) or minRarity % 1 ~= 0 or minRarity > 9) then
        return nil, "Invalid or inverted Operation bounds"
    end
    local available = view.cash - (reservations.cash or 0)
        - (reservations.uncertainCash or 0)
    local candidates, maxProfit, maxXp, maxChest = {}, 0, 0, 0
    for _, operation in ipairs(view.operations) do
        if type(operation) == "table" and type(operation.id) == "string"
            and #operation.id > 0 and finite(operation.cost)
            and finite(operation.level) and finite(operation.respect)
            and (policy ~= "Best chest" or finite(operation.chestScore))
            and (policy ~= "Balanced" or finite(operation.crateRarity) and finite(operation.primaryExpected))
            and finite(operation.order) and finite(operation.duration) and operation.duration > 0
            and finite(operation.cash) and finite(operation.xp)
            and (not selected or selected[operation.id] == true)
            and (not bounds or (operation.level >= minLevel and operation.level <= maxLevel
                and operation.duration >= minHours * 3600 and operation.duration <= maxHours * 3600
                and (minRarity == 0 or finite(operation.crateRarity) and operation.crateRarity >= minRarity)))
            and operation.level <= view.level
            and operation.respect <= view.respect
            and operation.cost <= available then
            local profit = (operation.cash - operation.cost) / operation.duration
            local xp = operation.xp / operation.duration
            local chest = (operation.crateRarity or 0) + (operation.primaryExpected or 0) / 100
            candidates[#candidates + 1] = { operation = operation, profit = profit, xp = xp, chest = chest }
            maxProfit, maxXp, maxChest = math.max(maxProfit, profit), math.max(maxXp, xp), math.max(maxChest, chest)
        end
    end
    local best, bestScore = nil, nil
    for _, row in ipairs(candidates) do
        local operation = row.operation
        local score = policy == "Best chest" and operation.chestScore or operation.order
        if policy == "Profit / hour" then score = row.profit
        elseif policy == "XP / hour" then score = row.xp
        elseif policy == "Shortest duration" then score = -operation.duration
        elseif policy == "Balanced" then
            -- Preserve the reviewed legacy heuristic over eligible current quotes.
            score = (maxProfit > 0 and row.profit / maxProfit or 0)
                + (maxXp > 0 and row.xp / maxXp or 0)
                + (maxChest > 0 and row.chest / maxChest or 0)
        end
        if score == score and math.abs(score) < math.huge and (not best or score > bestScore
            or score == bestScore and operation.id < best.id) then
            best, bestScore = operation, score
        end
    end
    if not best then return nil, "No unlocked Operation within cash reserve" end
    if policy == "Best chest" and bestScore <= 0 then
        return nil, "No verified chest chance for eligible Operations"
    end
    local key = "operations:" .. #view.catalogKey .. ":" .. view.catalogKey
        .. ":" .. #best.id .. ":" .. best.id .. ":" .. view.revision
    return {
        session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "operations", actionKey = key,
        resources = { cash = best.cost },
        intent = { kind = "operationStart", targetId = best.id,
            expectedCost = best.cost, catalogKey = view.catalogKey },
    }, nil
end

return OperationsStart
