-- Saved offscreen FamilyBossAction("state", nil), with exact Sync/family custody.
local FamilyBossQuery = {}
local function familyId(value)
    return type(value) == "string" and #value > 0 and #value <= 120
        and not value:find("[%c]")
        or type(value) == "number" and value == value and value >= 1
            and value <= 9007199254740991 and value % 1 == 0
end
local MAX = 9007199254740991
local fields = {"session", "account", "place", "release", "revision", "capturedAt"}
local stateFields = {"week", "famId", "inFamily", "stage", "resetAt", "freeMax", "freeUsed",
    "freeRegen", "nextFreeAt", "tickets", "myDmg"}
local claimFields = {"week", "stage", "expiresAt", "crateId", "crates", "cash", "gold", "medal", "border"}
local function number(value, minimum)
    return type(value) == "number" and value == value and value >= minimum and value <= MAX
end
local function integer(value, minimum) return number(value, minimum) and value % 1 == 0 end
local function header(raw, release)
    local native = type(raw) == "table" and raw.native
    local family = type(native) == "table" and native.family
    if type(raw) ~= "table" or raw.release ~= release or type(native) ~= "table"
        or native.fullSync ~= true or not number(native.serverNow, 0)
        or not integer(raw.revision, 0) or not number(raw.capturedAt, 0)
        or type(family) ~= "table" or not familyId(family.id) then return nil end
    local result = {familyId = family.id, serverNow = native.serverNow}
    for _, field in ipairs(fields) do result[field] = raw[field] end
    for _, field in ipairs({"session", "account", "place", "release"}) do
        if type(result[field]) ~= "string" or #result[field] == 0 or #result[field] > 200 then return nil end
    end
    return result
end
local function same(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs(fields) do if a[field] ~= b[field] then return false end end
    return a.familyId == b.familyId and a.serverNow == b.serverNow
end
local function dense(rows, maximum)
    if type(rows) ~= "table" or #rows > maximum then return false end
    local count = 0
    for key in pairs(rows) do
        if not integer(key, 1) or key > #rows then return false end
        count = count + 1
    end
    return count == #rows
end
local function state(reply)
    local result = {}
    for _, field in ipairs(stateFields) do
        local value = reply[field]
        if field == "famId" then
            if not familyId(value) then return nil end
        elseif value ~= nil and type(value) ~= "number" and type(value) ~= "boolean" then return nil end
        result[field] = value
    end
    result.claims, result.claimedStages = {}, {}
    if not dense(reply.claims or {}, 32) or not dense(reply.claimedStages or {}, 5) then return nil end
    for index, row in ipairs(reply.claims or {}) do
        if type(row) ~= "table" then return nil end
        local claim = {}
        for _, field in ipairs(claimFields) do
            local value = row[field]
            if field == "crateId" or field == "medal" or field == "border" then
                if value ~= nil and (type(value) ~= "string" or #value == 0 or #value > 120) then return nil end
            elseif value ~= nil and not integer(value, 0) then return nil end
            claim[field] = value
        end
        result.claims[index] = claim
    end
    for index, stage in ipairs(reply.claimedStages or {}) do result.claimedStages[index] = stage end
    return result
end
function FamilyBossQuery.new(stateReader, fingerprint, release)
    assert(type(stateReader) == "table" and type(stateReader.read) == "function"
        and type(fingerprint) == "string" and #fingerprint == 64 and fingerprint:match("^[%x]+$")
        and type(release) == "string" and #release > 0, "Missing Family Boss query dependencies")
    local closed, current = false, nil
    local result = {}
    function result:Prepare(snapshot)
        if closed then return nil, "Family Boss reader closed" end
        local bound = header(snapshot, release)
        if not bound then return nil, "Current full Family Boss Sync and membership required" end
        local request = {remote = "FamilyBossAction", method = "InvokeServer", arity = 2,
            args = {"state"}, kind = "readOnly"}
        current = {request = request, header = bound}
        return request, nil
    end
    function result:Accept(snapshot, request, reply)
        if closed or current == nil or request ~= current.request
            or not same(header(snapshot, release), current.header) then return nil, "Stale Family Boss state reply" end
        local bound = current.header
        if type(reply) ~= "table" or reply.ok ~= true or reply.pending == true
            or reply.code == "rate_limited" or reply.code == "busy" or reply.code == "presence"
            or reply.famId ~= bound.familyId or not number(reply.serverNow, bound.serverNow)
            or reply.serverNow > bound.serverNow + 2 then return nil, "Family Boss state is unavailable or stale" end
        local copied = state(reply)
        if not copied then return nil, "Invalid Family Boss state projection" end
        local enriched = {}
        for key, value in pairs(snapshot) do enriched[key] = value end
        enriched.familyTakedownProof = {account = bound.account, capturedAt = bound.capturedAt,
            sourceKey = fingerprint:lower(), header = bound, state = copied,
            observedServerNow = reply.serverNow}
        local context = {}
        for _, field in ipairs(fields) do context[field] = bound[field] end
        context.serverNow = bound.serverNow
        local ok, view, reason = pcall(stateReader.read, enriched, context)
        if not ok or not view then return nil, ok and reason or "Family Boss state validation raised" end
        current = nil
        return enriched, nil
    end
    function result:Close() closed, current = true, nil end
    return result
end
return FamilyBossQuery
