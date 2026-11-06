-- A Market list reply needs one exact new listing and loose-item transfer.
local MarketListEvidence = {}

local function integer(value, low, high)
    return type(value) == "number" and value == value
        and value >= low and value <= high and value % 1 == 0
end

local function finite(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

local function text(value, maximum)
    return type(value) == "string" and #value > 0
        and #value <= maximum
end

local function same(a, b, allowNewSession)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if not text(a[field], 200) or (a[field] ~= b[field]
            and not (allowNewSession and field == "session" and text(b[field], 200))) then return false end
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

local function listing(row)
    local origin = type(row) == "table" and row.itemOrigin
    if type(row) ~= "table"
        or not text(row.state, 40)
        or not text(row.item, 120)
        or not integer(row.indexed, 0, 1000000000)
        or not integer(row.price, 1, 9999999)
        or not integer(row.qty, 1, 999)
        or not integer(row.left, 0, row.qty)
        or not integer(row.createdAt, 0, 9007199254740991)
        or type(origin) ~= "table"
        or not integer(origin.total, 0, 1000000000)
        or not integer(origin.free, 0, origin.total) then
        return nil
    end
    return { state = row.state, item = row.item,
        indexed = row.indexed, price = row.price,
        qty = row.qty, left = row.left,
        createdAt = row.createdAt,
        total = origin.total, free = origin.free }
end

local function unchanged(a, b)
    for _, field in ipairs({ "state", "item", "indexed", "price",
        "qty", "left", "createdAt", "total", "free" }) do
        if a[field] ~= b[field] then return false end
    end
    return true
end

local function state(raw, id)
    local native = type(raw) == "table" and raw.native
    local market = type(native) == "table" and native.market
    local rows = type(market) == "table" and market.listings
    if type(native) ~= "table" or native.fullSync ~= true
        or type(rows) ~= "table" then return nil end
    local loose = count(native.inventory, id)
    local bound = count(native.inventoryBound, id)
    if loose == nil or bound == nil then return nil end
    local listings, size = {}, 0
    for listingId, row in pairs(rows) do
        size = size + 1
        local saved = listing(row)
        if size > 100 or not text(listingId, 160)
            or not saved then return nil end
        listings[listingId] = saved
    end
    return { loose = loose, bound = bound,
        listings = listings, size = size }
end

function MarketListEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if not same(proposal, before)
        or (proposal.feature ~= "marketSell"
            and not (proposal.feature == "marketFlip"
                and proposal.preflightOnly == true))
        or type(intent) ~= "table"
        or intent.kind ~= "marketList"
        or not text(intent.itemId, 120)
        or not integer(intent.quantity, 1, 999)
        or not integer(intent.ask, 1, 9999999)
        or type(before.native) ~= "table"
        or not finite(before.native.serverNow)
        or proposal.revision ~= before.revision
        or not integer(before.revision, 0, 9007199254740991) then
        return nil, "Market listing baseline mismatch"
    end
    local saved = state(before, intent.itemId)
    if not saved or saved.loose < intent.quantity then
        return nil, "Selected unbound item unavailable to list"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, itemId = intent.itemId,
        quantity = intent.quantity, ask = intent.ask,
        serverNow = before.native.serverNow,
        loose = saved.loose, bound = saved.bound,
        listings = saved.listings, size = saved.size }, nil
end

function MarketListEvidence.observe(baseline, after)
    if type(baseline) ~= "table" or type(after) ~= "table"
        or baseline.account ~= after.account
        or baseline.place ~= after.place
        or baseline.release ~= after.release
        or not text(baseline.session, 200)
        or not text(after.session, 200)
        or not integer(baseline.revision, 0, 9007199254740991)
        or not integer(after.revision, 0, 9007199254740991)
        or not finite(baseline.serverNow)
        or type(after.native) ~= "table"
        or not finite(after.native.serverNow)
        or not text(baseline.itemId, 120)
        or not integer(baseline.quantity, 1, 999)
        or not integer(baseline.ask, 1, 9999999)
        or not integer(baseline.loose, 0, 1000000000)
        or not integer(baseline.bound, 0, 1000000000)
        or not integer(baseline.size, 0, 100)
        or type(baseline.listings) ~= "table" then
        return false
    end
    local current = state(after, baseline.itemId)
    if not current then return false end
    local newCount = 0
    for id, row in pairs(current.listings) do
        local original = baseline.listings[id]
        if original then
            if not unchanged(original, row) then return false end
        else
            newCount = newCount + 1
            if row.state ~= "live"
                or row.item ~= baseline.itemId
                or row.qty ~= baseline.quantity
                or row.left ~= baseline.quantity
                or row.price ~= baseline.ask
                or row.total ~= baseline.quantity then
                return false
            end
        end
    end
    local newer = baseline.session == after.session
        and after.revision > baseline.revision
        or baseline.session ~= after.session
            and after.native.serverNow > baseline.serverNow
    return newer and after.native.serverNow >= baseline.serverNow
        and current.size == baseline.size + 1
        and newCount == 1
        and current.loose == baseline.loose - baseline.quantity
        and current.bound == baseline.bound
