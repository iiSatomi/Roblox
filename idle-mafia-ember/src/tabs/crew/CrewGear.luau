-- Conservative loose-inventory CrewEquip swaps with native set comparison.
local CrewGear = {}

local kinds = { weapon = true, armor = true, vehicle = true }

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function timestamp(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
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
    local amount = map[id] or 0
    if not integer(amount, 0) then return nil end
    return amount
end

local function member(raw, slot)
    local native = type(raw) == "table" and raw.native
    local crew = type(native) == "table" and native.crew
    local row = type(crew) == "table" and crew[slot]
    if type(native) ~= "table" or native.fullSync ~= true
        or type(row) ~= "table" then return nil end
    if slot == 1 then return row end
    if type(row.name) ~= "string" or #row.name == 0
        or #row.name > 64 or not integer(row.rarity, 1) then
        return nil
    end
    return row
end

local function identity(row,slot)
    if slot==1 then return "PLAYER" end
    local id=row.healId
    if type(id)~="string" or #id==0 or #id>128 then return nil end
    return "ID:"..#id..":"..id
end

function CrewGear.new(gameData, gearSets, fingerprint, release)
    assert(type(gameData) == "table"
        and type(gameData.ITEMS_BY_ID) == "table"
        and type(gearSets) == "table"
        and type(gearSets.slotBonus) == "function"
        and type(fingerprint) == "string" and #fingerprint == 64
        and fingerprint:match("^[%x]+$")
        and type(release) == "string" and #release > 0,
        "Missing reviewed Crew gear source")
    local items, sourceKey = {}, fingerprint:lower()
    local slotBonus = gearSets.slotBonus
    for id, row in pairs(gameData.ITEMS_BY_ID) do
        if type(id) == "string" and type(row) == "table"
            and row.id == id and kinds[row.kind]
            and finite(row.atk) and finite(row.def) then
            items[id] = { id = id, kind = row.kind,
                atk = row.atk, def = row.def,
                rankOnly = row.rankOnly == true }
        end
    end

    local function read(raw, context)
        if not same(raw, context) or raw.release ~= release
            or raw.revision ~= context.revision
            or raw.capturedAt ~= context.capturedAt
            or context.gearSourceKey ~= sourceKey then
            return nil, "Current Crew gear source required"
        end
        local native = raw.native
        local crew = type(native) == "table" and native.crew
        if type(native) ~= "table" or native.fullSync ~= true
            or not timestamp(native.serverNow)
            or type(crew) ~= "table" or #crew < 1
            or #crew > 46 or type(native.inventory) ~= "table"
            or type(native.inventoryBound) ~= "table" then
            return nil, "Current Crew and loose inventory required"
        end
        local available, seen, total = {}, {}, 0
        for slot, row in pairs(crew) do
            if not integer(slot, 1) or slot > #crew
                or type(row) ~= "table" then
                return nil, "Invalid Crew roster"
            end
            total = total + 1
            if slot > 1 and row.rarity ~= nil then
                if not member(raw, slot) then
                    return nil, "Unknown Crew identity"
                end
                local key = identity(row, slot)
                if key and seen[key] then return nil, "Duplicate Crew identity" end
                if key then seen[key] = true end
            end
            if slot == 1 or row.rarity ~= nil and identity(row,slot)~=nil then
                if not timestamp(row.injuredUntil or 0) then
                    return nil, "Invalid Crew injury time"
                end
                if row.duty == nil and row.rolling ~= true
                    and row.training == nil
                    and (row.injuredUntil or 0) <= native.serverNow then
                    available[#available + 1] = { slot = slot,
                        identity = identity(row, slot), row = row }
                end
            end
        end
        if total ~= #crew then return nil, "Sparse Crew roster" end
        local candidates = {}
        for id, amount in pairs(native.inventory) do
            if type(id) ~= "string" or not integer(amount, 0) then
                return nil, "Invalid loose gear custody"
            end
            local item = items[id]
            if amount > 0 and type(item) == "table"
                and item.id == id and kinds[item.kind]
                and item.rankOnly ~= true and not id:find("@", 1, true)
                and finite(item.atk) and finite(item.def)
                and item.atk >= 0 and item.def >= 0
                and count(native.inventoryBound, id) ~= nil then
                for _, entry in ipairs(available) do
                    local row, kind = entry.row, item.kind
                    if row[kind .. "Bound"] ~= true
                        and row[kind] ~= id then
                        local oldId = row[kind]
                        local old = oldId and items[oldId]
                        if oldId == nil or (type(old) == "table"
                            and old.kind == kind and finite(old.atk)
                            and finite(old.def)) then
                            local nextGear = { weapon = row.weapon,
                                armor = row.armor, vehicle = row.vehicle }
                            nextGear[kind] = id
                            local okOld, oldAtk, oldDef = pcall(
                                slotBonus, row, items)
                            local okNew, newAtk, newDef = pcall(
                                slotBonus, nextGear, items)
                            if okOld and okNew and finite(oldAtk)
                                and finite(oldDef) and finite(newAtk)
                                and finite(newDef) then
                                local attack = item.atk
                                    - (old and old.atk or 0)
                                    + newAtk - oldAtk
                                local defense = item.def
                                    - (old and old.def or 0)
                                    + newDef - oldDef
                                if attack >= 0 and defense >= 0
                                    and attack + defense > 0 then
                                    candidates[#candidates + 1] = {
                                        slot = entry.slot,
                                        identity = entry.identity,
                                        kind = kind, oldId = oldId,
                                        itemId = id, attack = attack,
                                        defense = defense,
                                        count = amount }
                                end
                            else
                                return nil, "Native GearSets comparison unavailable"
                            end
                        end
                    end
                end
            end
        end
        return { session = context.session, account = context.account,
            place = context.place, release = context.release,
            revision = context.revision, capturedAt = context.capturedAt,
            sourceKey = sourceKey, candidates = candidates }, nil
    end

    return { sourceKey = sourceKey, read = read,
        propose = CrewGear.propose,
        capture = function(proposal, before)
            if type(proposal) ~= "table"
                or type(proposal.intent) ~= "table"
                or proposal.intent.sourceKey ~= sourceKey
                or before.release ~= release then
                return nil, "Crew gear source changed"
            end
            return CrewGear.capture(proposal, before)
        end,
        evaluate = CrewGear.evaluate,
        recoverSaved=function(data,after)
            local p=type(data)=="table" and data.proposal
            if type(p)~="table" or type(p.intent)~="table" or p.intent.sourceKey~=sourceKey
                or type(data.before)~="table" or data.before.release~=release then return nil end
            return CrewGear.recoverSaved(data,after)
        end }
end

function CrewGear.propose(view, settings)
    if type(view) ~= "table" or type(settings) ~= "table"
        or not same(view, view) then return nil, "Missing Crew gear input" end
    if settings.enabled ~= true then return nil, "Crew gear disabled" end
    local policy = settings.policy
    if policy ~= "Attack" and policy ~= "Defense"
        and policy ~= "Balanced" then
        return nil, "Select a supported Crew gear objective"
    end
    local best, bestScore
    for _, row in ipairs(view.candidates or {}) do
        local score = policy == "Attack" and row.attack
            or policy == "Defense" and row.defense
            or row.attack + row.defense
        if score > 0 and (not best
            or score > bestScore
            or (score == bestScore and row.slot < best.slot)) then
            best, bestScore = row, score
        end
    end
    if not best then return nil, "No safe loose-inventory gear gain" end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "crewGear",
        actionKey = "crewGear:" .. view.sourceKey .. ":"
            .. best.slot .. ":" .. best.kind .. ":"
            .. tostring(best.oldId or "") .. ":" .. best.itemId,
        resources = { [best.itemId] = 1 },
        intent = { kind = "crewGear",
            slot = best.slot, identity = best.identity,
            gearKind = best.kind, oldId = best.oldId,
            itemId = best.itemId, oldCount = best.count,
            sourceKey = view.sourceKey } }, nil
