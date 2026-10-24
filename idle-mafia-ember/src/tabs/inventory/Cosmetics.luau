-- Loose unbound background/border improvements; no Collection transfer.
local Cosmetics = {}

local fields = { background = "equippedBackground",
    border = "equippedBorder" }
local remotes = { background = "EquipBackground",
    border = "EquipBorder" }

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function finite(value)
    return type(value) == "number" and value == value
        and value > -math.huge and value < math.huge
end

local function same(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or a[field] ~= b[field] then return false end
    end
    return true
end

local function count(map, id)
    if type(map) ~= "table" then return nil end
    local value = map[id] or 0
    if not integer(value, 0) then return nil end
    return value
end

function Cosmetics.new(gameData, fingerprint, release)
    assert(type(gameData) == "table"
        and type(gameData.ITEMS_BY_ID) == "table"
        and type(fingerprint) == "string" and #fingerprint == 64
        and fingerprint:match("^[%x]+$")
        and type(release) == "string" and #release > 0,
        "Missing reviewed Inventory cosmetic source")
    local items, sourceKey = {}, fingerprint:lower()
    for id, row in pairs(gameData.ITEMS_BY_ID) do
        if type(id) == "string" and type(row) == "table"
            and row.id == id and fields[row.kind]
            and finite(row.atk) and finite(row.def) then
            items[id] = { id = id, kind = row.kind,
                atk = row.atk, def = row.def }
        end
    end

    local function read(raw, context)
        if not same(raw, context) or raw.release ~= release
            or raw.revision ~= context.revision
            or raw.capturedAt ~= context.capturedAt
            or context.cosmeticSourceKey ~= sourceKey then
            return nil, "Current cosmetic source required"
        end
        local native = raw.native
        if type(native) ~= "table" or native.fullSync ~= true
            or type(native.inventory) ~= "table"
            or type(native.inventoryBound) ~= "table"
            or type(native.collectionBound) ~= "table" then
            return nil, "Current cosmetic custody required"
        end
        local worn = {}
        for kind, field in pairs(fields) do
            local id = native[field]
            if id ~= nil and (type(id) ~= "string"
                or type(items[id]) ~= "table"
                or items[id].kind ~= kind) then
                return nil, "Unknown worn cosmetic"
            end
            worn[kind] = id
        end
        for id, row in pairs(items) do
            if count(native.inventoryBound, id) == nil
                or count(native.collectionBound, id) == nil then
                return nil, "Invalid bound cosmetic custody"
            end
            if count(native.inventoryBound, id) > 0
                or count(native.collectionBound, id) > 0 then
                return nil, "Bound cosmetic transfer precedence unverified"
            end
        end
        local options = {}
        for id, amount in pairs(native.inventory) do
            if type(id) ~= "string" or not integer(amount, 0) then
                return nil, "Invalid loose cosmetic inventory"
            end
            local item = items[id]
            if amount > 0 and item then
                local currentId = worn[item.kind]
                if currentId ~= id then
                    local old = currentId and items[currentId]
                    local attack = item.atk - (old and old.atk or 0)
                    local defense = item.def - (old and old.def or 0)
                    if attack >= 0 and defense >= 0
                        and attack + defense > 0 then
                        options[#options + 1] = { id = id,
                            kind = item.kind, oldId = currentId,
                            attack = attack, defense = defense,
                            count = amount }
                    end
                end
            end
        end
        return { session = context.session,
            account = context.account, place = context.place,
            release = context.release, revision = context.revision,
            capturedAt = context.capturedAt,
            sourceKey = sourceKey, options = options }, nil
    end

    return { sourceKey = sourceKey, read = read,
        propose = Cosmetics.propose,
        capture = function(proposal, before)
            if type(proposal) ~= "table"
                or type(proposal.intent) ~= "table"
                or proposal.intent.sourceKey ~= sourceKey
                or before.release ~= release then
                return nil, "Cosmetic source changed"
            end
            local view = read(before, { session = proposal.session,
                account = proposal.account, place = proposal.place,
                release = proposal.release,
                revision = proposal.revision,
                capturedAt = before.capturedAt,
                cosmeticSourceKey = sourceKey })
            if not view then return nil, "Cosmetic custody changed" end
            local found = false
            for _, row in ipairs(view.options) do
                if row.id == proposal.intent.itemId
                    and row.kind == proposal.intent.cosmeticKind
                    and row.oldId == proposal.intent.oldId then
                    found = true
                    break
                end
            end
            if not found then return nil, "Cosmetic gain changed" end
            return Cosmetics.capture(proposal, before)
        end,
        evaluate = Cosmetics.evaluate }
end

function Cosmetics.propose(view, settings)
    if type(view) ~= "table" or type(settings) ~= "table"
        or not same(view, view) then return nil, "Missing cosmetic input" end
    if settings.enabled ~= true then return nil, "Cosmetics disabled" end
    local policy = settings.policy
    if policy ~= "Attack" and policy ~= "Defense"
        and policy ~= "Balanced" then
        return nil, "Select a supported cosmetic objective"
    end
    local best, bestScore
    for _, row in ipairs(view.options or {}) do
        local score = policy == "Attack" and row.attack
            or policy == "Defense" and row.defense
            or row.attack + row.defense
        if score > 0 and (not best or score > bestScore
            or (score == bestScore and row.id < best.id)) then
            best, bestScore = row, score
        end
    end
    if not best then return nil, "No safe loose cosmetic gain" end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "cosmetics",
        actionKey = "cosmetics:" .. view.sourceKey .. ":"
            .. best.kind .. ":" .. tostring(best.oldId or "")
            .. ":" .. best.id,
        resources = {},
        intent = { kind = "cosmetics",
            remote = remotes[best.kind], args = { best.id },
            cosmeticKind = best.kind, oldId = best.oldId,
            itemId = best.id, count = best.count,
            sourceKey = view.sourceKey } }, nil
end

function Cosmetics.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    local native = type(before) == "table" and before.native
    local field = type(intent) == "table" and fields[intent.cosmeticKind]
    if type(proposal) ~= "table" or proposal.feature ~= "cosmetics"
        or type(intent) ~= "table" or intent.kind ~= "cosmetics"
        or not field or not same(proposal, before)
        or proposal.revision ~= before.revision
        or type(native) ~= "table" or native.fullSync ~= true
        or native[field] ~= intent.oldId
        or count(native.inventory, intent.itemId) ~= intent.count
        or not integer(intent.count, 1)
        or count(native.inventoryBound, intent.itemId) ~= 0
        or count(native.collectionBound, intent.itemId) ~= 0
        or type(intent.args) ~= "table"
        or intent.args[1] ~= intent.itemId then
        return nil, "Exact loose cosmetic or worn state changed"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision,
        cosmeticKind = intent.cosmeticKind,
        oldId = intent.oldId, itemId = intent.itemId }, nil
end

function Cosmetics.evaluate(proposal, before, after, reply,
    baseline)
    if type(proposal) ~= "table" or type(reply) ~= "table"
        or not same(proposal, before) or not same(proposal, after)
        or not same(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or before.revision ~= baseline.revision
        or not integer(after.revision, baseline.revision + 1) then
        return "pending"
    end
    if reply.ok == false then return "rejected" end
    local native = after.native
    local field = fields[baseline.cosmeticKind]
    if reply.ok ~= true or type(native) ~= "table"
        or native.fullSync ~= true or not field
        or native[field] ~= baseline.itemId then return "pending" end
    return "confirmed"
end

return Cosmetics
