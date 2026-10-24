-- Saved CrewAction("sort") contract; exact roster order and pinned slots.
local CrewSort = {}

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
    local crew = type(native) == "table" and native.crew
    if type(native) ~= "table" or native.fullSync ~= true
        or type(crew) ~= "table" then return nil end
    local rows, identities, count = {}, {}, 0
    for index, member in pairs(crew) do
        if type(index) ~= "number" or index % 1 ~= 0
            or index < 1 or index > 32 or type(member) ~= "table"
            or (index > 1 and (type(member.name) ~= "string"
                or #member.name == 0 or #member.name > 64
                or type(member.rarity) ~= "number"
                or member.rarity ~= member.rarity
                or member.rarity < 0 or member.rarity > 20
                or member.rarity % 1 ~= 0)) then
            return nil
        end
        count = count + 1
        if count > 32 then return nil end
        local key = index == 1 and "PLAYER" or
            #member.name .. ":" .. member.name .. ":" .. member.rarity
        if identities[key] then return nil end
        identities[key] = true
        rows[index] = { key = key,
            pinned = index == 1 or member.duty ~= nil
                or member.rolling == true }
    end
    if not rows[1] then return nil end
    return rows, count
end

function CrewSort.read(raw, context)
    if not same(raw, context) or raw.revision ~= context.revision
        or raw.capturedAt ~= context.capturedAt then
        return nil, "Crew sort snapshot changed"
    end
    local rows, count = roster(raw)
    if not rows then return nil, "Current unique Crew roster required" end
    local order, movable = {}, 0
    for index = 1, 32 do
        local row = rows[index]
        if row then
            order[#order + 1] = index .. "=" .. row.key
            if not row.pinned then movable = movable + 1 end
        end
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        rows = rows, count = count, movable = movable,
        orderKey = table.concat(order, "|") }, nil
end

function CrewSort.propose(view, settings)
    if type(view) ~= "table" or type(settings) ~= "table" then
        return nil, "Missing Crew sort input"
    end
    if settings.enabled ~= true then return nil, "Crew sort disabled" end
    if not same(view, view) or type(view.orderKey) ~= "string"
        or type(view.movable) ~= "number" or view.movable < 2 then
        return nil, "Fewer than two available Crew members"
    end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "crewSort",
        actionKey = "crewSort:" .. view.orderKey,
        resources = {}, intent = { kind = "crewSort",
            remote = "CrewAction", args = { "sort" } } }, nil
end

function CrewSort.capture(proposal, before)
    if type(proposal) ~= "table" or proposal.feature ~= "crewSort"
        or type(proposal.intent) ~= "table"
        or proposal.intent.kind ~= "crewSort"
        or not same(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Crew sort baseline changed"
    end
    local rows, count = roster(before)
    if not rows then return nil, "Crew sort baseline unavailable" end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, rows = rows, count = count }, nil
end

function CrewSort.evaluate(proposal, before, after, reply, baseline)
    if type(proposal) ~= "table" or type(reply) ~= "table"
        or not same(proposal, before) or not same(proposal, after)
        or not same(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or before.revision ~= baseline.revision
        or type(after.revision) ~= "number"
        or after.revision <= baseline.revision then return "pending" end
    local current, count = roster(after)
    if not current or count ~= baseline.count then return "pending" end
    local oldKeys, newKeys, moved = {}, {}, false
    for index, row in pairs(baseline.rows) do
        oldKeys[row.key] = true
        if current[index] and current[index].pinned ~= row.pinned then
            return "pending"
        end
        if row.pinned and (not current[index]
            or current[index].key ~= row.key) then return "pending" end
        if not current[index] or current[index].key ~= row.key then
            moved = true
        end
    end
    for _, row in pairs(current) do newKeys[row.key] = true end
    for key in pairs(oldKeys) do
        if not newKeys[key] then return "pending" end
    end
    if reply.ok == false then return "rejected" end
    if reply.ok == true and type(reply.changed) == "boolean"
        and moved == reply.changed then return "confirmed" end
    return "pending"
end

return CrewSort
