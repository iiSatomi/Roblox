-- Offline ordinary personal Heist start selection; transport owns sequence.
local HeistStart = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function balance(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge
end

local policies = { ["Best chest"] = true, Balanced = true, ["Highest tier"] = true,
    ["Lowest stake"] = true, ["XP / hour"] = true, ["Profit / hour"] = true, Custom = true }

local function quote(row)
    return integer(row.duration, 1) and balance(row.cash, 0) and balance(row.xp, 0)
        and balance(row.crateChance, 0) and row.crateChance <= 1
        and integer(row.crateRarity, 0) and row.crateRarity <= 9
        and integer(row.helpGoal, 0)
end

local function score(row, policy)
    local expected = row.crateCount * row.crateChance
    local profit, xp = (row.cash - row.stake) / row.duration, row.xp / row.duration
    if policy == "Best chest" then return row.crateRarity * 1e9 + expected * 1e6 + row.level * 1e3 + profit end
    if policy == "Balanced" then return row.crateRarity * 1e9 + expected * 1e6 + xp * 1e3 + profit end
    if policy == "Highest tier" then return row.crateRarity * 1e6 + expected * 1e3 end
    if policy == "XP / hour" then return xp end
    if policy == "Profit / hour" then return profit end
    return -row.stake
end

function HeistStart.propose(view, settings, reservations)
    if type(view) ~= "table" or type(settings) ~= "table"
        or type(reservations) ~= "table" then
        return nil, "Missing Heist planning input"
    end
    if settings.enabled ~= true then return nil, "Heist starts disabled" end
    local policy = settings.policy
    if not policies[policy] then
        return nil, "Invalid Heist selection policy"
    end
    if view.state ~= "idle" then return nil, "Personal Heist board busy" end
    if not integer(view.startsLeft, 1)
        or not integer(view.bustWait, 0) or view.bustWait > 0
        or not integer(view.serverDay, 0)
        or not integer(view.level, 1)
        or not balance(view.cash, 0)
        or not integer(view.energy, 0)
        or type(view.options) ~= "table"
        or type(view.catalogKey) ~= "string" or #view.catalogKey == 0
        or not integer(reservations.cash or 0, 0)
        or not integer(reservations.energy or 0, 0)
        or not integer(reservations.uncertainCash or 0, 0)
        or not integer(reservations.uncertainEnergy or 0, 0) then
        return nil, "Current Heist capacity and resource proof required"
    end
    local floor = settings.energyReserve or 0
    if not balance(floor, 0) or floor > 1000000000000 then return nil, "Invalid shared energy reserve" end
    local cash = view.cash - (reservations.cash or 0)
        - (reservations.uncertainCash or 0)
    local energy = view.energy - (reservations.energy or 0)
        - (reservations.uncertainEnergy or 0) - floor
    local custom = type(settings.custom) == "table" and settings.custom or settings
    local selection, selected = custom.selection or "Automatic", nil
    if selection ~= "Automatic" and selection ~= "Only selected" then return nil, "Invalid Heist selection" end
    if selection == "Only selected" then
        if type(custom.selectedIds) ~= "string" or #custom.selectedIds > 4096 then return nil, "Select Heist IDs" end
        local known, count = {}, 0
        for _, row in ipairs(view.options) do if type(row) == "table" and type(row.id) == "string" then known[row.id] = true end end
        selected = {}
        for token in (custom.selectedIds .. ","):gmatch("(.-),") do
            local id = token:match("^%s*(.-)%s*$")
            count = count + 1
            if count > 32 or #id > 120 or not id:match("^[%w_%-]+$") or not known[id] then
                return nil, "Selected Heist ID is empty, invalid or unavailable"
            end
            selected[id] = true
        end
    end
    if custom.limitsEnabled ~= nil and type(custom.limitsEnabled) ~= "boolean" then return nil, "Invalid Heist limits permission" end
    local bounds = custom.limitsEnabled == true
    local minLevel, maxLevel = custom.minLevel or 1, custom.maxLevel or 10000
    local minEnergy, maxEnergy = custom.minEnergy or 0, custom.maxEnergy or 1e12
    local minRarity, maxHours, maxHelps = custom.minCrateRarity or 1, custom.maxHours or 2, custom.maxHelps or 6
    if bounds and (not balance(minLevel, 1) or not balance(maxLevel, 1) or minLevel > maxLevel or maxLevel > 10000
        or not balance(minEnergy, 0) or not balance(maxEnergy, 0) or minEnergy > maxEnergy or maxEnergy > 1e12
        or not balance(minRarity, 1) or minRarity > 9 or not balance(maxHours, .1) or maxHours > 24
        or not balance(maxHelps, 0) or maxHelps > 100) then return nil, "Invalid or inverted Heist bounds" end
    local chosen, chosenScore
    for _, row in ipairs(view.options) do
        if type(row) ~= "table" or type(row.id) ~= "string" or #row.id == 0
            or not integer(row.level, 1) or not integer(row.stake, 0) or not integer(row.energy, 0)
            or not integer(row.crateCount, 0) then return nil, "Current Heist cost and level quotes required" end
        if (not selected or selected[row.id]) and row.level <= view.level
            and row.stake <= cash and row.energy <= energy
            and (not bounds or row.level >= minLevel and row.level <= maxLevel
                and row.energy >= minEnergy and row.energy <= maxEnergy) then
            if not quote(row) then return nil, "Current Heist duration, reward, crate and helper quotes required" end
            if not bounds or row.crateRarity >= minRarity and row.duration <= maxHours * 3600 and row.helpGoal <= maxHelps then
                local rank = score(row, policy)
                if rank ~= rank or rank == math.huge or rank == -math.huge then return nil, "Heist score is outside the supported numeric range" end
                local better = not chosen or rank > chosenScore
                if policy == "Highest tier" and chosen then
                    better = row.level > chosen.level or row.level == chosen.level and rank > chosenScore
                elseif policy == "Custom" and chosen then
                    better = row.level > chosen.level or row.level == chosen.level
                        and (row.stake < chosen.stake or row.stake == chosen.stake and row.id < chosen.id)
                end
                if better then chosen, chosenScore = row, rank end
            end
        end
    end
    if not chosen then return nil, "No eligible personal Heist" end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "heists",
        actionKey = "heists:" .. view.serverDay .. ":"
            .. view.startsLeft .. ":" .. #view.catalogKey .. ":"
            .. view.catalogKey .. ":" .. chosen.id,
        resources = { cash = chosen.stake, energy = chosen.energy },
        intent = { kind = "heistStart", heistId = chosen.id,
            expectedStake = chosen.stake,
            expectedEnergy = chosen.energy,
            startsBefore = view.startsLeft,
            serverDay = view.serverDay,
            catalogKey = view.catalogKey,
            needsSequence = true } }, nil
end

return HeistStart
