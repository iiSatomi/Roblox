-- CrewAction("train", slot) with a same-release quote and exact start proof.
local CrewTrain = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function same(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or a[field] ~= b[field] then return false end
    end
    return true
end

local function roster(raw)
    local native = type(raw) == "table" and raw.native
    local source = type(native) == "table" and native.crew
    if type(native) ~= "table" or native.fullSync ~= true
        or type(source) ~= "table" or #source < 2
        or #source > 32 then return nil end
    local rows, seen, count = {}, {}, 0
    for slot, member in pairs(source) do
        if not integer(slot, 1) or slot > #source
            or type(member) ~= "table" then return nil end
        count = count + 1
        if slot > 1 then
            if type(member.name) ~= "string" or #member.name == 0
                or #member.name > 64 or not integer(member.rarity, 1)
                or not integer(member.train or 0, 0)
                or not integer(member.injuredUntil or 0, 0)
                or not integer(member.recalledUntil or 0, 0)
                or (member.training ~= nil
                    and type(member.training) ~= "table") then
                return nil
            end
            local identity = #member.name .. ":" .. member.name
                .. ":" .. member.rarity
            if seen[identity] then return nil end
            seen[identity] = true
            rows[slot] = { slot = slot, name = member.name,
                rarity = member.rarity, level = member.train or 0,
                injuredUntil = member.injuredUntil or 0,
                recalledUntil = member.recalledUntil or 0,
                duty = member.duty ~= nil,
                rolling = member.rolling == true,
                recalling = member.recalling == true,
                training = member.training ~= nil }
        end
    end
    if count ~= #source or not source[1] then return nil end
    return rows
end

function CrewTrain.read(raw, context)
    if not same(raw, context) or raw.revision ~= context.revision
        or raw.capturedAt ~= context.capturedAt then
        return nil, "Crew training snapshot changed"
    end
    local native, catalog = raw.native, raw.trainingCatalog
    if type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.serverNow, 0)
        or context.serverNow ~= native.serverNow
        or not integer(native.cash, 0)
        or type(catalog) ~= "table"
        or catalog.release ~= context.release
        or catalog.catalogKey ~= context.trainingCatalogKey
        or type(catalog.catalogKey) ~= "string"
        or not integer(catalog.minRarity, 1)
        or not integer(catalog.maxLevel, 1)
        or not integer(catalog.maxConcurrent, 1)
        or type(catalog.cost) ~= "table"
        or type(catalog.seconds) ~= "table" then
        return nil, "Current Crew training catalog and cash required"
    end
    local members = roster(raw)
    if not members then return nil, "Unique current Crew roster required" end
    local active, available = 0, 0
    for _, member in pairs(members) do
        if member.training then active = active + 1 end
        if not member.training and not member.duty
            and not member.rolling and not member.recalling
            and member.injuredUntil <= native.serverNow
            and member.recalledUntil <= native.serverNow then
            available = available + 1
        end
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        serverNow = native.serverNow, cash = native.cash,
        catalogKey = catalog.catalogKey,
        minRarity = catalog.minRarity,
        maxLevel = catalog.maxLevel,
        maxConcurrent = catalog.maxConcurrent,
        cost = catalog.cost, seconds = catalog.seconds,
        members = members, active = active, available = available }, nil
end