end

local function reconcile(proposal, beforeHeader, after, reply, baseline, restart)
    local intent = type(proposal) == "table" and proposal.intent
    if not same(proposal, beforeHeader)
        or not same(proposal, after, restart)
        or not same(proposal, baseline)
        or type(reply) ~= "table"
        or type(intent) ~= "table"
        or baseline.revision ~= beforeHeader.revision
        or proposal.revision ~= baseline.revision
        or intent.itemId ~= baseline.itemId
        or intent.quantity ~= baseline.quantity
        or intent.ask ~= baseline.ask then return "pending" end
    local advanced = MarketListEvidence.observe(baseline, after)
    if reply.ok == false then
        if advanced or reply.pending == true or reply.code == "rate_limited"
            or reply.code == "presence" then return "pending" end
        local current = state(after, baseline.itemId)
        local newer = after.session == baseline.session and integer(after.revision, 0, 9007199254740991)
            and after.revision > baseline.revision
            or restart and after.session ~= baseline.session and type(after.native) == "table"
                and finite(after.native.serverNow) and after.native.serverNow > baseline.serverNow
        if not current or not integer(after.revision, 0, 9007199254740991)
            or not newer
            or not finite(after.native.serverNow)
            or after.native.serverNow < baseline.serverNow
            or current.loose ~= baseline.loose or current.bound ~= baseline.bound
            or current.size ~= baseline.size then return "pending" end
        for id, row in pairs(baseline.listings) do
            if not current.listings[id] or not unchanged(row, current.listings[id]) then return "pending" end
        end
        return "rejected"
    end
    if reply.ok == true and reply.pending ~= true
        and reply.code ~= "rate_limited" and advanced then return "confirmed" end
    return "pending"
end

function MarketListEvidence.evaluate(proposal, beforeHeader, after, reply, baseline)
    return reconcile(proposal, beforeHeader, after, reply, baseline, false)
end

function MarketListEvidence.evaluateStored(baseline, after, reply)
    if type(baseline) ~= "table" or baseline.kind ~= "list" or not same(baseline, baseline)
        or not integer(baseline.revision, 0, 9007199254740991) or not finite(baseline.serverNow)
        or not text(baseline.itemId, 120) or not integer(baseline.quantity, 1, 999)
        or not integer(baseline.ask, 1, 9999999) or type(baseline.listings) ~= "table"
        or not integer(baseline.size, 0, 100) or not integer(baseline.loose, baseline.quantity, 1000000000)
        or not integer(baseline.bound, 0, 1000000000) then return "pending" end
    local header = {feature="marketSell",intent={kind="marketList",itemId=baseline.itemId,
        quantity=baseline.quantity,ask=baseline.ask}}
    for _, field in ipairs({"session","account","place","release","revision"}) do header[field]=baseline[field] end
    return reconcile(header, header, after, reply, baseline, true)
end

local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not equal(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
function MarketListEvidence.recoverSaved(data, after)
    if type(data) ~= "table" or type(data.baseline) ~= "table" or type(data.reply) ~= "table"
        or type(data.proposal) ~= "table" or (data.proposal.feature ~= "marketSell" and data.proposal.feature~="marketFlip") then return nil end
    local input={}
    for k,v in pairs(data.proposal) do input[k]=v end
    if input.feature=="marketFlip" then input.preflightOnly=true end
    local expected = MarketListEvidence.capture(input, data.before)
    if not expected or not equal(expected, data.baseline) then return nil end
    local outcome = reconcile(data.proposal, data.before, after, data.reply, data.baseline, true)
    return (outcome == "confirmed" or outcome == "rejected") and outcome or nil
end

return MarketListEvidence
