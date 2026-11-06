-- Exact newer Collection-to-loose transfer, preserving the checkpoint.
local MarketCollectionWithdrawEvidence = {}

local function finite(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

local function integer(value, low, high)
    return type(value) == "number" and value == value
        and value >= low and value <= high and value % 1 == 0
end

local function text(value, maximum)
    return type(value) == "string" and #value > 0
        and #value <= maximum
end

local function same(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if not text(a[field], 200) or a[field] ~= b[field] then
            return false
        end
    end
    return true
end

local function count(map, id)
    if type(map) ~= "table" then return nil end
    local value = map[id]
    if value == nil then value = 0 end
    if not integer(value, 0, 1000000000) then return nil end
    return value
end

local function variants(map, id)
    if type(map) ~= "table" then return nil end
    local result, total, rows = {}, 0, 0
    for key, value in pairs(map) do
        rows = rows + 1
        if rows > 10000 or type(key) ~= "string"
            or not integer(value, 0, 1000000000) then
            return nil
        end
        if key:sub(1, #id + 1) == id .. "@" then
            result[key] = value
            total = total + value
            if total > 1000000000 then return nil end
        end
    end
    return result, total
end

local function sameMap(a, b)
    for key, value in pairs(a) do
        if b[key] ~= value then return false end
    end
    for key in pairs(b) do
        if a[key] == nil then return false end
    end
    return true
end

local function state(raw, id)
    local native = type(raw) == "table" and raw.native
    if type(native) ~= "table" or native.fullSync ~= true then
        return nil
    end
    local loose = count(native.inventory, id)
    local bound = count(native.inventoryBound, id)
    local collected = count(native.collection, id)
    local collectedBound = count(native.collectionBound, id)
    local gold = count(native.inventory, "gold_bar")
    local boundGold = count(native.inventoryBound, "gold_bar")
    local looseVariants, looseTotal = variants(native.collection, id)
    local boundVariants, boundTotal = variants(
        native.collectionBound, id)
    if loose == nil or bound == nil or collected == nil
        or collectedBound == nil or gold == nil
        or boundGold == nil or not looseVariants
        or not boundVariants then return nil end
    local total = collected + collectedBound
        + looseTotal + boundTotal
    if total > 1000000000 then return nil end
    return { loose = loose, bound = bound,
        collected = collected, collectedBound = collectedBound,
        gold = gold, boundGold = boundGold,
        looseVariants = looseVariants,
        boundVariants = boundVariants,
        total = total }
end

local function unchanged(a, b)
    for _, field in ipairs({ "loose", "bound", "collected",
        "collectedBound", "gold", "boundGold", "total" }) do
        if a[field] ~= b[field] then return false end
    end
    return sameMap(a.looseVariants, b.looseVariants)
        and sameMap(a.boundVariants, b.boundVariants)
end

function MarketCollectionWithdrawEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if not same(proposal, before)
        or proposal.preflightOnly ~= true
        or proposal.feature ~= "marketSell"
        or type(intent) ~= "table"
        or intent.kind ~= "marketCollectionWithdraw"
        or not text(intent.itemId, 120)
        or intent.itemId == "gold_bar"
        or not integer(intent.quantity, 1, 999)
        or not integer(intent.checkpointFloor, 0, 1000000000)
        or not integer(intent.collectionBefore,
            intent.quantity, 1000000000)
        or not integer(intent.looseBefore, 0, 1000000000)
        or type(before.native) ~= "table"
        or not finite(before.native.serverNow)
        or not integer(before.revision, 0, 9007199254740991)
        or proposal.revision ~= before.revision then
        return nil, "Market Collection baseline mismatch"
    end
    local saved = state(before, intent.itemId)
    if not saved
        or saved.collected ~= intent.collectionBefore
        or saved.loose ~= intent.looseBefore
        or saved.total - intent.quantity
            < intent.checkpointFloor then
        return nil, "Protected Collection surplus unavailable"
    end
    saved.session = proposal.session
    saved.account = proposal.account
    saved.place = proposal.place
    saved.release = proposal.release
    saved.revision = proposal.revision
    saved.itemId = intent.itemId
    saved.quantity = intent.quantity
    saved.floor = intent.checkpointFloor
    saved.serverNow = before.native.serverNow
    return saved, nil
end

-- A restarted client has a new revision sequence; native time orders recovery.
function MarketCollectionWithdrawEvidence.observe(baseline, after)
    if type(baseline) ~= "table" or type(after) ~= "table"
        or not text(baseline.session, 200)
        or not text(after.session, 200)
        or not text(baseline.itemId, 120)
        or not integer(baseline.revision, 0, 9007199254740991)
        or not integer(after.revision, 0, 9007199254740991)
        or not finite(baseline.serverNow)
        or type(after.native) ~= "table"
        or not finite(after.native.serverNow)
        or after.native.serverNow < baseline.serverNow
        or not integer(baseline.quantity, 1, 999)
        or not integer(baseline.floor, 0, 1000000000)
        or not integer(baseline.collected,
            baseline.quantity, 1000000000)
        or type(baseline.looseVariants) ~= "table"
        or type(baseline.boundVariants) ~= "table" then return false end
    for _, field in ipairs({ "account", "place", "release" }) do
        if not text(baseline[field], 200)
            or baseline[field] ~= after[field] then return false end
    end
    for _, field in ipairs({ "loose", "bound", "collectedBound",
        "gold", "boundGold", "total" }) do
        if not integer(baseline[field], 0, 1000000000) then return false end
    end
    local newer = baseline.session == after.session
        and after.revision > baseline.revision
        or baseline.session ~= after.session
            and after.native.serverNow > baseline.serverNow
    local current = state(after, baseline.itemId)
    return newer and current ~= nil
        and current.loose == baseline.loose + baseline.quantity
        and current.bound == baseline.bound
        and current.collected == baseline.collected - baseline.quantity
        and current.collectedBound == baseline.collectedBound
        and current.gold == baseline.gold
        and current.boundGold == baseline.boundGold
        and current.total == baseline.total - baseline.quantity
        and current.total >= baseline.floor
        and sameMap(current.looseVariants, baseline.looseVariants)
        and sameMap(current.boundVariants, baseline.boundVariants)
end

local function reconcile(proposal, beforeHeader, after, reply, baseline, restart)
    local intent = type(proposal) == "table" and proposal.intent
    if not same(proposal, beforeHeader)
        or (not restart and not same(proposal, after))
        or type(after) ~= "table"
        or proposal.account ~= after.account or proposal.place ~= after.place or proposal.release ~= after.release
        or not same(proposal, baseline)
        or type(reply) ~= "table"
        or type(intent) ~= "table"
        or intent.kind ~= "marketCollectionWithdraw"
        or intent.itemId ~= baseline.itemId
        or intent.quantity ~= baseline.quantity
        or intent.checkpointFloor ~= baseline.floor
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision then
        return "pending"
    end
    local current = state(after, baseline.itemId)
    if not current then return "pending" end
    local advanced = MarketCollectionWithdrawEvidence.observe(baseline, after)
    if reply.pending == true or reply.code == "rate_limited" or reply.code == "presence" then return "pending" end
    if reply.ok == false then
        local newer = after.session == baseline.session and integer(after.revision,0,9007199254740991) and after.revision > baseline.revision
            or restart and after.session ~= baseline.session and finite(after.native.serverNow) and after.native.serverNow > baseline.serverNow
        return newer and finite(after.native.serverNow) and after.native.serverNow >= baseline.serverNow and unchanged(current, baseline)
            and "rejected" or "pending"
    end
    if reply.ok == true and reply.pending ~= true
        and reply.code ~= "rate_limited"
        and reply.moved == baseline.quantity
        and advanced then return "confirmed" end
    return "pending"
end

function MarketCollectionWithdrawEvidence.evaluate(proposal, beforeHeader, after, reply, baseline)
    return reconcile(proposal,beforeHeader,after,reply,baseline,false)
end
function MarketCollectionWithdrawEvidence.evaluateStored(baseline, after, reply)
    if type(baseline) ~= "table" then return "pending" end
    local p={feature="marketSell",intent={kind="marketCollectionWithdraw",itemId=baseline.itemId,
        quantity=baseline.quantity,checkpointFloor=baseline.floor}}
    for _,field in ipairs({"session","account","place","release","revision"}) do p[field]=baseline[field] end
    return reconcile(p,p,after,reply,baseline,true)
end
return MarketCollectionWithdrawEvidence