end

function CrewGear.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "crewGear"
        or type(intent) ~= "table" or intent.kind ~= "crewGear"
        or not kinds[intent.gearKind]
        or not integer(intent.slot, 1)
        or not same(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Crew gear baseline changed"
    end
    local row = member(before, intent.slot)
    local native = before.native
    if not row or identity(row, intent.slot) ~= intent.identity
        or row[intent.gearKind] ~= intent.oldId
        or row[intent.gearKind .. "Bound"] == true
        or row.duty ~= nil or row.rolling == true
        or row.training ~= nil
        or (row.injuredUntil or 0) > native.serverNow
        or count(native.inventory, intent.itemId) ~= intent.oldCount
        or intent.oldCount < 1 then
        return nil, "Crew gear member or loose copy changed"
    end
    local inputBound=count(native.inventoryBound,intent.itemId)
    local oldLoose=intent.oldId and count(native.inventory,intent.oldId) or 0
    local oldBound=intent.oldId and count(native.inventoryBound,intent.oldId) or 0
    if inputBound==nil or oldLoose==nil or oldBound==nil or intent.oldId==intent.itemId
        or not timestamp(native.serverNow) then return nil,"Exact gear origins unavailable" end
    local other={}
    for _,kind in ipairs({"weapon","armor","vehicle"}) do
        if kind~=intent.gearKind then other[kind]=row[kind];other[kind.."Bound"]=row[kind.."Bound"]==true end
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        serverNow=native.serverNow,inputBound=inputBound,oldLoose=oldLoose,oldBound=oldBound,other=other,
        revision = proposal.revision, slot = intent.slot,
        identity = intent.identity, gearKind = intent.gearKind,
        oldId = intent.oldId, itemId = intent.itemId,
        oldCount = intent.oldCount }, nil