function CrewTrain.propose(view, settings)
    if type(view) ~= "table" or type(settings) ~= "table" then
        return nil, "Missing Crew training input"
    end
    if settings.enabled ~= true then return nil, "Crew training disabled" end
    local custom = type(settings.custom) == "table"
        and settings.custom or settings
    if not integer(custom.minRarity, 1)
        or not integer(custom.targetLevel, 1)
        or not integer(custom.maxCost, 0)
        or not integer(custom.maxConcurrent, 1)
        or not integer(custom.cashReserve, 0) then
        return nil, "Crew training limits required"
    end
    if not same(view, view) or not integer(view.revision, 0)
        or type(view.catalogKey) ~= "string"
        or type(view.members) ~= "table"
        or not integer(view.cash, 0)
        or not integer(view.active, 0)
        or not integer(view.available, 0)
        or not integer(view.maxConcurrent, 1)
        or not integer(view.maxLevel, 1)
        or not integer(view.minRarity, 1)
        or type(view.cost) ~= "table"
        or type(view.seconds) ~= "table" then
        return nil, "Invalid Crew training view"
    end
    if view.active >= math.min(custom.maxConcurrent,
        view.maxConcurrent) then
        return nil, "Crew training concurrency limit reached"
    end
    if view.available <= 1 then
        return nil, "Keeping one available henchman at home"
    end
    local target = math.min(custom.targetLevel, view.maxLevel)
    local rarityFloor = math.max(custom.minRarity, view.minRarity)
    local chosen
    for _, member in pairs(view.members) do
        if member.rarity >= rarityFloor and member.level < target
            and not member.training and not member.duty
            and not member.rolling and not member.recalling
            and member.injuredUntil <= view.serverNow
            and member.recalledUntil <= view.serverNow then
            local to = member.level + 1
            local cost = type(view.cost[member.rarity]) == "table"
                and view.cost[member.rarity][to]
            local seconds = type(view.seconds[member.rarity]) == "table"
                and view.seconds[member.rarity][to]
            if integer(cost, 1) and integer(seconds, 1)
                and cost <= custom.maxCost
                and view.cash - cost >= custom.cashReserve then
                local row = { member = member, to = to,
                    cost = cost, seconds = seconds }
                if not chosen or member.rarity > chosen.member.rarity
                    or (member.rarity == chosen.member.rarity
                        and member.level < chosen.member.level)
                    or (member.rarity == chosen.member.rarity
                        and member.level == chosen.member.level
                        and member.slot < chosen.member.slot) then
                    chosen = row
                end
            end
        end
    end
    if not chosen then return nil, "No eligible affordable Crew training" end
    local member = chosen.member
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "crewTrain",
        actionKey = "crewTrain:" .. view.catalogKey .. ":"
            .. member.slot .. ":" .. member.level .. ":"
            .. #member.name .. ":" .. member.name .. ":"
            .. member.rarity,
        resources = { cash = chosen.cost },
        intent = { kind = "crewTrain", remote = "CrewAction",
            args = { "train", member.slot }, slot = member.slot,
            name = member.name, rarity = member.rarity,
            from = member.level, to = chosen.to,
            quotedCost = chosen.cost,
            quotedSeconds = chosen.seconds,
            cashReserve = custom.cashReserve,
            catalogKey = view.catalogKey } }, nil
end

function CrewTrain.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "crewTrain"
        or type(intent) ~= "table" or intent.kind ~= "crewTrain"
        or not integer(intent.slot, 2) or intent.slot > 32
        or not integer(intent.from, 0)
        or not integer(intent.to, intent.from + 1)
        or intent.to ~= intent.from + 1
        or not integer(intent.quotedCost, 1)
        or not integer(intent.quotedSeconds, 1)
        or not integer(intent.cashReserve, 0)
        or not same(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Crew training baseline changed"
    end
    local members = roster(before)
    local member = members and members[intent.slot]
    local catalog = before.trainingCatalog
    if not member or member.name ~= intent.name
        or member.rarity ~= intent.rarity
        or member.level ~= intent.from or member.training
        or type(catalog) ~= "table"
        or catalog.catalogKey ~= intent.catalogKey
        or catalog.release ~= proposal.release
        or type(catalog.cost) ~= "table"
        or type(catalog.seconds) ~= "table"
        or type(catalog.cost[intent.rarity]) ~= "table"
        or type(catalog.seconds[intent.rarity]) ~= "table"
        or catalog.cost[intent.rarity][intent.to] ~= intent.quotedCost
        or catalog.seconds[intent.rarity][intent.to]
            ~= intent.quotedSeconds
        or not integer(before.native.cash,
            intent.quotedCost + intent.cashReserve) then
        return nil, "Exact Crew training quote unavailable"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, slot = intent.slot,
        name = intent.name, rarity = intent.rarity,
        from = intent.from, to = intent.to,
        quotedCost = intent.quotedCost }, nil
end

function CrewTrain.evaluate(proposal, before, after, reply, baseline)
    if type(proposal) ~= "table" or type(reply) ~= "table"
        or not same(proposal, before) or not same(proposal, after)
        or not same(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or before.revision ~= baseline.revision
        or not integer(after.revision, baseline.revision + 1) then
        return "pending"
    end
    local members = roster(after)
    local member = members and members[baseline.slot]
    local rawMember = type(after.native) == "table"
        and type(after.native.crew) == "table"
        and after.native.crew[baseline.slot]
    if not member or member.name ~= baseline.name
        or member.rarity ~= baseline.rarity
        or member.level ~= baseline.from
        or type(rawMember.training) ~= "table" then
        return "pending"
    end
    if reply.ok == false then return "rejected" end
    if reply.ok == true
        and rawMember.training.to == baseline.to
        and integer(after.native.serverNow, 0)
        and integer(rawMember.training.endsAt,
            after.native.serverNow + 1) then
        return "confirmed"
    end
    return "pending"
end

return CrewTrain