end

local function reconcile(proposal,before,after,reply,baseline,restart)
    if type(proposal)~="table" or type(reply)~="table" or type(after)~="table" or type(baseline)~="table"
        or not same(proposal,before) or not same(proposal,baseline)
        or proposal.account~=after.account or proposal.place~=after.place or proposal.release~=after.release
        or (not restart and not same(proposal,after)) or proposal.revision~=baseline.revision
        or before.revision~=baseline.revision or not integer(after.revision,0)
        or type(after.native)~="table" or not timestamp(after.native.serverNow)
        or not timestamp(baseline.serverNow) or after.native.serverNow<baseline.serverNow
        or not (after.session==baseline.session and after.revision>baseline.revision
            or restart and after.session~=baseline.session and after.native.serverNow>baseline.serverNow)
        or reply.pending==true or reply.code=="rate_limited" or reply.code=="presence" then return "pending" end
    local row=member(after,baseline.slot)
    local native=after.native
    if not row or identity(row,baseline.slot)~=baseline.identity or row.duty~=nil or row.rolling==true
        or row.training~=nil or (row.injuredUntil or 0)>native.serverNow
        or row[baseline.gearKind.."Bound"]==true
        or count(native.inventoryBound,baseline.itemId)~=baseline.inputBound then return "pending" end
    for kind,value in pairs(baseline.other or {}) do
        if kind:sub(-5)=="Bound" then
            if (row[kind]==true)~=value then return "pending" end
        elseif row[kind]~=value then return "pending" end
    end
    for _,kind in ipairs({"weapon","armor","vehicle"}) do
        if kind~=baseline.gearKind and row[kind]~=(baseline.other or {})[kind] then return "pending" end
    end
    local oldLoose=baseline.oldId and count(native.inventory,baseline.oldId) or 0
    local oldBound=baseline.oldId and count(native.inventoryBound,baseline.oldId) or 0
    if oldBound~=baseline.oldBound then return "pending" end
    local current=count(native.inventory,baseline.itemId)
    if reply.ok==false then
        return row[baseline.gearKind]==baseline.oldId and current==baseline.oldCount and oldLoose==baseline.oldLoose
            and "rejected" or "pending"
    end
    if reply.ok==true and row[baseline.gearKind]==baseline.itemId and current==baseline.oldCount-1
        and oldLoose==baseline.oldLoose+(baseline.oldId and 1 or 0) then return "confirmed" end
    return "pending"
end
function CrewGear.evaluate(proposal,before,after,reply,baseline)
    return reconcile(proposal,before,after,reply,baseline,false)
end
local function equal(a,b)
    if type(a)~=type(b) then return false end
    if type(a)~="table" then return a==b end
    for k,v in pairs(a) do if not equal(v,b[k]) then return false end end
    for k in pairs(b) do if a[k]==nil then return false end end
    return true
end
function CrewGear.recoverSaved(data,after)
    if type(data)~="table" or type(data.reply)~="table" then return nil end
    local baseline=CrewGear.capture(data.proposal,data.before)
    if not baseline or not equal(baseline,data.baseline) then return nil end
    local outcome=reconcile(data.proposal,data.before,after,data.reply,baseline,true)
    return (outcome=="confirmed" or outcome=="rejected") and outcome or nil
end
return CrewGear
